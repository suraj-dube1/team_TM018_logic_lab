"""Small self-contained demo authentication helpers.

Passwords use PBKDF2-HMAC-SHA256 with a per-user random salt. Session tokens are
short-lived HMAC-signed bearer tokens; they are intentionally simple for the
hackathon and can be replaced by SSO/JWT without changing the RLS layer.
"""
import hashlib
import hmac
import secrets
import time

PWD_ITER = 100_000
TOKEN_TTL = 8 * 60 * 60

DEFAULT_PASSWORDS = {
    "intern": "intern123",
    "manager": "manager123",
    "admin": "admin123",
}


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
        return username
    except (TypeError, ValueError):
        return None
