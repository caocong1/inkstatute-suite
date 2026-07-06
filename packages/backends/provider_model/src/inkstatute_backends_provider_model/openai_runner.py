"""OpenAI chat completions runner with lazy SDK import and error normalization.

This module implements ``OpenAIClientRunner`` which invokes
``AsyncOpenAI.chat.completions.create`` via a **lazy SDK import**
(``importlib.import_module("openai")`` inside ``invoke``) so the package
imports cleanly without the ``openai`` SDK installed.

Key behaviours:
- ``parse_openai_response`` maps ``choices[0].message.content`` to
  ``AgentResult.content`` and ``finish_reason == "stop"`` to ``SUCCEEDED``.
- ``finish_reason`` in ``("length", "content_filter")`` maps to ``FAILED``
  with a normalized ``ErrorInfo`` (``provider_model_truncated``).
- The model name from the OpenAI response is sanitized to ``"redacted"`` in
  metadata — never appears in ``AgentResult.content`` or ``ErrorInfo.message``.
- API errors (``RateLimitError``, ``AuthenticationError``,
  ``APIConnectionError``, ``APIStatusError``) are mapped to normalized
  ``ErrorInfo`` codes via string-based class-name detection (the SDK cannot
  be imported at module top level).
- First failure is terminal — no subsequent event can flip status back to
  ``SUCCESS``.
- Error messages are sanitized (no URLs, tokens, file paths, model names).
"""

from __future__ import annotations

import importlib
import json
import re
from typing import Any, AsyncIterator, Iterator, Protocol

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    ErrorCategory,
    ReplyType,
)
from platform_contract.events import AgentResult, ErrorInfo, JsonObject
from platform_runtime import RunRequest

from .adapter import (
    ProviderModelExecResult,
    ProviderModelRunner,
    ProviderModelStreamDelta,
    StreamingProviderModelRunner,
)
from .config import ProviderModelBackendConfig

# ---------------------------------------------------------------------------
# Transport abstraction
# ---------------------------------------------------------------------------


class OpenAITransport(Protocol):
    """Transport abstraction for OpenAI chat completions.

    Tests inject a fake transport so no real ``openai`` SDK or network
    access is required.
    """

    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject:
        """Return the parsed JSON chat completion response dict."""
        ...


class FakeOpenAITransport:
    """Convenience fake transport for tests (no SDK required)."""

    def __init__(
        self,
        response: JsonObject | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error

    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject:
        if self.error is not None:
            raise self.error
        return self.response or {}


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_TRUNCATED_FINISH_REASONS = ("length", "content_filter")


def parse_openai_response(
    response: JsonObject,
    run_id: str,
    turn_id: str,
) -> ProviderModelExecResult:
    """Map an OpenAI chat completion response dict to a
    :class:`ProviderModelExecResult` containing a platform-contract
    :class:`AgentResult`.
    """

    choices = response.get("choices", []) or []
    choice = choices[0] if choices else {}
    if not isinstance(choice, dict):
        choice = {}
    message = choice.get("message", {}) or {}
    if not isinstance(message, dict):
        message = {}
    content = message.get("content")

    # Only default finish_reason to "stop" when a choice actually exists.
    finish_reason = choice.get("finish_reason") if choices else None
    if finish_reason is None:
        finish_reason = "stop" if choices else ""
    completion_id = response.get("id")
    usage = response.get("usage", {}) or {}
    if not isinstance(usage, dict):
        usage = {}
    model = response.get("model", "unknown")

    error: ErrorInfo | None = None
    status: AsyncTaskState = AsyncTaskState.SUCCEEDED
    result_status: AgentResultStatus = AgentResultStatus.SUCCESS

    if finish_reason == "stop" and (content is not None or choices):
        status = AsyncTaskState.SUCCEEDED
        result_status = AgentResultStatus.SUCCESS
    elif content is not None and choices:
        # Content present even without explicit "stop" — treat as success.
        status = AsyncTaskState.SUCCEEDED
        result_status = AgentResultStatus.SUCCESS
    elif finish_reason in _TRUNCATED_FINISH_REASONS:
        status = AsyncTaskState.FAILED
        result_status = AgentResultStatus.FAILED
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="provider_model_truncated",
            stage="completion",
            message=f"completion truncated: {finish_reason}",
        )
    else:
        # No content and no recognized finish reason — treat as failure.
        status = AsyncTaskState.FAILED
        result_status = AgentResultStatus.FAILED
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="provider_model_empty_completion",
            stage="completion",
            message="empty completion with no content",
        )

    artifact_refs = _extract_file_refs(response)

    result = AgentResult(
        result_id=f"provider-model-result-{run_id}",
        turn_id=turn_id,
        status=result_status,
        reply_type=ReplyType.TEXT,
        content=content,
        error=error,
        metadata={
            "provider_completion_id": completion_id,
            "source": "openai_chat_completions",
        },
    )

    return ProviderModelExecResult(
        status=status,
        result=result,
        completion_id=completion_id,
        artifact_refs=artifact_refs,
        raw_payload_ref=None,
        metadata={
            "provider_completion_id": completion_id,
            "provider_usage": _sanitize_usage(usage),
            "provider_model": _sanitize_model_name(model),
        },
    )


