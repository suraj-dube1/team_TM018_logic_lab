"""Pydantic schemas for administrative management and audit logging."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from app.models.user import Role
from app.services.access_control_service import SecurityLevel


class AuditLogResponse(BaseModel):
    id: str
    timestamp: datetime
    user_id: str | None
    user_email: str | None
    user_role: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    status: str
    details: str | None
    ip_address: str | None

    model_config = {"from_attributes": True}


class AdminUserItem(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateUserRoleRequest(BaseModel):
    role: Role = Field(..., description="Target role: STUDENT, FACULTY, or ADMIN")
    is_active: bool | None = Field(default=None, description="Optional active status update")


class UpdateDocumentClassificationRequest(BaseModel):
    security_level: SecurityLevel = Field(..., description="Target level: PUBLIC, INTERNAL, or CONFIDENTIAL")


class AdminStatsResponse(BaseModel):
    total_users: int
    total_documents: int
    documents_by_level: dict[str, int]
    total_queries: int
    successful_accesses: int
    denied_accesses: int
    recent_events_count: int
