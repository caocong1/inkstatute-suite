"""AgentCoreBackendConfig — configuration for InProcessAgentCoreAdapter.

This is the in-process entry point configuration (Plan 103-01).  The adapter
wraps the agent-core's ``run_turn()`` for direct use by the Gateway — no IPC,
no subprocess, full observability.

The config is a frozen dataclass holding:
- ``config``: the :class:`AgentCoreConfig` for the turn loop.
- ``provider_factory``: a callable that creates a fresh :class:`LlmProvider`
  for each run (so concurrent runs get independent provider instances).
- ``tool_executor_factory``: an optional callable that creates a
  :class:`ToolExecutor` for each run.
- ``backend_id``: the unique backend identifier (default ``"inkstatute"``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .config import AgentCoreConfig
from .model.provider import LlmProvider
from .turn_loop import ToolExecutor

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentCoreBackendConfig:
    """Configuration for :class:`InProcessAgentCoreAdapter`.

    Attributes
    ----------
    config
        The :class:`AgentCoreConfig` for the turn loop (max_turns,
        temperature, silence threshold, etc.).
    provider_factory
        A callable that returns a fresh :class:`LlmProvider` instance.
        Called once per ``submit_run`` so concurrent runs get independent
        provider state.  In production this creates an OpenAI / Anthropic /
        Ollama provider; in tests this creates a :class:`FixtureProvider`.
    tool_executor_factory
        An optional callable that returns a :class:`ToolExecutor` instance.
        Called once per ``submit_run``.  If ``None``, the turn loop uses
        its built-in fixture tool result (Phase 100 skeleton behaviour).
    backend_id
        Unique identifier for this backend.  Default ``"inkstatute"``.
    """

    config: AgentCoreConfig = field(default_factory=AgentCoreConfig)
    provider_factory: Callable[[], LlmProvider] = field(default_factory=lambda: _raise_no_provider)
    tool_executor_factory: Callable[[], ToolExecutor] | None = None
    backend_id: str = "inkstatute"


def _raise_no_provider() -> LlmProvider:
    """Default provider_factory that raises — callers must supply one."""
    raise RuntimeError(
        "AgentCoreBackendConfig.provider_factory is not configured. "
        "Provide a callable that returns a LlmProvider instance."
    )


__all__ = ["AgentCoreBackendConfig"]
