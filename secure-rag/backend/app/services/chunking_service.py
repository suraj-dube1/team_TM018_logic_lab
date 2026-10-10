"""Page-aware text chunking with source and authorization metadata."""

from dataclasses import dataclass
from uuid import uuid4

from app.services.document_extraction_service import ExtractedPage


DEFAULT_CHUNK_SIZE_CHARS = 1000
DEFAULT_CHUNK_OVERLAP_CHARS = 150
MIN_BOUNDARY_SEARCH_CHARS = 500


@dataclass(frozen=True)
class TextChunk:
    """A chunk and the metadata required by embedding and retrieval stages."""

    id: str
    document_id: str
    chunk_index: int
    page_number: int
    text: str
    document_title: str
    source_type: str
    security_level: str
    uploaded_by: str


def split_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Split text into bounded, overlapping segments near whitespace boundaries."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        hard_end = min(start + chunk_size, len(text))
        end = hard_end
        if hard_end < len(text):
            search_start = min(start + MIN_BOUNDARY_SEARCH_CHARS, hard_end)
            candidates = (
                text.rfind("\n", search_start, hard_end + 1),
                text.rfind(" ", search_start, hard_end + 1),
                text.rfind("\t", search_start, hard_end + 1),
            )
            boundary = max(candidates)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break

        next_start = max(start + 1, end - overlap)
        # Begin at a word boundary where possible; overlap may shrink slightly.
        while next_start < end and next_start > 0 and not text[next_start - 1].isspace():
            next_start += 1
        start = max(next_start, end)

    return chunks


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    document_id: str,
    document_title: str,
    source_type: str,
    security_level: str,
    uploaded_by: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[TextChunk]:
    """Chunk each extracted page independently and attach document metadata."""
    output: list[TextChunk] = []
    for page in pages:
        for text in split_text(page.text, chunk_size=chunk_size, overlap=overlap):
            output.append(
                TextChunk(
                    id=str(uuid4()),
                    document_id=document_id,
                    chunk_index=len(output),
                    page_number=page.page_number,
                    text=text,
                    document_title=document_title,
                    source_type=source_type,
                    security_level=security_level,
                    uploaded_by=uploaded_by,
                )
            )
    return output
