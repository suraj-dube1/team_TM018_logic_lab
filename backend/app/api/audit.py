"""Audit log query endpoints for security monitoring and compliance."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_user
from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.admin import AuditLogResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    status: Optional[str] = Query(default=None, description="Filter by status (SUCCESS, DENIED, ERROR)"),
    action: Optional[str] = Query(default=None, description="Filter by action name"),
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    """Retrieve immutable security audit trail ordered by most recent events."""
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())

    if status:
        query = query.where(AuditLog.status == status.upper())
    if action:
        query = query.where(AuditLog.action == action.upper())

    query = query.limit(limit)
    return list(db.scalars(query).all())
