"""Configuration for the Multi-Agent Runtime Adapter composite adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from platform_contract.events import JsonObject


class MultiAgentOrchestrationMode(StrEnum):
    """Orchestration patterns for multi-agent run delegation."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    SUPERVISOR = "supervisor"


@dataclass(frozen=True, slots=True)
class MultiAgentOrchestrationConfig:
    """Configuration for a single multi-agent orchestration run.

    ``mode`` selects the orchestration pattern:
    - **sequential**: entry agent runs, result ``handoff_to`` metadata chains
      to the next agent.  Handoff chain tracked with a visited-set for cycle
      detection.
    - **parallel**: fan-out to multiple agents concurrently using
      ``asyncio.Semaphore`` bounding concurrency.  Fan-in merges results.
    - **supervisor**: supervisor agent runs first, ``delegate_to`` metadata
      dispatches to worker agents.  Results flow back to the supervisor.

    ``max_handoffs`` limits the number of handoffs in sequential/supervisor
    mode.  When ``handoff_count >= max_handoffs``, the next handoff raises
    ``MultiAgentHandoffLimitError``.

    ``parallel_concurrency`` bounds the ``asyncio.Semaphore`` for parallel
    fan-out.

    ``agent_set`` optionally restricts the set of agents participating in
    parallel fan-out.  When empty, all registered sub-adapters participate.
    """

    mode: MultiAgentOrchestrationMode | str = MultiAgentOrchestrationMode.SEQUENTIAL
    entry_agent_id: str | None = None
    supervisor_agent_id: str | None = None
    max_handoffs: int = 5
    parallel_concurrency: int = 4
    agent_set: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MultiAgentRuntimeAdapterConfig:
    """Configuration for the composite Multi-Agent Runtime Adapter.

    ``enabled`` defaults to ``False`` — when disabled, the adapter is
    transparent (pass-through) with no orchestration, delegating directly
    to the sub-adapter matching ``solution.backend_id``.

    ``orchestration`` configures the orchestration pattern used when
    ``enabled`` is ``True``.
    """

    adapter_id: str = "multi-agent-runtime"
    enabled: bool = False
    orchestration: MultiAgentOrchestrationConfig = field(default_factory=MultiAgentOrchestrationConfig)
    metadata: JsonObject = field(default_factory=dict)


__all__ = [
    "MultiAgentOrchestrationConfig",
    "MultiAgentOrchestrationMode",
    "MultiAgentRuntimeAdapterConfig",
]
