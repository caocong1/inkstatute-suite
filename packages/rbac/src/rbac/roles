"""RBAC role definitions for InkStatute admin APIs."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """Four RBAC roles with increasing privilege.

    - ADMIN: full access to all admin API endpoints
    - OPERATOR: operational endpoints (sessions, tasks, feedback, health)
    - LAWYER: read-only case data (sessions, tasks)
    - VIEWER: read-only case data (sessions, tasks)
    """

    ADMIN = "admin"
    OPERATOR = "operator"
    LAWYER = "lawyer"
    VIEWER = "viewer"


__all__ = ["Role"]
