"""FAISS vector store for semantic indexing and chunk similarity search with security partitioning."""

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
from typing import Any, Sequence

import faiss
import numpy as np

from app.core.config import get_settings
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import EMBEDDING_DIMENSION, embed_text, embed_texts


logger = logging.getLogger(__name__)

SUPPORTED_SECURITY_LEVELS = ("PUBLIC", "INTERNAL", "CONFIDENTIAL")


@dataclass
class ChunkMetadata:
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    page_number: int
    text: str
    security_level: str
    source_type: str
    uploaded_by: str


@dataclass
class SearchResult:
    chunk: ChunkMetadata
    score: float


class VectorStoreService:
    """Manages security-partitioned FAISS indices with chunk metadata.

    Security filtering is enforced BEFORE or DURING search by querying only the
    sub-indices corresponding to the caller's permitted security levels.
    """

    def __init__(self, storage_dir: Path | None = None):
        settings = get_settings()
        self.storage_dir = storage_dir or settings.vector_store_dir
        self.meta_file = self.storage_dir / "metadata.json"
        self.dimension = EMBEDDING_DIMENSION
        self.indices: dict[str, faiss.IndexFlatIP] = {
            level: faiss.IndexFlatIP(self.dimension) for level in SUPPORTED_SECURITY_LEVELS
        }
        self.metadata_by_level: dict[str, list[ChunkMetadata]] = {
            level: [] for level in SUPPORTED_SECURITY_LEVELS
        }
        self.metadata: list[ChunkMetadata] = []
        self._load()

    def count(self, level: str | None = None) -> int:
        """Return the number of indexed vectors (overall or for a specific level)."""
        if level:
            return self.indices.get(level, faiss.IndexFlatIP(self.dimension)).ntotal
        return sum(idx.ntotal for idx in self.indices.values())

    def _ensure_storage_dir() -> None:
        pass

    def _get_index_file(self, level: str) -> Path:
        return self.storage_dir / f"index_{level.lower()}.faiss"

    def _save(self) -> None:
        """Persist partitioned indices and metadata to disk."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            for level, index in self.indices.items():
                faiss.write_index(index, str(self._get_index_file(level)))
            meta_dicts = [asdict(meta) for meta in self.metadata]
            self.meta_file.write_text(json.dumps(meta_dicts, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("Failed to persist vector indices or metadata to %s", self.storage_dir)

    def _load(self) -> None:
        """Load persisted partitioned indices and metadata from disk if available."""
        if self.meta_file.exists():
            try:
                raw_meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
                self.metadata = [ChunkMetadata(**item) for item in raw_meta]
                self.metadata_by_level = {level: [] for level in SUPPORTED_SECURITY_LEVELS}
                for item in self.metadata:
                    if item.security_level in self.metadata_by_level:
                        self.metadata_by_level[item.security_level].append(item)

                # Attempt to load saved FAISS indices per level
                for level in SUPPORTED_SECURITY_LEVELS:
                    idx_path = self._get_index_file(level)
                    if idx_path.exists():
                        self.indices[level] = faiss.read_index(str(idx_path))
                    else:
                        # Rebuild this level if index file is missing but metadata exists
                        self.indices[level] = faiss.IndexFlatIP(self.dimension)
                        level_chunks = self.metadata_by_level.get(level, [])
                        if level_chunks:
                            embs = embed_texts([c.text for c in level_chunks])
                            self.indices[level].add(embs)
                logger.info("Loaded %d vectors from %s", self.count(), self.storage_dir)
            except Exception:
                logger.exception("Failed to load vector store from %s; resetting to empty", self.storage_dir)
                self.clear()

    def clear(self) -> None:
        """Reset all indices and metadata in memory and delete files."""
        self.indices = {
            level: faiss.IndexFlatIP(self.dimension) for level in SUPPORTED_SECURITY_LEVELS
        }
        self.metadata_by_level = {level: [] for level in SUPPORTED_SECURITY_LEVELS}
        self.metadata = []
        if self.meta_file.exists():
            self.meta_file.unlink(missing_ok=True)
        for level in SUPPORTED_SECURITY_LEVELS:
            idx_file = self._get_index_file(level)
            if idx_file.exists():
                idx_file.unlink(missing_ok=True)

    def add_chunks(self, chunks: Sequence[DocumentChunk | dict[str, Any]]) -> int:
        """Embed and index chunks into their corresponding security-level indices.

        Returns:
            int: The total number of new chunks added.
        """
        if not chunks:
            return 0

        grouped_by_level: dict[str, list[ChunkMetadata]] = {
            level: [] for level in SUPPORTED_SECURITY_LEVELS
        }

        for item in chunks:
            if isinstance(item, ChunkMetadata):
                meta = item
            elif isinstance(item, DocumentChunk):
                meta = ChunkMetadata(
                    chunk_id=item.id,
                    document_id=item.document_id,
                    document_title=item.document_title,
                    chunk_index=item.chunk_index,
                    page_number=item.page_number,
                    text=item.text,
                    security_level=item.security_level,
                    source_type=item.source_type,
                    uploaded_by=item.uploaded_by,
                )
            elif isinstance(item, dict):
                meta = ChunkMetadata(
                    chunk_id=item["id"],
                    document_id=item["document_id"],
                    document_title=item["document_title"],
                    chunk_index=item["chunk_index"],
                    page_number=item["page_number"],
                    text=item["text"],
                    security_level=item["security_level"],
                    source_type=item["source_type"],
                    uploaded_by=item["uploaded_by"],
                )
            else:
                meta = ChunkMetadata(
                    chunk_id=getattr(item, "id", getattr(item, "chunk_id", "")),
                    document_id=getattr(item, "document_id"),
                    document_title=getattr(item, "document_title"),
                    chunk_index=getattr(item, "chunk_index"),
                    page_number=getattr(item, "page_number"),
                    text=getattr(item, "text"),
                    security_level=getattr(item, "security_level"),
                    source_type=getattr(item, "source_type"),
                    uploaded_by=getattr(item, "uploaded_by"),
                )

            level = meta.security_level.upper()
            if level not in grouped_by_level:
                grouped_by_level[level] = []
                self.indices[level] = faiss.IndexFlatIP(self.dimension)
                self.metadata_by_level[level] = []

            grouped_by_level[level].append(meta)

        total_added = 0
        for level, level_meta in grouped_by_level.items():
            if not level_meta:
                continue
            embs = embed_texts([m.text for m in level_meta])
            if embs.shape[0] > 0:
                self.indices[level].add(embs)
                self.metadata_by_level[level].extend(level_meta)
                self.metadata.extend(level_meta)
                total_added += len(level_meta)

        self._save()
        return total_added

    def search(
        self,
        query: str,
        allowed_security_levels: Sequence[str] | None = None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Perform similarity search restricted strictly to allowed security levels.

        Security Enforcement:
        - If `allowed_security_levels` is provided, ONLY indices belonging to those
          levels are searched. Unauthorized vector sets are never touched or scored.
        - If `allowed_security_levels` is None, all levels are searched.
        """
        if not query.strip() or self.count() == 0:
            return []

        # Determine target partitioned indices
        if allowed_security_levels is not None:
            active_levels = [
                lvl.upper() for lvl in allowed_security_levels
                if lvl.upper() in self.indices and self.indices[lvl.upper()].ntotal > 0
            ]
        else:
            active_levels = [lvl for lvl, idx in self.indices.items() if idx.ntotal > 0]

        if not active_levels:
            return []

        query_vec = embed_text(query).reshape(1, -1)
        candidates: list[SearchResult] = []

        for level in active_levels:
            index = self.indices[level]
            metadata = self.metadata_by_level[level]
            k = min(top_k, index.ntotal)
            scores, indices = index.search(query_vec, k)
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(metadata):
                    continue
                candidates.append(SearchResult(chunk=metadata[idx], score=float(score)))

        # Sort all candidates by cosine similarity descending
        candidates.sort(key=lambda r: r.score, reverse=True)
        return candidates[:top_k]

    def delete_document(self, document_id: str) -> int:
        """Remove all chunks for a document and rebuild partitioned indices."""
        remaining_meta = [m for m in self.metadata if m.document_id != document_id]
        removed_count = len(self.metadata) - len(remaining_meta)
        if removed_count == 0:
            return 0

        self.clear()
        if remaining_meta:
            self.add_chunks(remaining_meta)
        return removed_count


_vector_store_instance: VectorStoreService | None = None


def get_vector_store() -> VectorStoreService:
    """Return the global VectorStoreService singleton."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStoreService()
    return _vector_store_instance


def set_vector_store(instance: VectorStoreService | None) -> None:
    """Set or reset the global VectorStoreService instance (mainly for tests)."""
    global _vector_store_instance
    _vector_store_instance = instance
    try:
        from app.services.hybrid_search_service import reset_hybrid_search_service
        reset_hybrid_search_service()
    except ImportError:
        pass
