"""Error types for the Multi-Agent Runtime Adapter."""

from __future__ import annotations


class MultiAgentError(RuntimeError):
    """Base error for multi-agent orchestration failures."""


class MultiAgentHandoffLimitError(MultiAgentError):
    """Raised when the handoff count exceeds ``max_handoffs``."""


class MultiAgentCycleError(MultiAgentError):
    """Raised when a handoff target is already in the handoff chain (cycle)."""


class MultiAgentRoutingError(MultiAgentError):
    """Raised when a sub-adapter cannot be resolved for an agent_id."""


__all__ = [
    "MultiAgentCycleError",
    "MultiAgentError",
    "MultiAgentHandoffLimitError",
    "MultiAgentRoutingError",
]
