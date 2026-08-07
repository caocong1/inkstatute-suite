"""RBAC authorization helpers for practice profile operations.

Pure functions that check role and tenant access for practice profile
read/write operations.  The actual enforcement (raising 401/403) happens
in the Gateway layer (Plan 99-03); these helpers return ``bool`` only.

Authorization matrix (from RESEARCH.md §6.4):

================  =================================== ==============
Operation         Allowed Roles                       Cross-tenant
================  =================================== ==============
Read profile      ADMIN, OPERATOR, LAWYER, VIEWER     Always denied
Write profile     ADMIN, OPERATOR                     Always denied
Start interview   ADMIN, OPERATOR                     Always denied
================  =================================== ==============
"""

from __future__ import annotations

from rbac.roles import Role

#: Roles allowed to read practice profiles (all authenticated roles).
PROFILE_READ_ROLES: frozenset[Role] = frozenset({
    Role.ADMIN,
    Role.OPERATOR,
    Role.LAWYER,
    Role.VIEWER,
})

#: Roles allowed to write practice profiles (admin + operator only).
PROFILE_WRITE_ROLES: frozenset[Role] = frozenset({
    Role.ADMIN,
    Role.OPERATOR,
})


def check_read_access(role: Role) -> bool:
    """Return ``True`` if *role* is allowed to read practice profiles."""
    return role in PROFILE_READ_ROLES


def check_write_access(role: Role) -> bool:
    """Return ``True`` if *role* is allowed to write practice profiles."""
    return role in PROFILE_WRITE_ROLES


def check_tenant_access(ctx_tenant_id: str, resource_tenant_id: str) -> bool:
    """Return ``True`` if the caller's tenant matches the resource tenant.

    Cross-tenant access is always denied.
    """
    return ctx_tenant_id == resource_tenant_id


__all__ = [
    "PROFILE_READ_ROLES",
    "PROFILE_WRITE_ROLES",
    "check_read_access",
    "check_write_access",
    "check_tenant_access",
]
