"""Normalized, page-aware text produced by document extraction."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DocumentExtraction(Base):
    """One extraction result per document, retaining page-level text metadata."""

    __tablename__ = "document_extractions"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    page_count: Mapped[int] = mapped_column(nullable=False, default=0)
    extraction_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
