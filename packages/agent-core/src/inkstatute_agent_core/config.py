"""Configuration for the InkStatute agent core.

``AgentCoreConfig`` is a frozen dataclass holding all configurable
parameters for the agent core turn loop.  Default values match the
Rust original (``lawyer-desktop`` ``chat.rs`` / ``chat_tools.rs``):

================  =========  =====================
Constant           Value      Rust location
================  =========  =====================
MAX_TOOL_ROUNDS    10         chat_tools.rs:32
RESPONSE_MAX_TOKENS 8192      chat.rs:42
Temperature        0.3        chat.rs:781
================  =========  =====================

The silence threshold (default 5 s) is new in the Python port — the
Rust original had no heartbeat mechanism, which caused the "整轮静默"
(whole-round silence) defect during tool rounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentCoreConfig:
    """Configuration for the agent core turn loop.

    Fields:
        max_turns: Maximum number of tool-calling rounds before the
            turn is terminated with a ``turn_limit_exceeded`` error.
            Default 10, matching Rust ``MAX_TOOL_ROUNDS``.
        silence_threshold_seconds: If no event has been emitted for
            longer than this duration, the ``EventEmitter`` emits a
            heartbeat ``thought.delta`` event.  Default 5.0 seconds.
        response_max_tokens: Maximum tokens for the LLM response.
            Default 8192, matching Rust ``RESPONSE_MAX_TOKENS``.
        temperature: LLM sampling temperature.  Default 0.3, matching
            the Rust default.
        context_budget_tokens: Total token budget for context assembly
            (system prompt + history + skill bodies).  Default 32768.
        chars_per_token: Heuristic for token estimation (characters
            per token).  Default 4.
        heartbeat_metadata_key: Metadata key used to mark heartbeat
            events.  Default ``"heartbeat"``.
        max_leak_retries: Maximum number of leak-retry rounds after the
            LLM emits tool-call markup in plain text.  When exhausted,
            the leaked content is sanitised and emitted as the final
            answer.  Default 3, matching Rust ``MAX_LEAK_RETRIES``
            (``chat.rs:36``).
    """

    max_turns: int = 10
    silence_threshold_seconds: float = 5.0
    response_max_tokens: int = 8192
    temperature: float = 0.3
    context_budget_tokens: int = 32768
    chars_per_token: int = 4
    heartbeat_metadata_key: str = "heartbeat"
    max_leak_retries: int = 3
    metadata: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_turns < 1:
            raise ValueError(
                f"max_turns must be >= 1, got {self.max_turns}"
            )
        if self.silence_threshold_seconds <= 0:
            raise ValueError(
                f"silence_threshold_seconds must be > 0, "
                f"got {self.silence_threshold_seconds}"
            )
        if self.max_leak_retries < 0:
            raise ValueError(
                f"max_leak_retries must be >= 0, got {self.max_leak_retries}"
            )


__all__ = ["AgentCoreConfig"]
