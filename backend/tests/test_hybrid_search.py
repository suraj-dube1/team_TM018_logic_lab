"""Unit and integration tests for Hybrid Search (BM25 + FAISS Dense Vector + RRF).

Validates:
1. Lexical tokenization preserving exact identifiers, codes, and numerical values.
2. BM25Okapi scoring dynamics.
3. Reciprocal Rank Fusion (RRF) combining dense and sparse rankings.
4. Strict security pre-filtering (BM25 indices partitioned by security level).
5. Cross-role retrieval isolation across hybrid, dense, and bm25 search modes.
"""

from pathlib import Path
import tempfile
import pytest

from app.models.user import Role, User
from app.services.hybrid_search_service import (
    BM25PartitionIndex,
    get_hybrid_search_service,
    tokenize,
)
from app.services.rag_service import answer_question
from app.services.retrieval_service import retrieve_for_user
from app.services.vector_store_service import (
    ChunkMetadata,
    VectorStoreService,
    set_vector_store,
)


@pytest.fixture
def hybrid_vector_store():
    """Seed an isolated vector store with tiered chunks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStoreService(storage_dir=Path(tmpdir))
        store.add_chunks(
            [
                {
                    "id": "c-pub-1",
                    "document_id": "doc-pub",
                    "document_title": "Student Handbook",
                    "chunk_index": 0,
                    "page_number": 1,
                    "text": "Undergraduate students must maintain 80 percent class attendance to remain eligible for examinations.",
                    "security_level": "PUBLIC",
                    "source_type": "PDF",
                    "uploaded_by": "u-admin",
                },
                {
                    "id": "c-pub-2",
                    "document_id": "doc-pub",
                    "document_title": "Student Handbook",
                    "chunk_index": 1,
                    "page_number": 2,
                    "text": "The university library stays open 24 hours daily during final exam periods with free tutoring.",
                    "security_level": "PUBLIC",
                    "source_type": "PDF",
                    "uploaded_by": "u-admin",
                },
                {
                    "id": "c-int-1",
                    "document_id": "doc-int",
                    "document_title": "Faculty Operations Manual",
                    "chunk_index": 0,
                    "page_number": 1,
                    "text": "Faculty members may apply for sabbatical leave after six semesters. Internal research grants provide up to $75,000.",
                    "security_level": "INTERNAL",
                    "source_type": "PDF",
                    "uploaded_by": "u-admin",
                },
                {
                    "id": "c-conf-1",
                    "document_id": "doc-conf",
                    "document_title": "Executive Financial Plan",
                    "chunk_index": 0,
                    "page_number": 1,
                    "text": "Project Silicon Annex involves commercial parcel 104-B with an emergency reserve fund budget of $42.5M dollars.",
                    "security_level": "CONFIDENTIAL",
                    "source_type": "PDF",
                    "uploaded_by": "u-admin",
                },
            ]
        )
        set_vector_store(store)
        yield store
        set_vector_store(None)


def test_tokenize_preserves_identifiers_and_numbers():
    text = "The emergency fund of $42.5M for Project Silicon Annex at parcel 104-B."
    tokens = tokenize(text)
    assert "$42.5m" in tokens or "42.5m" in tokens or "42.5" in tokens
    assert "104-b" in tokens or "104" in tokens
    assert "emergency" in tokens
    assert "silicon" in tokens
    # Common stopwords removed
    assert "the" not in tokens
    assert "for" not in tokens
    assert "at" not in tokens


def test_bm25_pure_lexical_scoring():
    chunks = [
        ChunkMetadata(
            chunk_id="c1",
            document_id="d1",
            document_title="Title 1",
            chunk_index=0,
            page_number=1,
            text="Quantum computing utilizes qubits and superposition states.",
            security_level="PUBLIC",
            source_type="PDF",
            uploaded_by="u1",
        ),
        ChunkMetadata(
            chunk_id="c2",
            document_id="d2",
            document_title="Title 2",
            chunk_index=0,
            page_number=1,
            text="Campus dining hall hours and student meal plan balances.",
            security_level="PUBLIC",
            source_type="PDF",
            uploaded_by="u1",
        ),
    ]

    index = BM25PartitionIndex()
    index.fit(chunks)

    # Search for quantum
    results = index.search("quantum superposition", top_k=2)
    assert len(results) == 1
    assert results[0].chunk.chunk_id == "c1"
    assert results[0].score > 0.0

    # Search for dining
    results_dining = index.search("dining meal plan", top_k=2)
    assert len(results_dining) == 1
    assert results_dining[0].chunk.chunk_id == "c2"


def test_hybrid_search_security_partitioning_zero_leakage(hybrid_vector_store):
    """Verify that BM25 and Hybrid search never retrieve confidential chunks when searching as PUBLIC."""
    hybrid_service = get_hybrid_search_service()

    # Query matching CONFIDENTIAL keywords ($42.5M, Silicon Annex, 104-B)
    query = "What is the budget for Project Silicon Annex parcel 104-B?"

    # 1. Search with PUBLIC permissions only
    pub_hybrid = hybrid_service.search(
        query=query,
        allowed_security_levels=["PUBLIC"],
        top_k=5,
        mode="hybrid",
    )
    # Must NOT contain confidential chunk
    for r in pub_hybrid:
        assert r.chunk.security_level == "PUBLIC"
        assert r.chunk.chunk_id != "c-conf-1"

    pub_bm25 = hybrid_service.search(
        query=query,
        allowed_security_levels=["PUBLIC"],
        top_k=5,
        mode="bm25",
    )
    for r in pub_bm25:
        assert r.chunk.security_level == "PUBLIC"
        assert r.chunk.chunk_id != "c-conf-1"

    # 2. Search with CONFIDENTIAL permissions
    conf_hybrid = hybrid_service.search(
        query=query,
        allowed_security_levels=["PUBLIC", "INTERNAL", "CONFIDENTIAL"],
        top_k=5,
        mode="hybrid",
    )
    assert len(conf_hybrid) >= 1
    assert conf_hybrid[0].chunk.chunk_id == "c-conf-1"
    assert conf_hybrid[0].chunk.security_level == "CONFIDENTIAL"


def test_retrieval_service_all_search_modes(hybrid_vector_store):
    student = User(
        id="s-1",
        email="student@univ.edu",
        name="Student User",
        role=Role.STUDENT.value,
        is_active=True,
    )

    # 1. Hybrid search
    res_hybrid = retrieve_for_user(student, query="What are library hours?", top_k=2, mode="hybrid")
    assert res_hybrid.total_retrieved >= 1
    assert res_hybrid.results[0].chunk.chunk_id == "c-pub-2"

    # 2. Dense search
    res_dense = retrieve_for_user(student, query="What are library hours?", top_k=2, mode="dense")
    assert res_dense.total_retrieved >= 1
    assert res_dense.results[0].chunk.chunk_id == "c-pub-2"

    # 3. BM25 search
    res_bm25 = retrieve_for_user(student, query="library hours 24 hours", top_k=2, mode="bm25")
    assert res_bm25.total_retrieved >= 1
    assert res_bm25.results[0].chunk.chunk_id == "c-pub-2"


def test_hybrid_rag_anti_hallucination_and_grounded_answer(hybrid_vector_store):
    student = User(
        id="s-2",
        email="stu@univ.edu",
        name="Alice",
        role=Role.STUDENT.value,
        is_active=True,
    )
    admin = User(
        id="a-1",
        email="adm@univ.edu",
        name="Admin",
        role=Role.ADMIN.value,
        is_active=True,
    )

    # Student asks confidential question -> Fails closed with 0 citations
    res_stu = answer_question(
        user=student,
        question="What is the budget for Project Silicon Annex parcel 104-B?",
        search_mode="hybrid",
    )
    assert res_stu.has_sufficient_context is False
    assert res_stu.citations == []
    assert "not contain enough information" in res_stu.answer.lower()

    # Admin asks confidential question -> Grounded response with CONFIDENTIAL citation
    res_adm = answer_question(
        user=admin,
        question="What is the budget for Project Silicon Annex parcel 104-B?",
        search_mode="hybrid",
    )
    assert res_adm.has_sufficient_context is True
    assert len(res_adm.citations) >= 1
    assert res_adm.citations[0].security_level == "CONFIDENTIAL"
    assert "silicon annex" in res_adm.answer.lower() or "42.5m" in res_adm.answer.lower()
