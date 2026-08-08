"""Arena Service application — 5-endpoint routing with auth middleware.

The :class:`ArenaServiceApp` is the local-only HTTP+SSE surface for
multi-agent arena execution. It is framework-free (stdlib pattern, zero
external dependencies) and delegates to an injected ``engine`` object
(wired in Plan 05) for arena execution.

CRITICAL: The ``dispatch`` method applies checks in this order —
NO endpoint bypasses auth:

1. ``auth.require_localhost(client_address)`` — reject non-localhost
   connections with ``403 forbidden_remote`` BEFORE anything else.
2. ``auth.require_auth(headers)`` — reject missing/wrong token with
   ``401 unauthorized`` BEFORE routing to any handler.
3. Route to the appropriate handler.

The ``stream`` method (Plan 02) will use the same auth + localhost
checks for SSE connections.
"""

from __future__ import annotations

from typing import Any, Mapping

from .auth import ArenaServiceAuth, ArenaServiceAuthError, AuthContext
from .config import ArenaServiceConfig
from .openapi import build_openapi_document, render_openapi_json

JsonObject = dict[str, Any]

# ---------------------------------------------------------------------------
# Operation constants — 6 operations across 5 arena endpoint paths + OpenAPI
# ---------------------------------------------------------------------------

OPERATION_CREATE_ARENA = "create_arena"
OPERATION_STREAM_ARENA = "stream_arena"
OPERATION_CANCEL_ARENA = "cancel_arena"
OPERATION_USER_ACTION = "user_action"
OPERATION_STATUS_ARENA = "status_arena"
OPERATION_GET_OPENAPI = "get_openapi"

OPERATIONS: tuple[str, ...] = (
    OPERATION_CREATE_ARENA,
    OPERATION_STREAM_ARENA,
    OPERATION_CANCEL_ARENA,
    OPERATION_USER_ACTION,
    OPERATION_STATUS_ARENA,
    OPERATION_GET_OPENAPI,
)


