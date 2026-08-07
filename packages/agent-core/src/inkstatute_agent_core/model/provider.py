"""Unified LlmProvider Protocol with StreamDelta union types.

This module defines the core abstraction for the agent-core model layer:

- **StreamDelta** — a union of 5 frozen dataclass types representing
  structured streaming deltas from an LLM provider:
    - ``ContentDelta`` — text content streaming
    - ``ReasoningDelta`` — thinking/reasoning content streaming
    - ``ToolCallDelta`` — tool call from LLM (arguments is JSON string)
    - ``UsageDelta`` — token usage (prompt/completion/total tokens)
    - ``FinishDelta`` — stream end signal

- **ChatRequest** — a frozen dataclass representing a chat request
  with messages, optional tools, model override, and streaming config.

- **LlmProvider** — a Protocol with three methods:
    - ``chat_stream(request) -> AsyncIterator[StreamDelta]`` — unified
      streaming interface for all providers
    - ``model_name() -> str`` — returns the provider's model name
    - ``supports_tools() -> bool`` — capability flag for tool calling

- **UsageAccumulator** — helper class that accumulates ``UsageDelta``
  events across a single stream and provides ``to_dict()`` for attaching
  to event metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable

JsonObject = dict[str, Any]


# ---------------------------------------------------------------------------
# StreamDelta union types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContentDelta:
    """Text content streaming delta.

    Maps to ``message.delta`` events in the unified event vocabulary.
    """

    content: str


@dataclass(frozen=True, slots=True)
class ReasoningDelta:
    """Reasoning/thinking content streaming delta.

    Maps to ``thought.delta`` events in the unified event vocabulary.
    Some providers (e.g. DeepSeek, OpenAI o1) expose reasoning content
    separately from the final answer.
    """

    reasoning: str


@dataclass(frozen=True, slots=True)
class ToolCallDelta:
    """Tool call delta from the LLM.

    Represents a complete or partial tool call.  The ``arguments`` field
    is a JSON string (OpenAI function-calling format).

    Attributes:
        tool_call_id: Unique identifier for the tool call.
        tool_name: The name of the tool being called.
        arguments: JSON string of tool call arguments.
    """

    tool_call_id: str
    tool_name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class UsageDelta:
    """Token usage delta.

    Contains token counts from the provider.  Multiple ``UsageDelta``
    events may be emitted during a single stream (e.g. intermediate
    usage in some providers).  Use ``UsageAccumulator`` to sum them.

    Attributes:
        usage: Dict with keys like ``prompt_tokens``,
            ``completion_tokens``, ``total_tokens``.
    """

    usage: dict


@dataclass(frozen=True, slots=True)
class FinishDelta:
    """Stream end signal.

    Attributes:
        finish_reason: The provider's finish reason string
            (e.g. ``"stop"``, ``"tool_calls"``, ``"length"``).
    """

    finish_reason: str


# Union type alias for all stream delta types
StreamDelta = ContentDelta | ReasoningDelta | ToolCallDelta | UsageDelta | FinishDelta


# ---------------------------------------------------------------------------
# ChatRequest
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Chat request for the unified LlmProvider Protocol.

    Attributes:
        messages: List of chat message dicts (``{"role": ..., "content": ...}``).
        tools: Optional list of tool definitions in OpenAI function-calling
            format.
        model: Optional model name override.
        max_tokens: Optional response token limit.
        temperature: Optional sampling temperature.
        stream: Always True — the unified interface is streaming-only.
    """

    messages: list[dict]
    tools: list[dict] | None = None
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    stream: bool = True


# ---------------------------------------------------------------------------
# LlmProvider Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LlmProvider(Protocol):
    """Unified LLM provider Protocol with streaming + tool call support.

    All provider runners (OpenAI, Anthropic, Ollama, Fixture) implement
    this Protocol.  The turn loop calls ``chat_stream()`` for every round
    — even during tool rounds — to ensure the client never experiences
    whole-round silence.
    """

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        """Stream chat completion deltas.

        Yields ``StreamDelta`` union types: ``ContentDelta``,
        ``ReasoningDelta``, ``ToolCallDelta``, ``UsageDelta``,
        ``FinishDelta``.
        """
        ...

    def model_name(self) -> str:
        """Return the provider's model name (sanitized to 'redacted' in metadata)."""
        ...

    def supports_tools(self) -> bool:
        """Return True if this provider supports tool/function calling."""
        ...


# ---------------------------------------------------------------------------
# UsageAccumulator
# ---------------------------------------------------------------------------


class UsageAccumulator:
    """Accumulates ``UsageDelta`` events across a single stream.

    Sums ``prompt_tokens``, ``completion_tokens``, and ``total_tokens``
    from multiple ``UsageDelta`` events.  Provides ``to_dict()`` for
    attaching to event metadata.
    """

    def __init__(self) -> None:
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        self._total_tokens: int = 0

    def add(self, delta: UsageDelta) -> None:
        """Add a ``UsageDelta`` to the accumulator."""
        usage = delta.usage
        if not isinstance(usage, dict):
            return
        for key in ("prompt_tokens", "input_tokens"):
            val = usage.get(key)
            if isinstance(val, (int, float)):
                self._prompt_tokens += int(val)
                break
        for key in ("completion_tokens", "output_tokens"):
            val = usage.get(key)
            if isinstance(val, (int, float)):
                self._completion_tokens += int(val)
                break
        val = usage.get("total_tokens")
        if isinstance(val, (int, float)):
            self._total_tokens += int(val)

    @property
    def prompt_tokens(self) -> int:
        return self._prompt_tokens

    @property
    def completion_tokens(self) -> int:
        return self._completion_tokens

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    def to_dict(self) -> dict:
        """Return accumulated usage as a dict for event metadata."""
        return {
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "total_tokens": self._total_tokens,
        }


__all__ = [
    "ContentDelta",
    "ReasoningDelta",
    "ToolCallDelta",
    "UsageDelta",
    "FinishDelta",
    "StreamDelta",
    "ChatRequest",
    "LlmProvider",
    "UsageAccumulator",
]
