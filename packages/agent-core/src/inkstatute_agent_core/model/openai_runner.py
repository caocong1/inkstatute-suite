"""OpenAI chat completions stream provider with tool call support.

This module merges the existing ``openai_runner.py`` from
``packages/backends/provider_model`` and adds streaming with tool call
support, reasoning content extraction, and usage data extraction.

Key additions over the original runner:
- ``OpenAIStreamProvider`` implementing ``LlmProvider`` Protocol
- ``chat_stream()`` yields ``StreamDelta`` union types:
    - ``ContentDelta`` from ``choices[0].delta.content``
    - ``ReasoningDelta`` from ``choices[0].delta.reasoning_content``
    - ``ToolCallDelta`` accumulated from ``choices[0].delta.tool_calls``
    - ``UsageDelta`` from the final chunk's ``usage`` field
    - ``FinishDelta`` from ``choices[0].finish_reason``
- Tool call accumulation: OpenAI streams tool calls in fragments
  (function name in first chunk, arguments in subsequent chunks).
  The runner accumulates these and yields complete ``ToolCallDelta``
  objects when a new tool call index appears or when the stream ends.
- Extended ``parse_sse_deltas()`` that extracts tool calls, reasoning,
  and usage in addition to content.
- Lazy SDK import preserved — package imports cleanly without ``openai``.
- Error normalization reuses ``normalize_provider_error`` from
  ``error_normalization.py``.
- Model name is sanitized to ``"redacted"`` in all metadata.
"""

from __future__ import annotations

import importlib
import json
from typing import Any, AsyncIterator, Iterator, Protocol

from platform_contract.events import ErrorInfo, JsonObject

from .config import ProviderModelConfig
from .error_normalization import normalize_provider_error
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


class OpenAITransport(Protocol):
    """Transport abstraction for OpenAI chat completions.

    Tests inject a fake transport so no real ``openai`` SDK or network
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


class FakeOpenAITransport:
    """Convenience fake transport for tests (no SDK required).

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
# SSE parsing (extended with tool call + reasoning + usage support)
# ---------------------------------------------------------------------------


