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
from .auth import make_token, verify_password, verify_token
from .db import admin_conn, user_conn
from .ingest import ingest_file

app = FastAPI(title="VaultRAG")
SECRET = os.getenv("SECRET_KEY", "change-me").encode()
HERE = os.path.dirname(__file__)


# --- demo auth: username + password -> short-lived signed token. -------------------------
# The database remains the source of truth for clearance/departments.
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
            "SELECT username, display, clearance, departments FROM users WHERE username=%s", (name,)
        ).fetchone()
    if not u:
        raise HTTPException(401, "unknown user")
    return u


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
        return conn.execute("SELECT username, display, clearance, departments FROM users ORDER BY clearance").fetchall()


class Login(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(body: Login):
    username = body.username.strip().lower()
    if not username or not body.password:
        raise HTTPException(400, "username and password are required")
    with admin_conn() as conn:
        u = conn.execute(
            "SELECT username, display, clearance, departments, password_hash, password_salt FROM users WHERE username=%s",
            (username,),
        ).fetchone()
    if not u:
        raise HTTPException(401, "invalid username or password")
    if not verify_password(body.password, u["password_hash"], u["password_salt"]):
        raise HTTPException(401, "invalid username or password")
    safe = {k: u[k] for k in ("username", "display", "clearance", "departments")}
    return {"token": make_token(u["username"], SECRET), "user": safe}


@app.post("/api/logout")
def logout():
    # Tokens are stateless; the browser removes its bearer token.
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


class Ask(BaseModel):
    question: str


def _public(res):
    res.pop("_retrieved_text", None)
    return res


@app.post("/api/ask")
def ask(body: Ask, user=Depends(current_user)):
    if not body.question.strip():
        raise HTTPException(400, "empty question")
    return _public(qa.run(user, body.question.strip()))


@app.post("/api/compare")
def compare(body: Ask, user=Depends(current_user)):
    """Presenter mode: same question as every persona. Disabled unless DEMO_MODE=1."""
    if os.getenv("DEMO_MODE", "1") != "1":
        raise HTTPException(403, "demo mode is off")
    with admin_conn() as conn:
        everyone = conn.execute("SELECT username, display, clearance, departments FROM users ORDER BY clearance").fetchall()
    return [{**_public(qa.run(u, body.question.strip())), "display": u["display"]} for u in everyone]


@app.post("/api/redteam")
def red_team(user=Depends(current_user)):
    out = redteam.run(user)
    return out


def _chunk(user, cid):
    with user_conn(user) as conn:  # RLS: a chunk the user can't see simply doesn't exist for them
        return conn.execute(
            "SELECT c.id, c.source, c.kind, c.page, c.bbox, c.text, d.title, d.path "
            "FROM chunks c JOIN documents d ON d.id=c.doc_id WHERE c.id=%s", (cid,)).fetchone()


@app.get("/api/chunk/{cid}")
def chunk(cid: int, user=Depends(current_user)):
    ch = _chunk(user, cid)
    if not ch:
        raise HTTPException(404, "not found")
    ch.pop("path")
    return ch


@app.get("/api/chunk/{cid}/image")
def chunk_image(cid: int, user=Depends(current_user)):
    ch = _chunk(user, cid)
    if not ch or ch["kind"] not in ("pdf", "image") or not ch["path"]:
        raise HTTPException(404, "not found")
    if ch["kind"] == "pdf":
        pdf = pdfium.PdfDocument(ch["path"])
        img = pdf[ch["page"] - 1].render(scale=1.6).to_pil().convert("RGBA")
        pdf.close()
    else:
        img = Image.open(ch["path"]).convert("RGBA")
    if ch["bbox"]:
        W, H = img.size
        x0, y0, x1, y1 = ch["bbox"]
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(ov).rectangle([x0 * W - 4, y0 * H - 4, x1 * W + 4, y1 * H + 4],
                                     fill=(209, 32, 47, 55), outline=(209, 32, 47, 255), width=4)
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
    os.makedirs(os.path.join(os.getenv("DATA_DIR", "data"), "docs"), exist_ok=True)
    path = os.path.join(
        os.getenv("DATA_DIR", "data"),
        "docs",
        f"{uuid.uuid4().hex[:8]}_{name}",
    )
    total = 0
    with open(path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                try:
                    os.remove(path)
                except OSError:
                    pass
                raise HTTPException(413, f"file exceeds {max_bytes // (1024 * 1024)} MB limit")
            f.write(chunk)
    depts = [d.strip().lower() for d in departments.split(",") if d.strip()]
    clearance = max(0, min(3, clearance))
    try:
        if ext == ".csv":
            from .ingest import ingest_csv_file
            doc_id, rows = ingest_csv_file(path, title.strip(), clearance, depts)
            try:
                os.remove(path)
            except OSError:
                pass
            return {"doc_id": doc_id, "rows": rows, "kind": "db"}
        doc_id = ingest_file(path, title.strip(), clearance, depts)
    except Exception as e:
        try:
            os.remove(path)
        except OSError:
            pass
        raise HTTPException(422, str(e))
    return {"doc_id": doc_id}


@app.get("/api/audit")
def audit(user=Depends(current_user)):
    if user["clearance"] < 3:
        raise HTTPException(403, "admins only")
    with admin_conn() as conn:
        return conn.execute("SELECT ts, username, question, blocked, dropped FROM audit_log ORDER BY id DESC LIMIT 50").fetchall()
