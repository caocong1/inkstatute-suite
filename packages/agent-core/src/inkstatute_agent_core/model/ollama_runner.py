"""Ollama OpenAI-compatible stream provider with streaming support.

This module merges the existing ``ollama_runner.py`` from
``packages/backends/provider_model`` and adds streaming support.
Since Ollama is OpenAI-compatible, SSE parsing reuses the
``_ToolCallAccumulator`` and chunk parsing logic from ``openai_runner.py``.

Key features:
- ``OllamaStreamProvider`` implementing ``LlmProvider`` Protocol
- ``chat_stream()`` yields ``StreamDelta`` union types from Ollama's
  OpenAI-compatible SSE stream
- Reuses ``_ToolCallAccumulator`` from ``openai_runner.py`` for tool
  call accumulation (no duplicate parser)
- Real HTTP streaming path: Uses ``urllib.request`` with ``stream: true``
  in the request payload, reads the response stream line by line
- Lazy HTTP import preserved — package imports cleanly without external
  HTTP library
- Error normalization delegates to ``normalize_provider_error``
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Protocol

from platform_contract.events import ErrorInfo, JsonObject

from .config import ProviderModelConfig
from .error_normalization import normalize_provider_error
from .openai_runner import (
    _ProviderError,
    _sanitize_model_name,
    _sanitize_usage,
    _ToolCallAccumulator,
)
from .provider import (
    ChatRequest,
    ContentDelta,
    FinishDelta,
    LlmProvider,
    ReasoningDelta,
    StreamDelta,
    ToolCallDelta,
    UsageDelta,
)

# ---------------------------------------------------------------------------
# Transport abstraction
# ---------------------------------------------------------------------------


class OllamaTransport(Protocol):
    """Transport abstraction for Ollama OpenAI-compatible endpoint.

    Tests inject a fake transport so no real HTTP client or network
    access is required.
    """

    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject:
        """Return the parsed JSON chat completion response dict (non-streaming)."""
        ...

    async def create_chat_completion_stream(
        self, request_payload: JsonObject
    ) -> AsyncIterator[JsonObject]:
        """Yield parsed JSON SSE chunk dicts (streaming)."""
        ...


class FakeOllamaTransport:
    """Convenience fake transport for tests (no HTTP client required).

    Supports both non-streaming (``create_chat_completion``) and
    streaming (``create_chat_completion_stream``) modes.
    """

    def __init__(
        self,
        response: JsonObject | None = None,
        error: Exception | None = None,
        *,
        stream_chunks: list[JsonObject] | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.stream_chunks = stream_chunks
        self.last_request: JsonObject | None = None

    async def create_chat_completion(self, request_payload: JsonObject) -> JsonObject:
        self.last_request = request_payload
        if self.error is not None:
            raise self.error
        return self.response or {}

    async def create_chat_completion_stream(
        self, request_payload: JsonObject
    ) -> AsyncIterator[JsonObject]:
        self.last_request = request_payload
        if self.error is not None:
            raise self.error
        chunks = self.stream_chunks or []
        for chunk in chunks:
            yield chunk


# ---------------------------------------------------------------------------
# HTTP error class for Ollama
# ---------------------------------------------------------------------------


class OllamaHTTPError(Exception):
    """HTTP error from Ollama endpoint with status code for normalization."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# OllamaStreamProvider
# ---------------------------------------------------------------------------


