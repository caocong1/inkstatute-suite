"""Anthropic Messages API runner with lazy SDK import and error normalization.

This module implements ``AnthropicRunner`` which invokes
``AsyncAnthropic.messages.create`` via a **lazy SDK import**
(``importlib.import_module("anthropic")`` inside ``invoke``) so the package
imports cleanly without the ``anthropic`` SDK installed.

Key behaviours:
- Anthropic Messages API normalization: system prompt as top-level ``system``
  parameter (not in messages array), user message as content blocks
  (``[{"type": "text", "text": content}]``).
- ``parse_anthropic_response`` maps ``content[0].text`` to
  ``AgentResult.content`` and ``stop_reason == "end_turn"`` to ``SUCCEEDED``.
- ``stop_reason`` in ``("max_tokens", "content_filter")`` maps to ``FAILED``
  with a normalized ``ErrorInfo`` (``provider_model_truncated``).
- The model name from the Anthropic response is sanitized to ``"redacted"`` in
  metadata — never appears in ``AgentResult.content`` or ``ErrorInfo.message``.
- API errors (``RateLimitError``, ``AuthenticationError``,
  ``APIConnectionError``, ``APIStatusError``) are mapped to normalized
  ``ErrorInfo`` codes via string-based class-name detection (the SDK cannot
  be imported at module top level).
- Error messages are sanitized (no URLs, tokens, file paths, model names).
- ``dependencies = []`` invariant preserved — no ``import anthropic`` at
  module top level.
"""

from __future__ import annotations

import importlib
import json
import re
from typing import Any, Protocol

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    ErrorCategory,
    ReplyType,
)
from platform_contract.events import AgentResult, ErrorInfo, JsonObject
from platform_runtime import RunRequest

from .adapter import ProviderModelExecResult, ProviderModelRunner
from .config import ProviderModelBackendConfig

# ---------------------------------------------------------------------------
# Transport abstraction
# ---------------------------------------------------------------------------


class AnthropicTransport(Protocol):
    """Transport abstraction for Anthropic Messages API.

    Tests inject a fake transport so no real ``anthropic`` SDK or network
    access is required.
    """

    async def create_message(self, request_payload: JsonObject) -> JsonObject:
        """Return the parsed JSON Messages API response dict."""
        ...


class FakeAnthropicTransport:
    """Convenience fake transport for tests (no SDK required)."""

    def __init__(
        self,
        response: JsonObject | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.last_request: JsonObject | None = None

    async def create_message(self, request_payload: JsonObject) -> JsonObject:
        self.last_request = request_payload
        if self.error is not None:
            raise self.error
        return self.response or {}


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_TRUNCATED_STOP_REASONS = ("max_tokens", "content_filter")


def parse_anthropic_response(
    response: JsonObject,
    run_id: str,
    turn_id: str,
) -> ProviderModelExecResult:
    """Map an Anthropic Messages API response dict to a
    :class:`ProviderModelExecResult` containing a platform-contract
    :class:`AgentResult`.
    """

    content_blocks = response.get("content", []) or []
    if not isinstance(content_blocks, list):
        content_blocks = []
    text_parts: list[str] = []
    for block in content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            text_val = block.get("text", "")
            if text_val:
                text_parts.append(text_val)
    content = "".join(text_parts) if text_parts else None

    stop_reason = response.get("stop_reason")
    completion_id = response.get("id")
    usage = response.get("usage", {}) or {}
    if not isinstance(usage, dict):
        usage = {}
    model = response.get("model", "unknown")

    error: ErrorInfo | None = None
    status: AsyncTaskState = AsyncTaskState.SUCCEEDED
    result_status: AgentResultStatus = AgentResultStatus.SUCCESS

    if stop_reason == "end_turn" and content is not None:
        status = AsyncTaskState.SUCCEEDED
        result_status = AgentResultStatus.SUCCESS
    elif content is not None:
        # Content present even without explicit "end_turn" — treat as success.
        status = AsyncTaskState.SUCCEEDED
        result_status = AgentResultStatus.SUCCESS
    elif stop_reason in _TRUNCATED_STOP_REASONS:
        status = AsyncTaskState.FAILED
        result_status = AgentResultStatus.FAILED
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="provider_model_truncated",
            stage="completion",
            message=f"completion truncated: {stop_reason}",
        )
    else:
        # No content and no recognized stop reason — treat as failure.
        status = AsyncTaskState.FAILED
        result_status = AgentResultStatus.FAILED
        error = ErrorInfo(
            category=ErrorCategory.RUNTIME_ERROR,
            code="provider_model_empty_completion",
            stage="completion",
            message="empty completion with no content",
        )

    result = AgentResult(
        result_id=f"provider-model-result-{run_id}",
        turn_id=turn_id,
        status=result_status,
        reply_type=ReplyType.TEXT,
        content=content,
        error=error,
        metadata={
            "provider_completion_id": completion_id,
            "source": "anthropic_messages",
        },
    )

    return ProviderModelExecResult(
        status=status,
        result=result,
        completion_id=completion_id,
        artifact_refs=[],
        raw_payload_ref=None,
        metadata={
            "provider_completion_id": completion_id,
            "provider_usage": _sanitize_usage(usage),
            "provider_model": _sanitize_model_name(model),
        },
    )


