"""Page-aware PDF and OCR extraction tests."""

import pymupdf

from app.services import document_extraction_service as extraction


def test_pdf_text_extraction_preserves_page_numbers(tmp_path):
    pdf_path = tmp_path / "two-pages.pdf"
    with pymupdf.open() as document:
        first = document.new_page()
        first.insert_text((50, 60), "First page contains useful searchable policy text.")
        second = document.new_page()
        second.insert_text((50, 60), "Second page contains another section of policy text.")
        document.save(pdf_path)

    result = extraction.extract_pdf(pdf_path)
    assert result.extraction_method == "pdf_text"
    assert result.page_count == 2
    assert [page.page_number for page in result.pages] == [1, 2]
    assert "First page" in result.pages[0].text
    assert "Second page" in result.pages[1].text


def test_scanned_pdf_uses_ocr_fallback(tmp_path, monkeypatch):
    pdf_path = tmp_path / "scan.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(pdf_path)

    monkeypatch.setattr(extraction, "_ocr_pdf_page", lambda page: "recognized scanned policy text")
    result = extraction.extract_pdf(pdf_path)
    assert result.extraction_method == "pdf_ocr"
    assert result.pages[0].text == "recognized scanned policy text"


def test_text_normalization_removes_nulls_and_collapses_whitespace():
    assert extraction.normalize_text("  First\t line\x00\r\n\r\n  Second   line  ") == "First line\n\nSecond line"


def test_invalid_pdf_returns_safe_error_code(tmp_path):
    invalid_pdf = tmp_path / "broken.pdf"
    invalid_pdf.write_bytes(b"not a PDF")
    try:
        extraction.extract_pdf(invalid_pdf)
    except extraction.ExtractionError as exc:
        assert exc.code == "INVALID_PDF"
    else:
        raise AssertionError("Invalid PDF should fail extraction")
