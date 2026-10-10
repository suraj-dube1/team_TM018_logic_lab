"""Shared authentication dependencies for protected routes."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.user import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate a bearer token and load current user state from the database."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        claims = jwt.decode(
            credentials.credentials,
            get_settings().jwt_secret_key,
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp", "token_type"]},
        )
        if claims.get("token_type") != "access":
            raise unauthorized
        user = db.get(User, claims["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError):
        raise unauthorized from None
    if user is None or not user.is_active:
        raise unauthorized
    return user
