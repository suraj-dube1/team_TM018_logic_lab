# VaultRAG: secure multi-modal RAG with access control (Code Carnival 3.0, PS-01)

The vault enforces access, not the app. Every chunk carries an ACL, and Postgres Row-Level Security
filters rows **inside the retrieval query**, before ranking. A chunk the user may not see is never
retrieved, never reaches the LLM, and cannot leak through a prompt injection.

## Run it (5 minutes)
```bash
cp .env.example .env
# Option A, no LLM (works offline, answers are cited verbatim sentences):  LLM_PROVIDER=none
# Option B, Ollama on your laptop:  ollama pull qwen2.5:3b-instruct   (keep LLM_PROVIDER=ollama)
# Option C, OpenRouter: LLM_PROVIDER=openrouter and put OPENROUTER_API_KEY in .env
# Option D, Claude API: LLM_PROVIDER=anthropic and put ANTHROPIC_API_KEY in .env
docker compose up --build
# open http://localhost:8000   (synthetic data is seeded automatically on first start)
```
Reset everything: `docker compose down -v && rm -rf data`.

## Run without Docker (free cloud database, about 400 MB on disk)
1. Create a free Postgres at neon.tech (pgvector is built in) and copy its connection string.
2. In the `backend` folder: `copy ..\.env.local.example .env` and paste the string as `ADMIN_DB_URL`. Keep pooling off for this app connection and remove `&channel_binding=require` if your copied URL contains it.
3. `python -m venv venv`, then `venv\Scripts\activate`, then `pip install -r requirements.txt`.
4. `python setup_db.py` (creates/migrates tables, RLS policies, password hashes and the restricted app role; safe to rerun).
5. `uvicorn app.main:app --port 8000`, then open http://localhost:8000.
6. From the same `backend` directory, run `python smoke_test.py` after the server is up. It checks password login, persona/RLS outcomes, the red team, and—when `APP_DB_URL` is present—the fail-closed RLS behavior.
OCR of the two receipt images needs Tesseract (optional, about 70 MB); without it they are skipped and everything else works.

## How it meets the problem statement
| Requirement | Where |
|---|---|
| Mixed data: PDFs, images (OCR), DB records | `ingest.py`: pdfplumber text layer, Tesseract OCR for images and scanned pages, DB rows as one chunk each |
| Unified vector + metadata index | `chunks` table: pgvector embedding + tsvector + source, page, bbox, ACL columns |
| Access control at the retrieval layer | `schema.sql`: RLS policies, app connects as non-superuser `vault_app`, fail-closed when no session settings |
| Exact citations for every claim | `llm.py` returns claim-by-claim JSON with source ids; click a chip to see the page with the cited region highlighted |
| Hallucination grounding | `verify.py`: a claim is dropped unless it cites a chunk, every number appears in that chunk, and enough content words match |
| Hybrid retrieval | `retrieval.py`: vector + keyword, fused with RRF, one SQL statement |

Access model: `min_clearance` (0-3) plus `departments` (empty = all). Users: Intern (0), Manager (2, eng+finance), Admin (3, all).
A user sees a chunk only if clearance is high enough **and** the department matches, so the Manager can read Q3 finance but not HR salaries.

## Demo login

The UI now requires a password. Default demo credentials are:

| Username | Password | Persona |
|---|---|---|
| intern | `intern123` | Intern |
| manager | `manager123` | Manager |
| admin | `admin123` | Admin |

Change these before showing the app publicly. Passwords are stored as PBKDF2-HMAC-SHA256 hashes with per-user salts; the password is never stored in browser storage.

## Demo script (3 minutes)
1. Click **Intern**, ask "What is Project Midnight?" -> nothing found, counter shows chunks blocked.
2. Ask "What is Asha Mehta's salary?" as Intern, Manager, then Admin. Same DB rows, three outcomes (directory only vs. salary).
3. Type any question and press **Ask as all three**: side-by-side answers.
4. Click a citation chip: the exact PDF page / scanned receipt opens with the cited region boxed in red.
5. As Intern press **Run red team**: 12 prompt-injection and "I'm the admin" attacks, leak counter stays at 0.
6. As Admin, open the admin panel and ingest a new PDF/image/text/CSV live with its own clearance and departments. CSV rows become database-style chunks.

## Honest limits (say these to the judges before they ask)
- Demo login uses PBKDF2 password verification plus short-lived HMAC-signed bearer tokens. In production plug in SSO/JWT; the RLS layer stays identical.
- The "blocked chunks" counter and **Ask as all three** are demo features (`SHOW_BLOCKED_COUNT`, `DEMO_MODE`). Turn both off in production; the counter runs one unrestricted query and returns only a number.
- The verifier is lexical + numeric grounding, not full entailment checking. A natural next step is an NLI or LLM-judge pass.
- Metadata leaks through the answer text are possible if you cite visible chunks that mention hidden things; RLS guarantees only what the DB returns.
- Add an HNSW index and `hnsw.iterative_scan = relaxed_order` once the corpus is large (see note in `schema.sql`).
- OpenRouter uses its OpenAI-compatible `/api/v1/chat/completions` endpoint when `LLM_PROVIDER=openrouter`; `openrouter/free` is the default router and can be replaced with a specific model in `.env`.

## Layout
```
backend/app/  schema.sql  db.py  ingest.py  retrieval.py  llm.py  verify.py  qa.py  redteam.py  seed.py  main.py  static/index.html
```
