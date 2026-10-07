# Logic Labs — Hackathon Setup

## 1. Windows
Open PowerShell in the project root and run `.\SETUP_WINDOWS.ps1`.

If it says `ADMIN_DB_URL` is still needed, open `backend/.env` and put your Neon direct/unpooled connection string there. Do not commit `.env`.

## 2. Database
Run `python setup_db.py`. This migrates the existing schema, creates owner-aware RLS, and seeds the demo accounts.

## 3. Corpus
Run `python -m app.seed` once. This replaces the old demo corpus with the university synthetic corpus.

## 4. Start
`uvicorn app.main:app --host 127.0.0.1 --port 8000`

## Demo accounts
Student: `rahul@student` / `Student@123`
Faculty Member: `neha@faculty` / `Faculty@123`
Admin: `arjun@admin` / `Admin@123`
Other synthetic student accounts are documented in `DEMO_CREDENTIALS.md`.

## Self signup
The login page has **Create a new account**. Choose Student or Faculty Member; Admin signup is disabled.

## Privacy demo
Student result and timetable PDFs are owner-bound. Student A can retrieve Student A's records; Student B cannot. Admin can retrieve all authorized student records.
