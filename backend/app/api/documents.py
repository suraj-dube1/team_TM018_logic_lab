import io
import logging
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin_user
from app.core.config import get_settings
from app.db.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_extraction import DocumentExtraction
from app.models.user import Role, User
from app.schemas.admin import UpdateDocumentClassificationRequest
from app.schemas.document import (
    BatchUploadItemResult,
    BatchUploadResponse,
    DocumentChunkResponse,
    DocumentExtractionResponse,
    DocumentResponse,
)
from app.services.access_control_service import (
    SecurityLevel,
    can_access,
    can_classify,
    get_allowed_security_levels,
)
from app.services.audit_service import (
    ACTION_DOCUMENT_CLASSIFY,
    ACTION_DOCUMENT_DELETE,
    ACTION_DOCUMENT_UPLOAD,
    STATUS_SUCCESS,
    record_audit_event,
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
from app.services.vector_store_service import get_vector_store


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


def extract_files_from_zip(zip_bytes: bytes) -> list[tuple[str, io.BytesIO]]:
    """Safely unpack zip file bytes and return list of (filename, BytesIO) for supported documents."""
    supported_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
    extracted: list[tuple[str, io.BytesIO]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for info in z.infolist():
            if info.is_dir() or "__MACOSX" in info.filename:
                continue
            base_name = Path(info.filename).name
            if base_name.startswith(".") or not base_name:
                continue
            ext = Path(base_name).suffix.lower()
            if ext in supported_extensions:
                clean_name = safe_original_filename(base_name)
                if clean_name:
                    file_data = z.read(info)
                    extracted.append((clean_name, io.BytesIO(file_data)))
    return extracted


def ingest_document_stream(
    stream: BinaryIO,
    original_filename: str,
    title: str | None,
    security_level: SecurityLevel,
    current_user: User,
    db: Session,
) -> tuple[Document, int]:
    """Validate, store, extract, chunk, and index a single document stream into DB and Vector Store."""
    if not can_classify(current_user, security_level):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not permitted to assign this security level.",
        )

    safe_name = safe_original_filename(original_filename)
    resolved_title = (title or "").strip() or Path(safe_name).stem.strip() or "Uploaded document"
    settings = get_settings()
    try:
        stored = store_upload(
            stream,
            original_filename=safe_name,
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
        original_filename=safe_name,
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
        if processing_succeeded and chunks:
            try:
                get_vector_store().add_chunks(chunks)
            except Exception:
                logger.exception("Failed to index chunks into vector store")
    except SQLAlchemyError as exc:
        db.rollback()
        delete_stored_upload(stored.path)
        logger.exception("Document metadata save failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be saved.",
        ) from exc

    record_audit_event(
        db=db,
        action=ACTION_DOCUMENT_UPLOAD,
        status=STATUS_SUCCESS,
        user=current_user,
        resource_type="DOCUMENT",
        resource_id=document.id,
        details=f"Uploaded '{document.title}' ({document.security_level})",
    )
    return document, len(chunks)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=120),
    security_level: SecurityLevel = Form(default=SecurityLevel.PUBLIC),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    """Validate, store, and record one user-authorized document upload."""
    doc, _ = ingest_document_stream(
        stream=file.file,
        original_filename=file.filename or "uploaded_file",
        title=title,
        security_level=security_level,
        current_user=current_user,
        db=db,
    )
    return doc


@router.post("/batch", response_model=BatchUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_documents_batch(
    files: list[UploadFile] = File(...),
    security_level: SecurityLevel = Form(default=SecurityLevel.PUBLIC),
    folder_name: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchUploadResponse:
    """Ingest multiple files or a complete folder directory of documents."""
    if not can_classify(current_user, security_level):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not permitted to assign this security level.",
        )

    items_to_process: list[tuple[str, BinaryIO]] = []

    for file in files:
        fname = file.filename or "uploaded_file"
        if fname.lower().endswith(".zip"):
            try:
                zip_content = file.file.read()
                unpacked = extract_files_from_zip(zip_content)
                items_to_process.extend(unpacked)
            except Exception as exc:
                logger.warning("Failed to unpack zip %s: %s", fname, exc)
        else:
            items_to_process.append((fname, file.file))

    if not items_to_process:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported document files found in the upload.",
        )

    results: list[BatchUploadItemResult] = []
    successful_count = 0
    failed_count = 0

    for filename, stream in items_to_process:
        try:
            doc, chunk_count = ingest_document_stream(
                stream=stream,
                original_filename=filename,
                title=None,
                security_level=security_level,
                current_user=current_user,
                db=db,
            )
            successful_count += 1
            results.append(
                BatchUploadItemResult(
                    filename=filename,
                    status="SUCCESS",
                    document_id=doc.id,
                    title=doc.title,
                    chunk_count=chunk_count,
                )
            )
        except Exception as exc:
            failed_count += 1
            err_msg = str(getattr(exc, "detail", str(exc)))
            logger.warning("Failed to ingest file '%s' in batch: %s", filename, err_msg)
            results.append(
                BatchUploadItemResult(
                    filename=filename,
                    status="FAILED",
                    error=err_msg,
                )
            )

    record_audit_event(
        db=db,
        action=ACTION_DOCUMENT_UPLOAD,
        status=STATUS_SUCCESS if successful_count > 0 else "FAILED",
        user=current_user,
        resource_type="FOLDER",
        resource_id=folder_name or "batch_upload",
        details=f"Folder batch: {successful_count}/{len(items_to_process)} documents ingested ({security_level.value})",
    )

    return BatchUploadResponse(
        total_files=len(items_to_process),
        successful_count=successful_count,
        failed_count=failed_count,
        folder_name=folder_name,
        results=results,
    )


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


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a document, its physical file, and its vector store entries."""
    document = db.get(Document, document_id)
    if document is None or not can_access(current_user, document):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    is_admin = current_user.role == Role.ADMIN.value
    is_owner = document.uploaded_by == current_user.id
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this document.",
        )

    # Delete physical file
    file_path = get_settings().upload_dir / document.stored_filename
    delete_stored_upload(file_path)

    # Remove from vector store
    get_vector_store().delete_document(document.id)

    # Delete related database chunks and extraction
    chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id)).all())
    for chunk in chunks:
        db.delete(chunk)
    extraction = db.get(DocumentExtraction, document.id)
    if extraction:
        db.delete(extraction)

    title = document.title
    db.delete(document)
    db.commit()

    record_audit_event(
        db=db,
        action=ACTION_DOCUMENT_DELETE,
        status=STATUS_SUCCESS,
        user=current_user,
        resource_type="DOCUMENT",
        resource_id=document_id,
        details=f"Deleted document '{title}'",
    )


@router.patch("/{document_id}/classification", response_model=DocumentResponse)
def update_document_classification(
    document_id: str,
    payload: UpdateDocumentClassificationRequest,
    current_admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> Document:
    """Admin reclassification of a document's security level."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    old_level = document.security_level
    document.security_level = payload.security_level.value

    # Update chunks in database
    chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id)).all())
    for chunk in chunks:
        chunk.security_level = payload.security_level.value

    db.commit()
    db.refresh(document)

    # Refresh vector store
    get_vector_store().delete_document(document_id)
    if chunks:
        get_vector_store().add_chunks(chunks)

    record_audit_event(
        db=db,
        action=ACTION_DOCUMENT_CLASSIFY,
        status=STATUS_SUCCESS,
        user=current_admin,
        resource_type="DOCUMENT",
        resource_id=document.id,
        details=f"Reclassified document '{document.title}' from {old_level} to {document.security_level}",
    )
    return document
