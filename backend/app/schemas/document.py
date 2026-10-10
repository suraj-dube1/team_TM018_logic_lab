"""Document upload and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.services.access_control_service import SecurityLevel


class DocumentResponse(BaseModel):
    """Safe document metadata; never returns local storage paths or names."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    original_filename: str
    source_type: Literal["pdf", "image", "text"]
    security_level: SecurityLevel
    processing_status: str
    file_size_bytes: int
    uploaded_by: str
    created_at: datetime


class DocumentExtractionResponse(BaseModel):
    """Permission-filtered extraction result for one document."""

    document_id: str
    processing_status: str
    extraction_method: str | None
    page_count: int
    extracted_text: str | None
    error_code: str | None


class DocumentChunkResponse(BaseModel):
    """One permission-filtered chunk with its source and security metadata."""

    id: str
    document_id: str
    chunk_index: int
    page_number: int
    text: str
    document_title: str
    source_type: Literal["pdf", "image", "text"]
    security_level: SecurityLevel
    uploaded_by: str


class BatchUploadItemResult(BaseModel):
    filename: str
    status: Literal["SUCCESS", "FAILED"]
    document_id: str | None = None
    title: str | None = None
    chunk_count: int = 0
    error: str | None = None


class BatchUploadResponse(BaseModel):
    total_files: int
    successful_count: int
    failed_count: int
    folder_name: str | None = None
    results: list[BatchUploadItemResult]

