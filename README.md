# VaultRAG — Secure Multi-Modal RAG with Role-Based Access Control

> **Professional Enterprise MVP / Hackathon Showcase**  
> *Zero-Leakage Retrieval-Augmented Generation with Physical Vector Partitioning, Anti-Hallucination Guarantees, Dynamic Reclassification, and Comprehensive Audit Governance.*

---

## 🛡️ Executive Summary & The Security Problem

Standard Retrieval-Augmented Generation (RAG) architectures suffer from a critical security flaw:  
**Naive Post-Retrieval Filtering.** In conventional systems, a user query vector is matched against all vectors in the global database. If confidential chunks match the query, the system attempts to strip them *after* retrieval or relies on LLM system prompts to hide unauthorized content. This creates severe security risks:
1. **Prompt Injection & Token Leakage**: Clever jailbreak prompts can compel the LLM to summarize unauthorized context already in its prompt.
2. **Side-Channel Information Disclosure**: Similarity scores, metadata logs, or vector distance calculations can confirm the existence of confidential projects.

### VaultRAG's Solution: Zero-Leakage Pre-Retrieval Partitioning
In **VaultRAG**, authorization occurs **strictly before and during retrieval**:
- The FAISS vector store is partitioned into physical, isolated sub-indices (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`).
- When a `STUDENT` queries the system, FAISS **only executes vector similarity search on the `PUBLIC` sub-index**. 
- `INTERNAL` and `CONFIDENTIAL` vectors are physically excluded from the search space.
- If no authorized document matches above the cosine threshold ($0.35$), the system **fails closed**:
  > *"The authorized documents do not contain enough information to answer this question."*
- Zero unauthorized chunks enter the model context. Zero ghost citations are ever generated.

---

## 🏛️ System Architecture

```
                                  +---------------------------------------+
                                  |       React 19 + Tailwind v4 UI       |
                                  |   (Dashboard, Chat, Docs, Admin, Logs)|
                                  +---------------------------------------+
                                                      |
                                                      |  HTTP / REST (JWT)
                                                      v
                                  +---------------------------------------+
                                  |       FastAPI Application Engine      |
                                  |  - Argon2id Password Hashing          |
                                  |  - Short-Lived JWT Verification       |
                                  |  - Centralized Access Control (RBAC)  |
                                  +---------------------------------------+
                                         /            |             \
                                        /             |              \
                                       v              v               v
                +-------------------------+  +-----------------+  +--------------------------+
                |    Document Pipeline    |  |  Audit Engine   |  |   Secure RAG Service     |
                |  - PyMuPDF Extraction   |  |  - Telemetry    |  |  - Question Embedding    |
                |  - OCR Fallback Engine  |  |  - Access Denied|  |  - Pre-Search RBAC Filter|
                |  - Page-Aware Chunking  |  |  - Role Changes |  |  - Anti-Hallucination    |
                +-------------------------+  +-----------------+  +--------------------------+
                             |                        |                        |
                             v                        v                        v
                +-------------------------+  +-----------------+  +--------------------------+
                |   SQLite / PostgreSQL   |  |  Audit Log DB   |  |  Partitioned FAISS Store |
                |  - Users & Roles        |  |  (secure_rag.db)|  |  - Index [PUBLIC]        |
                |  - Documents & Chunks   |  |                 |  |  - Index [INTERNAL]      |
                |  - Extractions & Hashes |  |                 |  |  - Index [CONFIDENTIAL]  |
                +-------------------------+  +-----------------+  +--------------------------+
```

---

## 👥 Access Control Matrix (RBAC)

| User Role | Permitted Security Levels | Direct Document Access | Vector Retrieval Scope |
| :--- | :--- | :--- | :--- |
| **`STUDENT`** | `PUBLIC` only | Can only view/download `PUBLIC` documents. Other documents return `404 Not Found`. | Searches **only** `PUBLIC` sub-index. Confidential queries fail closed with 0 citations. |
| **`FACULTY`** | `PUBLIC` + `INTERNAL` | Can view `PUBLIC` and `INTERNAL` documents. `CONFIDENTIAL` returns `404 Not Found`. | Searches `PUBLIC` and `INTERNAL` sub-indices. |
| **`ADMIN`** | `PUBLIC` + `INTERNAL` + `CONFIDENTIAL` | Full access. Can reclassify documents, modify user roles, and view all audit logs. | Searches all sub-indices (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`). |

