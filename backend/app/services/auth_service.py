"""Password hashing and short-lived JWT issuance."""

from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import Role, User


password_hasher = PasswordHash.recommended()


def normalize_email(email: str) -> str:
    """Normalize email identifiers consistently before persistence or lookup."""
    return email.strip().casefold()


def hash_password(password: str) -> str:
    """Return a salted Argon2id password hash."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password while treating malformed stored hashes as invalid."""
    try:
        return password_hasher.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def create_user(db: Session, *, name: str, email: str, password: str) -> User:
    """Create a default-student account; public input cannot choose a role."""
    user = User(
        name=name.strip(),
        email=normalize_email(email),
        password_hash=hash_password(password),
        role=Role.STUDENT.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User | None:
    """Return an active matching account or None for invalid credentials."""
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user_id: str) -> tuple[str, int]:
    """Issue a signed token containing identity but no authoritative role."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    lifetime = settings.jwt_access_token_minutes * 60
    claims = {"sub": user_id, "iat": now, "exp": now + timedelta(seconds=lifetime), "token_type": "access"}
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")
    return token, lifetime
