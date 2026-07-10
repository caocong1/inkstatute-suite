"""Authoritative route prefix table for the Admin Console API.

``ROUTE_PREFIXES`` lists every route prefix dispatched by admin GET and PUT
handlers. The RBAC CI scan (``scripts/scan_rbac_annotations.py``) introspects
this tuple and fails when any prefix lacks a ``PERMISSIONS_MATRIX`` entry —
enforcing default-deny at CI time.
"""

from __future__ import annotations

ROUTE_PREFIXES: tuple[str, ...] = (
    "/sessions",
    "/tasks",
    "/feedback",
    "/health",
    "/gates",
    "/config",
)

__all__ = ["ROUTE_PREFIXES"]
