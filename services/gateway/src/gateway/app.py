"""Unified Gateway application — 12-endpoint routing with auth middleware.

The :class:`GatewayApp` is the single client-facing entry point for all
clients (web, desktop, WeCom, QQ, programmatic). It is framework-free
(stdlib pattern, zero external dependencies) and delegates to an injected
``RunRuntime`` for agent execution.

CRITICAL: The ``dispatch`` method calls ``auth.require_auth(headers)``
BEFORE routing to any handler. No endpoint bypasses auth. The ``stream``
method also calls ``auth.require_auth(headers)`` before yielding any SSE
frames. The output boundary is enforced in ``GatewaySseStream.encode_event``
— the second enforcement point per AGENTS.md.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, AsyncIterator, Iterable, Mapping

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    Channel,
    MessageType,
    RunEventType,
)
from platform_contract.events import (
    AgentTurn,
    Artifact,
    AttachmentRef,
    ErrorInfo,
    OutputConstraints,
)

from .artifacts import GatewayArtifactStore, handle_get_artifact_request
from .auth import AuthContext, GatewayAuth, GatewayAuthError
from .config import GatewayConfig
from .event_buffer import RunEventBuffer
from .feedback import GatewayFeedbackHandler, handle_submit_feedback_request
from .login import GatewayLoginHandler
from .runs import handle_get_run_request, handle_list_session_runs_request
from .sessions import GatewaySessionManager, build_set_cookie_header, serialize_session
from .skills import GatewaySkillsHandler, handle_skills_request
from .sse import GatewaySseStream, parse_last_event_id
from .upload import GatewayUploadHandler, handle_upload_request

JsonObject = dict[str, Any]

# ---------------------------------------------------------------------------
# Operation constants — 13 operations across 12 endpoint paths
# ---------------------------------------------------------------------------

OPERATION_CREATE_SESSION = "create_session"
OPERATION_LOGIN = "login"
OPERATION_GET_SESSION = "get_session"
OPERATION_LIST_SESSION_RUNS = "list_session_runs"
OPERATION_CREATE_RUN = "create_run"
OPERATION_GET_RUN = "get_run"
OPERATION_CANCEL_RUN = "cancel_run"
OPERATION_STREAM_RUN = "stream_run"
OPERATION_SUBMIT_ELICITATION = "submit_elicitation"
OPERATION_SUBMIT_APPROVAL = "submit_approval"
OPERATION_GET_ARTIFACT = "get_artifact"
OPERATION_UPLOAD = "upload"
OPERATION_SUBMIT_FEEDBACK = "submit_feedback"
OPERATION_LIST_SKILLS = "list_skills"

OPERATIONS: tuple[str, ...] = (
    OPERATION_CREATE_SESSION,
    OPERATION_GET_SESSION,
    OPERATION_LIST_SESSION_RUNS,
    OPERATION_CREATE_RUN,
    OPERATION_GET_RUN,
    OPERATION_CANCEL_RUN,
    OPERATION_STREAM_RUN,
    OPERATION_SUBMIT_ELICITATION,
    OPERATION_SUBMIT_APPROVAL,
    OPERATION_GET_ARTIFACT,
    OPERATION_UPLOAD,
    OPERATION_SUBMIT_FEEDBACK,
    OPERATION_LIST_SKILLS,
)


class GatewayError(RuntimeError):
    """Base error for the Gateway."""

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


class GatewayDisabledError(GatewayError):
    """Raised when the Gateway is invoked while disabled."""

    def __init__(self, message: str = "gateway disabled") -> None:
        super().__init__(message, code="gateway_disabled", status=503)


class GatewayApp:
    """Unified Gateway that routes all 12 endpoints with auth middleware."""

    def __init__(
        self,
        config: GatewayConfig,
        *,
        runtime: object,
        auth: GatewayAuth,
        session_manager: GatewaySessionManager,
        sse_stream: GatewaySseStream,
        event_buffer: RunEventBuffer | None = None,
        upload_handler: GatewayUploadHandler | None = None,
        artifact_store: GatewayArtifactStore | None = None,
        feedback_handler: GatewayFeedbackHandler | None = None,
        skills_handler: GatewaySkillsHandler | None = None,
        login_handler: GatewayLoginHandler | None = None,
    ) -> None:
        self._config = config
        self._runtime = runtime
        self._auth = auth
        self._session_manager = session_manager
        self._sse_stream = sse_stream
        self._event_buffer = event_buffer
        self._upload_handler = upload_handler or GatewayUploadHandler()
        self._artifact_store = artifact_store or GatewayArtifactStore()
        self._feedback_handler = feedback_handler or GatewayFeedbackHandler()
        self._skills_handler = skills_handler
        self._login_handler = login_handler

    @property
    def config(self) -> GatewayConfig:
        return self._config

    @property
    def runtime(self) -> object:
        return self._runtime

    @property
    def event_buffer(self) -> RunEventBuffer | None:
        return self._event_buffer

    @property
    def upload_handler(self) -> GatewayUploadHandler:
        return self._upload_handler

    @property
    def artifact_store(self) -> GatewayArtifactStore:
        return self._artifact_store

    @property
    def feedback_handler(self) -> GatewayFeedbackHandler:
        return self._feedback_handler

    @property
    def skills_handler(self) -> GatewaySkillsHandler | None:
        return self._skills_handler

    @property
    def login_handler(self) -> GatewayLoginHandler | None:
        return self._login_handler

    async def dispatch(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None,
    ) -> JsonObject:
        """Main non-streaming dispatch. Auth is applied BEFORE routing."""
        if not self._config.enabled:
            return _error_response("gateway_disabled", "Gateway is disabled", status=503)

        route = _parse_route(method, path, self._config.base_path)
        if route is None:
            return _error_response("not_found", f"Unknown route: {method} {path}", status=404)

        operation, path_params = route

        body_dict = dict(body) if body is not None else {}

        # The login endpoint is the ONLY route that bypasses require_auth.
        # It is checked BEFORE the auth call — all other routes continue
        # to require authentication.
        if operation == OPERATION_LOGIN:
            if self._login_handler is None:
                return _not_implemented("login")
            try:
                return self._login_handler.handle_login(body_dict)
            except GatewayError as exc:
                return _error_response(exc.code, str(exc), status=exc.status, details=exc.details)

        # Auth is applied BEFORE routing to any handler — no bypass.
        try:
            ctx = self._auth.require_auth(headers)
        except GatewayAuthError as exc:
            return _error_response(exc.code, exc.message, status=exc.status)

        try:
            if operation == OPERATION_CREATE_SESSION:
                return await self._handle_create_session(ctx, body_dict, headers)
            if operation == OPERATION_CREATE_RUN:
                return await self._handle_create_run(ctx, body_dict)
            if operation == OPERATION_CANCEL_RUN:
                return await self._handle_cancel_run(ctx, path_params)
            if operation == OPERATION_GET_SESSION:
                return self._handle_get_session(ctx, path_params)
            if operation == OPERATION_LIST_SESSION_RUNS:
                return self._handle_list_session_runs(ctx, path_params)
            if operation == OPERATION_GET_RUN:
                return self._handle_get_run(ctx, path_params)
            if operation == OPERATION_SUBMIT_ELICITATION:
                return _not_implemented("submit_elicitation")
            if operation == OPERATION_SUBMIT_APPROVAL:
                return _not_implemented("submit_approval")
            if operation == OPERATION_GET_ARTIFACT:
                return await self._handle_get_artifact(ctx, path_params)
            if operation == OPERATION_UPLOAD:
                return await self._handle_upload(ctx, body_dict)
            if operation == OPERATION_SUBMIT_FEEDBACK:
                return await self._handle_submit_feedback(ctx, body_dict)
            if operation == OPERATION_LIST_SKILLS:
                return self._handle_list_skills(ctx, path)
            return _error_response("unknown_operation", f"Unknown operation: {operation}", status=404)
        except GatewayError as exc:
            return _error_response(exc.code, str(exc), status=exc.status, details=exc.details)
        except GatewayAuthError as exc:
            return _error_response(exc.code, exc.message, status=exc.status)

    async def stream(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
    ) -> AsyncIterator[str]:
        """SSE streaming dispatch. Auth is applied BEFORE yielding frames.

        When a ``Last-Event-ID`` header is present and an event buffer is
        configured, buffered events with ``seq > last_event_id`` are replayed
        first (through the output boundary), then live streaming continues.
        Every live event is appended to the event buffer for future
        reconnections.
        """
        if not self._config.enabled:
            raise GatewayDisabledError()

        route = _parse_route(method, path, self._config.base_path)
        if route is None or route[0] != OPERATION_STREAM_RUN:
            raise GatewayError(
                f"Unknown stream route: {method} {path}",
                code="not_found",
                status=404,
            )

        _, path_params = route
        run_id = path_params.get("run_id", "")

        # Auth is applied BEFORE yielding any SSE frames.
        ctx = self._auth.require_auth(headers)

        # Parse Last-Event-ID for reconnection replay.
        last_seq = parse_last_event_id(headers) if self._event_buffer is not None else None

        # Replay buffered events when Last-Event-ID is present.
        if last_seq is not None and self._event_buffer is not None:
            for event in self._event_buffer.replay(run_id, last_seq):
                frame = self._sse_stream.encode_event(event)
                if frame is not None:
                    yield frame

        _assert_runtime_callable(self._runtime, "stream")
        async for event in self._runtime.stream(run_id):  # type: ignore[attr-defined]
            # Append every live event to the buffer for future reconnections.
            if self._event_buffer is not None:
                self._event_buffer.append(run_id, event)
            frame = self._sse_stream.encode_event(event)
            if frame is not None:
                yield frame

    def operations(self) -> tuple[str, ...]:
        return OPERATIONS

    def openapi_operations(self) -> tuple[str, ...]:
        return OPERATIONS

    # -----------------------------------------------------------------------
    # Tracer-critical handlers (fully implemented)
    # -----------------------------------------------------------------------

    async def _handle_create_session(
        self,
        ctx: AuthContext,
        body: Mapping[str, object],
        headers: Mapping[str, str],
    ) -> JsonObject:
        tenant_id = str(body.get("tenant_id") or ctx.tenant_id)
        user_id = str(body.get("user_id") or "unknown")
        conversation_id = str(body.get("conversation_id") or f"conv-{tenant_id}")
        device_id = body.get("device_id")
        if device_id is not None:
            device_id = str(device_id)

        from rbac.roles import Role

        session_id, cookie_value, session = self._session_manager.create_session(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            device_id=device_id,
            role=Role.LAWYER,
        )

        return {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "set_cookie": build_set_cookie_header(cookie_value),
            "status": "ok",
        }

    async def _handle_create_run(
        self,
        ctx: AuthContext,
        body: Mapping[str, object],
    ) -> JsonObject:
        turn_payload = _require_mapping(body, "turn")
        solution_payload = _require_mapping(body, "solution")

        turn = _build_agent_turn(turn_payload)
        solution = _build_solution_binding(solution_payload)
        run_request = _build_run_request(turn, solution, body, ctx.tenant_id)

        _assert_runtime_callable(self._runtime, "create_run")
        run = await self._runtime.create_run(run_request)  # type: ignore[attr-defined]
        result = _serialize_run(run)
        result["tenant_id"] = ctx.tenant_id
        return result

    async def _handle_cancel_run(
        self,
        ctx: AuthContext,
        path_params: dict[str, str],
    ) -> JsonObject:
        run_id = path_params.get("run_id", "")
        if not run_id:
            raise GatewayError(
                "run_id is required",
                code="invalid_request",
                details={"field": "run_id"},
            )
        _assert_runtime_callable(self._runtime, "cancel")
        run = await self._runtime.cancel(run_id)  # type: ignore[attr-defined]
        result = _serialize_run(run)
        result["tenant_id"] = ctx.tenant_id
        return result

    def _handle_get_session(
        self,
        ctx: AuthContext,
        path_params: dict[str, str],
    ) -> JsonObject:
        """Handle GET /v1/sessions/{session_id} — return session info."""
        session_id = path_params.get("session_id", "")
        if not session_id:
            raise GatewayError(
                "session_id is required",
                code="invalid_request",
                details={"field": "session_id"},
            )
        session = self._session_manager.get_session(session_id)
        if session is None:
            raise GatewayError(
                "Session not found",
                code="not_found",
                status=404,
            )
        # Cross-tenant check
        self._auth.check_tenant(ctx, session.tenant_id)
        return serialize_session(session)

    def _handle_list_session_runs(
        self,
        ctx: AuthContext,
        path_params: dict[str, str],
    ) -> JsonObject:
        """Handle GET /v1/sessions/{session_id}/runs — list runs for a session."""
        session_id = path_params.get("session_id", "")
        return handle_list_session_runs_request(
            self._runtime, ctx, self._session_manager, session_id,
        )

    def _handle_get_run(
        self,
        ctx: AuthContext,
        path_params: dict[str, str],
    ) -> JsonObject:
        """Handle GET /v1/runs/{run_id} — return run info."""
        run_id = path_params.get("run_id", "")
        return handle_get_run_request(self._runtime, ctx, run_id)

    # -----------------------------------------------------------------------
    # Upload / Artifact / Feedback handlers (Plan 91-03)
    # -----------------------------------------------------------------------

    async def _handle_upload(
        self,
        ctx: AuthContext,
        body: Mapping[str, object],
    ) -> JsonObject:
        return handle_upload_request(self._upload_handler, ctx, body)

    async def _handle_get_artifact(
        self,
        ctx: AuthContext,
        path_params: dict[str, str],
    ) -> JsonObject:
        artifact_id = path_params.get("artifact_id", "")
        if not artifact_id:
            raise GatewayError(
                "artifact_id is required",
                code="invalid_request",
                details={"field": "artifact_id"},
            )
        return handle_get_artifact_request(self._artifact_store, ctx, artifact_id)

    async def _handle_submit_feedback(
        self,
        ctx: AuthContext,
        body: Mapping[str, object],
    ) -> JsonObject:
        return handle_submit_feedback_request(self._feedback_handler, ctx, body)

    def _handle_list_skills(
        self,
        ctx: AuthContext,
        path: str,
    ) -> JsonObject:
        """Handle GET /v1/skills* — proxy to skill-registry via skills handler."""
        if self._skills_handler is None:
            return _not_implemented("list_skills")
        # Extract query string from path if present.
        query = None
        clean_path = path
        if "?" in path:
            clean_path, query = path.split("?", 1)
        return handle_skills_request(self._skills_handler, ctx, clean_path, query)


# ---------------------------------------------------------------------------
# Path routing
# ---------------------------------------------------------------------------


def _parse_route(method: str, path: str, base_path: str) -> tuple[str, dict[str, str]] | None:
    """Map ``(method, path)`` to ``(operation, path_params)``.

    Strips the ``base_path`` prefix and pattern-matches the remaining path
    to determine the operation and extract path parameters.
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

    # POST /v1/sessions
    if method == "POST" and parts == ["sessions"]:
        return OPERATION_CREATE_SESSION, {}

    # POST /v1/auth/login — unauthenticated login endpoint
    if method == "POST" and parts == ["auth", "login"]:
        return OPERATION_LOGIN, {}

    # GET /v1/sessions/{session_id}
    if method == "GET" and len(parts) == 2 and parts[0] == "sessions":
        return OPERATION_GET_SESSION, {"session_id": parts[1]}

    # GET /v1/sessions/{session_id}/runs
    if method == "GET" and len(parts) == 3 and parts[0] == "sessions" and parts[2] == "runs":
        return OPERATION_LIST_SESSION_RUNS, {"session_id": parts[1]}

    # POST /v1/runs
    if method == "POST" and parts == ["runs"]:
        return OPERATION_CREATE_RUN, {}

    # GET /v1/runs/{run_id}
    if method == "GET" and len(parts) == 2 and parts[0] == "runs":
        return OPERATION_GET_RUN, {"run_id": parts[1]}

    # DELETE /v1/runs/{run_id}
    if method == "DELETE" and len(parts) == 2 and parts[0] == "runs":
        return OPERATION_CANCEL_RUN, {"run_id": parts[1]}

    # GET /v1/runs/{run_id}/events
    if method == "GET" and len(parts) == 3 and parts[0] == "runs" and parts[2] == "events":
        return OPERATION_STREAM_RUN, {"run_id": parts[1]}

    # POST /v1/runs/{run_id}/elicitation
    if method == "POST" and len(parts) == 3 and parts[0] == "runs" and parts[2] == "elicitation":
        return OPERATION_SUBMIT_ELICITATION, {"run_id": parts[1]}

    # POST /v1/runs/{run_id}/approvals
    if method == "POST" and len(parts) == 3 and parts[0] == "runs" and parts[2] == "approvals":
        return OPERATION_SUBMIT_APPROVAL, {"run_id": parts[1]}

    # GET /v1/artifacts/{artifact_id}
    if method == "GET" and len(parts) == 2 and parts[0] == "artifacts":
        return OPERATION_GET_ARTIFACT, {"artifact_id": parts[1]}

    # POST /v1/uploads
    if method == "POST" and parts == ["uploads"]:
        return OPERATION_UPLOAD, {}

    # POST /v1/feedback
    if method == "POST" and parts == ["feedback"]:
        return OPERATION_SUBMIT_FEEDBACK, {}

    # GET /v1/skills
    if method == "GET" and parts == ["skills"]:
        return OPERATION_LIST_SKILLS, {}

    # GET /v1/skills/search
    if method == "GET" and len(parts) == 2 and parts[0] == "skills" and parts[1] == "search":
        return OPERATION_LIST_SKILLS, {}

    # GET /v1/skills/{skill_id}
    if method == "GET" and len(parts) == 2 and parts[0] == "skills":
        return OPERATION_LIST_SKILLS, {"skill_id": parts[1]}

    return None


