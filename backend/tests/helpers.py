"""Small valid document fixtures generated entirely in memory."""

from io import BytesIO

import pymupdf
from PIL import Image


def make_pdf(text: str = "Attendance information for students and faculty.") -> bytes:
    """Generate a valid one-page text PDF for extraction and upload tests."""
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=12)
        return document.tobytes()


def make_png() -> bytes:
    """Generate a valid one-pixel PNG without touching disk."""
    output = BytesIO()
    Image.new("RGB", (8, 8), color="white").save(output, format="PNG")
    return output.getvalue()