---

## ⚡ Technology Stack

### Backend
- **Python 3.11+ / 3.14 compatible**
- **FastAPI**: Asynchronous high-performance REST APIs with strict Pydantic v2 schemas (`extra="forbid"`).
- **SQLAlchemy 2.0**: Relational ORM abstraction (SQLite for localhost demo; seamless PostgreSQL production migration).
- **Argon2id (`pwdlib`)**: State-of-the-art password hashing with random salting.
- **PyJWT**: Signed HMAC-SHA256 bearer tokens with short lifespans.

### AI & Vector Pipeline
- **`sentence-transformers` (`all-MiniLM-L6-v2`)**: 384-dimensional dense semantic embeddings with L2 normalization.
- **`faiss-cpu`**: High-performance vector similarity search using partitioned `IndexFlatIP` indices.
- **PyMuPDF (`fitz`)**: Fast, page-aware PDF text extraction and metadata preservation.
- **Multi-Modal OCR**: Image & scanned PDF fallback support.
- **Pluggable LLM Provider**:
  - `GeminiProvider`: Google Gemini 2.5 Flash integration.
  - `OpenAICompatibleProvider`: Local Ollama, vLLM, or OpenAI endpoints.
  - `LocalSynthesizerProvider`: **Zero-dependency offline synthesizer** guaranteeing 100% reliable hackathon demos without internet or API keys.

### Frontend
- **React 19 + TypeScript**: Modern component architecture with strict typing.
- **Vite 6**: Instant HMR development server and optimized rollup production bundling.
- **Tailwind CSS v4**: Dark enterprise cybersecurity UI styling with responsive layouts.
- **Lucide React**: Clean iconography for security badges, status indicators, and audit actions.

---

## 🚀 Quickstart & Localhost Setup

### 1. Prerequisites
- **Python 3.11** or newer (`py -3` / `python3`)
- **Node.js 20+** and `npm`

---

### 2. Backend Setup

Open a PowerShell terminal in the project root:

```powershell
# 1. Navigate to backend
cd backend

# 2. Create and activate Python virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install backend dependencies
python -m pip install -r requirements.txt

# 4. Initialize local environment secrets
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    $jwtSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
    (Get-Content .env) -replace '^JWT_SECRET_KEY=.*', "JWT_SECRET_KEY=$jwtSecret" | Set-Content .env
}

# 5. Run the Automated Demo Seed Script (Populates Users, Documents, Embeddings & Audit Logs)
python demo_seed.py

# 6. Start the FastAPI backend server
uvicorn app.main:app --reload --port 8000
```

> **Backend API URL**: `http://localhost:8000`  
> **Interactive Swagger Docs**: `http://localhost:8000/docs`  
> **API Health Check**: `http://localhost:8000/api/health`

---

### 3. Frontend Setup

Open a **second** terminal window:

```powershell
# 1. Navigate to frontend
cd frontend

# 2. Install Node dependencies
npm install

# 3. Configure frontend environment
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}

# 4. Start Vite development server
npm run dev
```

> **Frontend Application URL**: `http://localhost:5173`

---

## 🔑 Pre-Seeded Demo Credentials

The `demo_seed.py` script automatically configures 3 tiered user personas:

| Persona | Email | Password | Role | Permitted Access |
| :--- | :--- | :--- | :--- | :--- |
| **Student** | `student@example.com` | `StudentPass123!` | `STUDENT` | `PUBLIC` only |
| **Faculty** | `faculty@example.com` | `FacultyPass123!` | `FACULTY` | `PUBLIC` + `INTERNAL` |
| **Admin** | `admin@example.com` | `AdminPass123!` | `ADMIN` | `PUBLIC` + `INTERNAL` + `CONFIDENTIAL` |

---

## 📑 Pre-Seeded Multi-Page Documents