# ---------------------------------------------------------------------------
# Build helpers (ported from platform_api/app.py)
# ---------------------------------------------------------------------------

_TURN_REQUIRED_FIELDS = (
    "turn_id",
    "conversation_id",
    "channel",
    "user_id",
    "message_type",
    "received_at",
)

_OUTPUT_CONSTRAINT_FIELDS = (
    "format",
    "features",
    "template_ref",
    "citation_style",
    "language_register",
    "must_cite",
)

_ATTACHMENT_FIELDS = (
    "attachment_id",
    "kind",
    "uri",
    "name",
    "mime_type",
)


def _build_agent_turn(payload: Mapping[str, object]) -> AgentTurn:
    for field_name in _TURN_REQUIRED_FIELDS:
        if field_name not in payload:
            raise GatewayError(
                f"turn.{field_name} is required",
                code="invalid_request",
                details={"field": f"turn.{field_name}"},
            )
    output_constraints_payload = payload.get("output_constraints")
    output_constraints = _build_output_constraints(output_constraints_payload) if isinstance(
        output_constraints_payload, Mapping
    ) else None
    attachments_payload = payload.get("attachments") or []
    if not isinstance(attachments_payload, Iterable):
        raise GatewayError(
            "turn.attachments must be a list",
            code="invalid_request",
            details={"field": "turn.attachments"},
        )
    return AgentTurn(
        turn_id=str(payload["turn_id"]),
        conversation_id=str(payload["conversation_id"]),
        channel=str(payload["channel"]),
        user_id=str(payload["user_id"]),
        message_type=str(payload["message_type"]),
        received_at=str(payload["received_at"]),
        content=_optional_string(payload.get("content")),
        attachments=[_build_attachment(item) for item in attachments_payload],
        output_constraints=output_constraints,
        industry_context=dict(payload.get("industry_context") or {}),
        metadata=dict(payload.get("metadata") or {}),
    )


