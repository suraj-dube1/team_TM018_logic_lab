"""Unit and integration tests for audit logging and administrative endpoints."""

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.user import Role, User
from app.services.auth_service import create_access_token
from tests.helpers import make_pdf


@pytest.fixture
def admin_token(client):
    """Seed an admin user and return a signed JWT."""
    from app.db.database import get_db
    from app.services.auth_service import create_user

    # Create admin directly in database
    db = next(client.app.dependency_overrides[get_db]())
    admin = create_user(db, name="Admin Root", email="admin.root@univ.edu", password="admin_password_123")
    admin.role = Role.ADMIN.value
    db.commit()
    token, _ = create_access_token(admin.id)
    return token, admin.id


@pytest.fixture
def student_token(client):
    """Register and login standard student."""
    client.post(
        "/api/auth/register",
        json={"name": "Alice Audit", "email": "alice.audit@univ.edu", "password": "password_long_123"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "alice.audit@univ.edu", "password": "password_long_123"},
    )
    return login.json()["access_token"]


def test_non_admin_forbidden_from_admin_endpoints(client, student_token):
    # Student attempts to access admin stats
    resp_stats = client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp_stats.status_code == 403

    # Student attempts to access audit logs
    resp_audit = client.get(
        "/api/audit",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp_audit.status_code == 403


def test_admin_stats_and_user_listing(client, admin_token, student_token):
    token, _ = admin_token

    # 1. Check stats
    resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_users"] >= 2
    assert "PUBLIC" in stats["documents_by_level"]

    # 2. Check user list
    resp_users = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp_users.status_code == 200
    users = resp_users.json()
    assert len(users) >= 2


def test_admin_can_update_user_role_with_audit_trail(client, admin_token):
    adm_token, _ = admin_token

    # Register student
    reg = client.post(
        "/api/auth/register",
        json={"name": "Promotee", "email": "promotee@univ.edu", "password": "password_long_123"},
    )
    target_id = reg.json()["id"]

    # Admin promotes student to FACULTY
    resp = client.patch(
        f"/api/admin/users/{target_id}/role",
        headers={"Authorization": f"Bearer {adm_token}"},
        json={"role": "FACULTY"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "FACULTY"

    # Verify audit log records the promotion
    audit_resp = client.get(
        "/api/audit?action=ADMIN_ROLE_CHANGE",
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    assert logs[0]["resource_id"] == target_id
    assert "FACULTY" in logs[0]["details"]


def test_document_lifecycle_deletion_and_reclassification(client, admin_token, student_token):
    adm_token, admin_id = admin_token

    # 1. Upload a document as student
    upload = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {student_token}"},
        files={"file": ("guide.pdf", make_pdf("Freshman campus orientation guide."), "application/pdf")},
        data={"title": "Orientation Guide", "security_level": "PUBLIC"},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    # 2. Admin reclassifies the document to INTERNAL
    reclass = client.patch(
        f"/api/documents/{doc_id}/classification",
        headers={"Authorization": f"Bearer {adm_token}"},
        json={"security_level": "INTERNAL"},
    )
    assert reclass.status_code == 200
    assert reclass.json()["security_level"] == "INTERNAL"

    # 3. Student can no longer access this INTERNAL document
    get_doc = client.get(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert get_doc.status_code == 404

    # 4. Admin deletes the document
    del_resp = client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert del_resp.status_code == 204

    # Confirm deletion from DB
    get_after_del = client.get(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert get_after_del.status_code == 404


def test_login_and_query_audit_trail(client, student_token, admin_token):
    adm_token, _ = admin_token

    # Query RAG
    client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"question": "What is the secret formula?"},
    )

    # Check audit log contains login and query events
    resp = client.get(
        "/api/audit",
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert resp.status_code == 200
    actions = {log["action"] for log in resp.json()}
    assert "LOGIN_SUCCESS" in actions
    assert "ACCESS_DENIED" in actions or "DOCUMENT_QUERY" in actions