class OllamaStreamProvider:
    """Ollama streaming provider implementing ``LlmProvider``.

    Since Ollama is OpenAI-compatible, SSE parsing reuses the
    ``_ToolCallAccumulator`` and chunk parsing logic from
    ``openai_runner.py``.

    The HTTP client (``urllib.request`` from stdlib) is imported inside
    ``_real_http_stream`` only — never at module top level — so the
    package imports cleanly without any external HTTP library.

    Tests inject a :class:`FakeOllamaTransport` to avoid real HTTP calls.
    """

    def __init__(
        self,
        *,
        config: ProviderModelConfig | None = None,
        transport: OllamaTransport | None = None,
    ) -> None:
        self.config = config or ProviderModelConfig()
        self._transport = transport

    async def chat_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[StreamDelta]:
        """Stream chat completion deltas from Ollama.

        Yields ``StreamDelta`` union types: ``ContentDelta``,
        ``ReasoningDelta``, ``ToolCallDelta``, ``UsageDelta``,
        ``FinishDelta``.
        """
        request_payload = self._build_request_payload(request)
        self._tool_accumulator = _ToolCallAccumulator()

        try:
            if self._transport is not None:
                chunks = self._transport.create_chat_completion_stream(request_payload)
                async for chunk in chunks:
                    for delta in self._parse_chunk(chunk):
                        yield delta
            else:
                async for chunk in self._real_http_stream(request_payload):
                    for delta in self._parse_chunk(chunk):
                        yield delta
        except Exception as exc:  # noqa: BLE001
            normalized = normalize_provider_error(exc, stage="completion", provider="ollama")
            raise _ProviderError(normalized) from exc

    def _build_request_payload(self, request: ChatRequest) -> JsonObject:
        """Build the Ollama OpenAI-compatible request payload."""
        payload: JsonObject = {
            "model": request.model or self.config.model_name,
            "messages": request.messages,
            "stream": True,
        }
        if request.tools is not None:
            payload["tools"] = request.tools
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        return payload

    def _parse_chunk(self, chunk: JsonObject) -> list[StreamDelta]:
        """Parse a single streaming chunk into ``StreamDelta`` objects.

        Reuses the same parsing logic as ``OpenAIStreamProvider._parse_chunk``
        since Ollama is OpenAI-compatible.
        """
        deltas: list[StreamDelta] = []

        choices = chunk.get("choices", []) or []
        if not isinstance(choices, list) or not choices:
            usage = chunk.get("usage")
            if isinstance(usage, dict) and usage:
                deltas.append(UsageDelta(usage=_sanitize_usage(usage)))
            return deltas

        choice = choices[0]
        if not isinstance(choice, dict):
            return deltas

        delta = choice.get("delta", {}) or {}
        if not isinstance(delta, dict):
            delta = {}

        # Content delta
        content = delta.get("content")
        if isinstance(content, str) and content:
            deltas.append(ContentDelta(content=content))

        # Reasoning delta
        reasoning = delta.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning:
            deltas.append(ReasoningDelta(reasoning=reasoning))

        # Tool call deltas (accumulated)
        tool_calls = delta.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            completed = self._tool_accumulator.process_chunk(tool_calls)
            deltas.extend(completed)

        # Finish reason
        finish_reason = choice.get("finish_reason")
        if isinstance(finish_reason, str) and finish_reason:
            finalized = self._tool_accumulator.finalize_all()
            deltas.extend(finalized)
            deltas.append(FinishDelta(finish_reason=finish_reason))

        # Usage
        usage = chunk.get("usage")
        if isinstance(usage, dict) and usage:
            deltas.append(UsageDelta(usage=_sanitize_usage(usage)))

        return deltas

    async def _real_http_stream(self, request_payload: JsonObject) -> AsyncIterator[JsonObject]:
        """Make a real streaming HTTP call to the Ollama endpoint.

        Uses ``urllib.request`` from stdlib (lazy import). This path is
        never exercised in tests — tests inject a :class:`FakeOllamaTransport`.
        """
        import urllib.request
        import urllib.error

        base_url = self.config.api_base_url or "http://localhost:11434"
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
                buffer = b""
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line_str = line.decode("utf-8", errors="replace").strip()
                        if not line_str:
                            continue
                        if line_str.startswith("data: "):
                            payload = line_str[len("data: "):]
                        else:
                            payload = line_str
                        if payload == "[DONE]":
                            continue
                        try:
                            parsed = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(parsed, dict):
                            yield parsed
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OllamaHTTPError(body, status_code=exc.code) from exc

    def model_name(self) -> str:
        """Return the sanitized model name."""
        return _sanitize_model_name(self.config.model_name)

    def supports_tools(self) -> bool:
        """Ollama supports tool calling (OpenAI-compatible)."""
        return True


__all__ = [
    "OllamaStreamProvider",
    "OllamaTransport",
    "FakeOllamaTransport",
    "OllamaHTTPError",
]
