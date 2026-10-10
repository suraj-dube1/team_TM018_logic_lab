"""Unit tests for reusable page-aware chunking."""

import pytest

from app.services.chunking_service import chunk_pages, split_text
from app.services.document_extraction_service import ExtractedPage


def test_split_text_bounds_chunks_and_keeps_overlap():
    text = " ".join(f"word{i}" for i in range(100))
    chunks = split_text(text, chunk_size=120, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks)
    assert all(chunk.strip() == chunk for chunk in chunks)
    assert any(set(previous.split()) & set(following.split()) for previous, following in zip(chunks, chunks[1:]))


def test_chunk_pages_preserves_page_and_document_metadata():
    pages = [
        ExtractedPage(page_number=1, text="alpha " * 20),
        ExtractedPage(page_number=2, text="beta " * 20),
    ]

    chunks = chunk_pages(
        pages,
        document_id="document-123",
        document_title="Faculty handbook",
        source_type="pdf",
        security_level="INTERNAL",
        uploaded_by="faculty-123",
        chunk_size=40,
        overlap=8,
    )

    assert chunks
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert {chunk.document_id for chunk in chunks} == {"document-123"}
    assert {chunk.document_title for chunk in chunks} == {"Faculty handbook"}
    assert {chunk.source_type for chunk in chunks} == {"pdf"}
    assert {chunk.security_level for chunk in chunks} == {"INTERNAL"}
    assert {chunk.uploaded_by for chunk in chunks} == {"faculty-123"}
    assert all(chunk.id for chunk in chunks)


def test_blank_text_produces_no_chunks():
    assert split_text(" \n  ") == []


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (10, -1), (10, 10)],
)
def test_invalid_chunk_parameters_are_rejected(chunk_size, overlap):
    with pytest.raises(ValueError):
        split_text("some text", chunk_size=chunk_size, overlap=overlap)
