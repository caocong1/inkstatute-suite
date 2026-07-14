"""Declarative permissions matrix mapping admin API endpoint prefixes to allowed roles.

The matrix is the single source of truth for RBAC enforcement.  Endpoints
absent from the matrix are denied by default (``RbacGuard.check`` returns
``False``).  The CI scan (``scripts/scan_rbac_annotations.py``) fails when any
dispatched admin API route prefix lacks a matrix entry.
"""

from __future__ import annotations

from .roles import Role

PERMISSIONS_MATRIX: dict[str, frozenset[Role]] = {
    "/sessions": frozenset({Role.ADMIN, Role.OPERATOR, Role.LAWYER, Role.VIEWER}),
    "/tasks": frozenset({Role.ADMIN, Role.OPERATOR, Role.LAWYER, Role.VIEWER}),
    "/feedback": frozenset({Role.ADMIN, Role.OPERATOR}),
    "/health": frozenset({Role.ADMIN, Role.OPERATOR}),
    "/gates": frozenset({Role.ADMIN}),
    "/skills-write": frozenset({Role.ADMIN}),
    "/config": frozenset({Role.ADMIN, Role.OPERATOR}),
    "/processes": frozenset({Role.ADMIN, Role.OPERATOR}),
    "/reports": frozenset({Role.ADMIN, Role.OPERATOR, Role.LAWYER, Role.VIEWER}),
}

__all__ = ["PERMISSIONS_MATRIX"]