def parse_sse_deltas(lines: list[str]) -> Iterator[JsonObject]:
    """Parse SSE-format ``data: `` lines into raw JSON chunk dicts.

    Lines not prefixed with ``data: `` (comments, keepalive pings, empty
    lines) are skipped.  ``data: [DONE]`` signals end of stream and is
    not yielded.  Unparseable JSON payloads are skipped.

    Returns raw parsed JSON dicts — the caller (``chat_stream``) is
    responsible for translating them to ``StreamDelta`` types.
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
        if isinstance(parsed, dict):
            yield parsed


# ---------------------------------------------------------------------------
# Helpers (reused from original runner)
# ---------------------------------------------------------------------------


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
    """Always redact the model name for the prototype."""

    return "redacted"


def _default_api_key_resolver(ref: str | None) -> str:
    """Resolve an ``api_key_ref`` to a credential from the environment."""

    import os

    if not ref:
        return ""
    return os.environ.get(ref, "")


def _completion_to_dict(completion: Any) -> JsonObject:
    """Convert an ``AsyncOpenAI`` ChatCompletion object to a dict."""

    dump = getattr(completion, "model_dump_json", None)
    if callable(dump):
        return json.loads(dump())
    dump = getattr(completion, "model_dump", None)
    if callable(dump):
        return dict(dump())
    return dict(completion)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tool call accumulator
# ---------------------------------------------------------------------------


class _ToolCallAccumulator:
    """Accumulates tool call fragments from OpenAI streaming chunks.

    OpenAI streams tool calls in fragments: the function name appears
    in the first chunk for a given index, and argument fragments arrive
    in subsequent chunks.  This accumulator tracks per-index state and
    yields complete ``ToolCallDelta`` objects when a tool call is
    finalized (new index appears or stream ends).
    """

    def __init__(self) -> None:
        self._pending: dict[int, dict[str, Any]] = {}
        self._completed: list[ToolCallDelta] = []
        self._last_index: int | None = None

    def process_chunk(self, tool_calls: list[dict]) -> list[ToolCallDelta]:
        """Process a ``delta.tool_calls`` list from a streaming chunk.

        Returns a list of completed ``ToolCallDelta`` objects (may be empty).
        When a new tool call index appears, the previous one is finalized.
        """
        completed: list[ToolCallDelta] = []

        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            idx = tc.get("index", 0)
            if idx is None:
                idx = 0

            # If we see a new index and we have a pending one, finalize it
            if self._last_index is not None and idx != self._last_index:
                if self._last_index in self._pending:
                    finalized = self._finalize(self._last_index)
                    if finalized is not None:
                        completed.append(finalized)

            self._last_index = idx

            if idx not in self._pending:
                self._pending[idx] = {
                    "id": "",
                    "name": "",
                    "arguments": "",
                }

            entry = self._pending[idx]

            tc_id = tc.get("id")
            if isinstance(tc_id, str):
                entry["id"] = tc_id

            function = tc.get("function", {})
            if isinstance(function, dict):
                name = function.get("name")
                if isinstance(name, str) and name:
                    entry["name"] = name
                args = function.get("arguments")
                if isinstance(args, str):
                    entry["arguments"] += args

        return completed

    def _finalize(self, idx: int) -> ToolCallDelta | None:
        """Finalize a pending tool call and return it as ``ToolCallDelta``."""
        entry = self._pending.pop(idx, None)
        if entry is None:
            return None
        return ToolCallDelta(
            tool_call_id=entry["id"],
            tool_name=entry["name"],
            arguments=entry["arguments"],
        )

    def finalize_all(self) -> list[ToolCallDelta]:
        """Finalize all remaining pending tool calls (called at stream end)."""
        completed: list[ToolCallDelta] = []
        for idx in sorted(self._pending.keys()):
            finalized = self._finalize(idx)
            if finalized is not None:
                completed.append(finalized)
        self._last_index = None
        return completed


# ---------------------------------------------------------------------------
# OpenAIStreamProvider
# ---------------------------------------------------------------------------


class OpenAIStreamProvider:
    """OpenAI-compatible streaming provider implementing ``LlmProvider``.

    The ``openai`` SDK is imported via ``importlib.import_module("openai")``
    inside ``chat_stream`` only — never at module top level — so the
    package imports cleanly without the SDK installed.

    Tests inject a :class:`FakeOpenAITransport` to avoid real API calls.
    """

    def __init__(
        self,
        *,
        config: ProviderModelConfig | None = None,
        transport: OpenAITransport | None = None,
        api_key_resolver: Any | None = None,
    ) -> None:
        self.config = config or ProviderModelConfig()
        self._transport = transport
        self._api_key_resolver = api_key_resolver or _default_api_key_resolver

    async def chat_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[StreamDelta]:
        """Stream chat completion deltas from OpenAI.

        Yields ``StreamDelta`` union types: ``ContentDelta``,
        ``ReasoningDelta``, ``ToolCallDelta``, ``UsageDelta``,
        ``FinishDelta``.
        """
        request_payload = self._build_request_payload(request)

        try:
            if self._transport is not None:
                chunks = self._transport.create_chat_completion_stream(request_payload)
                async for chunk in chunks:
                    for delta in self._parse_chunk(chunk):
                        yield delta
            else:
                # Real SDK path — never exercised in tests.  Lazy import.
                async for chunk in self._real_sdk_stream(request_payload):
                    for delta in self._parse_chunk(chunk):
                        yield delta
        except Exception as exc:  # noqa: BLE001
            normalized = normalize_provider_error(exc, stage="completion", provider="openai")
            raise _ProviderError(normalized) from exc

    def _build_request_payload(self, request: ChatRequest) -> JsonObject:
        """Build the OpenAI chat completion request payload."""
        payload: JsonObject = {
            "model": request.model or self.config.model_name,
            "messages": request.messages,
            "stream": True,
        }
        if request.tools is not None:
            payload["tools"] = request.tools
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        elif self.config.metadata.get("max_tokens"):
            payload["max_tokens"] = self.config.metadata["max_tokens"]
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        return payload

    def _parse_chunk(self, chunk: JsonObject) -> list[StreamDelta]:
        """Parse a single streaming chunk into ``StreamDelta`` objects.

        Extracts:
        - ``choices[0].delta.content`` → ``ContentDelta``
        - ``choices[0].delta.reasoning_content`` → ``ReasoningDelta``
        - ``choices[0].delta.tool_calls`` → accumulated ``ToolCallDelta``
        - ``choices[0].finish_reason`` → ``FinishDelta``
        - ``usage`` (if present) → ``UsageDelta``
        """
        deltas: list[StreamDelta] = []

        choices = chunk.get("choices", []) or []
        if not isinstance(choices, list) or not choices:
            # Check for usage in the final chunk (some providers send it separately)
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

        # Reasoning delta (DeepSeek, o1, etc.)
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
            # Finalize any pending tool calls
            finalized = self._tool_accumulator.finalize_all()
            deltas.extend(finalized)
            deltas.append(FinishDelta(finish_reason=finish_reason))

        # Usage (some providers include it in the final chunk)
        usage = chunk.get("usage")
        if isinstance(usage, dict) and usage:
            deltas.append(UsageDelta(usage=_sanitize_usage(usage)))

        return deltas

    async def _real_sdk_stream(self, request_payload: JsonObject) -> AsyncIterator[JsonObject]:
        """Real SDK streaming path — never exercised in tests.

        Uses ``AsyncOpenAI`` with ``stream=True`` and converts each
        chunk to a dict.
        """
        openai_module = importlib.import_module("openai")
        AsyncOpenAI = getattr(openai_module, "AsyncOpenAI")
        cred = self._api_key_resolver(self.config.api_key_ref)
        client = AsyncOpenAI(
            api_key=cred,
            base_url=self.config.api_base_url,
        )

        # Remove 'stream' from payload since the SDK uses stream=True param
        sdk_payload = {k: v for k, v in request_payload.items() if k != "stream"}

        stream = await client.chat.completions.create(**sdk_payload, stream=True)
        async for chunk in stream:
            yield _completion_to_dict(chunk)

    def model_name(self) -> str:
        """Return the sanitized model name."""
        return _sanitize_model_name(self.config.model_name)

    def supports_tools(self) -> bool:
        """OpenAI-compatible providers support tool calling."""
        return True

    @property
    def _tool_accumulator(self) -> _ToolCallAccumulator:
        """Lazily create a tool call accumulator per chat_stream call.

        Since ``chat_stream`` is an async generator, we need a fresh
        accumulator per call.  We store it as an instance attribute
        that is reset at the start of each ``chat_stream`` call.
        """
        if not hasattr(self, "_tc_accumulator"):
            self._tc_accumulator = _ToolCallAccumulator()
        return self._tc_accumulator


# Need to reset the accumulator at the start of each chat_stream call.
# We wrap the original chat_stream to do this.
_original_chat_stream = OpenAIStreamProvider.chat_stream


async def _chat_stream_with_reset(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
    """Wrapper that resets the tool call accumulator per call."""
    self._tc_accumulator = _ToolCallAccumulator()
    async for delta in _original_chat_stream(self, request):
        yield delta


OpenAIStreamProvider.chat_stream = _chat_stream_with_reset  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# ProviderError wrapper
# ---------------------------------------------------------------------------


class _ProviderError(Exception):
    """Wrapper exception carrying a normalized ``ErrorInfo``."""

    def __init__(self, error_info: ErrorInfo) -> None:
        self.error_info = error_info
        super().__init__(error_info.message)


__all__ = [
    "OpenAIStreamProvider",
    "OpenAITransport",
    "FakeOpenAITransport",
    "parse_sse_deltas",
    "_ToolCallAccumulator",
    "_ProviderError",
]
