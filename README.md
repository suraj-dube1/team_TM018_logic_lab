# Logic Labs — Secure University Multi-Modal RAG

This hackathon build demonstrates data-level authorization with PostgreSQL RLS.
The demo corpus is synthetic and modeled after the structure of the uploaded student marks statement and Division BW timetable screenshot.

## Demo login IDs
- Students: `<handle>@student`
- Faculty Members: `<handle>@faculty`
- Admin: `arjun@admin` (admin self-signup is disabled)

## Student privacy
Student result PDFs are owner-bound and enforced by PostgreSQL RLS. A student can retrieve their own result; another student cannot. Admins can retrieve all authorized records.

## Sign up
The login screen supports self-service Student and Faculty Member registration. The server generates the role suffix and stores a PBKDF2 password hash.

## Dataset
See `dataset/DATASET_README.md` and `dataset/UPLOAD_MANIFEST.csv`. All student names, marks, IDs, faculty names and results are synthetic demo data.

## Run
1. Create `backend/.env` from `.env.local.example`.
2. Set `ADMIN_DB_URL` to your Neon connection string.
3. Run `python generate_secret.py`.
4. Run `python setup_db.py`.
5. Run `python -m app.seed`.
6. Run `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
7. Open `http://127.0.0.1:8000`.
