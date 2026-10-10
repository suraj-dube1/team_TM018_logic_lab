"""Authenticated permission-aware chunk retrieval endpoints."""

import logging

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.retrieval import RetrievalChunkItem, RetrievalQueryRequest, RetrievalResponse
from app.services.retrieval_service import retrieve_for_user


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse, status_code=status.HTTP_200_OK)
def search_documents(
    payload: RetrievalQueryRequest,
    current_user: User = Depends(get_current_user),
) -> RetrievalResponse:
    """Retrieve semantically relevant chunks constrained strictly to the caller's role.

    - Students can ONLY retrieve PUBLIC chunks.
    - Faculty can retrieve PUBLIC and INTERNAL chunks.
    - Admins can retrieve PUBLIC, INTERNAL, and CONFIDENTIAL chunks.
    """
    res = retrieve_for_user(
        user=current_user,
        query=payload.query,
        top_k=payload.top_k,
        mode=payload.search_mode,
    )

    chunk_items = [
        RetrievalChunkItem(
            chunk_id=r.chunk.chunk_id,
            document_id=r.chunk.document_id,
            document_title=r.chunk.document_title,
            page_number=r.chunk.page_number,
            text=r.chunk.text,
            security_level=r.chunk.security_level,
            score=round(r.score, 4),
        )
        for r in res.results
    ]

    return RetrievalResponse(
        query=payload.query,
        user_role=res.user_role,
        allowed_security_levels=res.allowed_security_levels,
        total_retrieved=len(chunk_items),
        chunks=chunk_items,
    )
