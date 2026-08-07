"""Anthropic Messages API stream provider with tool call support.

This module merges the existing ``anthropic_runner.py`` from
``packages/backends/provider_model`` and adds streaming support with
tool call and reasoning content extraction.

Anthropic streaming uses SSE events with different types:
- ``content_block_start`` with ``type: "text"`` → start of text content
- ``content_block_delta`` with ``type: "text_delta"`` → ``ContentDelta``
- ``content_block_delta`` with ``type: "thinking_delta"`` → ``ReasoningDelta``
- ``content_block_start`` with ``type: "tool_use"`` → tool call start
- ``content_block_delta`` with ``type: "input_json_delta"`` → accumulate args
- ``content_block_stop`` → tool call complete, yield ``ToolCallDelta``
- ``message_delta`` with ``usage`` → ``UsageDelta``
- ``message_stop`` → ``FinishDelta``

System prompt handling: Anthropic uses a top-level ``system`` parameter
(not in the messages array).  The runner extracts system messages from
``ChatRequest.messages`` and moves them to the ``system`` parameter.

Tool definitions: Converted from OpenAI function-calling format to
Anthropic tool format if needed.
"""

from __future__ import annotations

import importlib
import json
from typing import Any, AsyncIterator, Protocol

from platform_contract.events import ErrorInfo, JsonObject

from .config import ProviderModelConfig
from .error_normalization import normalize_provider_error
from .openai_runner import _ProviderError
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


class AnthropicTransport(Protocol):
    """Transport abstraction for Anthropic Messages API.

    Tests inject a fake transport so no real ``anthropic`` SDK or
    network access is required.
    """

    async def create_message(self, request_payload: JsonObject) -> JsonObject:
        """Return the parsed JSON Messages API response dict (non-streaming)."""
        ...

    async def create_message_stream(
        self, request_payload: JsonObject
    ) -> AsyncIterator[JsonObject]:
        """Yield parsed JSON SSE event dicts (streaming)."""
        ...


