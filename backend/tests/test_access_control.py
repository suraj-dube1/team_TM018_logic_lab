"""Role and document-classification authorization policy tests."""

from types import SimpleNamespace

import pytest

from app.models.user import Role
from app.services.access_control_service import (
    SecurityLevel,
    allowed_security_levels_for_role,
    can_access,
    filter_accessible,
    get_allowed_security_levels,
)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.STUDENT, {SecurityLevel.PUBLIC}),
        (Role.INTERN, {SecurityLevel.PUBLIC}),
        (Role.FACULTY, {SecurityLevel.PUBLIC, SecurityLevel.INTERNAL}),
        (Role.MANAGER, {SecurityLevel.PUBLIC, SecurityLevel.INTERNAL}),
        (Role.ADMIN, {SecurityLevel.PUBLIC, SecurityLevel.INTERNAL, SecurityLevel.CONFIDENTIAL}),
    ],
)
def test_roles_receive_expected_security_levels(role, expected):
    assert allowed_security_levels_for_role(role) == frozenset(expected)


@pytest.mark.parametrize(
    ("role", "level", "expected"),
    [
        (Role.STUDENT, SecurityLevel.PUBLIC, True),
        (Role.STUDENT, SecurityLevel.INTERNAL, False),
        (Role.STUDENT, SecurityLevel.CONFIDENTIAL, False),
        (Role.INTERN, SecurityLevel.PUBLIC, True),
        (Role.INTERN, SecurityLevel.INTERNAL, False),
        (Role.INTERN, SecurityLevel.CONFIDENTIAL, False),
        (Role.FACULTY, SecurityLevel.PUBLIC, True),
        (Role.FACULTY, SecurityLevel.INTERNAL, True),
        (Role.FACULTY, SecurityLevel.CONFIDENTIAL, False),
        (Role.MANAGER, SecurityLevel.PUBLIC, True),
        (Role.MANAGER, SecurityLevel.INTERNAL, True),
        (Role.MANAGER, SecurityLevel.CONFIDENTIAL, False),
        (Role.ADMIN, SecurityLevel.PUBLIC, True),
        (Role.ADMIN, SecurityLevel.INTERNAL, True),
        (Role.ADMIN, SecurityLevel.CONFIDENTIAL, True),
    ],
)
def test_can_access_applies_role_policy(role, level, expected):
    user = SimpleNamespace(id="user-1", role=role.value, is_active=True)
    resource = SimpleNamespace(id="doc-1", security_level=level.value)
    assert can_access(user, resource) is expected


def test_unknown_values_and_inactive_users_fail_closed():
    resource = SimpleNamespace(security_level="CONFIDENTIAL")
    assert get_allowed_security_levels(SimpleNamespace(role="UNKNOWN", is_active=True)) == frozenset()
    assert not can_access(SimpleNamespace(role="ADMIN", is_active=False), resource)
    assert not can_access(SimpleNamespace(role="ADMIN", is_active=True), SimpleNamespace(security_level="SECRET"))


def test_filter_accessible_returns_only_authorized_resources():
    user = SimpleNamespace(id="student-1", role="STUDENT", is_active=True)
    documents = [
        SimpleNamespace(id="public-doc", security_level="PUBLIC"),
        SimpleNamespace(id="internal-doc", security_level="INTERNAL"),
        SimpleNamespace(id="confidential-doc", security_level="CONFIDENTIAL"),
    ]
    assert [item.id for item in filter_accessible(user, documents)] == ["public-doc"]