def _build_output_constraints(payload: Mapping[str, object]) -> OutputConstraints:
    must_cite = payload.get("must_cite") or []
    if not isinstance(must_cite, list):
        raise GatewayError(
            "turn.output_constraints.must_cite must be a list",
            code="invalid_request",
            details={"field": "turn.output_constraints.must_cite"},
        )
    features = payload.get("features") or []
    if not isinstance(features, list):
        raise GatewayError(
            "turn.output_constraints.features must be a list",
            code="invalid_request",
            details={"field": "turn.output_constraints.features"},
        )
    return OutputConstraints(
        format=payload.get("format"),
        features=[str(item) for item in features],
        template_ref=_optional_string(payload.get("template_ref")),
        citation_style=_optional_string(payload.get("citation_style")),
        language_register=payload.get("language_register"),
        must_cite=[str(item) for item in must_cite],
        metadata=dict(payload.get("metadata") or {}),
    )


def _build_attachment(payload: object) -> AttachmentRef:
    if not isinstance(payload, Mapping):
        raise GatewayError(
            "turn.attachments entries must be objects",
            code="invalid_request",
            details={"field": "turn.attachments[]"},
        )
    for field_name in _ATTACHMENT_FIELDS[:3]:
        if field_name not in payload:
            raise GatewayError(
                f"turn.attachments[].{field_name} is required",
                code="invalid_request",
                details={"field": f"turn.attachments[].{field_name}"},
            )
    return AttachmentRef(
        attachment_id=str(payload["attachment_id"]),
        kind=str(payload["kind"]),
        uri=str(payload["uri"]),
        name=_optional_string(payload.get("name")),
        mime_type=_optional_string(payload.get("mime_type")),
        metadata=dict(payload.get("metadata") or {}),
    )


