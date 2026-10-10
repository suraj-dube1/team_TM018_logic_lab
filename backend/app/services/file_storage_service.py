"""Validate and safely store uploaded PDF and image files."""

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


CHUNK_SIZE = 64 * 1024
FILE_TYPES: dict[str, tuple[str, bytes | None]] = {
    ".pdf": ("pdf", b"%PDF-"),
    ".png": ("image", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image", b"\xff\xd8\xff"),
    ".jpeg": ("image", b"\xff\xd8\xff"),
    ".txt": ("text", None),
    ".md": ("text", None),
}


class UploadRejected(ValueError):
    """Raised when the uploaded file is empty or has unsupported content."""

    status_code = 415


class EmptyUpload(UploadRejected):
    """Raised when the client submits an empty file."""

    status_code = 400


class UploadTooLarge(ValueError):
    """Raised when the stream exceeds its configured size limit."""


@dataclass(frozen=True)
class StoredUpload:
    """Metadata about a file successfully committed to local storage."""

    stored_filename: str
    source_type: str
    file_size_bytes: int
    sha256: str
    path: Path


def safe_original_filename(filename: str | None) -> str:
    """Keep a display-only basename and remove control characters."""
    if not filename:
        return ""
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return re.sub(r"[\x00-\x1f\x7f]", "", basename).strip()[:255]


def store_upload(
    stream: BinaryIO,
    *,
    original_filename: str,
    upload_dir: Path,
    max_size_bytes: int,
) -> StoredUpload:
    """Validate a bounded byte stream and atomically save it under a random name."""
    safe_name = safe_original_filename(original_filename)
    extension = Path(safe_name).suffix.lower()
    file_type = FILE_TYPES.get(extension)
    if file_type is None:
        raise UploadRejected("Unsupported file type.")

    upload_dir.mkdir(parents=True, exist_ok=True)
    stream.seek(0)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".upload-", suffix=".part", dir=upload_dir, delete=False
        ) as destination:
            temp_path = Path(destination.name)
            first_chunk = stream.read(min(CHUNK_SIZE, max_size_bytes + 1))
            if not first_chunk:
                raise EmptyUpload("The uploaded file is empty.")
            if len(first_chunk) > max_size_bytes:
                raise UploadTooLarge("File exceeds the maximum upload size.")

            source_type, signature = file_type
            if signature is not None:
                if not first_chunk.startswith(signature):
                    raise UploadRejected("File content does not match its extension.")
            else:
                try:
                    first_chunk.decode("utf-8", errors="replace")
                except Exception as exc:
                    raise UploadRejected("File content is not valid text.") from exc

            digest = hashlib.sha256()
            digest.update(first_chunk)
            destination.write(first_chunk)
            total_size = len(first_chunk)

            while True:
                remaining_plus_one = max_size_bytes - total_size + 1
                chunk = stream.read(min(CHUNK_SIZE, remaining_plus_one))
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size_bytes:
                    raise UploadTooLarge("File exceeds the maximum upload size.")
                digest.update(chunk)
                destination.write(chunk)

        stored_filename = f"{uuid4().hex}{extension}"
        final_path = upload_dir / stored_filename
        os.replace(temp_path, final_path)
        temp_path = None
        return StoredUpload(
            stored_filename=stored_filename,
            source_type=source_type,
            file_size_bytes=total_size,
            sha256=digest.hexdigest(),
            path=final_path,
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def delete_stored_upload(path: Path) -> None:
    """Remove a generated file after a database transaction failure."""
    path.unlink(missing_ok=True)