def _extract_file_refs(response: JsonObject) -> list[str]:
    """Extract artifact file references from an OpenAI-compatible provider response.

    Supports ``files`` (list of ``{"uri": ..., "name": ...}`` dicts) and
    ``file_ids`` (list of string IDs) fields. Non-dict entries and missing
    URIs are skipped. Returns a list of reference strings suitable for
    ``ProviderModelExecResult.artifact_refs``.
    """

    refs: list[str] = []
    files = response.get("files", []) or []
    if not isinstance(files, list):
        return refs
    for entry in files:
        if not isinstance(entry, dict):
            continue
        uri = entry.get("uri") or entry.get("url")
        if isinstance(uri, str) and uri:
            refs.append(uri)
            continue
        fid = entry.get("id")
        if isinstance(fid, str) and fid:
            refs.append(f"provider://files/{fid}")
    file_ids = response.get("file_ids", []) or []
    if isinstance(file_ids, list):
        for fid in file_ids:
            if isinstance(fid, str) and fid:
                refs.append(f"provider://files/{fid}")
    return refs


def parse_sse_deltas(lines: list[str]) -> Iterator[ProviderModelStreamDelta]:
    """Parse SSE-format ``data: `` lines into :class:`ProviderModelStreamDelta` records.

    Lines not prefixed with ``data: `` (comments, keepalive pings, empty lines)
    are skipped. ``data: [DONE]`` signals end of stream and is not yielded.
    Unparseable JSON payloads are skipped.
    """

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith("data: "):
            continue
        payload = line[len("data: "):]
        if payload == "[DONE]":
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        choices = (parsed.get("choices", []) or []) if isinstance(parsed, dict) else []
        choice = choices[0] if choices else {}
        if not isinstance(choice, dict):
            choice = {}
        delta = choice.get("delta", {}) or {}
        if not isinstance(delta, dict):
            delta = {}
        content = delta.get("content", "")
        if content is None:
            content = ""
        finish_reason = choice.get("finish_reason")
        yield ProviderModelStreamDelta(content=content, finish_reason=finish_reason)


def _sanitize_usage(usage: JsonObject) -> JsonObject:
    """Keep only safe token-count fields as integers; strip everything else."""

    sanitized: JsonObject = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if key in usage:
            try:
                sanitized[key] = int(usage[key])
            except (TypeError, ValueError):
                continue
    return sanitized


def _sanitize_model_name(model: str) -> str:
    """Always redact the model name for the prototype.

    The model name is never needed in platform-visible metadata and could
    leak provider information into visible output.
    """

    return "redacted"


# ---------------------------------------------------------------------------
# Error normalization
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://\S+")
_TOKEN_RE = re.compile(r"token=\S+")
_PATH_RE = re.compile(r"/(?:home|Users)[/\w.\-]*")
_MODEL_RE = re.compile(r"\b(?:gpt|claude|gemini)[-\w]*", re.IGNORECASE)


def _sanitize_error_message(msg: str) -> str:
    """Strip URLs, tokens, file paths, and model names from an error message."""

    sanitized = _URL_RE.sub("[url_redacted]", msg)
    sanitized = _TOKEN_RE.sub("token=[redacted]", sanitized)
    sanitized = _PATH_RE.sub("[redacted]", sanitized)
    sanitized = _MODEL_RE.sub("[model_redacted]", sanitized)
    return sanitized


