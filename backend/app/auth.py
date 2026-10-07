"""Authentication helpers for Logic Labs.

Login IDs intentionally follow a human-readable role suffix convention:
    name@student
    name@faculty
    name@admin

Passwords use PBKDF2-HMAC-SHA256 with per-user random salts. Session tokens are
short-lived HMAC-signed bearer tokens for the hackathon demo.
"""
import hashlib
import hmac
import re
import secrets
import time

PWD_ITER = 100_000
TOKEN_TTL = 8 * 60 * 60

DEFAULT_PASSWORDS = {
    "rahul@student": "Rahul@123",
    "neha@faculty": "Neha@123",
    "arjun@admin": "Arjun@123",
}

HANDLE_RE = re.compile(r"^[a-z][a-z0-9._-]{2,30}$", re.I)

LOGIN_RE = re.compile(r"^[a-z][a-z0-9._-]{1,62}@(student|faculty|admin)$", re.I)


def normalize_login_id(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("@faculty member", "@faculty")
    value = value.replace("@faculty-member", "@faculty")
    value = value.replace(" ", "")
    if not LOGIN_RE.fullmatch(value):
        raise ValueError("Use a login ID like rahul@student, neha@faculty, or arjun@admin")
    return value


def role_from_login_id(login_id: str) -> str:
    return normalize_login_id(login_id).rsplit("@", 1)[1]


def normalize_handle(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.split("@", 1)[0]
    value = re.sub(r"\s+", "", value)
    if not HANDLE_RE.fullmatch(value):
        raise ValueError("Handle must be 3–31 characters using letters, numbers, dot, underscore, or hyphen")
    return value


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PWD_ITER)
    return digest.hex(), salt.hex()


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    try:
        digest, _ = hash_password(password, password_salt)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(digest, str(password_hash))


def make_token(username: str, secret: bytes, ttl_seconds: int = TOKEN_TTL) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"{username}.{exp}"
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token: str, secret: bytes) -> str | None:
    try:
        username, exp_text, sig = token.split(".", 2)
        payload = f"{username}.{exp_text}"
        expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if int(exp_text) <= int(time.time()):
            return None
        if not username or len(username) > 64:
            return None
        return normalize_login_id(username)
    except (TypeError, ValueError):
        return None
