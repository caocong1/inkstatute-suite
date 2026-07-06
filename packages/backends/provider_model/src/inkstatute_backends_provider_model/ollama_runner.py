"""Ollama OpenAI-compatible endpoint runner with lazy HTTP import and error normalization.

This module implements ``OllamaRunner`` which invokes Ollama's
OpenAI-compatible ``/v1/chat/completions`` endpoint via a **lazy HTTP
client import** (``urllib.request`` from stdlib inside ``invoke``) so the
package imports cleanly without any external HTTP library installed.

Key behaviours:
- Ollama's ``/v1/chat/completions`` endpoint is OpenAI-compatible, so the
  request format (``{"model": ..., "messages": [...], "stream": false}``)
  and response format are identical to OpenAI Chat Completions.
- ``parse_openai_response`` from ``openai_runner.py`` is reused for response
  parsing — no duplicate parser needed.
- HTTP errors (429 rate limit, 401/403 auth, timeout, 5xx server error) are
  mapped to normalized ``ErrorInfo`` codes via HTTP status-code detection.
- The model name from the Ollama response is sanitized to ``"redacted"`` in
  metadata (handled by ``parse_openai_response``).
- Error messages are sanitized (no URLs, tokens, file paths, model names).
- ``dependencies = []`` invariant preserved — no ``import httpx`` or
  ``import urllib`` at module top level.
"""

from __future__ import annotations

import json
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
from .error_normalization import normalize_provider_error, sanitize_error_message
from .openai_runner import parse_openai_response

# ---------------------------------------------------------------------------
# Transport abstraction
# ---------------------------------------------------------------------------


class OllamaTransport(Protocol):
    """Transport abstraction for Ollama OpenAI-compatible endpoint.

    Tests inject a fake transport so no real HTTP client or network
    access is required.
    """

    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject:
        """Return the parsed JSON chat completion response dict."""
        ...


class FakeOllamaTransport:
    """Convenience fake transport for tests (no HTTP client required)."""

    def __init__(
        self,
        response: JsonObject | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.last_request: JsonObject | None = None

    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject:
        self.last_request = request_payload
        if self.error is not None:
            raise self.error
        return self.response or {}


# ---------------------------------------------------------------------------
# HTTP error class for Ollama
# ---------------------------------------------------------------------------


class OllamaHTTPError(Exception):
    """HTTP error from Ollama endpoint with status code for normalization."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Error normalization (delegates to shared error_normalization module)
# ---------------------------------------------------------------------------


def _sanitize_error_message(msg: str) -> str:
    """Strip URLs, tokens, file paths, and model names from an error message.

    Delegates to :func:`error_normalization.sanitize_error_message`.
    """

    return sanitize_error_message(msg)


def _normalize_ollama_error(exc: Exception, stage: str) -> ErrorInfo:
    """Normalize an Ollama HTTP/transport exception into a sanitized
    :class:`ErrorInfo`.

    Delegates to :func:`error_normalization.normalize_provider_error` with
    ``provider="ollama"``. HTTP status codes are detected via
    ``getattr(exc, "status_code", None)``.
    """

    return normalize_provider_error(exc, stage, provider="ollama")


# ---------------------------------------------------------------------------
# OllamaRunner
# ---------------------------------------------------------------------------


class OllamaRunner:
    """Runner that invokes Ollama's OpenAI-compatible endpoint lazily.

    The HTTP client (``urllib.request`` from stdlib) is imported inside
    :meth:`invoke` only — never at module top level — so the package
    imports cleanly without any external HTTP library.

    Tests inject a :class:`FakeOllamaTransport` to avoid real HTTP calls.
    """

    def __init__(
        self,
        *,
        config: ProviderModelBackendConfig | None = None,
        transport: OllamaTransport | None = None,
    ) -> None:
        self.config = config or ProviderModelBackendConfig()
        self._transport = transport

    async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
        request_payload: JsonObject = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": req.turn.content}],
            "stream": False,
        }

        try:
            if self._transport is not None:
                response = await self._transport.create_chat_completion(request_payload)
            else:
                response = await self._real_http_call(request_payload)
        except Exception as exc:  # noqa: BLE001 - normalize all errors
            return self._build_error_result(exc, req)

        # Reuse OpenAI response parser — Ollama is OpenAI-compatible.
        return parse_openai_response(
            response,
            run_id=req.turn.turn_id,
            turn_id=req.turn.turn_id,
        )

    async def _real_http_call(self, request_payload: JsonObject) -> JsonObject:
        """Make a real HTTP call to the Ollama endpoint.

        Uses ``urllib.request`` from stdlib (lazy import). This path is
        never exercised in tests — tests inject a :class:`FakeOllamaTransport`.
        """

        import urllib.request
        import urllib.error

        base_url = self.config.api_base_url or "http://localhost:11434"
        # Normalize trailing slash.
        url = base_url.rstrip("/") + "/v1/chat/completions"

        data = json.dumps(request_payload).encode("utf-8")
        req_obj = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req_obj, timeout=self.config.timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OllamaHTTPError(body, status_code=exc.code) from exc

    def _build_error_result(
        self,
        exc: Exception,
        req: RunRequest,
    ) -> ProviderModelExecResult:
        normalized = _normalize_ollama_error(exc, stage="completion")
        result = AgentResult(
            result_id=f"provider-model-result-{req.turn.turn_id}",
            turn_id=req.turn.turn_id,
            status=AgentResultStatus.FAILED,
            reply_type=ReplyType.TEXT,
            content=None,
            error=normalized,
            metadata={"source": "ollama_openai_compatible"},
        )
        return ProviderModelExecResult(
            status=AsyncTaskState.FAILED,
            result=result,
            completion_id=None,
            raw_payload_ref=None,
            metadata={"provider_error_code": normalized.code},
        )


__all__ = [
    "OllamaRunner",
    "OllamaTransport",
    "FakeOllamaTransport",
    "OllamaHTTPError",
]