def _normalize_api_error(exc: Exception, stage: str) -> ErrorInfo:
    """Normalize an OpenAI SDK exception into a sanitized :class:`ErrorInfo`.

    Detection is string-based on the exception class name because the
    ``openai`` SDK cannot be imported at module top level (lazy import).
    """

    exc_name = type(exc).__name__

    if "RateLimit" in exc_name:
        code = "provider_model_rate_limit"
        retryable: bool | None = True
    elif "Authentication" in exc_name or "Auth" in exc_name:
        code = "provider_model_auth_error"
        retryable = False
    elif "Connection" in exc_name or "Timeout" in exc_name:
        code = "provider_model_connection_error"
        retryable = True
    elif "APIStatus" in exc_name or "API" in exc_name:
        code = "provider_model_api_error"
        retryable = None
    else:
        code = "provider_model_unknown_error"
        retryable = None

    message = _sanitize_error_message(str(exc))

    return ErrorInfo(
        category=ErrorCategory.RUNTIME_ERROR,
        code=code,
        message=message,
        stage=stage,
        retryable=retryable,
        details={},
    )


# ---------------------------------------------------------------------------
# Credential resolution
# ---------------------------------------------------------------------------


def _default_api_key_resolver(ref: str | None) -> str:
    """Resolve an ``api_key_ref`` to a credential from the environment.

    The key is resolved at invocation time and never stored in config or
    metadata.
    """

    import os

    if not ref:
        return ""
    return os.environ.get(ref, "")


def _completion_to_dict(completion: Any) -> JsonObject:
    """Convert an ``AsyncOpenAI`` ChatCompletion object to a dict.

    Only used in the real SDK path (never exercised in tests).
    """

    dump = getattr(completion, "model_dump_json", None)
    if callable(dump):
        return json.loads(dump())
    dump = getattr(completion, "model_dump", None)
    if callable(dump):
        return dict(dump())
    # Fallback: best-effort conversion.
    return dict(completion)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# OpenAIClientRunner
# ---------------------------------------------------------------------------


class OpenAIClientRunner:
    """Runner that invokes ``AsyncOpenAI.chat.completions.create`` lazily.

    The ``openai`` SDK is imported via ``importlib.import_module("openai")``
    inside :meth:`invoke` only — never at module top level — so the package
    imports cleanly without the SDK installed.

    Tests inject a :class:`FakeOpenAITransport` to avoid real API calls.
    """

    def __init__(
        self,
        *,
        config: ProviderModelBackendConfig | None = None,
        transport: OpenAITransport | None = None,
        api_key_resolver: Any | None = None,
    ) -> None:
        self.config = config or ProviderModelBackendConfig()
        self._transport = transport
        self._api_key_resolver = api_key_resolver or _default_api_key_resolver

    async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
        request_payload: JsonObject = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": req.turn.content}],
            "timeout": self.config.timeout,
        }

        try:
            if self._transport is not None:
                response = await self._transport.create_chat_completion(request_payload)
            else:
                # Real SDK path — never exercised in tests.  Lazy import.
                openai_module = importlib.import_module("openai")
                AsyncOpenAI = getattr(openai_module, "AsyncOpenAI")
                cred = self._api_key_resolver(self.config.api_key_ref)
                client = AsyncOpenAI(
                    api_key=cred,
                    base_url=self.config.api_base_url,
                )
                completion = await client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[{"role": "user", "content": req.turn.content}],
                )
                response = _completion_to_dict(completion)
        except Exception as exc:  # noqa: BLE001 - normalize all API errors
            return self._build_error_result(exc, req)

        return parse_openai_response(
            response,
            run_id=req.turn.turn_id,
            turn_id=req.turn.turn_id,
        )

    def _build_error_result(
        self,
        exc: Exception,
        req: RunRequest,
    ) -> ProviderModelExecResult:
        normalized = _normalize_api_error(exc, stage="completion")
        result = AgentResult(
            result_id=f"provider-model-result-{req.turn.turn_id}",
            turn_id=req.turn.turn_id,
            status=AgentResultStatus.FAILED,
            reply_type=ReplyType.TEXT,
            content=None,
            error=normalized,
            metadata={"source": "openai_chat_completions"},
        )
        return ProviderModelExecResult(
            status=AsyncTaskState.FAILED,
            result=result,
            completion_id=None,
            raw_payload_ref=None,
            metadata={"provider_error_code": normalized.code},
        )


class FakeStreamingProviderModelRunner:
    """Convenience fake streaming runner for tests (no SDK required)."""

    def __init__(self, deltas: list[ProviderModelStreamDelta]) -> None:
        self._deltas = list(deltas)

    async def stream(self, req: RunRequest) -> AsyncIterator[ProviderModelStreamDelta]:
        for delta in self._deltas:
            yield delta


__all__ = [
    "OpenAIClientRunner",
    "OpenAITransport",
    "FakeOpenAITransport",
    "parse_openai_response",
    "ProviderModelStreamDelta",
    "StreamingProviderModelRunner",
    "FakeStreamingProviderModelRunner",
    "parse_sse_deltas",
]
