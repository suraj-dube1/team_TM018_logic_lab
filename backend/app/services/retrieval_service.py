"""Permission-filtered secure chunk retrieval service."""

from dataclasses import dataclass
import logging

from typing import Literal

from app.models.user import User
from app.services.access_control_service import get_allowed_security_levels
from app.services.hybrid_search_service import get_hybrid_search_service
from app.services.vector_store_service import ChunkMetadata, SearchResult


logger = logging.getLogger(__name__)


@dataclass
class SecureRetrievalResult:
    user_id: str
    user_role: str
    query: str
    allowed_security_levels: list[str]
    total_retrieved: int
    results: list[SearchResult]


def retrieve_for_user(
    user: User,
    query: str,
    top_k: int = 5,
    mode: Literal["hybrid", "dense", "bm25"] = "hybrid",
) -> SecureRetrievalResult:
    """Retrieve semantically relevant chunks constrained strictly to the user's role.

    Critical Security Behavior:
    - Inactive users are rejected immediately and receive 0 chunks.
    - Resolves permitted security levels using the central access control service.
    - Restricts search exclusively to the authorized sub-indices (both BM25 and Dense).
    - Unauthorized chunks are NEVER searched, scored, or retrieved.
    - Supports 'hybrid' (RRF fusion), 'dense' (FAISS), and 'bm25' (lexical).
    """
    if not getattr(user, "is_active", True):
        logger.warning("Retrieval attempted by inactive user %s", user.id)
        return SecureRetrievalResult(
            user_id=user.id,
            user_role=getattr(user, "role", "STUDENT"),
            query=query,
            allowed_security_levels=[],
            total_retrieved=0,
            results=[],
        )

    allowed_levels = get_allowed_security_levels(user)
    level_strings = [level.value for level in allowed_levels]

    if not level_strings:
        logger.warning("User %s with role %s has no allowed security levels", user.id, user.role)
        return SecureRetrievalResult(
            user_id=user.id,
            user_role=user.role,
            query=query,
            allowed_security_levels=[],
            total_retrieved=0,
            results=[],
        )

    hybrid_service = get_hybrid_search_service()
    results = hybrid_service.search(
        query=query,
        allowed_security_levels=level_strings,
        top_k=top_k,
        mode=mode,
    )

    return SecureRetrievalResult(
        user_id=user.id,
        user_role=user.role,
        query=query,
        allowed_security_levels=level_strings,
        total_retrieved=len(results),
        results=results,
    )
