"""Mode 1 — Standard Parallel arena execution (ENGINE-01).

N agents process the same task in parallel via ``asyncio.TaskGroup``.
Each agent slot runs through :func:`run_agent_slot` (Plan 01), which
calls ``adapter.submit_run`` + ``adapter.stream_events``.  Every
streamed event is re-emitted through the :class:`EventEmitter` callback
tagged with ``metadata["agent_slot"]`` so downstream consumers can
demultiplex the interleaved event stream.

Key invariants
--------------
- **Structured concurrency** — all slots run concurrently inside a
  single ``asyncio.TaskGroup`` (Python 3.11+).
- **Exception isolation** — one slot failure does NOT cancel sibling
  slots.  ``run_agent_slot`` never raises; a crashed slot returns a
  ``SlotResult(status="failed")``.
- **Reference-first persistence** — successful slot outputs are
  persisted via :class:`ArtifactStore.store_round_output`, which
  returns a :class:`RoundArtifact` carrying ``raw_payload_ref`` (a file
  path, not the full content).
- **Lifecycle events** — ``arena.workflow_started`` is emitted before
  any slot runs; ``arena.workflow_completed`` is emitted after all
  slots finish and artifacts are stored.

ENGINE-05: this module imports zero LLM provider packages.
ENGINE-06: this module never calls ``session/resume`` or ``resume_session``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from platform_contract.arena_contract import ArenaWorkflowConfig
from platform_contract.enums import RunEventType
from platform_contract.events import AgentTurn
from platform_runtime.protocols import BackendAdapter, RunRequest, SolutionBinding

from .artifact_store import ArtifactStore, RoundArtifact
from .slot_runner import SlotResult, run_agent_slot


# ---------------------------------------------------------------------------
# EventEmitter Protocol
# ---------------------------------------------------------------------------


class EventEmitter(Protocol):
    """Callback protocol for emitting arena lifecycle and slot events.

    The mode calls ``emit`` for:
    - ``arena.workflow_started`` (once, before any slot runs)
    - Per-slot ``RunEvent`` re-emissions (tagged with ``agent_slot``)
    - ``arena.workflow_completed`` (once, after all slots finish)
    """

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None: ...


# ---------------------------------------------------------------------------
# Mode1Result — frozen slotted dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Mode1Result:
    """Frozen slotted result of a Mode 1 parallel arena execution.

    Attributes
    ----------
    arena_id
        Identifier of the arena workflow.
    slot_results
        Mapping of slot ID → :class:`SlotResult` for every slot that
        was run.  Includes failed slots (``status="failed"``).
    artifacts
        Mapping of slot ID → :class:`RoundArtifact` for successful
        slots, or ``None`` for failed slots (when ``artifact_store`` is
        provided).  Empty when no ``artifact_store`` is given.
    metadata
        Additional metadata (mode name, round number, etc.).
    """

    arena_id: str
    slot_results: dict[str, SlotResult] = field(default_factory=dict)
    artifacts: dict[str, RoundArtifact | None] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# run_mode1_parallel
# ---------------------------------------------------------------------------


async def run_mode1_parallel(
    config: ArenaWorkflowConfig,
    agent_adapters: dict[str, BackendAdapter],
    event_emitter: EventEmitter | None = None,
    artifact_store: ArtifactStore | None = None,
) -> Mode1Result:
    """Run N agents in parallel on the same task (Mode 1 Standard Parallel).

    Parameters
    ----------
    config
        Arena workflow configuration — ``agent_slots`` lists the slot
        IDs to run, ``task_instruction`` is the shared prompt.
    agent_adapters
        Mapping of slot ID → :class:`BackendAdapter`.  Must contain an
        entry for every slot in ``config.agent_slots``.
    event_emitter
        Optional callback for emitting arena lifecycle and per-slot
        events.  When ``None``, no events are emitted.
    artifact_store
        Optional :class:`ArtifactStore` for persisting successful slot
        outputs.  When ``None``, no artifacts are stored.

    Returns
    -------
    Mode1Result
        Contains ``slot_results`` for all slots and ``artifacts`` for
        successful slots (when ``artifact_store`` is provided).
    """
    # -- Step 1: emit arena.workflow_started -----------------------------
    if event_emitter is not None:
        await event_emitter.emit(
            RunEventType.ARENA_WORKFLOW_STARTED.value,
            {
                "arena_id": config.arena_id,
                "mode": "mode1_parallel",
                "agent_slots": list(config.agent_slots),
            },
            {
                "arena_id": config.arena_id,
                "arena_phase": "mode1_parallel",
            },
        )

    # -- Steps 2-4: run all slots concurrently via TaskGroup -------------
    slot_results: dict[str, SlotResult] = {}

    async def _run_slot(slot_id: str) -> None:
        """Run a single slot and re-emit its events with agent_slot tagging."""
        req = _build_run_request(config, slot_id)
        result = await run_agent_slot(
            slot_id=slot_id,
            adapter=agent_adapters[slot_id],
            run_request=req,
            timeout=30.0,
        )
        slot_results[slot_id] = result

        # Re-emit each RunEvent through the emitter with agent_slot metadata
        if event_emitter is not None:
            tag = {
                "agent_slot": slot_id,
                "arena_id": config.arena_id,
                "arena_phase": "mode1_parallel",
            }
            for event in result.events:
                merged_metadata = {**event.metadata, **tag}
                await event_emitter.emit(
                    event.event_type,
                    dict(event.payload),
                    merged_metadata,
                )

    # TaskGroup provides structured concurrency.  Because run_agent_slot
    # never raises, a crashed slot does NOT cancel sibling slots.
    async with asyncio.TaskGroup() as tg:
        for slot_id in config.agent_slots:
            tg.create_task(_run_slot(slot_id))

    # -- Step 5: persist successful outputs via ArtifactStore ------------
    artifacts: dict[str, RoundArtifact | None] = {}
    if artifact_store is not None:
        for slot_id in config.agent_slots:
            result = slot_results.get(slot_id)
            if result is not None and result.status == "success" and result.content is not None:
                artifacts[slot_id] = artifact_store.store_round_output(
                    arena_id=config.arena_id,
                    agent_slot=slot_id,
                    round=0,
                    content=result.content,
                )
            else:
                artifacts[slot_id] = None

    # -- Step 6: emit arena.workflow_completed ---------------------------
    if event_emitter is not None:
        await event_emitter.emit(
            RunEventType.ARENA_WORKFLOW_COMPLETED.value,
            {
                "arena_id": config.arena_id,
                "mode": "mode1_parallel",
                "status": "completed",
                "agent_slots": list(config.agent_slots),
            },
            {
                "arena_id": config.arena_id,
                "arena_phase": "mode1_parallel",
            },
        )

    # -- Step 7: return Mode1Result --------------------------------------
    return Mode1Result(
        arena_id=config.arena_id,
        slot_results=slot_results,
        artifacts=artifacts,
        metadata={"mode": "mode1_parallel", "round": 0},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_run_request(config: ArenaWorkflowConfig, slot_id: str) -> RunRequest:
    """Build a fresh ``RunRequest`` for a single slot.

    Each slot gets a unique ``turn_id`` of the form
    ``"{arena_id}-{slot_id}-round0"`` so that runs are distinguishable
    across slots and rounds.
    """
    turn_id = f"{config.arena_id}-{slot_id}-round0"
    return RunRequest(
        turn=AgentTurn(
            turn_id=turn_id,
            conversation_id=f"{config.arena_id}-conv",
            channel="web",
            user_id="arena-user",
            message_type="text",
            received_at=datetime.now(UTC).isoformat(),
            content=config.task_instruction,
        ),
        solution=SolutionBinding(solution_id=f"arena-{config.arena_id}"),
    )


__all__ = [
    "EventEmitter",
    "Mode1Result",
    "run_mode1_parallel",
]