def _build_solution_binding(payload: Mapping[str, object]) -> Any:
    if "solution_id" not in payload:
        raise GatewayError(
            "solution.solution_id is required",
            code="invalid_request",
            details={"field": "solution.solution_id"},
        )
    from platform_runtime.protocols import SolutionBinding
    return SolutionBinding(
        solution_id=str(payload["solution_id"]),
        version=_optional_string(payload.get("version")),
        backend_id=_optional_string(payload.get("backend_id")),
        config_ref=_optional_string(payload.get("config_ref")),
        metadata=dict(payload.get("metadata") or {}),
    )


def _build_run_request(
    turn: AgentTurn,
    solution: Any,
    request: Mapping[str, object],
    tenant_id: str,
) -> Any:
    from platform_runtime.protocols import RunRequest
    return RunRequest(
        turn=turn,
        solution=solution,
        tenant_id=tenant_id,
        workspace_id=_optional_string(request.get("workspace_id")),
        bot_instance_id=_optional_string(request.get("bot_instance_id")),
        session_id=_optional_string(request.get("session_id")),
        output_constraints=turn.output_constraints,
        metadata=dict(request.get("metadata") or {}),
    )


# ---------------------------------------------------------------------------
# Serialization (ported from platform_api/app.py)
# ---------------------------------------------------------------------------


