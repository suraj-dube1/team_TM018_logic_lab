"""Multi-modal ingestion: PDFs (text layer, OCR fallback), images (OCR), DB records, plain text.
Every chunk stores its source, page, bounding box and ACL so answers can cite exact regions."""
import csv
import os
import re

import pdfplumber
import pypdfium2 as pdfium
import pytesseract
from PIL import Image
from pytesseract import Output

from .db import admin_conn
from .embed import embed_docs

if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

MAX_WORDS, STEP = 80, 60


def _window(words, page):
    out, i = [], 0
    while i < len(words):
        w = words[i:i + MAX_WORDS]
        out.append({
            "page": page,
            "text": " ".join(x["t"] for x in w),
            "bbox": [min(x["x0"] for x in w), min(x["y0"] for x in w),
                     max(x["x1"] for x in w), max(x["y1"] for x in w)],
        })
        if i + MAX_WORDS >= len(words):
            break
        i += STEP
    return out


def _ocr_words(img):
    img = img.convert("RGB")
    W, H = img.size
    d = pytesseract.image_to_data(img, output_type=Output.DICT)
    words = []
    for t, l, tp, w, h, c in zip(d["text"], d["left"], d["top"], d["width"], d["height"], d["conf"]):
        if t.strip() and float(c) > 40:
            words.append({"t": t.strip(), "x0": l / W, "y0": tp / H, "x1": (l + w) / W, "y1": (tp + h) / H})
    return words


def extract(path):
    ext = os.path.splitext(path)[1].lower()
    chunks = []
    if ext == ".pdf":
        with pdfplumber.open(path) as pdf:
            for pno, page in enumerate(pdf.pages, start=1):
                W, H = float(page.width), float(page.height)
                words = [{"t": w["text"], "x0": w["x0"] / W, "y0": w["top"] / H,
                          "x1": w["x1"] / W, "y1": w["bottom"] / H} for w in page.extract_words()]
                if len(words) < 5:  # scanned page -> OCR
                    pdoc = pdfium.PdfDocument(path)
                    words = _ocr_words(pdoc[pno - 1].render(scale=2).to_pil())
                    pdoc.close()
                chunks += _window(words, pno)
        return "pdf", chunks
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        return "image", _window(_ocr_words(Image.open(path)), 1)
    text = open(path, encoding="utf-8", errors="ignore").read()
    words = [{"t": t, "x0": 0, "y0": 0, "x1": 1, "y1": 1} for t in text.split()]
    return "text", _window(words, 1)


def _store(title, kind, path, clearance, depts, items, canaries, owner_username=None):
    """items: list of dicts(page, text, bbox, source). Returns doc id."""
    vecs = embed_docs([i["text"] for i in items])
    with admin_conn() as conn:
        doc_id = conn.execute(
            "INSERT INTO documents(title, kind, path, min_clearance, departments, owner_username) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (title, kind, path, clearance, list(depts), owner_username),
        ).fetchone()["id"]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks(doc_id, source, kind, page, bbox, text, embedding, min_clearance, departments, owner_username) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(doc_id, i["source"], kind, i.get("page", 1), i.get("bbox"), i["text"], v, clearance, list(depts), owner_username)
                 for i, v in zip(items, vecs)],
            )
        for tok in canaries or []:
            conn.execute("INSERT INTO canaries(doc_id, token) VALUES (%s,%s)", (doc_id, tok))
    return doc_id


def ingest_file(path, title, clearance, depts, canaries=None, owner_username=None):
    kind, chunks = extract(path)
    for c in chunks:
        c["source"] = f"{title}, p.{c['page']}" if kind == "pdf" else title
    if not chunks:
        raise ValueError("no text could be extracted from this file")
    return _store(title, kind, path, clearance, depts, chunks, canaries, owner_username)


def ingest_csv_file(path, title, clearance, depts, canaries=None, owner_username=None):
    """Ingest a CSV as database-style records: one searchable/citable chunk per row.

    Preferred columns are `id` and one of `text`, `content`, `record`, `description`.
    If no text column exists, every column is joined into a readable record.
    """
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV needs a header row")
        fields = [x.strip() for x in reader.fieldnames if x and x.strip()]
        lower = {x.lower(): x for x in fields}
        text_key = next((lower[k] for k in ("text", "content", "record", "description", "data") if k in lower), None)
        id_key = next((lower[k] for k in ("id", "record_id", "key") if k in lower), None)
        records = []
        for n, row in enumerate(reader, 1):
            rid = (row.get(id_key, "") or "").strip() if id_key else str(n)
            if text_key:
                text = (row.get(text_key, "") or "").strip()
            else:
                text = "; ".join(f"{k}: {(row.get(k, '') or '').strip()}" for k in fields if (row.get(k, '') or '').strip())
            if text:
                records.append((rid or str(n), re.sub(r"\s+", " ", text)))
        if not records:
            raise ValueError("CSV contains no non-empty records")
        doc_id = ingest_records(title, "csv_records", records, clearance, depts, canaries, owner_username)
        return doc_id, len(records)


def ingest_records(title, table, records, clearance, depts, canaries=None, owner_username=None):
    """Structured DB rows: one chunk per row, citable as db:<table>#<row id>."""
    items = [{"text": re.sub(r"\s+", " ", txt), "source": f"db:{table}#{rid}", "page": 1, "bbox": None}
             for rid, txt in records]
    return _store(title, "db", None, clearance, depts, items, canaries, owner_username)