class FakeAnthropicTransport:
    """Convenience fake transport for tests (no SDK required).

    Supports both non-streaming (``create_message``) and streaming
    (``create_message_stream``) modes.
    """

    def __init__(
        self,
        response: JsonObject | None = None,
        error: Exception | None = None,
        *,
        stream_events: list[JsonObject] | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.stream_events = stream_events
        self.last_request: JsonObject | None = None

    async def create_message(self, request_payload: JsonObject) -> JsonObject:
        self.last_request = request_payload
        if self.error is not None:
            raise self.error
        return self.response or {}

    async def create_message_stream(
        self, request_payload: JsonObject
    ) -> AsyncIterator[JsonObject]:
        self.last_request = request_payload
        if self.error is not None:
            raise self.error
        events = self.stream_events or []
        for event in events:
            yield event


# ---------------------------------------------------------------------------
# Helpers (reused from original runner)
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


def _default_api_key_resolver(ref: str | None) -> str:
    """Resolve an ``api_key_ref`` to a credential from the environment."""

    import os

    if not ref:
        return ""
    return os.environ.get(ref, "")


def _message_to_dict(message: Any) -> JsonObject:
    """Convert an ``AsyncAnthropic`` Message response object to a dict."""

    dump = getattr(message, "model_dump_json", None)
    if callable(dump):
        return json.loads(dump())
    dump = getattr(message, "model_dump", None)
    if callable(dump):
        return dict(dump())
    return dict(message)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# System prompt extraction
# ---------------------------------------------------------------------------


def _extract_system_prompt(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Extract system messages from the messages list.

    Anthropic uses a top-level ``system`` parameter rather than a
    system message in the messages array.  This function extracts
    all ``role: "system"`` messages and concatenates their content,
    returning the system prompt string and the remaining messages.
    """
    system_parts: list[str] = []
    remaining: list[dict] = []

    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                system_parts.append(content)
        else:
            remaining.append(msg)

    system_prompt = "\n".join(system_parts) if system_parts else None
    return system_prompt, remaining


# ---------------------------------------------------------------------------
# Tool definition conversion
# ---------------------------------------------------------------------------


def _convert_tools_to_anthropic(tools: list[dict] | None) -> list[dict] | None:
    """Convert OpenAI function-calling tool format to Anthropic tool format.

    OpenAI format:
        {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}

    Anthropic format:
        {"name": ..., "description": ..., "input_schema": ...}
    """
    if tools is None:
        return None

    anthropic_tools: list[dict] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        # Already in Anthropic format?
        if "name" in tool and "input_schema" in tool:
            anthropic_tools.append(tool)
            continue

        func = tool.get("function", tool)
        if not isinstance(func, dict):
            continue

        anthropic_tools.append({
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
        })

    return anthropic_tools if anthropic_tools else None


# ---------------------------------------------------------------------------
# AnthropicStreamProvider
# ---------------------------------------------------------------------------


class AnthropicStreamProvider:
    """Anthropic streaming provider implementing ``LlmProvider``.

    The ``anthropic`` SDK is imported via ``importlib.import_module("anthropic")``
    inside ``chat_stream`` only — never at module top level — so the
    package imports cleanly without the SDK installed.

    Tests inject a :class:`FakeAnthropicTransport` to avoid real API calls.
    """

    def __init__(
        self,
        *,
        config: ProviderModelConfig | None = None,
        transport: AnthropicTransport | None = None,
        api_key_resolver: Any | None = None,
    ) -> None:
        self.config = config or ProviderModelConfig()
        self._transport = transport
        self._api_key_resolver = api_key_resolver or _default_api_key_resolver

    async def chat_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[StreamDelta]:
        """Stream chat completion deltas from Anthropic.

        Yields ``StreamDelta`` union types: ``ContentDelta``,
        ``ReasoningDelta``, ``ToolCallDelta``, ``UsageDelta``,
        ``FinishDelta``.
        """
        request_payload = self._build_request_payload(request)

        # Reset per-call state
        self._tool_use_blocks: dict[int, dict[str, Any]] = {}

        try:
            if self._transport is not None:
                events = self._transport.create_message_stream(request_payload)
                async for event in events:
                    for delta in self._parse_event(event):
                        yield delta
            else:
                async for event in self._real_sdk_stream(request_payload):
                    for delta in self._parse_event(event):
                        yield delta
        except Exception as exc:  # noqa: BLE001
            normalized = normalize_provider_error(exc, stage="completion", provider="anthropic")
            raise _ProviderError(normalized) from exc

    def _build_request_payload(self, request: ChatRequest) -> JsonObject:
        """Build the Anthropic Messages API request payload."""
        system_prompt, messages = _extract_system_prompt(request.messages)

        payload: JsonObject = {
            "model": request.model or self.config.model_name,
            "max_tokens": request.max_tokens or 8192,
            "messages": messages,
            "stream": True,
        }

        if system_prompt:
            payload["system"] = system_prompt
        elif self.config.metadata.get("system_prompt"):
            payload["system"] = self.config.metadata["system_prompt"]

        if request.temperature is not None:
            payload["temperature"] = request.temperature

        anthropic_tools = _convert_tools_to_anthropic(request.tools)
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        return payload

    def _parse_event(self, event: JsonObject) -> list[StreamDelta]:
        """Parse a single Anthropic SSE event into ``StreamDelta`` objects.

        Anthropic event types:
        - ``content_block_start``: start of a content block (text or tool_use)
        - ``content_block_delta``: delta within a content block
        - ``content_block_stop``: end of a content block
        - ``message_delta``: message-level delta (usage, stop_reason)
        - ``message_stop``: stream end
        """
        deltas: list[StreamDelta] = []
        event_type = event.get("type", "")

        if event_type == "content_block_delta":
            deltas.extend(self._parse_content_block_delta(event))
        elif event_type == "content_block_start":
            deltas.extend(self._parse_content_block_start(event))
        elif event_type == "content_block_stop":
            deltas.extend(self._parse_content_block_stop(event))
        elif event_type == "message_delta":
            deltas.extend(self._parse_message_delta(event))
        elif event_type == "message_stop":
            deltas.append(FinishDelta(finish_reason="end_turn"))

        return deltas

    def _parse_content_block_start(self, event: JsonObject) -> list[StreamDelta]:
        """Parse content_block_start event."""
        deltas: list[StreamDelta] = []
        index = event.get("index", 0)
        content_block = event.get("content_block", {})
        if not isinstance(content_block, dict):
            return deltas

        block_type = content_block.get("type", "")
        if block_type == "tool_use":
            # Start tracking a tool use block
            self._tool_use_blocks[index] = {
                "id": content_block.get("id", ""),
                "name": content_block.get("name", ""),
                "arguments": "",
            }
        # text blocks don't need special start handling

        return deltas

    def _parse_content_block_delta(self, event: JsonObject) -> list[StreamDelta]:
        """Parse content_block_delta event."""
        deltas: list[StreamDelta] = []
        index = event.get("index", 0)
        delta = event.get("delta", {})
        if not isinstance(delta, dict):
            return deltas

        delta_type = delta.get("type", "")

        if delta_type == "text_delta":
            text = delta.get("text", "")
            if isinstance(text, str) and text:
                deltas.append(ContentDelta(content=text))

        elif delta_type == "thinking_delta":
            thinking = delta.get("thinking", "")
            if isinstance(thinking, str) and thinking:
                deltas.append(ReasoningDelta(reasoning=thinking))

        elif delta_type == "input_json_delta":
            partial_json = delta.get("partial_json", "")
            if isinstance(partial_json, str):
                if index in self._tool_use_blocks:
                    self._tool_use_blocks[index]["arguments"] += partial_json

        return deltas

    def _parse_content_block_stop(self, event: JsonObject) -> list[StreamDelta]:
        """Parse content_block_stop event — finalize tool use blocks."""
        deltas: list[StreamDelta] = []
        index = event.get("index", 0)

        if index in self._tool_use_blocks:
            block = self._tool_use_blocks.pop(index)
            deltas.append(ToolCallDelta(
                tool_call_id=block["id"],
                tool_name=block["name"],
                arguments=block["arguments"],
            ))

        return deltas

    def _parse_message_delta(self, event: JsonObject) -> list[StreamDelta]:
        """Parse message_delta event — usage and stop_reason."""
        deltas: list[StreamDelta] = []
        delta = event.get("delta", {})
        if isinstance(delta, dict):
            usage = delta.get("usage")
            if isinstance(usage, dict) and usage:
                deltas.append(UsageDelta(usage=_sanitize_usage(usage)))

        # Also check top-level usage in the event
        usage = event.get("usage")
        if isinstance(usage, dict) and usage:
            deltas.append(UsageDelta(usage=_sanitize_usage(usage)))

        return deltas

    async def _real_sdk_stream(self, request_payload: JsonObject) -> AsyncIterator[JsonObject]:
        """Real SDK streaming path — never exercised in tests."""
        anthropic_module = importlib.import_module("anthropic")
        AsyncAnthropic = getattr(anthropic_module, "AsyncAnthropic")
        cred = self._api_key_resolver(self.config.api_key_ref)
        client = AsyncAnthropic(
            api_key=cred,
            base_url=self.config.api_base_url,
        )

        # Remove 'stream' from payload since the SDK uses stream=True param
        sdk_payload = {k: v for k, v in request_payload.items() if k != "stream"}

        async with client.messages.stream(**sdk_payload) as stream:
            async for event in stream:
                yield _event_to_dict(event)

    def model_name(self) -> str:
        """Return the sanitized model name."""
        return _sanitize_model_name(self.config.model_name)

    def supports_tools(self) -> bool:
        """Anthropic supports tool calling."""
        return True


def _event_to_dict(event: Any) -> JsonObject:
    """Convert an Anthropic SDK event object to a dict."""

    dump = getattr(event, "model_dump_json", None)
    if callable(dump):
        return json.loads(dump())
    dump = getattr(event, "model_dump", None)
    if callable(dump):
        return dict(dump())
    if isinstance(event, dict):
        return event
    return {"type": str(event)}


__all__ = [
    "AnthropicStreamProvider",
    "AnthropicTransport",
    "FakeAnthropicTransport",
    "_extract_system_prompt",
    "_convert_tools_to_anthropic",
]
