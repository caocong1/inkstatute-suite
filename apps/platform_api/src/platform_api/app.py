"""Pure HTTP/SSE-shaped handlers for the InkStatute platform API host.

The handlers are intentionally framework-free: they accept plain dictionaries
and return plain dictionaries (or SSE-shaped frame dictionaries) suitable for
any ASGI/WSGI/starlette/fastapi adapter. The :class:`PlatformApiApp` container
exposes a single ``dispatch`` method that routes by operation name and an
explicit ``stream`` method for SSE consumers.

No ASGI/WSGI server is started by this module, no production queue is used,
and no secret material is read at runtime.
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

from .config import PlatformApiConfig

JsonObject = dict[str, Any]

OPERATION_CREATE_RUN = "create_run"
OPERATION_POLL_RUN = "poll_run"
OPERATION_CANCEL_RUN = "cancel_run"
OPERATION_SUBMIT_APPROVAL = "submit_approval"
OPERATION_STREAM_RUN = "stream_run"

OPERATIONS: tuple[str, ...] = (
    OPERATION_CREATE_RUN,
    OPERATION_POLL_RUN,
    OPERATION_CANCEL_RUN,
    OPERATION_SUBMIT_APPROVAL,
    OPERATION_STREAM_RUN,
)

# Field name sets used to validate and translate between request dicts and
# platform-contract dataclasses. The platform contract bindings remain the
# source of truth; the API surface only describes their dict shape.
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

_APPROVAL_REQUIRED_FIELDS = (
    "approval_id",
    "decision",
)

# SSE frame constants keep the channel/web_chat renderers and the API host in
# lock-step. The ``data`` payload is JSON serialized by the consumer adapter.
SSE_EVENT_RUN = "run_event"
SSE_EVENT_RUN_COMPLETED = "run_completed"


class PlatformApiError(RuntimeError):
    """Base error for the platform API host."""

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


class PlatformApiDisabledError(PlatformApiError):
    """Raised when the platform API host is invoked while disabled."""

    def __init__(self, message: str = "platform_api disabled") -> None:
        super().__init__(message, code="platform_api_disabled", status=503)


class PlatformApiApp:
    """Thin host container that delegates to an injected runtime."""

    def __init__(
        self,
        config: PlatformApiConfig,
        *,
        runtime: object,
    ) -> None:
        self._config = config
        self._runtime = runtime

    @property
    def config(self) -> PlatformApiConfig:
        return self._config

    @property
    def runtime(self) -> object:
        return self._runtime

    async def dispatch(self, operation: str, request: Mapping[str, object]) -> JsonObject:
        """Dispatch a non-streaming operation by name and return a JSON dict."""
        if not self._config.enabled:
            raise PlatformApiDisabledError()
        if operation == OPERATION_CREATE_RUN:
            return await handle_create_run(self._runtime, request)
        if operation == OPERATION_POLL_RUN:
            return await handle_poll_run(self._runtime, request)
        if operation == OPERATION_CANCEL_RUN:
            return await handle_cancel_run(self._runtime, request)
        if operation == OPERATION_SUBMIT_APPROVAL:
            return await handle_submit_approval(self._runtime, request)
        raise PlatformApiError(
            f"unknown operation: {operation}",
            code="unknown_operation",
            status=404,
            details={"operation": operation},
        )

    async def stream(self, request: Mapping[str, object]) -> AsyncIterator[JsonObject]:
        """Yield SSE-shaped frame dicts for a stream run operation."""
        if not self._config.enabled:
            raise PlatformApiDisabledError()
        if "run_id" not in request or not isinstance(request["run_id"], str):
            raise PlatformApiError(
                "stream_run requires a string 'run_id'",
                code="invalid_request",
                details={"field": "run_id"},
            )
        run_id = str(request["run_id"])
        async for frame in handle_stream_run(self._runtime, run_id):
            yield frame

    def operations(self) -> tuple[str, ...]:
        return OPERATIONS

    def openapi_operations(self) -> tuple[str, ...]:
        return OPERATIONS


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------


async def handle_create_run(runtime: object, request: Mapping[str, object]) -> JsonObject:
    turn_payload = _require_mapping(request, "turn")
    solution_payload = _require_mapping(request, "solution")
    if "turn_id" not in turn_payload:
        raise PlatformApiError(
            "turn.turn_id is required",
            code="invalid_request",
            details={"field": "turn.turn_id"},
        )

    turn = _build_agent_turn(turn_payload)
    solution = _build_solution_binding(solution_payload)

    run_request = _build_run_request(turn, solution, request)

    _assert_runtime_callable(runtime, "create_run")
    run = await runtime.create_run(run_request)  # type: ignore[attr-defined]
    return _serialize_run(run)


async def handle_poll_run(runtime: object, request: Mapping[str, object]) -> JsonObject:
    run_id = _require_string(request, "run_id")
    _assert_runtime_callable(runtime, "poll")
    run = await runtime.poll(run_id)  # type: ignore[attr-defined]
    return _serialize_run(run)


async def handle_cancel_run(runtime: object, request: Mapping[str, object]) -> JsonObject:
    run_id = _require_string(request, "run_id")
    _assert_runtime_callable(runtime, "cancel")
    run = await runtime.cancel(run_id)  # type: ignore[attr-defined]
    return _serialize_run(run)


async def handle_submit_approval(runtime: object, request: Mapping[str, object]) -> JsonObject:
    run_id = _require_string(request, "run_id")
    approval_payload = _require_mapping(request, "approval")
    for field_name in _APPROVAL_REQUIRED_FIELDS:
        if field_name not in approval_payload:
            raise PlatformApiError(
                f"approval.{field_name} is required",
                code="invalid_request",
                details={"field": f"approval.{field_name}"},
            )
    approval = _build_approval(approval_payload)
    _assert_runtime_callable(runtime, "approve")
    run = await runtime.approve(run_id, approval)  # type: ignore[attr-defined]
    return _serialize_run(run)


async def handle_stream_run(runtime: object, run_id: str) -> AsyncIterator[JsonObject]:
    _assert_runtime_callable(runtime, "stream")
    async for event in runtime.stream(run_id):  # type: ignore[attr-defined]
        frame = _serialize_run_event(event)
        yield frame
    yield {
        "event": SSE_EVENT_RUN_COMPLETED,
        "id": f"run-{run_id}-completed",
        "data": _stable_json({"run_id": run_id, "completed": True}),
    }


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------


def _build_agent_turn(payload: Mapping[str, object]) -> AgentTurn:
    for field_name in _TURN_REQUIRED_FIELDS:
        if field_name not in payload:
            raise PlatformApiError(
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
        raise PlatformApiError(
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
    for field_name in _OUTPUT_CONSTRAINT_FIELDS:
        if field_name in payload:
            continue
    must_cite = payload.get("must_cite") or []
    if not isinstance(must_cite, list):
        raise PlatformApiError(
            "turn.output_constraints.must_cite must be a list",
            code="invalid_request",
            details={"field": "turn.output_constraints.must_cite"},
        )
    features = payload.get("features") or []
    if not isinstance(features, list):
        raise PlatformApiError(
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
        raise PlatformApiError(
            "turn.attachments entries must be objects",
            code="invalid_request",
            details={"field": "turn.attachments[]"},
        )
    for field_name in _ATTACHMENT_FIELDS[:3]:
        if field_name not in payload:
            raise PlatformApiError(
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
        raise PlatformApiError(
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
) -> Any:
    from platform_runtime.protocols import RunRequest
    return RunRequest(
        turn=turn,
        solution=solution,
        tenant_id=_optional_string(request.get("tenant_id")),
        workspace_id=_optional_string(request.get("workspace_id")),
        bot_instance_id=_optional_string(request.get("bot_instance_id")),
        session_id=_optional_string(request.get("session_id")),
        output_constraints=turn.output_constraints,
        metadata=dict(request.get("metadata") or {}),
    )


def _build_approval(payload: Mapping[str, object]) -> Any:
    from platform_runtime.protocols import Approval
    return Approval(
        approval_id=str(payload["approval_id"]),
        decision=str(payload["decision"]),
        decided_by=_optional_string(payload.get("decided_by")),
        decided_at=_optional_string(payload.get("decided_at")),
        metadata=dict(payload.get("metadata") or {}),
    )


# ---------------------------------------------------------------------------
# Serialization
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
    result = data.get("result")
    if result is not None and is_dataclass(result):
        data["result"] = _serialize_agent_result(result)
    return data


def _serialize_agent_result(result: object) -> JsonObject:
    data = asdict(result) if is_dataclass(result) else dict(vars(result))
    status = data.get("status")
    if isinstance(status, AgentResultStatus):
        data["status"] = status.value
    return data


def _serialize_run_event(event: object) -> JsonObject:
    if is_dataclass(event):
        data = asdict(event)
    elif hasattr(event, "__dict__"):
        data = dict(vars(event))
    else:
        data = {"event": str(event)}
    event_type = data.get("event_type")
    if isinstance(event_type, RunEventType):
        data["event_type"] = event_type.value
    payload = data.get("payload") or {}
    status = payload.get("status") if isinstance(payload, dict) else None
    if isinstance(status, AsyncTaskState):
        payload = {**payload, "status": status.value}
    if isinstance(payload, dict):
        data["payload"] = payload
    return {
        "event": SSE_EVENT_RUN,
        "id": str(data.get("event_id") or ""),
        "data": _stable_json(data),
    }


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _require_mapping(payload: Mapping[str, object], field_name: str) -> Mapping[str, object]:
    value = payload.get(field_name)
    if not isinstance(value, Mapping):
        raise PlatformApiError(
            f"{field_name} must be an object",
            code="invalid_request",
            details={"field": field_name},
        )
    return value


def _require_string(payload: Mapping[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise PlatformApiError(
            f"{field_name} must be a non-empty string",
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
        raise PlatformApiError(
            f"runtime is missing required method: {method_name}",
            code="invalid_runtime",
            status=500,
            details={"method": method_name},
        )


def _stable_json(payload: Mapping[str, object] | list[object]) -> str:
    import json
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


__all__ = [
    "OPERATION_CANCEL_RUN",
    "OPERATION_CREATE_RUN",
    "OPERATION_POLL_RUN",
    "OPERATION_STREAM_RUN",
    "OPERATION_SUBMIT_APPROVAL",
    "OPERATIONS",
    "PlatformApiApp",
    "PlatformApiDisabledError",
    "PlatformApiError",
    "SSE_EVENT_RUN",
    "SSE_EVENT_RUN_COMPLETED",
    "handle_cancel_run",
    "handle_create_run",
    "handle_poll_run",
    "handle_stream_run",
    "handle_submit_approval",
]