def _serialize_run(run: object) -> JsonObject:
    if run is None:
        return {}
    if is_dataclass(run):
        data = asdict(run)
    elif hasattr(run, "__dict__"):
        data = dict(vars(run))
    else:
        data = {"run_id": getattr(run, "run_id", None)}
    status = data.get("status")
    if isinstance(status, AsyncTaskState):
        data["status"] = status.value
    elif hasattr(status, "value"):
        data["status"] = status.value
    result = data.get("result")
    if result is not None and is_dataclass(result):
        data["result"] = _serialize_agent_result(result)
    return data


def _serialize_agent_result(result: object) -> JsonObject:
    data = asdict(result) if is_dataclass(result) else dict(vars(result))
    status = data.get("status")
    if isinstance(status, AgentResultStatus):
        data["status"] = status.value
    elif hasattr(status, "value"):
        data["status"] = status.value
    return data


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _require_mapping(payload: Mapping[str, object], field_name: str) -> Mapping[str, object]:
    value = payload.get(field_name)
    if not isinstance(value, Mapping):
        raise GatewayError(
            f"{field_name} must be an object",
            code="invalid_request",
            details={"field": field_name},
        )
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _assert_runtime_callable(runtime: object, method_name: str) -> None:
    method = getattr(runtime, method_name, None)
    if not callable(method):
        raise GatewayError(
            f"runtime is missing required method: {method_name}",
            code="invalid_runtime",
            status=500,
            details={"method": method_name},
        )


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
    "OPERATION_CANCEL_RUN",
    "OPERATION_CREATE_RUN",
    "OPERATION_CREATE_SESSION",
    "OPERATION_GET_ARTIFACT",
    "OPERATION_GET_RUN",
    "OPERATION_GET_SESSION",
    "OPERATION_LIST_SESSION_RUNS",
    "OPERATION_LIST_SKILLS",
    "OPERATION_LOGIN",
    "OPERATION_STREAM_RUN",
    "OPERATION_SUBMIT_APPROVAL",
    "OPERATION_SUBMIT_ELICITATION",
    "OPERATION_SUBMIT_FEEDBACK",
    "OPERATION_UPLOAD",
    "GatewayApp",
    "GatewayArtifactStore",
    "GatewayDisabledError",
    "GatewayError",
    "GatewayFeedbackHandler",
    "GatewayLoginHandler",
    "GatewaySkillsHandler",
    "GatewayUploadHandler",
]
