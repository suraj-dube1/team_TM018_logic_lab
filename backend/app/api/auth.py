"""Registration, login, and current-user endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import authenticate_user, create_access_token, create_user, normalize_email
from app.services.audit_service import (
    ACTION_LOGIN_FAILURE,
    ACTION_LOGIN_SUCCESS,
    STATUS_DENIED,
    STATUS_SUCCESS,
    record_audit_event,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """Create a student account; registration never grants elevated roles."""
    normalized_email = normalize_email(str(payload.email))
    existing = db.scalar(select(User.id).where(User.email == normalized_email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    try:
        return create_user(db, name=payload.name, email=normalized_email, password=payload.password)
    except IntegrityError as exc:
        db.rollback()
        logger.info("Registration conflict for normalized email")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.") from exc


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Validate credentials and return a short-lived signed access token."""
    user = authenticate_user(db, email=str(payload.email), password=payload.password)
    if user is None:
        record_audit_event(
            db=db,
            action=ACTION_LOGIN_FAILURE,
            status=STATUS_DENIED,
            user_email=str(payload.email),
            details="Invalid credentials submitted",
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    token, lifetime = create_access_token(user.id)
    record_audit_event(
        db=db,
        action=ACTION_LOGIN_SUCCESS,
        status=STATUS_SUCCESS,
        user=user,
        details="User logged in successfully",
    )
    return TokenResponse(access_token=token, expires_in=lifetime)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's profile and current database role."""
    return current_user
