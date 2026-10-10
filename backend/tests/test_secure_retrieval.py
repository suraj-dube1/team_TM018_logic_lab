"""Unit and integration tests for secure, permission-filtered retrieval."""

from pathlib import Path
import tempfile
import pytest

from app.models.user import Role, User
from app.services.access_control_service import SecurityLevel
from app.services.retrieval_service import retrieve_for_user
from app.services.vector_store_service import (
    VectorStoreService,
    get_vector_store,
    set_vector_store,
)


@pytest.fixture
def isolated_vector_store():
    """Provide an isolated vector store for the duration of the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStoreService(storage_dir=Path(tmpdir))
        # Populate with 3 security-tiered chunks
        store.add_chunks(
            [
                {
                    "id": "c-pub",
                    "document_id": "doc-1",
                    "document_title": "Student Handbook",
                    "chunk_index": 0,
                    "page_number": 1,
                    "text": "Undergraduate student attendance requires minimum 80 percent class attendance.",
                    "security_level": "PUBLIC",
                    "source_type": "PDF",
                    "uploaded_by": "user-pub",
                },
                {
                    "id": "c-int",
                    "document_id": "doc-2",
                    "document_title": "Faculty Operations Manual",
                    "chunk_index": 0,
                    "page_number": 2,
                    "text": "Faculty committee internal sabbatical guidelines and promotion timeline.",
                    "security_level": "INTERNAL",
                    "source_type": "PDF",
                    "uploaded_by": "user-fac",
                },
                {
                    "id": "c-conf",
                    "document_id": "doc-3",
                    "document_title": "Executive Financial Budget",
                    "chunk_index": 0,
                    "page_number": 1,
                    "text": "The confidential executive annual budget allocated twelve million dollars.",
                    "security_level": "CONFIDENTIAL",
                    "source_type": "PDF",
                    "uploaded_by": "user-adm",
                },
            ]
        )
        set_vector_store(store)
        yield store
        set_vector_store(None)


def test_student_cannot_retrieve_internal_or_confidential(isolated_vector_store):
    student = User(
        id="s-1",
        email="student@univ.edu",
        name="Alice Student",
        role=Role.STUDENT.value,
        is_active=True,
    )

    # 1. Student searches for confidential budget
    res = retrieve_for_user(student, query="What is the confidential annual budget?", top_k=5)
    assert res.user_role == "STUDENT"
    assert res.allowed_security_levels == ["PUBLIC"]

    # Must NEVER contain INTERNAL or CONFIDENTIAL chunks
    retrieved_levels = {r.chunk.security_level for r in res.results}
    assert "CONFIDENTIAL" not in retrieved_levels
    assert "INTERNAL" not in retrieved_levels

    # 2. Student searches for attendance policy
    res_pub = retrieve_for_user(student, query="What is the attendance requirement?", top_k=2)
    assert res_pub.total_retrieved >= 1
    assert res_pub.results[0].chunk.chunk_id == "c-pub"
    assert res_pub.results[0].chunk.security_level == "PUBLIC"


def test_faculty_can_retrieve_public_and_internal_but_never_confidential(isolated_vector_store):
    faculty = User(
        id="f-1",
        email="faculty@univ.edu",
        name="Dr. Bob",
        role=Role.FACULTY.value,
        is_active=True,
    )

    # 1. Faculty queries confidential budget
    res_conf = retrieve_for_user(faculty, query="Tell me the confidential annual budget", top_k=5)
    assert res_conf.user_role == "FACULTY"
    assert set(res_conf.allowed_security_levels) == {"PUBLIC", "INTERNAL"}

    # Must NEVER contain CONFIDENTIAL chunks
    retrieved_levels = {r.chunk.security_level for r in res_conf.results}
    assert "CONFIDENTIAL" not in retrieved_levels

    # 2. Faculty queries internal guidelines
    res_int = retrieve_for_user(faculty, query="sabbatical promotion guidelines", top_k=2)
    assert res_int.total_retrieved >= 1
    top_chunk = res_int.results[0].chunk
    assert top_chunk.chunk_id == "c-int"
    assert top_chunk.security_level == "INTERNAL"


def test_admin_can_retrieve_all_security_levels(isolated_vector_store):
    admin = User(
        id="a-1",
        email="admin@univ.edu",
        name="Sys Admin",
        role=Role.ADMIN.value,
        is_active=True,
    )

    res = retrieve_for_user(admin, query="confidential executive annual budget", top_k=3)
    assert res.user_role == "ADMIN"
    assert set(res.allowed_security_levels) == {"PUBLIC", "INTERNAL", "CONFIDENTIAL"}

    assert res.total_retrieved >= 1
    top_chunk = res.results[0].chunk
    assert top_chunk.chunk_id == "c-conf"
    assert top_chunk.security_level == "CONFIDENTIAL"


def test_inactive_user_fails_closed(isolated_vector_store):
    inactive_admin = User(
        id="a-disabled",
        email="disabled@univ.edu",
        name="Disabled Admin",
        role=Role.ADMIN.value,
        is_active=False,
    )
    res = retrieve_for_user(inactive_admin, query="annual budget")
    assert res.total_retrieved == 0
    assert res.results == []


def test_retrieval_api_unauthorized_rejected(client):
    response = client.post("/api/retrieval/search", json={"query": "attendance", "top_k": 3})
    assert response.status_code == 401


def test_retrieval_api_student_token_enforcement(client, isolated_vector_store):
    # Register and login student
    reg = client.post(
        "/api/auth/register",
        json={"name": "Alice Tester", "email": "alice.test@univ.edu", "password": "secure_password_123"},
    )
    assert reg.status_code == 201

    login = client.post(
        "/api/auth/login",
        json={"email": "alice.test@univ.edu", "password": "secure_password_123"},
    )
    token = login.json()["access_token"]

    response = client.post(
        "/api/retrieval/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "confidential annual budget", "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_role"] == "STUDENT"
    assert data["allowed_security_levels"] == ["PUBLIC"]

    for chunk in data["chunks"]:
        assert chunk["security_level"] == "PUBLIC"
