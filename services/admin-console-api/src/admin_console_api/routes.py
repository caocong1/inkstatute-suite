"""Authoritative route prefix table for the Admin Console API.

``ROUTE_PREFIXES`` lists every route prefix dispatched by ``handle_admin_get``.
The RBAC CI scan (``scripts/scan_rbac_annotations.py``) introspects this tuple
and fails when any prefix lacks a ``PERMISSIONS_MATRIX`` entry — enforcing
default-deny at CI time.
"""

from __future__ import annotations

ROUTE_PREFIXES: tuple[str, ...] = (
    "/sessions",
    "/tasks",
    "/feedback",
    "/health",
    "/gates",
)

__all__ = ["ROUTE_PREFIXES"]
