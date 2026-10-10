"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.core.config import get_settings
from app.db.database import Base, check_database_connection, engine
from app.models.document import Document  # noqa: F401 - registers this model with SQLAlchemy metadata.
from app.models.document_chunk import DocumentChunk  # noqa: F401 - registers chunk persistence.
from app.models.document_extraction import DocumentExtraction  # noqa: F401 - registers this model with SQLAlchemy metadata.
from app.models.user import User  # noqa: F401 - registers this model with SQLAlchemy metadata.


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create MVP tables and validate the database during startup."""
    Base.metadata.create_all(bind=engine)
    check_database_connection()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first secure document retrieval and question answering.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(documents_router)


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Report API and database readiness without exposing internal details."""
    try:
        check_database_connection()
    except Exception as exc:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The service is temporarily unavailable.",
        ) from exc
    return {"status": "ok", "database": "ok", "environment": settings.environment}
