"""Seed the Logic Labs university demo corpus shipped in ../../dataset."""
import csv
import os
from pathlib import Path

from .db import admin_conn
from .ingest import ingest_csv_file, ingest_file

BASE = Path(__file__).resolve().parents[2]
DATASET = Path(os.getenv("DEMO_DATASET_DIR", str(BASE / "dataset")))

PUBLIC = (0, [], None)
FACULTY = (2, ["eng"], None)
ADMIN = (3, [], None)

# Student result PDFs are owner-only. The username is derived from the file name.


def iter_entries():
    for p in sorted((DATASET / "pdfs").glob("*.pdf")):
        if p.name.startswith("RESULT_"):
            slug = p.stem.split("_")[-1]
            yield p.name, (0, ["student"], f"{slug}@student")
        elif p.name.startswith("TIMETABLE_"):
            parts = p.stem.split("_")
            slug = parts[-1]
            yield p.name, (0, ["student"], f"{slug}@student")
        elif p.name.startswith("FACULTY_TIMETABLE_"):
            slug = p.stem.replace("FACULTY_TIMETABLE_", "")
            yield p.name, (2, ["eng"], f"{slug}@faculty")
        elif p.name == "18_Faculty_Timetable_SemV_CSE.pdf":
            yield p.name, FACULTY
        elif p.name == "17_Student_Timetable_SemV_DivBW.pdf":
            yield p.name, PUBLIC

    for p in sorted((DATASET / "csv").glob("*.csv")):
        if p.name == "course_catalog.csv":
            yield p.name, PUBLIC
        elif p.name == "faculty_accounts.csv":
            yield p.name, FACULTY
        elif p.name == "student_directory_21.csv":
            yield p.name, ADMIN
        elif p.name == "students_21.csv":
            # account list, not knowledge; don't ingest it into RAG
            continue


def seed(force=False):
    if not DATASET.exists():
        print(f"Logic Labs demo dataset not found: {DATASET}")
        return False

    with admin_conn() as conn:
        has_documents = bool(conn.execute("SELECT count(*) AS n FROM documents").fetchone()["n"])
        if has_documents and not force:
            return False
        if force:
            conn.execute("TRUNCATE documents, chunks, canaries, audit_log RESTART IDENTITY CASCADE")

    os.makedirs(os.getenv("DATA_DIR", str(BASE / "data")), exist_ok=True)
    loaded = skipped = 0
    for name, (clearance, departments, owner) in iter_entries():
        subdir = "csv" if name.endswith(".csv") else "pdfs"
        path = DATASET / subdir / name
        if not path.exists():
            skipped += 1
            print(f"skip missing demo file: {path}")
            continue
        title = path.stem.replace("_", " ").strip()
        try:
            if path.suffix.lower() == ".csv":
                ingest_csv_file(str(path), title, clearance, departments, owner_username=owner)
            else:
                ingest_file(str(path), title, clearance, departments, owner_username=owner)
            loaded += 1
        except Exception as exc:
            skipped += 1
            print(f"skip {name}: {exc}")

    # OCR receipt is intentionally handled through the Admin upload flow to demonstrate live ingestion.
    print(f"Logic Labs university corpus seeded: {loaded} files loaded, {skipped} skipped.")
    return loaded > 0


if __name__ == "__main__":
    print("seeded" if seed(force=True) else "already seeded / unavailable")