| Document Title | Security Level | Pages / Chunks | Key Grounded Content |
| :--- | :--- | :--- | :--- |
| **Undergraduate Student Handbook 2026** | `PUBLIC` | 3 pages (3 chunks) | - Mandatory 80% class attendance requirement<br>- Central library 24/7 hours during final exam periods<br>- Parking permits ($120/sem) and free 24/7 student health clinic |
| **Faculty Senate Operations & Guidelines** | `INTERNAL` | 3 pages (3 chunks) | - Tenured faculty sabbatical leave after 6 continuous semesters<br>- Internal competitive research grants up to $75,000<br>- Mandatory grade submission within 72 hours of finals |
| **Board of Trustees Executive Financial Plan** | `CONFIDENTIAL` | 3 pages (3 chunks) | - Emergency reserve endowment ($42.5M) for campus expansion<br>- Senior executive retention compensation pool ($4.8M)<br>- Project Silicon Annex: downtown commercial parcel acquisition ($18.0M) |

---

## 🎬 Step-by-Step Hackathon Demo Walkthrough

### Scenario 1: The Student Zero-Leakage & Anti-Hallucination Test
1. Log in as **Student** (`student@example.com` / `StudentPass123!`).
2. Navigate to **Secure AI Chat**.
3. **Ask a Confidential Question**:
   > *"What is the institutional emergency reserve endowment balance?"*
4. **Observe the Zero-Leakage Response**:
   - The system responds: *"The authorized documents do not contain enough information to answer this question."*
   - Citations badge displays `0 citations`.
   - The confidential financial document was **never searched or scored**.
5. **Ask an Authorized Public Question**:
   > *"What are the campus library operating hours and attendance rules?"*
6. **Observe the Grounded Response**:
   - Grounded answer detailing the 24/7 exam hours and the 80% attendance rule.
   - Interactive citation card links to **Undergraduate Student Handbook 2026** (Page 1 & 2, `PUBLIC`).

---

### Scenario 2: The Faculty Tiered Access Test
1. Switch user / log in as **Faculty** (`faculty@example.com` / `FacultyPass123!`).
2. In **Secure AI Chat**, ask:
   > *"How much research grant funding is available and when are final grades due?"*
3. **Observe the Internal Citation**:
   - Answer returns: *"The University Research Council awards competitive internal research grants of up to $75,000 per academic cycle... grades within 72 hours."*
   - Citations card confirms source is **Faculty Senate Operations & Research Guidelines** (`INTERNAL`).
4. Ask about confidential real estate:
   > *"What is the purchase price for Project Silicon Annex?"*
5. **Observe Immediate Denial**:
   - Fails closed with 0 citations; faculty cannot access Board of Trustees documents.

---

### Scenario 3: The Admin Full Clearance & Dynamic Reclassification Test
1. Log in as **Admin** (`admin@example.com` / `AdminPass123!`).
2. In **Secure AI Chat**, ask:
   > *"What is the emergency reserve endowment balance and the budget for Project Silicon Annex?"*
3. **Observe Confidential Retrieval**:
   - Grounded answer quotes the **$42.5M reserve endowment** and **$18.0M downtown acquisition**.
   - Citations card explicitly tags the source with a red **CONFIDENTIAL** security badge.
4. **Dynamic Reclassification**:
   - Navigate to **Documents** in the sidebar.
   - Find **Board of Trustees Executive Financial Plan 2026**.
   - Click the security level badge and change it from `CONFIDENTIAL` to `PUBLIC`.
   - *Under the hood*: The database updates, and the FAISS vector store seamlessly migrates the chunk vectors into the `PUBLIC` sub-index!
5. **Verify Student Access Now Granted**:
   - Log back in as **Student** (`student@example.com`).
   - Query again: *"What is the emergency reserve endowment balance?"*
   - The student now receives the full answer citing the document as `PUBLIC`!

---

### Scenario 4: Admin Dashboard & Audit Log Governance
1. Log in as **Admin** (`admin@example.com`).
2. Navigate to **Admin Console**:
   - Inspect live metrics: Total Users, Total Documents, Document Distribution by Security Level, Successful Accesses, and Denied Accesses.
   - View User Management table: Elevate students to faculty or deactivate compromised accounts in real-time.
3. Navigate to **Audit Logs**:
   - Inspect the chronological, tamper-evident security audit trail.
   - Filter by Action (`ACCESS_DENIED`, `DOCUMENT_QUERY`, `DOCUMENT_UPLOAD`, `DOCUMENT_CLASSIFY`).
   - Observe how the earlier student queries for confidential data were logged as `ACCESS_DENIED` with full query details and timestamps.

---

## 🧪 Comprehensive Verification Suite

