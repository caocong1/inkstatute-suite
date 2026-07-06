"""Subprocess-based Codex exec runner with JSONL parsing and error normalization.

This module implements ``SubprocessCodexExecRunner`` which invokes the Codex
execution subcommand via ``subprocess`` and parses JSONL output into a
``CodexExecResult`` containing a platform-contract ``AgentResult``.

Key behaviours:
- ``parse_codex_jsonl`` reads JSONL lines, extracts the final
  ``agent_message``/``assistant_message`` item text as ``AgentResult.content``.
- ``turn.completed`` maps to ``SUCCEEDED``; the first ``turn.failed`` or
  ``error`` event maps to ``FAILED`` with a normalized ``ErrorInfo``.
- First failure is terminal — no subsequent event can flip status back to
  ``SUCCESS``.
- Field-name aliases are handled: ``item.type`` vs ``item.item_type``,
  ``assistant_message`` vs ``agent_message``.
- Error messages and details are sanitized (no URLs, tokens, raw payloads,
  file paths).
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any, AsyncIterator, Iterator, Protocol

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    ErrorCategory,
    ReplyType,
    RunEventType,
)
from platform_contract.events import AgentResult, ErrorInfo, JsonObject
from platform_runtime import RunRequest

from .adapter import CodexExecResult, CodexExecRunner, CodexStreamEvent, StreamingCodexExecRunner
from .config import CodexBackendConfig

# ---------------------------------------------------------------------------
# Subprocess transport
# ---------------------------------------------------------------------------


class SubprocessTransport(Protocol):
    """Transport abstraction for running the Codex subprocess."""

    def run(
        self,
        command: tuple[str, ...],
        input_text: str | None,
        timeout: float | None,
    ) -> tuple[int, str, str]:
        """Return ``(returncode, stdout, stderr)``."""
        ...


class _SystemSubprocessTransport:
    """Default transport using :func:`subprocess.run`."""

    def run(
        self,
        command: tuple[str, ...],
        input_text: str | None,
        timeout: float | None,
    ) -> tuple[int, str, str]:
        completed = subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (completed.returncode, completed.stdout, completed.stderr)


# ---------------------------------------------------------------------------
# JSONL parsing
# ---------------------------------------------------------------------------

_MESSAGE_ITEM_TYPES = ("assistant_message", "agent_message")
_SENSITIVE_DETAIL_KEYS = frozenset({
    "raw_payload",
    "content",
    "transcript",
    "prompt",
    "response_body",
})
_SENSITIVE_DETAIL_SUBSTRINGS = ("secret", "token", "profile_path")

_URL_RE = re.compile(r"https?://\S+")
_TOKEN_RE = re.compile(r"token=\S+")
_PATH_RE = re.compile(r"/(?:home|Users)[/\w.\-]*|/\.codex[/\w.\-]*")


def parse_codex_jsonl(
    lines: list[str],
    run_id: str,
    turn_id: str,
) -> CodexExecResult:
    """Parse Codex JSONL stdout lines into a :class:`CodexExecResult`.

    The parser scans events in order. The first ``turn.failed`` or ``error``
    event is terminal — subsequent events cannot flip the status back to
    ``SUCCESS``.
    """

    content: str | None = None
    status: AsyncTaskState | None = None
    error: ErrorInfo | None = None
    thread_id: str | None = None
    usage: JsonObject = {}
    unparsed: list[str] = []
    failed = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            unparsed.append(line)
            continue

        event_type = event.get("type")

        if event_type == "thread.started":
            thread_id = event.get("thread_id")

        if event_type in ("item.completed", "item.updated"):
            item = event.get("item", {})
            if not isinstance(item, dict):
                item = {}
            item_type = item.get("type") or item.get("item_type")
            if item_type in _MESSAGE_ITEM_TYPES:
                content = item.get("text") or item.get("content")

        if event_type == "turn.completed" and not failed:
            status = AsyncTaskState.SUCCEEDED
            usage = event.get("usage", {})

        if event_type == "turn.failed" and not failed:
            failed = True
            status = AsyncTaskState.FAILED
            error = _normalize_error(event, stage="turn")

        if event_type == "error" and not failed:
            failed = True
            status = AsyncTaskState.FAILED
            error = _normalize_error(event, stage="stream")

    # After the loop: if no terminal event was seen, treat as a contract error.
    if status is None:
        status = AsyncTaskState.FAILED
        error = ErrorInfo(
            category=ErrorCategory.CONTRACT_ERROR,
            code="codex_empty_stream",
            stage="parse",
            message="no terminal event in codex jsonl stream",
        )

    result_status = (
        AgentResultStatus.SUCCESS
        if status == AsyncTaskState.SUCCEEDED
        else AgentResultStatus.FAILED
    )
    result = AgentResult(
        result_id=f"codex-result-{run_id}",
        turn_id=turn_id,
        status=result_status,
        reply_type=ReplyType.TEXT,
        content=content,
        error=error,
        metadata={
            "codex_thread_id": thread_id,
            "codex_usage": usage,
            "source": "codex_exec",
        },
    )

    return CodexExecResult(
        status=status,
        result=result,
        thread_id=thread_id,
        raw_payload_ref=None,
        metadata={
            "codex_thread_id": thread_id,
            "codex_usage": usage,
            "codex_unparsed_lines": unparsed[:5],
        },
    )


def parse_codex_jsonl_stream(lines: list[str]) -> Iterator[CodexStreamEvent]:
    """Parse Codex JSONL lines into a stream of :class:`CodexStreamEvent` records.

    Unlike :func:`parse_codex_jsonl` which collects a final result, this
    generator yields intermediate events as each line is parsed:

    - ``item.completed``/``item.updated`` with message item types yield
      ``MESSAGE_DELTA`` events.
    - ``turn.completed`` yields a ``STATE_CHANGED`` event with ``SUCCEEDED``.
    - ``turn.failed`` yields a ``STATE_CHANGED`` event with ``FAILED`` and
      a sanitized error.
    - ``error`` yields a ``STATE_CHANGED`` event with ``FAILED`` and a
      sanitized error.
    - ``thread.started``, empty lines, and unparseable lines are skipped.
    """

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        event_type = event.get("type")

        if event_type in ("item.completed", "item.updated"):
            item = event.get("item", {})
            if not isinstance(item, dict):
                item = {}
            item_type = item.get("type") or item.get("item_type")
            if item_type in _MESSAGE_ITEM_TYPES:
                item_text = item.get("text") or item.get("content")
                yield CodexStreamEvent(
                    event_type=RunEventType.MESSAGE_DELTA.value,
                    payload={"message_delta": item_text},
                )

        if event_type == "turn.completed":
            yield CodexStreamEvent(
                event_type=RunEventType.STATE_CHANGED.value,
                payload={"status": AsyncTaskState.SUCCEEDED.value},
            )

        if event_type == "turn.failed":
            yield CodexStreamEvent(
                event_type=RunEventType.STATE_CHANGED.value,
                payload={
                    "status": AsyncTaskState.FAILED.value,
                    "error": _normalize_error(event, stage="turn"),
                },
            )

        if event_type == "error":
            yield CodexStreamEvent(
                event_type=RunEventType.STATE_CHANGED.value,
                payload={
                    "status": AsyncTaskState.FAILED.value,
                    "error": _normalize_error(event, stage="stream"),
                },
            )


# ---------------------------------------------------------------------------
# Error normalization
# ---------------------------------------------------------------------------


def _normalize_error(event: dict[str, Any], stage: str) -> ErrorInfo:
    """Normalize a Codex failure event into a sanitized :class:`ErrorInfo`."""

    error_obj = event.get("error", {})
    if not isinstance(error_obj, dict):
        error_obj = {}

    message = event.get("message", "")
    if not message and isinstance(error_obj, dict):
        message = error_obj.get("message", "")
    if not message:
        message = ""
    message = str(message)

    error_kind = str(error_obj.get("kind", "")) if isinstance(error_obj, dict) else ""
    message_lower = message.lower()

    if "rate_limit" in error_kind or "rate limit" in message_lower:
        code = "codex_rate_limit"
        retryable: bool | None = True
    elif "auth" in error_kind or "auth" in message_lower:
        code = "codex_auth_error"
        retryable = False
    elif stage == "turn":
        code = "codex_turn_failed"
        retryable = None
    else:
        code = "codex_stream_error"
        retryable = None

    sanitized_details = _sanitize_error_details(error_obj)

    return ErrorInfo(
        category=ErrorCategory.RUNTIME_ERROR,
        code=code,
        message=_sanitize_message(message),
        stage=stage,
        retryable=retryable,
        details=sanitized_details,
    )


def _sanitize_message(msg: str) -> str:
    """Strip URLs, tokens, and file paths from an error message string."""

    sanitized = _URL_RE.sub("[url_redacted]", msg)
    sanitized = _TOKEN_RE.sub("token=[redacted]", sanitized)
    sanitized = _PATH_RE.sub("[redacted]", sanitized)
    return sanitized


def _sanitize_error_details(details: dict[str, Any]) -> JsonObject:
    """Sanitize error detail keys, reusing the adapter sanitization pattern."""

    sanitized: JsonObject = {}
    for key, value in details.items():
        lowered = key.lower()
        if lowered in _SENSITIVE_DETAIL_KEYS:
            continue
        if any(sub in lowered for sub in _SENSITIVE_DETAIL_SUBSTRINGS):
            continue
        sanitized[key] = _sanitize_detail_value(value)
    return sanitized


def _sanitize_detail_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _sanitize_error_details(value)
    if isinstance(value, list):
        return [_sanitize_detail_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_message(value)
    return value


# ---------------------------------------------------------------------------
# SubprocessCodexExecRunner
# ---------------------------------------------------------------------------


class SubprocessCodexExecRunner:
    """Concrete runner that invokes the Codex subprocess and parses JSONL."""

    def __init__(
        self,
        config: CodexBackendConfig | None = None,
        transport: SubprocessTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.config = config or CodexBackendConfig()
        self.transport = transport or _SystemSubprocessTransport()
        self.timeout = timeout

    async def invoke(self, req: RunRequest) -> CodexExecResult:
        command = list(self.config.exec_command) + [req.turn.content or ""]
        try:
            returncode, stdout, stderr = self.transport.run(
                tuple(command),
                input_text=None,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return CodexExecResult(
                status=AsyncTaskState.FAILED,
                result=AgentResult(
                    result_id=f"codex-result-exec",
                    turn_id=req.turn.turn_id,
                    status=AgentResultStatus.FAILED,
                    reply_type=ReplyType.TEXT,
                    error=ErrorInfo(
                        category=ErrorCategory.RUNTIME_ERROR,
                        code="codex_exec_timeout",
                        stage="exec",
                        message="codex exec timed out",
                        retryable=True,
                    ),
                    metadata={"source": "codex_exec"},
                ),
                thread_id=None,
                metadata={"codex_usage": {}},
            )

        lines = stdout.splitlines()
        result = parse_codex_jsonl(lines, run_id="exec", turn_id=req.turn.turn_id)

        # Override to nonzero-exit error when the subprocess exited non-zero
        # AND no real failure event (turn.failed/error) was found.  We detect
        # "no real failure event" by checking for the codex_empty_stream code
        # which the parser assigns when no terminal event was seen.
        no_real_failure = (
            result.status != AsyncTaskState.FAILED
            or (result.result is not None
                and result.result.error is not None
                and result.result.error.code == "codex_empty_stream")
        )
        if returncode != 0 and no_real_failure:
            result = CodexExecResult(
                status=AsyncTaskState.FAILED,
                result=AgentResult(
                    result_id=result.result.result_id if result.result else "codex-result-exec",
                    turn_id=req.turn.turn_id,
                    status=AgentResultStatus.FAILED,
                    reply_type=ReplyType.TEXT,
                    content=result.result.content if result.result else None,
                    error=ErrorInfo(
                        category=ErrorCategory.RUNTIME_ERROR,
                        code="codex_exec_nonzero_exit",
                        stage="exec",
                        message=f"codex exec exited with code {returncode}",
                    ),
                    metadata=result.result.metadata if result.result else {},
                ),
                thread_id=result.thread_id,
                metadata=result.metadata,
            )

        return result


class FakeStreamingCodexRunner:
    """Test helper that yields a pre-configured list of CodexStreamEvent records."""

    def __init__(self, events: list[CodexStreamEvent]) -> None:
        self._events = list(events)

    async def stream(self, req: RunRequest) -> AsyncIterator[CodexStreamEvent]:
        for event in self._events:
            yield event


__all__ = [
    "CodexStreamEvent",
    "FakeStreamingCodexRunner",
    "StreamingCodexExecRunner",
    "SubprocessCodexExecRunner",
    "SubprocessTransport",
    "parse_codex_jsonl",
    "parse_codex_jsonl_stream",
]
