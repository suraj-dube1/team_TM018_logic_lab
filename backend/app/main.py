import io
import os
import threading
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageDraw
import pypdfium2 as pdfium
from pydantic import BaseModel

from . import qa, redteam
from .auth import make_token, normalize_handle, normalize_login_id, role_from_login_id, verify_password, hash_password, verify_token
from .db import admin_conn, user_conn
from .ingest import ingest_file

app = FastAPI(title="Logic Labs")
SECRET = os.getenv("SECRET_KEY", "change-me").encode()
HERE = os.path.dirname(__file__)

ROLE_META = {
    "student": ("Student", "Student access"),
    "faculty": ("Faculty Member", "Faculty access"),
    "admin": ("Admin", "Administrator"),
}


def public_user(user):
    username = str(user["username"]).strip().lower()
    clearance = int(user["clearance"] or 0)
    role = str(user.get("role") or "").strip().lower() if hasattr(user, "get") else ""
    if role not in ROLE_META:
        role = role_from_login_id(username)
    role_name, role_description = ROLE_META[role]
    return {
        "username": username,
        "login_id": username,
        "display": user["display"],
        "role": role,
        "role_name": role_name,
        "role_description": role_description,
        "clearance": clearance,
        "departments": user["departments"] or [],
    }


def _token_from_request(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.query_params.get("token", "")


def current_user(request: Request):
    name = verify_token(_token_from_request(request), SECRET)
    if not name:
        raise HTTPException(401, "invalid or expired token")
    with admin_conn() as conn:
        u = conn.execute(
            "SELECT username, display, role, clearance, departments FROM users WHERE username=%s",
            (name,),
        ).fetchone()
    if not u:
        raise HTTPException(401, "unknown user")
    return public_user(u)


@app.on_event("startup")
def _startup():
    if os.getenv("AUTO_SEED", "1") == "1":
        from .seed import seed
        threading.Thread(target=seed, daemon=True).start()


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


@app.get("/api/users")
def users():
    with admin_conn() as conn:
        rows = conn.execute(
            "SELECT username, display, role, clearance, departments FROM users ORDER BY clearance"
        ).fetchall()
    return [public_user(row) for row in rows]


class Login(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(body: Login):
    try:
        login_id = normalize_login_id(body.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if not body.password:
        raise HTTPException(400, "password is required")

    expected_role = role_from_login_id(login_id)
    with admin_conn() as conn:
        u = conn.execute(
            """
            SELECT username, display, role, clearance, departments, password_hash, password_salt
            FROM users
            WHERE username=%s
            """,
            (login_id,),
        ).fetchone()

    if not u:
        raise HTTPException(401, "unknown login ID or password")

    actual_role = str(u["role"] or "").lower()
    if actual_role and actual_role != expected_role:
        raise HTTPException(401, "login ID role does not match the account")

    if not verify_password(body.password, u["password_hash"], u["password_salt"]):
        raise HTTPException(401, "unknown login ID or password")

    return {
        "token": make_token(login_id, SECRET),
        "user": public_user(u),
    }




class Signup(BaseModel):
    full_name: str
    handle: str
    role: str
    password: str
    password_confirm: str


@app.post("/api/signup")
def signup(body: Signup):
    role = str(body.role or "").strip().lower()
    if role not in {"student", "faculty"}:
        raise HTTPException(400, "Only Student or Faculty Member registration is available")
    full_name = " ".join((body.full_name or "").split())
    if len(full_name) < 3 or len(full_name) > 80:
        raise HTTPException(400, "Enter a valid full name")
    try:
        handle = normalize_handle(body.handle)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if body.password != body.password_confirm:
        raise HTTPException(400, "Passwords do not match")
    try:
        password_hash, password_salt = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    login_id = f"{handle}@{role}"
    clearance = 0 if role == "student" else 2
    departments = ["student"] if role == "student" else ["eng"]
    with admin_conn() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE username=%s", (login_id,)).fetchone()
        if exists:
            raise HTTPException(409, "That login ID is already registered")
        row = conn.execute(
            """INSERT INTO users(username, display, role, clearance, departments, password_hash, password_salt)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               RETURNING username, display, role, clearance, departments""",
            (login_id, full_name, role, clearance, departments, password_hash, password_salt),
        ).fetchone()
    safe = public_user(row)
    return {"token": make_token(login_id, SECRET), "user": safe}


@app.post("/api/logout")
def logout():
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


class Ask(BaseModel):
    question: str


def _public(res):
    if isinstance(res, dict):
        res.pop("_retrieved_text", None)
    return res


@app.post("/api/ask")
def ask(body: Ask, user=Depends(current_user)):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "empty question")
    return _public(qa.run(user, question))


@app.post("/api/compare")
def compare(body: Ask, user=Depends(current_user)):
    if os.getenv("DEMO_MODE", "1") != "1":
        raise HTTPException(403, "demo mode is off")
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "empty question")

    with admin_conn() as conn:
        rows = conn.execute(
            "SELECT username, display, role, clearance, departments FROM users ORDER BY clearance"
        ).fetchall()

    results = []
    for row in rows:
        safe = public_user(row)
        answer = _public(qa.run(safe, question))
        results.append({**answer, **safe})
    return results


@app.post("/api/redteam")
def red_team(user=Depends(current_user)):
    return redteam.run(user)


def _chunk(user, cid):
    with user_conn(user) as conn:
        return conn.execute(
            """
            SELECT c.id, c.source, c.kind, c.page, c.bbox, c.text, d.title, d.path
            FROM chunks c JOIN documents d ON d.id=c.doc_id WHERE c.id=%s
            """,
            (cid,),
        ).fetchone()


@app.get("/api/chunk/{cid}")
def chunk(cid: int, user=Depends(current_user)):
    ch = _chunk(user, cid)
    if not ch:
        raise HTTPException(404, "not found")
    ch.pop("path", None)
    return ch


@app.get("/api/chunk/{cid}/image")
def chunk_image(cid: int, user=Depends(current_user)):
    ch = _chunk(user, cid)
    if not ch or ch["kind"] not in ("pdf", "image") or not ch["path"]:
        raise HTTPException(404, "not found")
    if ch["kind"] == "pdf":
        pdf = pdfium.PdfDocument(ch["path"])
        try:
            page_index = max(0, int(ch["page"] or 1) - 1)
            img = pdf[page_index].render(scale=1.6).to_pil().convert("RGBA")
        finally:
            pdf.close()
    else:
        img = Image.open(ch["path"]).convert("RGBA")
    if ch["bbox"]:
        W, H = img.size
        x0, y0, x1, y1 = ch["bbox"]
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(ov).rectangle(
            [x0 * W - 4, y0 * H - 4, x1 * W + 4, y1 * H + 4],
            fill=(209, 32, 47, 55), outline=(209, 32, 47, 255), width=4,
        )
        img = Image.alpha_composite(img, ov)
    img.thumbnail((1000, 1400))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    title: str = Form(...),
    clearance: int = Form(0),
    departments: str = Form(""),
    owner_username: str = Form(""),
    user=Depends(current_user),
):
    if user["clearance"] < 3:
        raise HTTPException(403, "only admins can ingest documents")
    name = os.path.basename(file.filename or "")
    ext = os.path.splitext(name)[1].lower()
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".txt", ".md", ".csv"}
    if ext not in allowed:
        raise HTTPException(415, "unsupported file type")
    if not title.strip():
        raise HTTPException(400, "document title is required")

    max_bytes = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
    data_dir = os.getenv("DATA_DIR", "data")
    docs_dir = os.path.join(data_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    path = os.path.join(docs_dir, f"{uuid.uuid4().hex[:8]}_{name}")

    total = 0
    with open(path, "wb") as f:
        while True:
            chunk_data = await file.read(1024 * 1024)
            if not chunk_data:
                break
            total += len(chunk_data)
            if total > max_bytes:
                try:
                    os.remove(path)
                except OSError:
                    pass
                raise HTTPException(413, f"file exceeds {max_bytes // (1024 * 1024)} MB limit")
            f.write(chunk_data)

    depts = [d.strip().lower() for d in departments.split(",") if d.strip()]
    clearance = max(0, min(3, clearance))
    try:
        if ext == ".csv":
            from .ingest import ingest_csv_file
            doc_id, rows = ingest_csv_file(path, title.strip(), clearance, depts, owner_username=owner_username or None)
            try:
                os.remove(path)
            except OSError:
                pass
            return {"doc_id": doc_id, "rows": rows, "kind": "db"}
        doc_id = ingest_file(path, title.strip(), clearance, depts, owner_username=owner_username or None)
    except Exception as exc:
        try:
            os.remove(path)
        except OSError:
            pass
        raise HTTPException(422, str(exc))
    return {"doc_id": doc_id}


@app.get("/api/audit")
def audit(user=Depends(current_user)):
    if user["clearance"] < 3:
        raise HTTPException(403, "admins only")
    with admin_conn() as conn:
        return conn.execute(
            "SELECT ts, username, question, blocked, dropped FROM audit_log ORDER BY id DESC LIMIT 50"
        ).fetchall()
