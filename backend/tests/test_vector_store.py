"""Unit tests for FAISS vector store service."""

from pathlib import Path
import tempfile

import pytest

from app.services.vector_store_service import (
    ChunkMetadata,
    SearchResult,
    VectorStoreService,
)


@pytest.fixture
def temp_vector_store() -> VectorStoreService:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield VectorStoreService(storage_dir=Path(tmpdir))


def test_empty_vector_store(temp_vector_store: VectorStoreService) -> None:
    assert temp_vector_store.count() == 0
    results = temp_vector_store.search("any query")
    assert results == []


def test_add_chunks_and_semantic_retrieval(temp_vector_store: VectorStoreService) -> None:
    chunks = [
        {
            "id": "c-1",
            "document_id": "doc-public",
            "document_title": "Student Handbook",
            "chunk_index": 0,
            "page_number": 1,
            "text": "All undergraduate students must maintain 80 percent attendance across all registered courses.",
            "security_level": "PUBLIC",
            "source_type": "PDF",
            "uploaded_by": "user-1",
        },
        {
            "id": "c-2",
            "document_id": "doc-internal",
            "document_title": "Faculty Operations",
            "chunk_index": 0,
            "page_number": 3,
            "text": "Faculty research grants are renewed each fiscal year following committee evaluation.",
            "security_level": "INTERNAL",
            "source_type": "PDF",
            "uploaded_by": "user-2",
        },
        {
            "id": "c-3",
            "document_id": "doc-confidential",
            "document_title": "Executive Budget",
            "chunk_index": 0,
            "page_number": 1,
            "text": "The confidential budget allocation reserves 4 million dollars for capital equipment.",
            "security_level": "CONFIDENTIAL",
            "source_type": "PDF",
            "uploaded_by": "user-admin",
        },
    ]

    added = temp_vector_store.add_chunks(chunks)
    assert added == 3
    assert temp_vector_store.count() == 3

    # Query for student attendance
    results = temp_vector_store.search("What is the mandatory attendance requirement?", top_k=2)
    assert len(results) == 2
    top_result = results[0]
    assert top_result.chunk.chunk_id == "c-1"
    assert top_result.chunk.document_title == "Student Handbook"
    assert top_result.chunk.security_level == "PUBLIC"
    assert top_result.score > 0.45

    # Results should be sorted by score descending
    assert results[0].score >= results[1].score


def test_delete_document(temp_vector_store: VectorStoreService) -> None:
    chunks = [
        {
            "id": "c-1",
            "document_id": "doc-1",
            "document_title": "Doc 1",
            "chunk_index": 0,
            "page_number": 1,
            "text": "Alpha protocol guidelines for system login.",
            "security_level": "PUBLIC",
            "source_type": "PDF",
            "uploaded_by": "user-1",
        },
        {
            "id": "c-2",
            "document_id": "doc-2",
            "document_title": "Doc 2",
            "chunk_index": 0,
            "page_number": 1,
            "text": "Beta network setup instructions.",
            "security_level": "PUBLIC",
            "source_type": "PDF",
            "uploaded_by": "user-1",
        },
    ]
    temp_vector_store.add_chunks(chunks)
    assert temp_vector_store.count() == 2

    removed = temp_vector_store.delete_document("doc-1")
    assert removed == 1
    assert temp_vector_store.count() == 1
    assert temp_vector_store.metadata[0].document_id == "doc-2"


def test_persistence_save_and_reload() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)
        store_1 = VectorStoreService(storage_dir=storage_path)
        store_1.add_chunks(
            [
                {
                    "id": "c-p1",
                    "document_id": "doc-p1",
                    "document_title": "Persisted Document",
                    "chunk_index": 0,
                    "page_number": 1,
                    "text": "Persisted chunk data for testing cold boot reload.",
                    "security_level": "INTERNAL",
                    "source_type": "PDF",
                    "uploaded_by": "user-p",
                }
            ]
        )
        assert store_1.count() == 1

        # Simulate fresh service instance loading from same directory
        store_2 = VectorStoreService(storage_dir=storage_path)
        assert store_2.count() == 1
        res = store_2.search("cold boot reload")
        assert len(res) == 1
        assert res[0].chunk.chunk_id == "c-p1"
        assert res[0].chunk.document_title == "Persisted Document"
