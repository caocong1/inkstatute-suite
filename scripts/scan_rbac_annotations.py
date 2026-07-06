#!/usr/bin/env python3
"""CI scan: fail when any admin API endpoint lacks an RBAC role annotation.

This script enforces default-deny at CI time.  It introspects
``ROUTE_PREFIXES`` (the authoritative list of route prefixes dispatched by
``handle_admin_get``) and fails (exit 1) when any prefix is absent from the
``PERMISSIONS_MATRIX`` — meaning the endpoint would be denied by
``RbacGuard.check`` because it has no role annotation.

Usage::

    PYTHONPATH=packages/rbac/src:services/admin-console-api/src \
        python3 scripts/scan_rbac_annotations.py
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping


def find_unannotated(
    route_prefixes: Iterable[str],
    matrix: Mapping[str, object],
) -> list[str]:
    """Return route prefixes that lack a ``PERMISSIONS_MATRIX`` entry."""
    return [prefix for prefix in route_prefixes if prefix not in matrix]


def main(argv: list[str] | None = None) -> int:
    from admin_console_api.routes import ROUTE_PREFIXES
    from rbac.matrix import PERMISSIONS_MATRIX

    unannotated = find_unannotated(ROUTE_PREFIXES, PERMISSIONS_MATRIX)
    if unannotated:
        print(
            f"FAIL: unannotated endpoints (no RBAC role): {unannotated}",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK: all {len(ROUTE_PREFIXES)} admin API endpoints have RBAC annotations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
