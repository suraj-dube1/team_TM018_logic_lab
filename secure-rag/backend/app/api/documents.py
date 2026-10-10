"""Authenticated document upload and access-filtered metadata endpoints."""

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.schemas.document import DocumentChunkResponse, DocumentExtractionResponse, DocumentResponse
from app.services.access_control_service import (
    SecurityLevel,
    can_access,
    can_classify,
    get_allowed_security_levels,
)
from app.services.file_storage_service import (
    UploadRejected,
    UploadTooLarge,
    delete_stored_upload,
    safe_original_filename,
    store_upload,
)
from app.services.document_extraction_service import ExtractionError, extract_document
from app.services.chunking_service import chunk_pages


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=120),
    security_level: SecurityLevel = Form(default=SecurityLevel.PUBLIC),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    """Validate, store, and record one user-authorized PDF or image upload."""
    if not can_classify(current_user, security_level):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not permitted to assign this security level.",
        )

    original_filename = safe_original_filename(file.filename)
    resolved_title = (title or "").strip() or Path(original_filename).stem.strip() or "Uploaded document"
    settings = get_settings()
    try:
        stored = store_upload(
            file.file,
            original_filename=original_filename,
            upload_dir=settings.upload_dir,
            max_size_bytes=settings.max_upload_size_bytes,
        )
    except UploadTooLarge as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except UploadRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("Document storage failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be saved.",
        ) from exc

    extraction_result = None
    extraction_error = None
    try:
        extraction_result = extract_document(stored.path, stored.source_type)
    except ExtractionError as exc:
        extraction_error = exc.code
        logger.info("Document extraction failed with code %s", exc.code)
    except Exception:
        extraction_error = "EXTRACTION_FAILED"
        logger.exception("Unexpected document extraction failure")

    document = Document(
        id=str(uuid4()),
        title=resolved_title[:120],
        original_filename=original_filename,
        stored_filename=stored.stored_filename,
        source_type=stored.source_type,
        security_level=security_level.value,
        processing_status="PROCESSING_FAILED",
        file_size_bytes=stored.file_size_bytes,
        sha256=stored.sha256,
        uploaded_by=current_user.id,
    )
    chunks = []
    if extraction_result:
        try:
            chunks = chunk_pages(
                extraction_result.pages,
                document_id=document.id,
                document_title=document.title,
                source_type=document.source_type,
                security_level=document.security_level,
                uploaded_by=document.uploaded_by,
            )
            if not chunks:
                extraction_error = "NO_TEXT_FOUND"
        except Exception:
            extraction_error = "CHUNKING_FAILED"
            logger.exception("Document chunking failed")

    processing_succeeded = extraction_result is not None and bool(chunks)
    document.processing_status = "READY" if processing_succeeded else "PROCESSING_FAILED"
    try:
        db.add(document)
        db.flush()
        db.add(
            DocumentExtraction(
                document_id=document.id,
                extracted_text=extraction_result.extracted_text if extraction_result else "",
                pages=(
                    [
                        {"page_number": page.page_number, "text": page.text}
                        for page in extraction_result.pages
                    ]
                    if extraction_result
                    else []
                ),
                page_count=extraction_result.page_count if extraction_result else 0,
                extraction_method=extraction_result.extraction_method if extraction_result else None,
                error_code=extraction_error,
            )
        )
        db.add_all(
            [
                DocumentChunk(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    document_title=chunk.document_title,
                    source_type=chunk.source_type,
                    security_level=chunk.security_level,
                    uploaded_by=chunk.uploaded_by,
                )
                for chunk in chunks
            ]
        )
        db.commit()
        db.refresh(document)
    except SQLAlchemyError as exc:
        db.rollback()
        delete_stored_upload(stored.path)
        logger.exception("Document metadata save failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be saved.",
        ) from exc
    return document


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    """List only documents in the caller's permitted security levels."""
    allowed_levels = get_allowed_security_levels(current_user)
    if not allowed_levels:
        return []
    query = (
        select(Document)
        .where(Document.security_level.in_([level.value for level in allowed_levels]))
        .order_by(Document.created_at.desc())
    )
    return list(db.scalars(query).all())


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    """Return metadata only when the caller may access the document."""
    document = db.get(Document, document_id)
    if document is None or not can_access(current_user, document):
        # Hide existence from callers who are not authorized to see this record.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@router.get("/{document_id}/extraction", response_model=DocumentExtractionResponse)
def get_document_extraction(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentExtractionResponse:
    """Return extracted text only after the same document access check."""
    document = db.get(Document, document_id)
    if document is None or not can_access(current_user, document):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    extraction = db.get(DocumentExtraction, document_id)
    if extraction is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document extraction is not available yet.",
        )
    return DocumentExtractionResponse(
        document_id=document_id,
        processing_status=document.processing_status,
        extraction_method=extraction.extraction_method,
        page_count=extraction.page_count,
        extracted_text=extraction.extracted_text if document.processing_status == "READY" else None,
        error_code=extraction.error_code,
    )


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
def list_document_chunks(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentChunk]:
    """Return persisted chunks only after checking parent-document access."""
    document = db.get(Document, document_id)
    if document is None or not can_access(current_user, document):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    query = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(db.scalars(query).all())
