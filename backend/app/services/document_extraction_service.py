"""PDF text extraction and optional Tesseract OCR for images and scans."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, UnidentifiedImageError
from pytesseract import TesseractError, TesseractNotFoundError

from app.core.config import get_settings


OCR_RENDER_SCALE = 2.0


class ExtractionError(Exception):
    """Safe, user-displayable extraction failure code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ExtractedPage:
    """Normalized page text with its one-based source page number."""

    page_number: int
    text: str


@dataclass(frozen=True)
class ExtractionResult:
    """Complete extraction output ready for persistence and later chunking."""

    pages: list[ExtractedPage]
    extraction_method: str

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def extracted_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace without joining separate text lines."""
    normalized = unicodedata.normalize("NFKC", text).replace("\x00", "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    output_lines: list[str] = []
    for line in normalized.split("\n"):
        line = re.sub(r"[\t\f\v ]+", " ", line).strip()
        if line or (output_lines and output_lines[-1]):
            output_lines.append(line)
    return "\n".join(output_lines).strip()


def _run_ocr(image: Image.Image) -> str:
    """Run the configured Tesseract binary and map failures to safe codes."""
    settings = get_settings()
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    try:
        return normalize_text(pytesseract.image_to_string(image, lang=settings.ocr_languages))
    except TesseractNotFoundError as exc:
        raise ExtractionError("OCR_UNAVAILABLE") from exc
    except TesseractError as exc:
        raise ExtractionError("OCR_FAILED") from exc


def _ocr_pdf_page(page: pymupdf.Page) -> str:
    """Rasterize a scanned PDF page at a readable resolution for OCR."""
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE), alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    return _run_ocr(image)


def extract_pdf(path: Path) -> ExtractionResult:
    """Extract selectable PDF text and use OCR when the document looks scanned."""
    try:
        document = pymupdf.open(path)
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise ExtractionError("INVALID_PDF") from exc

    with document:
        if document.is_encrypted:
            raise ExtractionError("PASSWORD_PROTECTED_PDF")
        if document.page_count == 0:
            raise ExtractionError("EMPTY_DOCUMENT")

        text_pages = [
            ExtractedPage(page_number=index + 1, text=normalize_text(page.get_text("text")))
            for index, page in enumerate(document)
        ]
        text_characters = sum(len(page.text) for page in text_pages)
        settings = get_settings()
        if text_characters >= settings.min_extracted_text_chars:
            return ExtractionResult(pages=text_pages, extraction_method="pdf_text")

        try:
            ocr_pages = [
                ExtractedPage(page_number=index + 1, text=_ocr_pdf_page(page))
                for index, page in enumerate(document)
            ]
        except ExtractionError:
            if text_characters:
                return ExtractionResult(pages=text_pages, extraction_method="pdf_text")
            raise

        if any(page.text for page in ocr_pages):
            return ExtractionResult(pages=ocr_pages, extraction_method="pdf_ocr")
        if text_characters:
            return ExtractionResult(pages=text_pages, extraction_method="pdf_text")
        raise ExtractionError("NO_TEXT_FOUND")


def extract_image(path: Path) -> ExtractionResult:
    """Run OCR on a stored image and retain its single-page source metadata."""
    try:
        with Image.open(path) as source_image:
            if source_image.width * source_image.height > get_settings().max_image_pixels:
                raise ExtractionError("IMAGE_TOO_LARGE")
            source_image.load()
            image = source_image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ExtractionError("INVALID_IMAGE") from exc

    text = _run_ocr(image)
    if not text:
        raise ExtractionError("NO_TEXT_FOUND")
    return ExtractionResult(
        pages=[ExtractedPage(page_number=1, text=text)],
        extraction_method="image_ocr",
    )


def extract_text_file(path: Path) -> ExtractionResult:
    """Extract plain text or markdown document into normalized page text."""
    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ExtractionError("CANNOT_READ_TEXT_FILE") from exc

    cleaned = normalize_text(raw_text)
    if not cleaned:
        raise ExtractionError("NO_TEXT_FOUND")

    return ExtractionResult(
        pages=[ExtractedPage(page_number=1, text=cleaned)],
        extraction_method="plain_text",
    )


def extract_document(path: Path, source_type: str) -> ExtractionResult:
    """Select a supported extraction path using persisted source metadata."""
    if source_type == "pdf":
        return extract_pdf(path)
    if source_type == "image":
        return extract_image(path)
    if source_type == "text":
        return extract_text_file(path)
    raise ExtractionError("UNSUPPORTED_SOURCE_TYPE")
