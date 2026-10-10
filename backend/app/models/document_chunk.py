"""Persisted page-aware chunks derived from an extracted document."""

from uuid import uuid4

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DocumentChunk(Base):
    """A searchable text segment with the source and access metadata it inherits."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        Index("ix_document_chunks_security_document", "security_level", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    document_title: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    security_level: Mapped[str] = mapped_column(String(20), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