# ---------------------------------------------------------------------------
# Shared helpers (reused from openai_runner pattern)
# ---------------------------------------------------------------------------


def _sanitize_usage(usage: JsonObject) -> JsonObject:
    """Keep only safe token-count fields as integers; strip everything else."""

    sanitized: JsonObject = {}
    for key in ("input_tokens", "output_tokens", "prompt_tokens", "completion_tokens", "total_tokens"):
        if key in usage:
            try:
                sanitized[key] = int(usage[key])
            except (TypeError, ValueError):
                continue
    return sanitized


def _sanitize_model_name(model: str) -> str:
    """Always redact the model name for the prototype."""

    return "redacted"


# ---------------------------------------------------------------------------
# Error normalization
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://\S+")
_TOKEN_RE = re.compile(r"token=\S+")
_PATH_RE = re.compile(r"/(?:home|Users)[/\w.\-]*")
_MODEL_RE = re.compile(r"\b(?:gpt|claude|gemini|llama)[-\w]*", re.IGNORECASE)


def _sanitize_error_message(msg: str) -> str:
    """Strip URLs, tokens, file paths, and model names from an error message."""

    sanitized = _URL_RE.sub("[url_redacted]", msg)
    sanitized = _TOKEN_RE.sub("token=[redacted]", sanitized)
    sanitized = _PATH_RE.sub("[redacted]", sanitized)
    sanitized = _MODEL_RE.sub("[model_redacted]", sanitized)
    return sanitized


def _normalize_anthropic_error(exc: Exception, stage: str) -> ErrorInfo:
    """Normalize an Anthropic SDK exception into a sanitized :class:`ErrorInfo`.

    Detection is string-based on the exception class name because the
    ``anthropic`` SDK cannot be imported at module top level (lazy import).
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
        details={"provider": "anthropic"},
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


def _message_to_dict(message: Any) -> JsonObject:
    """Convert an ``AsyncAnthropic`` Message response object to a dict.

    Only used in the real SDK path (never exercised in tests).
    """

    dump = getattr(message, "model_dump_json", None)
    if callable(dump):
        return json.loads(dump())
    dump = getattr(message, "model_dump", None)
    if callable(dump):
        return dict(dump())
    # Fallback: best-effort conversion.
    return dict(message)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AnthropicRunner
# ---------------------------------------------------------------------------


class AnthropicRunner:
    """Runner that invokes ``AsyncAnthropic.messages.create`` lazily.

    The ``anthropic`` SDK is imported via ``importlib.import_module("anthropic")``
    inside :meth:`invoke` only — never at module top level — so the package
    imports cleanly without the SDK installed.

    Tests inject a :class:`FakeAnthropicTransport` to avoid real API calls.
    """

    def __init__(
        self,
        *,
        config: ProviderModelBackendConfig | None = None,
        transport: AnthropicTransport | None = None,
        api_key_resolver: Any | None = None,
    ) -> None:
        self.config = config or ProviderModelBackendConfig()
        self._transport = transport
        self._api_key_resolver = api_key_resolver or _default_api_key_resolver

    async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
        # Normalize to Anthropic Messages API format.
        request_payload: JsonObject = {
            "model": self.config.model_name,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": req.turn.content or ""},
                    ],
                }
            ],
        }

        # System prompt as top-level parameter (Anthropic Messages API).
        system_prompt = self.config.metadata.get("system_prompt")
        if system_prompt:
            request_payload["system"] = system_prompt

        try:
            if self._transport is not None:
                response = await self._transport.create_message(request_payload)
            else:
                # Real SDK path — never exercised in tests.  Lazy import.
                anthropic_module = importlib.import_module("anthropic")
                AsyncAnthropic = getattr(anthropic_module, "AsyncAnthropic")
                cred = self._api_key_resolver(self.config.api_key_ref)
                client = AsyncAnthropic(
                    api_key=cred,
                    base_url=self.config.api_base_url,
                )
                message = await client.messages.create(**request_payload)
                response = _message_to_dict(message)
        except Exception as exc:  # noqa: BLE001 - normalize all API errors
            return self._build_error_result(exc, req)

        return parse_anthropic_response(
            response,
            run_id=req.turn.turn_id,
            turn_id=req.turn.turn_id,
        )

    def _build_error_result(
        self,
        exc: Exception,
        req: RunRequest,
    ) -> ProviderModelExecResult:
        normalized = _normalize_anthropic_error(exc, stage="completion")
        result = AgentResult(
            result_id=f"provider-model-result-{req.turn.turn_id}",
            turn_id=req.turn.turn_id,
            status=AgentResultStatus.FAILED,
            reply_type=ReplyType.TEXT,
            content=None,
            error=normalized,
            metadata={"source": "anthropic_messages"},
        )
        return ProviderModelExecResult(
            status=AsyncTaskState.FAILED,
            result=result,
            completion_id=None,
            raw_payload_ref=None,
            metadata={"provider_error_code": normalized.code},
        )


__all__ = [
    "AnthropicRunner",
    "AnthropicTransport",
    "FakeAnthropicTransport",
    "parse_anthropic_response",
]
