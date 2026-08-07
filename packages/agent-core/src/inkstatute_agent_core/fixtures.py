"""FixtureProvider with TurnScript for testing the turn loop without external LLM calls.

The ``FixtureProvider`` implements the ``LlmProvider`` Protocol and yields
pre-configured ``StreamDelta`` sequences.  It enables testing the async
turn loop, silence threshold, tool call orchestration, and multi-turn
behavior without any real API calls.

Key features:
- **TurnScript**: A frozen dataclass holding pre-configured deltas for a
  single turn, with optional delay and error injection.
- **Multi-turn support**: The provider pops the next ``TurnScript`` from
  the script list for each ``chat_stream()`` call (round-robin if exhausted).
- **Error injection**: If ``TurnScript.error`` is set, the provider raises
  it instead of yielding deltas.
- **Delay support**: ``TurnScript.delay_seconds`` causes ``asyncio.sleep``
  between delta yields (for silence threshold testing).
- **Call tracking**: ``call_count`` increments each time ``chat_stream``
  is called, for turn limit testing.
- **Script exhaustion**: If the script is exhausted, raises
  ``RuntimeError("fixture script exhausted")``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .model.provider import ChatRequest, StreamDelta

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class TurnScript:
    """Pre-configured stream deltas for a single turn.

    Attributes:
        deltas: List of ``StreamDelta`` objects to yield in order.
        delay_seconds: Optional delay before yielding each delta.
            Used for silence threshold testing.
        error: If set, the provider raises this error instead of
            yielding deltas.
    """

    deltas: list[StreamDelta] = field(default_factory=list)
    delay_seconds: float = 0.0
    error: Exception | None = None


class FixtureProvider:
    """Fixture LLM provider for testing without external LLM calls.

    Implements the ``LlmProvider`` Protocol by yielding pre-configured
    ``StreamDelta`` sequences from a list of ``TurnScript`` objects.

    Args:
        script: List of ``TurnScript`` objects, one per turn.
        model_name: Model name to return from ``model_name()``.
            Default ``"fixture"``.
        supports_tools: Whether this provider supports tool calling.
            Default ``True``.
    """

    def __init__(
        self,
        script: list[TurnScript],
        *,
        model_name: str = "fixture",
        supports_tools: bool = True,
    ) -> None:
        self._script: list[TurnScript] = list(script)
        self._model_name = model_name
        self._supports_tools = supports_tools
        self._call_count: int = 0
        self._script_index: int = 0

    @property
    def call_count(self) -> int:
        """Number of times ``chat_stream`` has been called."""
        return self._call_count

    @property
    def remaining_scripts(self) -> int:
        """Number of unconsumed scripts remaining."""
        return len(self._script) - self._script_index

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        """Yield pre-configured deltas for the next turn.

        Pops the next ``TurnScript`` from the script list.  If
        ``TurnScript.error`` is set, raises it.  Otherwise, yields each
        delta with optional ``asyncio.sleep(delay_seconds)`` between yields.

        Raises:
            RuntimeError: If the script is exhausted.
        """
        if self._script_index >= len(self._script):
            raise RuntimeError(
                f"fixture script exhausted: {self._call_count} calls, "
                f"{len(self._script)} scripts"
            )

        turn = self._script[self._script_index]
        self._script_index += 1
        self._call_count += 1

        if turn.error is not None:
            raise turn.error

        for delta in turn.deltas:
            if turn.delay_seconds > 0:
                await asyncio.sleep(turn.delay_seconds)
            yield delta

    def model_name(self) -> str:
        """Return the fixture model name."""
        return self._model_name

    def supports_tools(self) -> bool:
        """Return the configured tool support flag."""
        return self._supports_tools


__all__ = ["FixtureProvider", "TurnScript"]
