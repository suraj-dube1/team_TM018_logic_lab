"""Administrative endpoints for user management, system metrics, and governance."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_user
from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.user import User
from app.schemas.admin import AdminStatsResponse, AdminUserItem, UpdateUserRoleRequest
from app.services.audit_service import (
    ACTION_ADMIN_ROLE_CHANGE,
    ACTION_DOCUMENT_QUERY,
    STATUS_DENIED,
    STATUS_SUCCESS,
    record_audit_event,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
def get_system_stats(
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> AdminStatsResponse:
    """Return high-level security metrics, user counts, and document distribution."""
    total_users = db.scalar(select(func.count(User.id))) or 0
    total_documents = db.scalar(select(func.count(Document.id))) or 0

    level_rows = db.execute(
        select(Document.security_level, func.count(Document.id)).group_by(Document.security_level)
    ).all()
    documents_by_level = {row[0]: row[1] for row in level_rows}
    for level in ("PUBLIC", "INTERNAL", "CONFIDENTIAL"):
        documents_by_level.setdefault(level, 0)

    total_queries = (
        db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == ACTION_DOCUMENT_QUERY))
        or 0
    )
    successful_accesses = (
        db.scalar(select(func.count(AuditLog.id)).where(AuditLog.status == STATUS_SUCCESS))
        or 0
    )
    denied_accesses = (
        db.scalar(select(func.count(AuditLog.id)).where(AuditLog.status == STATUS_DENIED))
        or 0
    )
    recent_events_count = db.scalar(select(func.count(AuditLog.id))) or 0

    return AdminStatsResponse(
        total_users=total_users,
        total_documents=total_documents,
        documents_by_level=documents_by_level,
        total_queries=total_queries,
        successful_accesses=successful_accesses,
        denied_accesses=denied_accesses,
        recent_events_count=recent_events_count,
    )


@router.get("/users", response_model=list[AdminUserItem])
def list_users(
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> list[User]:
    """List all accounts and their authorization roles."""
    query = select(User).order_by(User.created_at.desc())
    return list(db.scalars(query).all())


@router.patch("/users/{user_id}/role", response_model=AdminUserItem)
def update_user_role(
    user_id: str,
    payload: UpdateUserRoleRequest,
    current_admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> User:
    """Elevate, change, or deactivate an account."""
    target_user = db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    old_role = target_user.role
    target_user.role = payload.role.value
    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    db.commit()
    db.refresh(target_user)

    record_audit_event(
        db=db,
        action=ACTION_ADMIN_ROLE_CHANGE,
        status=STATUS_SUCCESS,
        user=current_admin,
        resource_type="USER",
        resource_id=target_user.id,
        details=f"Changed role for {target_user.email} from {old_role} to {target_user.role} (is_active={target_user.is_active})",
    )
    return target_user