class ArenaServiceError(RuntimeError):
    """Base error for the Arena Service."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status: int = 400,
        details: JsonObject | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details: JsonObject = dict(details or {})


class ArenaServiceApp:
    """Local-only Arena Service that routes 5 arena endpoints + OpenAPI.

    Auth (localhost + token) is applied BEFORE routing to any handler.
    No endpoint bypasses auth.
    """

    def __init__(
        self,
        config: ArenaServiceConfig,
        *,
        auth: ArenaServiceAuth,
        engine: object | None = None,
    ) -> None:
        self._config = config
        self._auth = auth
        self._engine = engine

    @property
    def config(self) -> ArenaServiceConfig:
        return self._config

    @property
    def auth(self) -> ArenaServiceAuth:
        return self._auth

    @property
    def engine(self) -> object | None:
        return self._engine

    async def dispatch(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
        client_address: str = "127.0.0.1",
    ) -> JsonObject:
        """Main non-streaming dispatch. Localhost → auth → routing.

        The order is critical:
        1. Localhost check (403 forbidden_remote) — BEFORE auth.
        2. Auth check (401 unauthorized) — BEFORE routing.
        3. Route to handler.
        """
        if not self._config.enabled:
            return _error_response("arena_disabled", "Arena Service is disabled", status=503)

        # 1. Localhost check — reject non-localhost BEFORE anything else.
        try:
            self._auth.require_localhost(client_address)
        except ArenaServiceAuthError as exc:
            return _error_response(exc.code, exc.message, status=exc.status)

        route = _parse_route(method, path, self._config.base_path)
        if route is None:
            return _error_response("not_found", f"Unknown route: {method} {path}", status=404)

        operation, path_params = route

        # OPERATION_STREAM_ARENA is handled by the stream() method (Plan 02),
        # not dispatch. If it reaches dispatch, return a method-not-allowed
        # style error directing the client to use the streaming endpoint.
        if operation == OPERATION_STREAM_ARENA:
            return _error_response(
                "use_stream_endpoint",
                "Use the streaming endpoint for SSE connections.",
                status=405,
            )

        # 2. Auth check — BEFORE routing to any handler. No bypass.
        try:
            ctx = self._auth.require_auth(headers)
        except ArenaServiceAuthError as exc:
            return _error_response(exc.code, exc.message, status=exc.status)

        body_dict = dict(body) if body is not None else {}

        # 3. Route to handler.
        try:
            if operation == OPERATION_GET_OPENAPI:
                return self._handle_get_openapi(ctx)
            if operation == OPERATION_CREATE_ARENA:
                return await self._handle_create_arena(ctx, body_dict)
            if operation == OPERATION_CANCEL_ARENA:
                return await self._handle_cancel_arena(ctx, path_params)
            if operation == OPERATION_USER_ACTION:
                return await self._handle_user_action(ctx, path_params, body_dict)
            if operation == OPERATION_STATUS_ARENA:
                return await self._handle_status_arena(ctx, path_params)
            return _error_response("unknown_operation", f"Unknown operation: {operation}", status=404)
        except ArenaServiceError as exc:
            return _error_response(exc.code, str(exc), status=exc.status, details=exc.details)
        except ArenaServiceAuthError as exc:
            return _error_response(exc.code, exc.message, status=exc.status)

    def operations(self) -> tuple[str, ...]:
        return OPERATIONS

    def openapi_operations(self) -> tuple[str, ...]:
        return OPERATIONS

    # -----------------------------------------------------------------------
    # Handlers — delegate to injected engine (wired in Plan 05)
    # -----------------------------------------------------------------------

    def _handle_get_openapi(self, ctx: AuthContext) -> JsonObject:
        """Handle GET /v1/openapi — return the OpenAPI document."""
        doc = build_openapi_document(self._config.base_path)
        return {
            "status": 200,
            "body": doc,
        }

    async def _handle_create_arena(
        self,
        ctx: AuthContext,
        body: Mapping[str, object],
    ) -> JsonObject:
        """Handle POST /v1/arena — create a new arena."""
        if self._engine is None:
            return _not_implemented("create_arena")
        mode = str(body.get("mode") or "")
        agent_slots = body.get("agent_slots") or []
        if not isinstance(agent_slots, list):
            return _error_response(
                "invalid_request",
                "agent_slots must be a list",
                status=400,
            )
        task = str(body.get("task") or "")
        if not mode:
            return _error_response("invalid_request", "mode is required", status=400)
        if not agent_slots:
            return _error_response("invalid_request", "agent_slots is required", status=400)
        if not task:
            return _error_response("invalid_request", "task is required", status=400)
        create = getattr(self._engine, "create_arena", None)
        if not callable(create):
            return _not_implemented("create_arena")
        result = create(
            mode=mode,
            agent_slots=[str(s) for s in agent_slots],
            task=task,
            metadata=dict(body.get("metadata") or {}),
        )
        if isinstance(result, Mapping):
            data = dict(result)
        else:
            data = {"arena_id": getattr(result, "arena_id", ""), "status": getattr(result, "status", "created")}
        data.setdefault("status", "created")
        return {"status": 201, "body": data}

    async def _handle_cancel_arena(
        self,
        ctx: AuthContext,
        path_params: dict[str, str],
    ) -> JsonObject:
        """Handle POST /v1/arena/{arena_id}/cancel — cancel an arena."""
        arena_id = path_params.get("arena_id", "")
        if not arena_id:
            return _error_response("invalid_request", "arena_id is required", status=400)
        if self._engine is None:
            return _not_implemented("cancel_arena")
        cancel = getattr(self._engine, "cancel_arena", None)
        if not callable(cancel):
            return _not_implemented("cancel_arena")
        result = cancel(arena_id)
        if isinstance(result, Mapping):
            data = dict(result)
        else:
            data = {"arena_id": arena_id, "status": getattr(result, "status", "cancelled")}
        return {"status": 200, "body": data}

    async def _handle_user_action(
        self,
        ctx: AuthContext,
        path_params: dict[str, str],
        body: Mapping[str, object],
    ) -> JsonObject:
        """Handle POST /v1/arena/{arena_id}/action — submit a user action."""
        arena_id = path_params.get("arena_id", "")
        if not arena_id:
            return _error_response("invalid_request", "arena_id is required", status=400)
        action = str(body.get("action") or "")
        if not action:
            return _error_response("invalid_request", "action is required", status=400)
        if self._engine is None:
            return _not_implemented("user_action")
        submit = getattr(self._engine, "submit_user_action", None)
        if not callable(submit):
            return _not_implemented("user_action")
        result = submit(
            arena_id,
            action=action,
            selection=body.get("selection"),
            metadata=dict(body.get("metadata") or {}),
        )
        if isinstance(result, Mapping):
            data = dict(result)
        else:
            data = {"arena_id": arena_id, "status": getattr(result, "status", "running")}
        return {"status": 200, "body": data}

    async def _handle_status_arena(
        self,
        ctx: AuthContext,
        path_params: dict[str, str],
    ) -> JsonObject:
        """Handle GET /v1/arena/{arena_id}/status — query arena status."""
        arena_id = path_params.get("arena_id", "")
        if not arena_id:
            return _error_response("invalid_request", "arena_id is required", status=400)
        if self._engine is None:
            return _not_implemented("status_arena")
        query = getattr(self._engine, "query_status", None)
        if not callable(query):
            return _not_implemented("status_arena")
        result = query(arena_id)
        if isinstance(result, Mapping):
            data = dict(result)
        else:
            data = {"arena_id": arena_id, "status": getattr(result, "status", "running")}
        return {"status": 200, "body": data}


# ---------------------------------------------------------------------------
# Path routing
# ---------------------------------------------------------------------------


def _parse_route(method: str, path: str, base_path: str) -> tuple[str, dict[str, str]] | None:
    """Map ``(method, path)`` to ``(operation, path_params)``.

    Strips the ``base_path`` prefix and pattern-matches the remaining
    path to determine the operation and extract path parameters.
    Supports trailing slash tolerance.
    """
    # Strip query string
    clean_path = path.split("?")[0]

    # Strip base_path prefix
    if not clean_path.startswith(base_path + "/") and clean_path != base_path:
        if clean_path.startswith(base_path):
            clean_path = clean_path[len(base_path):]
        else:
            return None
    else:
        clean_path = clean_path[len(base_path):]

    if not clean_path.startswith("/"):
        clean_path = "/" + clean_path

    parts = [p for p in clean_path.split("/") if p]

    # POST /v1/arena — create arena
    if method == "POST" and parts == ["arena"]:
        return OPERATION_CREATE_ARENA, {}

    # GET /v1/arena/{arena_id}/stream — SSE stream
    if method == "GET" and len(parts) == 3 and parts[0] == "arena" and parts[2] == "stream":
        return OPERATION_STREAM_ARENA, {"arena_id": parts[1]}

    # POST /v1/arena/{arena_id}/cancel — cancel arena
    if method == "POST" and len(parts) == 3 and parts[0] == "arena" and parts[2] == "cancel":
        return OPERATION_CANCEL_ARENA, {"arena_id": parts[1]}

    # POST /v1/arena/{arena_id}/action — user action
    if method == "POST" and len(parts) == 3 and parts[0] == "arena" and parts[2] == "action":
        return OPERATION_USER_ACTION, {"arena_id": parts[1]}

    # GET /v1/arena/{arena_id}/status — status query
    if method == "GET" and len(parts) == 3 and parts[0] == "arena" and parts[2] == "status":
        return OPERATION_STATUS_ARENA, {"arena_id": parts[1]}

    # GET /v1/openapi — OpenAPI document
    if method == "GET" and parts == ["openapi"]:
        return OPERATION_GET_OPENAPI, {}

    return None


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _error_response(code: str, message: str, *, status: int = 400, details: JsonObject | None = None) -> JsonObject:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "status": status,
    }


def _not_implemented(operation: str) -> JsonObject:
    return {
        "error": {
            "code": "not_implemented",
            "message": f"Endpoint not yet implemented: {operation}",
        },
        "status": 501,
    }


__all__ = [
    "OPERATIONS",
    "OPERATION_CANCEL_ARENA",
    "OPERATION_CREATE_ARENA",
    "OPERATION_GET_OPENAPI",
    "OPERATION_STATUS_ARENA",
    "OPERATION_STREAM_ARENA",
    "OPERATION_USER_ACTION",
    "ArenaServiceApp",
    "ArenaServiceError",
]
