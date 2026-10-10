"""Unit and integration tests for secure RAG pipeline with citations."""

from pathlib import Path
import tempfile
import pytest

from app.models.user import Role, User
from app.services.rag_service import answer_question
from app.services.vector_store_service import (
    VectorStoreService,
    set_vector_store,
)


@pytest.fixture
def rag_vector_store():
    """Seed an isolated vector store for RAG testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStoreService(storage_dir=Path(tmpdir))
        store.add_chunks(
            [
                {
                    "id": "chunk-handbook",
                    "document_id": "doc-handbook",
                    "document_title": "Student Handbook",
                    "chunk_index": 0,
                    "page_number": 4,
                    "text": "Undergraduate students must maintain at least 80 percent attendance across all registered courses.",
                    "security_level": "PUBLIC",
                    "source_type": "PDF",
                    "uploaded_by": "u-admin",
                },
                {
                    "id": "chunk-sabbatical",
                    "document_id": "doc-faculty",
                    "document_title": "Faculty Policy Guide",
                    "chunk_index": 0,
                    "page_number": 7,
                    "text": "Faculty sabbatical leave applications require approval from the department chair and academic dean.",
                    "security_level": "INTERNAL",
                    "source_type": "PDF",
                    "uploaded_by": "u-admin",
                },
                {
                    "id": "chunk-budget",
                    "document_id": "doc-budget",
                    "document_title": "Executive Financial Plan",
                    "chunk_index": 0,
                    "page_number": 2,
                    "text": "The confidential institutional research budget allocation is fifteen million dollars for fiscal year 2026.",
                    "security_level": "CONFIDENTIAL",
                    "source_type": "PDF",
                    "uploaded_by": "u-admin",
                },
            ]
        )
        set_vector_store(store)
        yield store
        set_vector_store(None)


def test_student_gets_grounded_answer_and_public_citations(rag_vector_store):
    student = User(
        id="s-1",
        email="student@univ.edu",
        name="Sam Student",
        role=Role.STUDENT.value,
        is_active=True,
    )

    result = answer_question(student, question="What is the student attendance percentage requirement?")
    assert result.has_sufficient_context is True
    assert result.user_role == "STUDENT"
    assert result.allowed_security_levels == ["PUBLIC"]
    assert "80 percent" in result.answer or "80%" in result.answer

    assert len(result.citations) >= 1
    cit = result.citations[0]
    assert cit.document_title == "Student Handbook"
    assert cit.page_number == 4
    assert cit.security_level == "PUBLIC"
    assert cit.chunk_id == "chunk-handbook"


def test_student_asking_confidential_gets_anti_hallucination_and_zero_citations(rag_vector_store):
    student = User(
        id="s-1",
        email="student@univ.edu",
        name="Sam Student",
        role=Role.STUDENT.value,
        is_active=True,
    )

    # Student attempts to inquire about confidential executive budget
    result = answer_question(student, question="What is the confidential institutional research budget allocation?")
    assert result.has_sufficient_context is False
    assert "not contain enough information" in result.answer.lower()
    assert result.citations == []


def test_faculty_can_answer_internal_but_denied_confidential(rag_vector_store):
    faculty = User(
        id="f-1",
        email="faculty@univ.edu",
        name="Prof. Sarah",
        role=Role.FACULTY.value,
        is_active=True,
    )

    # 1. Internal query succeeds
    res_int = answer_question(faculty, question="Who must approve faculty sabbatical leave?")
    assert res_int.has_sufficient_context is True
    assert len(res_int.citations) >= 1
    assert res_int.citations[0].security_level == "INTERNAL"
    assert "department chair" in res_int.answer.lower()

    # 2. Confidential query fails closed
    res_conf = answer_question(faculty, question="What is the confidential research budget?")
    assert res_conf.has_sufficient_context is False
    assert res_conf.citations == []


def test_admin_can_access_confidential_and_receive_confidential_citation(rag_vector_store):
    admin = User(
        id="a-1",
        email="admin@univ.edu",
        name="Admin Chief",
        role=Role.ADMIN.value,
        is_active=True,
    )

    result = answer_question(admin, question="What is the confidential institutional research budget?")
    assert result.has_sufficient_context is True
    assert "fifteen million" in result.answer.lower()
    assert len(result.citations) >= 1
    assert result.citations[0].security_level == "CONFIDENTIAL"
    assert result.citations[0].document_title == "Executive Financial Plan"


def test_rag_api_unauthorized_rejected(client):
    response = client.post("/api/rag/query", json={"question": "What is the attendance policy?"})
    assert response.status_code == 401


def test_rag_api_student_query_flow(client, rag_vector_store):
    # Register and login student
    reg = client.post(
        "/api/auth/register",
        json={"name": "RAG Student", "email": "rag.student@univ.edu", "password": "password_long_123"},
    )
    assert reg.status_code == 201

    login = client.post(
        "/api/auth/login",
        json={"email": "rag.student@univ.edu", "password": "password_long_123"},
    )
    token = login.json()["access_token"]

    resp = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What attendance percentage must students maintain?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_sufficient_context"] is True
    assert data["user_role"] == "STUDENT"
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["security_level"] == "PUBLIC"
    assert data["citations"][0]["document_title"] == "Student Handbook"
