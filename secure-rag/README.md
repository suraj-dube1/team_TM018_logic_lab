# Secure Multi-Modal RAG System

A localhost-first secure document question-answering application. Phases 1–5 provide the backend foundation, authentication, access control, secure uploads, and PDF/image text extraction. Phase 6 creates persistent page-aware chunks for later embedding and retrieval.

## Phase 1 architecture

React + Vite frontend → FastAPI REST API → authentication and SQLAlchemy services → SQLite. Later phases add centralized document authorization, document processing, permission-aware vector retrieval, citations, and audit events.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer and npm

## Backend setup (Windows PowerShell)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    $jwtSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
    (Get-Content .env) -replace '^JWT_SECRET_KEY=.*', "JWT_SECRET_KEY=$jwtSecret" | Set-Content .env
}
uvicorn app.main:app --reload
```

If PowerShell blocks virtual-environment activation, either use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for that terminal, or invoke `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe -m uvicorn app.main:app --reload` directly.

The API listens at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`.

## Frontend setup (second PowerShell terminal)

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`. The page should report the API and database as operational.

## Linux/macOS equivalents

From `backend/`, create and activate a virtual environment with `python3 -m venv .venv` and `source .venv/bin/activate`; then install requirements, copy `.env.example` to `.env`, set a fresh `JWT_SECRET_KEY` (for example, `python -c 'import secrets; print(secrets.token_urlsafe(48))'`), and run `uvicorn app.main:app --reload`. From `frontend/`, run `npm install` and `npm run dev`.

## Environment configuration

Copy each `.env.example` to `.env` for local overrides. Generate a unique `JWT_SECRET_KEY` as shown in the backend setup; the example placeholder is intentionally rejected by the app. The backend defaults to a SQLite database at `backend/data/secure_rag.db` and only allows the Vite localhost origins in CORS. Do not commit `.env` files or place secrets in frontend variables; Vite variables are visible to browsers.

## Phase 1 check

With both services running, visit `http://localhost:8000/api/health`. Expected response:

```json
{"status":"ok","database":"ok","environment":"development"}
```

The frontend status card should show **API service: Operational** and **Database: Connected**. If the API is stopped, it should show a friendly unavailable message. SQLite file and the users table are created automatically.

## Phase 2: authentication

Public registration creates a `STUDENT` account only; role input is rejected. Passwords are hashed with Argon2id. Login returns a short-lived JWT access token. The protected `/api/auth/me` endpoint validates the token and reads the current role and active status from SQLite. The role is not trusted from the token, so later role changes take effect without waiting for token expiry.

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/register` | Public | Create student account (`name`, `email`, `password`; password 12–128 characters) |
| `POST` | `/api/auth/login` | Public | Return bearer access token (`email`, `password`) |
| `GET` | `/api/auth/me` | Bearer token | Return the caller's safe profile and current role |

Use the interactive docs at `http://localhost:8000/docs` to try the endpoints. After login, click **Authorize** and enter `Bearer <access_token>` to call `/api/auth/me`.

### Authentication checks

From `backend/` with its virtual environment active, run:

```powershell
python -m pytest
```

The tests use an isolated in-memory database and cover registration, duplicate emails, role-escalation rejection, incorrect passwords, and missing or malformed JWTs. A successful run reports five passing tests.

## Phase 3: centralized access control

`app.services.access_control_service` is the single policy location for role-to-classification decisions. It defines `SecurityLevel`, returns each active user's permitted levels, checks `can_access(user, resource)`, and provides `filter_accessible(...)` for filtering before downstream processing. Unknown roles, unknown classifications, and inactive users fail closed.

| Role | Permitted levels |
|---|---|
| Student | `PUBLIC` |
| Faculty | `PUBLIC`, `INTERNAL` |
| Admin | `PUBLIC`, `INTERNAL`, `CONFIDENTIAL` |

Document routes and retrieval must call this service before returning documents or adding chunks to a retrieval result. Document-specific grants will be layered into this same policy when document ACL storage is added; role checks should not be reimplemented in routes or the frontend.

Run `python -m pytest -q` from `backend/` to check authentication and the full role/classification matrix. The suite should report 19 passing tests.

## Phase 4: document upload

Authenticated users can upload PDF, PNG, and JPEG files with `POST /api/documents` using `multipart/form-data` fields `file`, optional `title`, and optional `security_level` (default `PUBLIC`). The endpoint checks the extension and file signature, streams up to the configured size limit, stores content under a generated UUID filename, and saves document metadata plus a SHA-256 digest in SQLite. API responses never expose the local storage filename or path. Phase 5 now extracts the upload and records its processing status.

