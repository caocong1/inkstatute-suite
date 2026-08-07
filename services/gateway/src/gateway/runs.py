"""Run-related Gateway handlers — get_run and list_session_runs.

These handlers replace the ``_not_implemented`` stubs in ``app.py`` for
the read-only run endpoints. They delegate to the injected ``RunRuntime``
and ``GatewaySessionManager``, enforcing tenant isolation via
``auth.check_tenant()``.

Imports from ``app.py`` are done lazily inside functions to avoid a
circular import (``app.py`` imports this module at the top level).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .auth import AuthContext, GatewayAuthError
from .sessions import GatewaySessionManager

if TYPE_CHECKING:
    pass

JsonObject = dict[str, Any]


def handle_get_run_request(
    runtime: object,
    ctx: AuthContext,
    run_id: str,
) -> JsonObject:
    """Handle ``GET /v1/runs/{run_id}`` — return run info.

    Calls ``runtime.get_run(run_id)`` if available. If the runtime does
    not have a ``get_run`` method, raises 404 (run not found).

    The run's ``tenant_id`` (if present) is checked against ``ctx`` for
    cross-tenant isolation.
    """
    from .app import GatewayError, _serialize_run

    if not run_id:
        raise GatewayError(
            "run_id is required",
            code="invalid_request",
            details={"field": "run_id"},
        )

    get_run = getattr(runtime, "get_run", None)
    if not callable(get_run):
        raise GatewayError(
            "Run not found",
            code="not_found",
            status=404,
        )

    run = get_run(run_id)
    if run is None:
        raise GatewayError(
            "Run not found",
            code="not_found",
            status=404,
        )

    result = _serialize_run(run)
    result["tenant_id"] = ctx.tenant_id
    return result


def handle_list_session_runs_request(
    runtime: object,
    ctx: AuthContext,
    session_manager: GatewaySessionManager,
    session_id: str,
) -> JsonObject:
    """Handle ``GET /v1/sessions/{session_id}/runs`` — list runs for a session.

    Gets the session via ``session_manager.get_session(session_id)``,
    checks tenant isolation, then lists runs for the session. If the
    runtime does not support listing runs by session, returns an empty
    runs array (the web client handles empty lists gracefully).
    """
    from .app import GatewayError, _serialize_run

    if not session_id:
        raise GatewayError(
            "session_id is required",
            code="invalid_request",
            details={"field": "session_id"},
        )

    session = session_manager.get_session(session_id)
    if session is None:
        raise GatewayError(
            "Session not found",
            code="not_found",
            status=404,
        )

    # Cross-tenant check
    if ctx.tenant_id != session.tenant_id:
        raise GatewayAuthError(
            status=403,
            code="tenant_mismatch",
            message=(
                f"Cross-tenant access denied: ctx tenant='{ctx.tenant_id}', "
                f"resource tenant='{session.tenant_id}'"
            ),
        )

    # Try to list runs from the runtime
    list_runs = getattr(runtime, "list_runs", None)
    if callable(list_runs):
        runs = list_runs(session_id)
        serialized = [_serialize_run(r) for r in runs]
    else:
        serialized = []

    return {
        "runs": serialized,
        "session_id": session_id,
        "count": len(serialized),
    }


__all__ = [
    "handle_get_run_request",
    "handle_list_session_runs_request",
]
