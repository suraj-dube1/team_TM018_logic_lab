"""End-to-end security integration tests for VaultRAG.

Validates multi-role access control, sub-index physical isolation,
zero-leakage RAG retrieval, anti-hallucination fail-closed behavior,
document deletion cascading, role privilege escalation defenses,
and complete audit log fidelity.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import Role, User
from app.services.auth_service import create_access_token, create_user
from app.services.vector_store_service import (
    VectorStoreService,
    get_vector_store,
    set_vector_store,
)
from tests.helpers import make_pdf


@pytest.fixture
def isolated_vector_store(tmp_path):
    """Ensure an isolated FAISS vector store on disk for the duration of each test."""
    store_dir = tmp_path / "vector_store"
    store = VectorStoreService(storage_dir=store_dir)
    set_vector_store(store)
    yield store
    set_vector_store(None)


def create_test_user(client, *, name: str, email: str, role: Role) -> tuple[str, str]:
    """Helper to seed a user in the test database and return (jwt_token, user_id)."""
    db = next(client.app.dependency_overrides[get_db]())
    user = create_user(db, name=name, email=email, password="SecurePassword_2026!")
    user.role = role.value
    db.commit()
    token, _ = create_access_token(user.id)
    return token, user.id


def test_e2e_cross_role_upload_and_rag_isolation(client, isolated_vector_store):
    """End-to-end test verifying multi-role ingestion, physical vector partitioning,

    and strict cross-role retrieval isolation:
    1. Admin uploads CONFIDENTIAL document.
    2. Faculty uploads INTERNAL document.
    3. Student uploads PUBLIC document.
    4. Student queries confidential topic -> 0 confidential vectors searched, fails closed, records ACCESS_DENIED.
    5. Student queries public topic -> grounded answer + PUBLIC citation.
    6. Faculty queries confidential topic -> fails closed.
    7. Faculty queries internal topic -> grounded answer + INTERNAL citation.
    8. Admin queries confidential topic -> grounded answer + CONFIDENTIAL citation.
    """
    # 1. Provision 3 users
    admin_token, admin_id = create_test_user(client, name="Admin Root", email="adm@univ.edu", role=Role.ADMIN)
    faculty_token, fac_id = create_test_user(client, name="Dr. Faculty", email="fac@univ.edu", role=Role.FACULTY)
    student_token, stu_id = create_test_user(client, name="Alice Student", email="stu@univ.edu", role=Role.STUDENT)

    # 2. Ingest 3 documents with tiered security levels
    # CONFIDENTIAL document
    conf_pdf = make_pdf(
        "The institutional emergency reserve fund endowment contains forty-two million dollars allocated "
        "exclusively for high-security campus expansion in fiscal year 2026."
    )
    conf_res = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"title": "Executive Fiscal Reserve", "security_level": "CONFIDENTIAL"},
        files={"file": ("confidential-reserve.pdf", conf_pdf, "application/pdf")},
    )
    assert conf_res.status_code == 201
    conf_doc_id = conf_res.json()["id"]

    # INTERNAL document
    int_pdf = make_pdf(
        "Tenured and tenure-track faculty are eligible for competitive research grant funding up to "
        "seventy-five thousand dollars each academic cycle."
    )
    int_res = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {faculty_token}"},
        data={"title": "Faculty Senate Research Policy", "security_level": "INTERNAL"},
        files={"file": ("faculty-policy.pdf", int_pdf, "application/pdf")},
    )
    assert int_res.status_code == 201
    int_doc_id = int_res.json()["id"]

    # PUBLIC document
    pub_pdf = make_pdf(
        "The central undergraduate campus library operates twenty-four hours a day with free tutoring "
        "and digital research workstations for all enrolled students."
    )
    pub_res = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {student_token}"},
        data={"title": "Student Campus Guide", "security_level": "PUBLIC"},
        files={"file": ("student-guide.pdf", pub_pdf, "application/pdf")},
    )
    assert pub_res.status_code == 201
    pub_doc_id = pub_res.json()["id"]

    # Verify physical FAISS sub-index partitioning
    store = get_vector_store()
    assert store.indices["PUBLIC"].ntotal >= 1
    assert store.indices["INTERNAL"].ntotal >= 1
    assert store.indices["CONFIDENTIAL"].ntotal >= 1

    # 3. STUDENT Queries:
    # A. Student asks about Confidential Reserve -> Must fail closed with 0 citations
    stu_conf_query = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"question": "What is the emergency reserve fund endowment allocation?", "top_k": 3},
    )
    assert stu_conf_query.status_code == 200
    stu_conf_data = stu_conf_query.json()
    assert stu_conf_data["has_sufficient_context"] is False
    assert stu_conf_data["citations"] == []
    assert "not contain enough information" in stu_conf_data["answer"].lower()

    # B. Student asks about Public Campus Library -> Must succeed with citation
    stu_pub_query = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"question": "What are the campus library operating hours?", "top_k": 3},
    )
    assert stu_pub_query.status_code == 200
    stu_pub_data = stu_pub_query.json()
    assert stu_pub_data["has_sufficient_context"] is True
    assert len(stu_pub_data["citations"]) >= 1
    assert stu_pub_data["citations"][0]["document_title"] == "Student Campus Guide"
    assert stu_pub_data["citations"][0]["security_level"] == "PUBLIC"
    assert "twenty-four hours" in stu_pub_data["answer"].lower()

    # 4. FACULTY Queries:
    # A. Faculty asks about Confidential Reserve -> Must fail closed
    fac_conf_query = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {faculty_token}"},
        json={"question": "What is the emergency reserve fund endowment allocation?", "top_k": 3},
    )
    assert fac_conf_query.status_code == 200
    fac_conf_data = fac_conf_query.json()
    assert fac_conf_data["has_sufficient_context"] is False
    assert fac_conf_data["citations"] == []

    # B. Faculty asks about Research Grants -> Must succeed with INTERNAL citation
    fac_int_query = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {faculty_token}"},
        json={"question": "How much research grant funding can faculty receive?", "top_k": 3},
    )
    assert fac_int_query.status_code == 200
    fac_int_data = fac_int_query.json()
    assert fac_int_data["has_sufficient_context"] is True
    assert len(fac_int_data["citations"]) >= 1
    assert fac_int_data["citations"][0]["document_title"] == "Faculty Senate Research Policy"
    assert fac_int_data["citations"][0]["security_level"] == "INTERNAL"
    assert "research grant" in fac_int_data["answer"].lower()

    # 5. ADMIN Queries:
    # Admin asks about Confidential Reserve -> Must succeed with CONFIDENTIAL citation
    adm_conf_query = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"question": "What is the emergency reserve fund endowment allocation?", "top_k": 3},
    )
    assert adm_conf_query.status_code == 200
    adm_conf_data = adm_conf_query.json()
    assert adm_conf_data["has_sufficient_context"] is True
    assert len(adm_conf_data["citations"]) >= 1
    assert adm_conf_data["citations"][0]["document_title"] == "Executive Fiscal Reserve"
    assert adm_conf_data["citations"][0]["security_level"] == "CONFIDENTIAL"
    assert "forty-two million" in adm_conf_data["answer"].lower()


def test_e2e_document_level_direct_api_access_control(client, isolated_vector_store):
    """Validate that unauthorized users cannot probe, read, delete, or classify

    documents outside their permission scope (existence is masked via 404).
    """
    admin_token, _ = create_test_user(client, name="Admin Root", email="adm2@univ.edu", role=Role.ADMIN)
    student_token, _ = create_test_user(client, name="Alice Student", email="stu2@univ.edu", role=Role.STUDENT)

    # Admin uploads CONFIDENTIAL document
    doc_res = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"title": "Restricted Patent Specs", "security_level": "CONFIDENTIAL"},
        files={"file": ("patent.pdf", make_pdf("Proprietary patent details."), "application/pdf")},
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    # 1. Student attempts direct access (metadata, extraction, chunks)
    meta_res = client.get(f"/api/documents/{doc_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert meta_res.status_code == 404

    ext_res = client.get(f"/api/documents/{doc_id}/extraction", headers={"Authorization": f"Bearer {student_token}"})
    assert ext_res.status_code == 404

    chunks_res = client.get(f"/api/documents/{doc_id}/chunks", headers={"Authorization": f"Bearer {student_token}"})
    assert chunks_res.status_code == 404

    # 2. Student attempts deletion
    del_res = client.delete(f"/api/documents/{doc_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert del_res.status_code == 404

    # 3. Student attempts classification modification
    class_res = client.patch(
        f"/api/documents/{doc_id}/classification",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"security_level": "PUBLIC"},
    )
    assert class_res.status_code == 403

    # 4. Admin accesses same endpoints successfully
    assert client.get(f"/api/documents/{doc_id}", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
    assert (
        client.get(f"/api/documents/{doc_id}/extraction", headers={"Authorization": f"Bearer {admin_token}"}).status_code
        == 200
    )
    assert (
        client.get(f"/api/documents/{doc_id}/chunks", headers={"Authorization": f"Bearer {admin_token}"}).status_code
        == 200
    )


def test_e2e_admin_reclassification_and_instant_retrieval_reindexing(client, isolated_vector_store):
    """Validate that when an Admin reclassifies a document:

    1. Database document and chunks are updated.
    2. FAISS vector store seamlessly migrates chunk vectors between partitions.
    3. Student who was previously denied can instantly query and receive citations.
    """
    admin_token, _ = create_test_user(client, name="Admin Root", email="adm3@univ.edu", role=Role.ADMIN)
    student_token, _ = create_test_user(client, name="Student Bob", email="stu3@univ.edu", role=Role.STUDENT)

    # Ingest document as CONFIDENTIAL
    doc_res = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"title": "Student Health Insurance Plan", "security_level": "CONFIDENTIAL"},
        files={
            "file": (
                "health.pdf",
                make_pdf("University health insurance includes comprehensive dental and ophthalmology coverage."),
                "application/pdf",
            )
        },
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    # Student queries -> denied
    q1 = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"question": "Does the student health insurance include dental coverage?", "top_k": 3},
    )
    assert q1.json()["has_sufficient_context"] is False
    assert q1.json()["citations"] == []

    # Admin reclassifies to PUBLIC
    reclass_res = client.patch(
        f"/api/documents/{doc_id}/classification",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"security_level": "PUBLIC"},
    )
    assert reclass_res.status_code == 200
    assert reclass_res.json()["security_level"] == "PUBLIC"

    # Student queries again -> now permitted!
    q2 = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"question": "Does the student health insurance include dental coverage?", "top_k": 3},
    )
    assert q2.status_code == 200
    data2 = q2.json()
    assert data2["has_sufficient_context"] is True
    assert len(data2["citations"]) >= 1
    assert data2["citations"][0]["security_level"] == "PUBLIC"
    assert "dental" in data2["answer"].lower()


def test_e2e_document_deletion_cascading_purge_from_vector_store(client, isolated_vector_store, tmp_path):
    """Validate that deleting a document cascades:

    1. Deletes physical file on disk.
    2. Deletes Document and DocumentChunk database records.
    3. Purges chunks from the FAISS vector store.
    4. Subsequent queries immediately fail closed without ghost citations.
    """
    admin_token, _ = create_test_user(client, name="Admin Root", email="adm4@univ.edu", role=Role.ADMIN)

    # Ingest document
    doc_res = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"title": "Classified Ion Thruster", "security_level": "CONFIDENTIAL"},
        files={
            "file": (
                "thruster.pdf",
                make_pdf("The experimental prototype ion thruster reaches four thousand seconds of specific impulse."),
                "application/pdf",
            )
        },
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    # Verify query works before deletion
    q_before = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"question": "What is the specific impulse of the experimental thruster?", "top_k": 3},
    )
    assert q_before.json()["has_sufficient_context"] is True
    assert len(q_before.json()["citations"]) >= 1

    # Delete the document
    del_res = client.delete(f"/api/documents/{doc_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_res.status_code == 204

    # 1. Verify DB deletion
    db = next(client.app.dependency_overrides[get_db]())
    assert db.get(Document, doc_id) is None
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc_id)).all()
    assert list(chunks) == []

    # 2. Verify physical file is gone
    stored_files = list((tmp_path / "uploads").glob("*"))
    assert stored_files == []

    # 3. Verify vector store chunks are purged
    store = get_vector_store()
    assert len(store.metadata_by_level["CONFIDENTIAL"]) == 0

    # 4. Verify RAG query now fails closed
    q_after = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"question": "What is the specific impulse of the experimental thruster?", "top_k": 3},
    )
    assert q_after.json()["has_sufficient_context"] is False
    assert q_after.json()["citations"] == []
    assert "not contain enough information" in q_after.json()["answer"].lower()


def test_e2e_privilege_escalation_and_auth_hardening(client):
    """Validate system defenses against registration role injection,

    unauthorized role modifications, unauthorized classifications,
    and tampered or expired JWT credentials.
    """
    settings = get_settings()

    # 1. Registration role tampering: Attacker injects "role": "ADMIN" -> Rejected by extra="forbid"
    reg_tamper = client.post(
        "/api/auth/register",
        json={
            "name": "Malicious User",
            "email": "hacker@evil.org",
            "password": "HackerPassword_2026!",
            "role": "ADMIN",
        },
    )
    assert reg_tamper.status_code == 422

    # Standard registration defaults strictly to STUDENT
    reg_res = client.post(
        "/api/auth/register",
        json={
            "name": "Malicious User",
            "email": "hacker@evil.org",
            "password": "HackerPassword_2026!",
        },
    )
    assert reg_res.status_code == 201
    assert reg_res.json()["role"] == "STUDENT"

    # Login as attacker
    login_res = client.post(
        "/api/auth/login",
        json={"email": "hacker@evil.org", "password": "HackerPassword_2026!"},
    )
    hacker_token = login_res.json()["access_token"]

    # 2. Attacker attempts to access admin stats
    assert client.get("/api/admin/stats", headers={"Authorization": f"Bearer {hacker_token}"}).status_code == 403

    # 3. Attacker attempts to elevate own role
    hacker_id = reg_res.json()["id"]
    elevate_res = client.patch(
        f"/api/admin/users/{hacker_id}/role",
        headers={"Authorization": f"Bearer {hacker_token}"},
        json={"role": "ADMIN"},
    )
    assert elevate_res.status_code == 403

    # 4. Attacker attempts to upload a CONFIDENTIAL document
    conf_upload = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {hacker_token}"},
        data={"title": "Illicit Confidential", "security_level": "CONFIDENTIAL"},
        files={"file": ("illicit.pdf", make_pdf("Secret content"), "application/pdf")},
    )
    assert conf_upload.status_code == 403

    # 5. Attacker attempts to upload an INTERNAL document
    int_upload = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {hacker_token}"},
        data={"title": "Illicit Internal", "security_level": "INTERNAL"},
        files={"file": ("illicit_int.pdf", make_pdf("Internal content"), "application/pdf")},
    )
    assert int_upload.status_code == 403

    # 6. Tampered JWT signature
    tampered_token = hacker_token[:-5] + "XXXXX"
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"}).status_code
        == 401
    )

    # 7. Forged token with invalid secret
    now = datetime.now(timezone.utc)
    forged_token = jwt.encode(
        {"sub": hacker_id, "iat": now, "exp": now + timedelta(hours=1), "token_type": "access"},
        "wrong-secret-key-123",
        algorithm="HS256",
    )
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged_token}"}).status_code == 401

    # 8. Expired token
    expired_token = jwt.encode(
        {"sub": hacker_id, "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1), "token_type": "access"},
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"}).status_code == 401


def test_e2e_vector_search_endpoint_role_filtering(client, isolated_vector_store):
    """Validate direct semantic vector search API (/api/retrieval/search)

    ensures zero leakage before or during search execution.
    """
    admin_token, _ = create_test_user(client, name="Admin Root", email="adm5@univ.edu", role=Role.ADMIN)
    faculty_token, _ = create_test_user(client, name="Faculty Dr", email="fac5@univ.edu", role=Role.FACULTY)
    student_token, _ = create_test_user(client, name="Student Alice", email="stu5@univ.edu", role=Role.STUDENT)

    # Admin uploads a CONFIDENTIAL document
    client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"title": "Confidential Semiconductor Research", "security_level": "CONFIDENTIAL"},
        files={
            "file": (
                "semi.pdf",
                make_pdf("Next-generation Gallium Nitride power semiconductor wafers operate at 1200 Volts."),
                "application/pdf",
            )
        },
    )

    # 1. Student queries directly -> 0 matches, allowed_security_levels == ["PUBLIC"]
    stu_res = client.post(
        "/api/retrieval/search",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"query": "Gallium Nitride power semiconductor wafers", "top_k": 5},
    )
    assert stu_res.status_code == 200
    stu_data = stu_res.json()
    assert stu_data["user_role"] == "STUDENT"
    assert stu_data["allowed_security_levels"] == ["PUBLIC"]
    assert stu_data["total_retrieved"] == 0
    assert stu_data["chunks"] == []

    # 2. Faculty queries directly -> 0 matches, allowed_security_levels == ["PUBLIC", "INTERNAL"]
    fac_res = client.post(
        "/api/retrieval/search",
        headers={"Authorization": f"Bearer {faculty_token}"},
        json={"query": "Gallium Nitride power semiconductor wafers", "top_k": 5},
    )
    assert fac_res.status_code == 200
    fac_data = fac_res.json()
    assert fac_data["user_role"] == "FACULTY"
    assert set(fac_data["allowed_security_levels"]) == {"PUBLIC", "INTERNAL"}
    assert fac_data["total_retrieved"] == 0

    # 3. Admin queries directly -> returns matched CONFIDENTIAL chunk
    adm_res = client.post(
        "/api/retrieval/search",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"query": "Gallium Nitride power semiconductor wafers", "top_k": 5},
    )
    assert adm_res.status_code == 200
    adm_data = adm_res.json()
    assert adm_data["user_role"] == "ADMIN"
    assert "CONFIDENTIAL" in adm_data["allowed_security_levels"]
    assert adm_data["total_retrieved"] >= 1
    assert adm_data["chunks"][0]["security_level"] == "CONFIDENTIAL"
    assert "Gallium Nitride" in adm_data["chunks"][0]["text"]


def test_e2e_complete_audit_trail_and_metrics_verification(client, isolated_vector_store):
    """Validate that every security event, query, denied access, and administrative action

    is recorded accurately in audit logs and aggregated into admin metrics.
    """
    admin_token, admin_id = create_test_user(client, name="Admin Root", email="adm6@univ.edu", role=Role.ADMIN)
    student_token, stu_id = create_test_user(client, name="Student Charlie", email="stu6@univ.edu", role=Role.STUDENT)

    # 1. Student attempts unauthorized upload of CONFIDENTIAL document -> 403
    client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {student_token}"},
        data={"title": "Denied Doc", "security_level": "CONFIDENTIAL"},
        files={"file": ("denied.pdf", make_pdf("Denied content"), "application/pdf")},
    )

    # 2. Admin uploads a PUBLIC document
    upload_res = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"title": "Public Course Directory", "security_level": "PUBLIC"},
        files={"file": ("courses.pdf", make_pdf("Course listings for computer science department include CS101 Intro to Programming and CS201 Data Structures."), "application/pdf")},
    )
    assert upload_res.status_code == 201
    pub_doc_id = upload_res.json()["id"]

    # 3. Student performs successful query
    client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"question": "What courses are in computer science?", "top_k": 3},
    )

    # 4. Student queries for nonexistent/unauthorized topic -> triggers ACCESS_DENIED
    client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"question": "What is the secret nuclear reactor code?", "top_k": 3},
    )

    # 5. Admin promotes student to FACULTY
    client.patch(
        f"/api/admin/users/{stu_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "FACULTY"},
    )

    # 6. Admin inspects audit logs via GET /api/audit
    audit_res = client.get("/api/audit", headers={"Authorization": f"Bearer {admin_token}"})
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 4

    actions = [log["action"] for log in logs]
    assert "DOCUMENT_UPLOAD" in actions
    assert "DOCUMENT_QUERY" in actions
    assert "ACCESS_DENIED" in actions
    assert "ADMIN_ROLE_CHANGE" in actions

    # Verify filtering by action
    denied_res = client.get("/api/audit?action=ACCESS_DENIED", headers={"Authorization": f"Bearer {admin_token}"})
    assert denied_res.status_code == 200
    for entry in denied_res.json():
        assert entry["action"] == "ACCESS_DENIED"
        assert entry["status"] == "DENIED"

    # 7. Admin inspects system stats via GET /api/admin/stats
    stats_res = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_users"] >= 2
    assert stats["total_documents"] >= 1
    assert stats["total_queries"] >= 1
    assert stats["successful_accesses"] >= 1
    assert stats["denied_accesses"] >= 1
