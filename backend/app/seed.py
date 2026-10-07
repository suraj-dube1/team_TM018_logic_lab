"""Synthetic company data: PDFs, scanned-style images and DB rows, each with its own ACL."""
import os

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .db import admin_conn
from .ingest import ingest_file, ingest_records

DATA = os.getenv("DATA_DIR", "data")
DOCS = os.path.join(DATA, "docs")
FONT = next((f for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf",
             "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"] if os.path.exists(f)), "")


def make_pdf(name, title, paras):
    path = os.path.join(DOCS, name)
    st = getSampleStyleSheet()
    story = [Paragraph(title, st["Title"]), Spacer(1, 12)]
    for p in paras:
        story += [Paragraph(p, st["BodyText"]), Spacer(1, 10)]
    SimpleDocTemplate(path, pagesize=A4).build(story)
    return path


def make_image(name, lines):
    path = os.path.join(DOCS, name)
    f = ImageFont.truetype(FONT, 30) if FONT else ImageFont.load_default()
    img = Image.new("RGB", (1000, 120 + 52 * len(lines)), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((50, 50 + 52 * i), line, fill="black", font=f)
    img.save(path)
    return path


def seed(force=False):
    with admin_conn() as conn:
        if conn.execute("SELECT count(*) AS n FROM documents").fetchone()["n"] and not force:
            return False
        if force:
            conn.execute("TRUNCATE documents, chunks, canaries, audit_log RESTART IDENTITY CASCADE")
    os.makedirs(DOCS, exist_ok=True)

    # ---- PDFs ----------------------------------------------------------------
    p = make_pdf("handbook.pdf", "Employee Handbook", [
        "Working hours are 9:30 to 18:30, Monday to Friday. Employees receive 24 days of paid leave each year.",
        "The office is located at 4th Floor, Kalawad Road, Rajkot. Guest Wi-Fi is available in the lobby.",
        "Expense claims must be submitted within 30 days with the original receipt attached.",
        "Public holidays follow the Gujarat state calendar. Remote work needs written manager approval.",
    ])
    ingest_file(p, "Employee Handbook", 0, [])

    p = make_pdf("eng_roadmap.pdf", "Engineering Roadmap Q4", [
        "Project Falcon, our new search backend, launches on 14 November. The migration team has 6 engineers.",
        "The infrastructure budget for Q4 is Rs. 12,50,000. Priority one is reducing p95 latency below 200 ms.",
        "The mobile app rewrite is planned for Q1 next year and is not yet staffed.",
    ])
    ingest_file(p, "Engineering Roadmap Q4", 1, ["eng"], ["Project Falcon"])

    p = make_pdf("finance_q3.pdf", "Q3 Financial Review", [
        "Q3 revenue was Rs. 48.2 crore, up 14 percent over Q2. Operating burn was Rs. 6.4 crore.",
        "Cash runway stands at 19 months. Vendor payments are settled on a net 45 day cycle.",
    ])
    ingest_file(p, "Q3 Financial Review", 2, ["finance"], ["Rs. 48.2 crore", "Rs. 6.4 crore"])

    p = make_pdf("hr_salary_bands.pdf", "Compensation Bands", [
        "Band L5 covers Senior Engineers with annual pay from Rs. 24,00,000 to Rs. 32,00,000.",
        "Band L7 covers Directors with annual pay from Rs. 70,00,000 to Rs. 95,00,000.",
        "Interns receive a monthly stipend of Rs. 25,000. Bonus pool this year is 8 percent of base pay.",
    ])
    ingest_file(p, "Compensation Bands", 2, ["hr"], ["Band L7", "Rs. 70,00,000"])

    p = make_pdf("legal_memo.pdf", "Privileged Legal Memo", [
        "Zephyr Logistics has filed a breach of contract claim against the company in the Gujarat High Court.",
        "Counsel recommends settling for Rs. 3.1 crore before the hearing on 3 December.",
        "This memo is attorney client privileged and restricted to the legal team and executives.",
    ])
    ingest_file(p, "Privileged Legal Memo", 3, ["legal"], ["Zephyr Logistics", "Rs. 3.1 crore"])

    p = make_pdf("project_midnight.pdf", "Project Midnight Board Brief", [
        "Project Midnight is the proposed acquisition of Nimbus Labs, a Bengaluru AI startup.",
        "The board has approved an offer of Rs. 210 crore, payable 60 percent in cash and 40 percent in shares.",
        "Announcement is scheduled for January. Staff must not be informed before signing.",
    ])
    ingest_file(p, "Project Midnight Board Brief", 3, ["exec"], ["Project Midnight", "Nimbus Labs", "Rs. 210 crore"])

    # ---- Scanned images (OCR) ------------------------------------------------
    def try_image(path, *a, **k):
        try:
            ingest_file(path, *a, **k)
        except Exception as e:
            print(f"skipped image {os.path.basename(path)} (install Tesseract to enable OCR): {e}")

    img = make_image("receipt_supplies.png", [
        "SHREE STATIONERS, RAJKOT", "Invoice 8841   Date 12 Sep", "Printer paper A4 x 20   Rs. 6,400",
        "Whiteboard markers x 40   Rs. 2,050", "TOTAL   Rs. 8,450", "Paid by company card",
    ])
    try_image(img, "Receipt: Office Supplies", 1, ["finance"])

    img = make_image("receipt_offsite.png", [
        "AURORA PALACE RESORT, UDAIPUR", "Invoice 20931   Date 21 Sep", "Executive offsite, 12 rooms   Rs. 6,40,000",
        "Banquet and events   Rs. 3,40,000", "TOTAL   Rs. 9,80,000", "Billed to the CEO office",
    ])
    try_image(img, "Receipt: Executive Offsite", 3, ["exec"], ["Aurora Palace Resort", "9,80,000"])

    # ---- Structured DB rows, ACL differs per table ----------------------------
    people = [
        (1, "Asha Mehta", "Senior Engineer", "Engineering", "asha@acme.example", "2,800,000", "2,10,000"),
        (2, "Rohan Shah", "Finance Analyst", "Finance", "rohan@acme.example", "1,400,000", "90,000"),
        (3, "Kavya Iyer", "HR Partner", "HR", "kavya@acme.example", "1,650,000", "1,10,000"),
        (4, "Dev Patel", "Counsel", "Legal", "dev@acme.example", "3,200,000", "2,50,000"),
    ]
    ingest_records("Employee Directory", "employees", [
        (r[0], f"Employee directory entry: {r[1]} is a {r[2]} in the {r[3]} department. Email {r[4]}.") for r in people
    ], 0, [])
    ingest_records("Compensation Records", "compensation", [
        (r[0], f"Compensation record: {r[1]}, {r[2]}, annual salary Rs. {r5(r[5])}, last bonus Rs. {r[6]}.")
        for r in people
    ], 2, ["hr"], ["Rs. 28,00,000", "Rs. 14,00,000", "Rs. 16,50,000", "Rs. 32,00,000"])
    return True


def r5(s):
    """2,800,000 -> 28,00,000 (Indian digit grouping)"""
    n = int(s.replace(",", ""))
    head, tail = str(n)[:-3], str(n)[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


if __name__ == "__main__":
    print("seeded" if seed(force=True) else "already seeded")
