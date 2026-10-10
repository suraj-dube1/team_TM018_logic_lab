"""Central role and resource authorization policy.

All document access decisions should pass through this module. Retrieval and
document endpoints can call ``can_access`` before returning resources or
chunks, preventing unauthorized content from entering later processing stages.
"""

from collections.abc import Iterable
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Protocol

from app.models.user import Role, User


class SecurityLevel(StrEnum):
    """Classification levels supported by the initial access policy."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"


class AccessControlledResource(Protocol):
    """Minimal resource interface required by the authorization policy."""

    security_level: str | SecurityLevel


ROLE_SECURITY_LEVELS: Mapping[Role, frozenset[SecurityLevel]] = MappingProxyType(
    {
        Role.STUDENT: frozenset({SecurityLevel.PUBLIC}),
        Role.FACULTY: frozenset({SecurityLevel.PUBLIC, SecurityLevel.INTERNAL}),
        Role.ADMIN: frozenset(
            {SecurityLevel.PUBLIC, SecurityLevel.INTERNAL, SecurityLevel.CONFIDENTIAL}
        ),
    }
)


def _parse_role(value: object) -> Role | None:
    """Convert a persisted role value to a known role; unknown roles deny."""
    try:
        return Role(value)
    except (ValueError, TypeError):
        return None


def _parse_security_level(value: object) -> SecurityLevel | None:
    """Convert a resource classification to a known security level."""
    try:
        return SecurityLevel(value)
    except (ValueError, TypeError):
        return None


def allowed_security_levels_for_role(role: Role | str) -> frozenset[SecurityLevel]:
    """Return the levels permitted for a role, or an empty set for unknown roles."""
    parsed_role = _parse_role(role)
    return ROLE_SECURITY_LEVELS.get(parsed_role, frozenset()) if parsed_role else frozenset()


def get_allowed_security_levels(user: User) -> frozenset[SecurityLevel]:
    """Return a user's effective levels; inactive and unknown users get none."""
    if not getattr(user, "is_active", False):
        return frozenset()
    return allowed_security_levels_for_role(getattr(user, "role", None))


def can_classify(user: User, level: SecurityLevel | str) -> bool:
    """Return whether an active user may assign a classification to a document."""
    parsed_level = _parse_security_level(level)
    return parsed_level is not None and parsed_level in get_allowed_security_levels(user)


def can_access(user: User, resource: AccessControlledResource) -> bool:
    """Return whether an active user may access a classified resource.

    Unknown roles and classifications fail closed. This role-to-classification
    check is the baseline policy; document-specific grants can be layered into
    this function when document ACL persistence is introduced.
    """
    permitted_levels = get_allowed_security_levels(user)
    resource_level = _parse_security_level(getattr(resource, "security_level", None))
    return resource_level is not None and resource_level in permitted_levels


def filter_accessible(
    user: User,
    resources: Iterable[AccessControlledResource],
) -> list[AccessControlledResource]:
    """Filter resources by permission before they enter downstream pipelines."""
    return [resource for resource in resources if can_access(user, resource)]
