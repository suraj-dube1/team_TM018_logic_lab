"""Secure upload and document metadata API tests."""

from app.db.database import get_db
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from tests.helpers import make_pdf, make_png


def register_and_get_token(client, email="student@example.com"):
    client.post(
        "/api/auth/register",
        json={"name": "Student", "email": email, "password": "long-demo-password"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "long-demo-password"},
    )
    return response.json()["access_token"]


def test_authenticated_student_uploads_public_pdf_and_lists_metadata(client, tmp_path):
    token = register_and_get_token(client)
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Handbook", "security_level": "PUBLIC"},
        files={"file": ("student-handbook.pdf", make_pdf(), "application/pdf")},
    )
    assert response.status_code == 201
    document = response.json()
    assert document["title"] == "Handbook"
    assert document["source_type"] == "pdf"
    assert document["security_level"] == "PUBLIC"
    assert document["processing_status"] == "READY"
    assert "stored_filename" not in document
    assert "sha256" not in document

    stored_files = list((tmp_path / "uploads").iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].name != "student-handbook.pdf"
    assert stored_files[0].read_bytes().startswith(b"%PDF-")

    listing = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert [entry["id"] for entry in listing.json()] == [document["id"]]
    details = client.get(
        f"/api/documents/{document['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert details.status_code == 200
    extraction = client.get(
        f"/api/documents/{document['id']}/extraction",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extraction.status_code == 200
    assert extraction.json()["processing_status"] == "READY"
    assert extraction.json()["page_count"] == 1
    assert "Attendance information" in extraction.json()["extracted_text"]

    chunks_response = client.get(
        f"/api/documents/{document['id']}/chunks", headers={"Authorization": f"Bearer {token}"}
    )
    assert chunks_response.status_code == 200
    chunks = chunks_response.json()
    assert chunks
    assert chunks[0]["document_id"] == document["id"]
    assert chunks[0]["document_title"] == "Handbook"
    assert chunks[0]["page_number"] == 1
    assert chunks[0]["security_level"] == "PUBLIC"
    assert "Attendance information" in chunks[0]["text"]


def test_supported_png_image_is_accepted_and_ocr_result_saved(client, monkeypatch):
    from app.services import document_extraction_service

    monkeypatch.setattr(document_extraction_service, "_run_ocr", lambda image: "OCR sample text")
    token = register_and_get_token(client)
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("scan.png", make_png(), "image/png")},
    )
    assert response.status_code == 201
    assert response.json()["source_type"] == "image"
    assert response.json()["processing_status"] == "READY"
    extraction = client.get(
        f"/api/documents/{response.json()['id']}/extraction",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extraction.json()["extraction_method"] == "image_ocr"
    assert extraction.json()["extracted_text"] == "OCR sample text"


def test_student_cannot_list_or_open_confidential_document(client):
    token = register_and_get_token(client)
    created = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("report.pdf", make_pdf("Confidential report content for annual planning."), "application/pdf")},
    )
    document_id = created.json()["id"]

    # Simulate a later admin classification action; the student API view must filter it.
    session = next(app.dependency_overrides[get_db]())
    try:
        document = session.get(Document, document_id)
        document.security_level = "CONFIDENTIAL"
        session.commit()
    finally:
        session.close()

    assert client.get("/api/documents", headers={"Authorization": f"Bearer {token}"}).json() == []
    detail = client.get(
        f"/api/documents/{document_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert detail.status_code == 404
    chunks = client.get(
        f"/api/documents/{document_id}/chunks", headers={"Authorization": f"Bearer {token}"}
    )
    assert chunks.status_code == 404


def test_chunks_are_stored_with_security_metadata(client):
    token = register_and_get_token(client)
    upload = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Public policy", "security_level": "PUBLIC"},
        files={"file": ("policy.pdf", make_pdf("Attendance is required for all students."), "application/pdf")},
    )
    assert upload.status_code == 201

    session = next(app.dependency_overrides[get_db]())
    try:
        persisted = session.query(DocumentChunk).filter_by(document_id=upload.json()["id"]).all()
        assert persisted
        assert all(chunk.security_level == "PUBLIC" for chunk in persisted)
        assert all(chunk.uploaded_by for chunk in persisted)
    finally:
        session.close()


def test_student_cannot_classify_upload_as_internal(client, tmp_path):
    token = register_and_get_token(client)
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"security_level": "INTERNAL"},
        files={"file": ("notes.pdf", make_pdf("Private notes for faculty reference."), "application/pdf")},
    )
    assert response.status_code == 403
    assert list((tmp_path / "uploads").glob("*")) == []


def test_upload_requires_authentication(client):
    response = client.post(
        "/api/documents",
        data={"security_level": "PUBLIC"},
        files={"file": ("notes.pdf", make_pdf(), "application/pdf")},
    )
    assert response.status_code == 401


def test_unsupported_extension_and_mismatched_file_signature_are_rejected(client, tmp_path):
    token = register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    unsupported = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("script.exe", b"MZ-not-a-document", "application/octet-stream")},
    )
    spoofed = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("fake.pdf", b"not a PDF", "application/pdf")},
    )
    assert unsupported.status_code == 415
    assert spoofed.status_code == 415
    assert list((tmp_path / "uploads").glob("*")) == []


def test_accepted_pdf_signature_with_invalid_pdf_structure_is_recorded_as_failed(client):
    token = register_and_get_token(client)
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("broken.pdf", b"%PDF-1.4\nnot a complete PDF", "application/pdf")},
    )
    assert response.status_code == 201
    document = response.json()
    assert document["processing_status"] == "PROCESSING_FAILED"
    extraction = client.get(
        f"/api/documents/{document['id']}/extraction",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extraction.json()["error_code"] == "INVALID_PDF"
    assert extraction.json()["extracted_text"] is None


def test_upload_size_limit_is_enforced_and_partial_file_removed(client, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_size_bytes", 32)
    token = register_and_get_token(client)
    response = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("large.pdf", b"%PDF-1.4\n" + b"x" * 40, "application/pdf")},
    )
    assert response.status_code == 413
    assert list((tmp_path / "uploads").glob("*")) == []
