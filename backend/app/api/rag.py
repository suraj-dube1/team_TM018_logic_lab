"""Authenticated RAG query endpoints with citations."""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.rag import CitationItem, RAGQueryRequest, RAGQueryResponse
from app.services.audit_service import (
    ACTION_ACCESS_DENIED,
    ACTION_DOCUMENT_QUERY,
    STATUS_DENIED,
    STATUS_SUCCESS,
    record_audit_event,
)
from app.services.rag_service import answer_question


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/query", response_model=RAGQueryResponse, status_code=status.HTTP_200_OK)
def query_documents(
    payload: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RAGQueryResponse:
    """Generate a grounded, permission-filtered answer with citations for an authorized user."""
    history_dicts = [{"role": m.role, "content": m.content} for m in payload.history]
    result = answer_question(
        user=current_user,
        question=payload.question,
        top_k=payload.top_k,
        search_mode=payload.search_mode,
        history=history_dicts,
    )

    if result.has_sufficient_context:
        record_audit_event(
            db=db,
            action=ACTION_DOCUMENT_QUERY,
            status=STATUS_SUCCESS,
            user=current_user,
            details=f"Query: '{payload.question[:80]}' returned {len(result.citations)} citations",
        )
    else:
        record_audit_event(
            db=db,
            action=ACTION_ACCESS_DENIED,
            status=STATUS_DENIED,
            user=current_user,
            details=f"Query: '{payload.question[:80]}' failed closed (no authorized context)",
        )

    citation_items = [
        CitationItem(
            source_number=c.source_number,
            document_id=c.document_id,
            document_title=c.document_title,
            page_number=c.page_number,
            security_level=c.security_level,
            chunk_id=c.chunk_id,
            quote_excerpt=c.quote_excerpt,
        )
        for c in result.citations
    ]

    return RAGQueryResponse(
        question=result.question,
        answer=result.answer,
        user_role=result.user_role,
        allowed_security_levels=result.allowed_security_levels,
        citations=citation_items,
        has_sufficient_context=result.has_sufficient_context,
    )