### Backend Test Suite (75/75 Passed)
The backend test suite covers isolated unit tests, access-control matrices, vector partitioning, BM25 lexical ranking, RRF fusion, RAG citation grounding, and end-to-end multi-role integration tests.

```powershell
backend/.venv/Scripts/python.exe -m pytest -v
```

```
====================== 75 passed in 17.27s =======================
backend/tests/test_access_control.py ..............                      [ 18%]
backend/tests/test_audit_and_admin.py .....                              [ 25%]
backend/tests/test_auth.py .....                                         [ 32%]
backend/tests/test_chunking_service.py ......                            [ 40%]
backend/tests/test_document_extraction.py ....                           [ 45%]
backend/tests/test_documents.py .........                                [ 57%]
backend/tests/test_embedding_service.py ....                             [ 62%]
backend/tests/test_hybrid_search.py .....                                [ 69%]
backend/tests/test_rag_service.py ......                                 [ 77%]
backend/tests/test_secure_retrieval.py ......                            [ 85%]
backend/tests/test_security_e2e.py .......                               [ 94%]
backend/tests/test_vector_store.py ....                                  [100%]
```

### Frontend Build Verification
```powershell
cd frontend
npm run build
```

```
✓ 1589 modules transformed.
dist/index.html                   0.54 kB
dist/assets/index-BqYr1D4I.css   36.17 kB
dist/assets/index-B60BHre1.js   284.56 kB
✓ built in 2.18s
```

---

## 📋 Complete 15-Phase Implementation Summary

| Phase | Milestone | Core Implementation |
| :---: | :--- | :--- |
| **1** | **Foundation & Health** | FastAPI REST application, SQLite engine, CORS configuration, `/api/health`. |
| **2** | **Authentication & JWT** | Argon2id password hashing, PyJWT tokens, protected `/api/auth/me`. |
| **3** | **Centralized RBAC** | Single-source-of-truth access control service (`STUDENT`, `FACULTY`, `ADMIN`). |
| **4** | **Document Uploads** | Streaming upload validation, magic byte checks, SHA-256 digests, safe UUID storage. |
| **5** | **Extraction & OCR** | PyMuPDF page-aware extraction with automatic Tesseract OCR fallback. |
| **6** | **Page-Aware Chunking** | Strict page boundary preservation (max 1000 chars, 150 overlap) with security metadata. |
| **7** | **Embeddings Service** | Sentence-transformers `all-MiniLM-L6-v2` generating 384d L2-normalized dense vectors. |
| **8** | **FAISS Vector Store** | Security-partitioned `IndexFlatIP` indices with metadata persistence. |
| **9** | **Secure Retrieval** | Pre-retrieval authorization filtering with zero unauthorized chunk exposure. |
| **10** | **RAG & Citations** | Multi-provider LLM abstraction, anti-hallucination prompts, verified citation cards. |
| **11** | **Audit & Admin APIs** | Event logging, `/api/admin/stats`, user role management, document reclassification. |
| **12** | **Frontend SaaS UI** | React 19 + Tailwind v4 dark enterprise interface with sidebar, chat, and admin views. |
| **13** | **Security E2E Tests** | 7 end-to-end integration tests verifying cross-role isolation, cascading deletions, and token security. |
| **14** | **Demo Prep & Seed** | Automated `demo_seed.py` script, realistic multi-page demo documents, and turn-key walkthrough. |
| **15** | **Hybrid Search (BM25 + RRF)** | Partitioned BM25Okapi lexical retrieval fused with dense FAISS vectors via Reciprocal Rank Fusion. |

---

## 🔒 Security Best Practices Summary

- **Fail-Closed by Design**: Unauthenticated callers, inactive accounts, unknown roles, or missing permissions fail closed immediately.
- **Existence Masking**: Unauthorized documents return `404 Not Found` rather than `403 Forbidden` to prevent resource probing.
- **No Token Role Trust**: User roles are retrieved from the database per request, ensuring immediate effect of administrative promotions or deactivations.
- **Zero Sensitive Exposure**: Passwords, API keys, JWT secrets, stored filenames, and internal storage paths are never exposed in API outputs or logs.
- **Physical Vector Partitioning**: Unauthorized chunks are never searched, eliminating LLM prompt leakage vectors.

---

## 📄 License
MIT License. Built for secure enterprise document knowledge and hackathon presentation.