The default maximum is 10 MiB and can be changed with `MAX_UPLOAD_SIZE_BYTES` (up to 100 MiB). Files are stored in `backend/uploads/` by default. Students can classify uploads as public, faculty can classify public or internal, and only admins can classify confidential documents. `GET /api/documents` filters the database query to the caller's permitted levels; `GET /api/documents/{id}` returns 404 when a record is missing or inaccessible.

Try the upload from `/docs`: authorize with a student token, select a small PDF, and submit it with `security_level=PUBLIC`. To inspect only metadata, call `GET /api/documents`. The test suite covers public PDF and PNG upload, metadata visibility, access filtering, authentication, prohibited classification, spoofed files, and size limits. Run `python -m pytest -q`; the Phase 4 suite reported 26 passing tests.

## Phase 5: extraction and OCR

Uploads are extracted immediately after safe storage. PyMuPDF reads selectable PDF text; pages below the configured text threshold trigger a Tesseract OCR fallback. PNG and JPEG uploads are OCR'd directly. Text is Unicode-normalized and stored with one-based page numbers in `document_extractions`; the document record moves to `READY` or `PROCESSING_FAILED`. Failed extraction keeps the uploaded file and metadata, while returning a safe error code instead of a stack trace.

Install the Python extraction packages with `python -m pip install -r requirements.txt`. OCR also requires the Tesseract executable. On Windows, install Tesseract OCR and ensure `tesseract.exe` is on `PATH`; otherwise set `TESSERACT_CMD` in `backend/.env`. `OCR_LANGUAGES` defaults to `eng`; `MIN_EXTRACTED_TEXT_CHARS` defaults to `30` and controls scanned-PDF fallback.

Use `GET /api/documents/{id}/extraction` to inspect extracted text, page count, extraction method, and safe error code. This endpoint checks document access before returning the text. Expected methods are `pdf_text`, `pdf_ocr`, and `image_ocr`. A successful text PDF or OCR'd image reports `READY`; malformed or unreadable content reports `PROCESSING_FAILED` and an error such as `INVALID_PDF`, `OCR_UNAVAILABLE`, or `NO_TEXT_FOUND`.

From `backend/`, run `python -m pytest -q`. The Phase 5 suite reported 31 passing tests, including page-aware text extraction, scanned-PDF fallback, upload integration, and permission checks on extraction results.

## Phase 6: page-aware chunking

After extraction succeeds, uploads are split into reusable text chunks and stored in the `document_chunks` table. Chunking is performed separately for each source page, so a chunk never loses its page number or crosses a page boundary. The default maximum is 1,000 characters per chunk with 150 characters of overlap; split points prefer whitespace. Each chunk stores its generated ID, document ID and title, sequential index, page number, source type, security level, and uploader ID. This metadata is ready for the embedding and vector-search phases.

The protected `GET /api/documents/{id}/chunks` endpoint returns chunks only after checking access to the parent document. A missing or unauthorized document returns the same 404 response; callers cannot retrieve chunks by guessing an ID. Failed extraction or chunking does not produce a partially searchable chunk set.

No new dependency or database migration is needed for the local MVP. SQLAlchemy creates the new `document_chunks` table at startup; existing document and user records remain intact. To inspect the result in Swagger, authorize, upload a PDF, copy its returned `id`, then call `GET /api/documents/{id}/chunks`. Each response item includes `page_number`, `text`, and the source/security metadata. From `backend/`, run `python -m pytest -q`; the Phase 6 suite should report 38 passing tests, including chunk boundaries, overlap, metadata persistence, and access checks.

## Roadmap

1. Project foundation and health check — complete
2. Authentication and JWT — complete
3. Centralized RBAC and document access rules — complete
4. Secure upload and metadata persistence — complete
5. PDF extraction and OCR — complete
6. Page-aware chunking and metadata persistence — complete
7. Embeddings with sentence-transformers
8. FAISS vector search
9. Permission-filtered retrieval
10. Provider-independent grounded answers and citations
11. Audit logging and admin APIs
12. Frontend workflows and dashboard
13. Security and retrieval tests
14. Demo preparation

## Security direction

The backend is the authority for authentication and later access decisions. Retrieval will search only indexes the caller is allowed to access so unauthorized chunks cannot enter the model context. Development secrets and user credentials are supplied locally and never hardcoded. Public registration always assigns the least-privileged role; admin accounts require a separate controlled provisioning step in a later phase.
