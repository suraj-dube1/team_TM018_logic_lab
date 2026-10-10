"""Audit logging service for tracking security events."""

import logging
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


logger = logging.getLogger(__name__)

# Standard audit action constants
ACTION_LOGIN_SUCCESS = "LOGIN_SUCCESS"
ACTION_LOGIN_FAILURE = "LOGIN_FAILURE"
ACTION_DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
ACTION_DOCUMENT_DELETE = "DOCUMENT_DELETE"
ACTION_DOCUMENT_CLASSIFY = "DOCUMENT_CLASSIFY"
ACTION_DOCUMENT_QUERY = "DOCUMENT_QUERY"
ACTION_ACCESS_DENIED = "ACCESS_DENIED"
ACTION_ACCESS_GRANTED = "ACCESS_GRANTED"
ACTION_ADMIN_ROLE_CHANGE = "ADMIN_ROLE_CHANGE"

# Status constants
STATUS_SUCCESS = "SUCCESS"
STATUS_DENIED = "DENIED"
STATUS_ERROR = "ERROR"


def record_audit_event(
    db: Session,
    action: str,
    status: str,
    user: User | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
    user_role: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: str | None = None,
    ip_address: str | None = None,
) -> AuditLog | None:
    """Safely record an immutable audit event to the database."""
    try:
        resolved_user_id = user.id if user else user_id
        resolved_email = user.email if user else user_email
        resolved_role = user.role if user else user_role

        log_entry = AuditLog(
            user_id=resolved_user_id,
            user_email=resolved_email,
            user_role=resolved_role,
            action=action,
            status=status,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry
    except Exception:
        db.rollback()
        logger.exception("Failed to write audit event for action '%s'", action)
        return None
