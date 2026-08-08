"""Mode 2 — Self-score Iteration (ENGINE-02, ENGINE-07, ENGINE-08).

Each agent self-scores its output using a free-form 10-point framework
and self-optimizes across rounds.  The user can manually stop iteration
at any time via an :class:`asyncio.Event`; on stop the best result per
slot is preserved.  There is **no auto-stop on convergence** — only a
user stop or the ``max_rounds`` limit ends iteration.

The 10-point framework is **free-form**: the agent self-scores within
its own output text and :func:`_extract_self_score` parses the score.
No fixed scoring dimensions are imposed by the engine.

ENGINE-05: this module imports zero LLM provider packages.
ENGINE-06: this module never calls ``session/resume`` or
``resume_session`` — each round uses a fresh ``RunRequest`` with a new
``turn_id``.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from platform_contract.arena_contract import ArenaWorkflowConfig
from platform_contract.enums import RunEventType
from platform_contract.events import AgentTurn
from platform_contract.unified_events import (
    ArenaEarlyStopTriggeredPayload,
    ArenaScoreRecordedPayload,
    ArenaWorkflowCompletedPayload,
    ArenaWorkflowStartedPayload,
)
from platform_runtime.protocols import BackendAdapter, RunRequest, SolutionBinding

from .artifact_store import ArtifactStore
from .mode1 import EventEmitter
from .slot_runner import run_agent_slot


# ---------------------------------------------------------------------------
# Dataclasses (frozen, slotted)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IterationState:
    """Per-slot best state across iteration rounds.

    The highest-scoring round's state is preserved in
    :attr:`Mode2Result.best_results`.
    """

    slot_id: str
    round: int
    score: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Mode2Result:
    """Frozen slotted result of a Mode 2 self-score iteration run."""

    arena_id: str
    best_results: dict[str, IterationState] = field(default_factory=dict)
    rounds_completed: int = 0
    stopped_early: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Self-score extraction (free-form 10-point framework)
# ---------------------------------------------------------------------------

# Matches patterns like "自评分数：8/10", "score: 8", "评分: 9".
_SCORE_RE = re.compile(
    r"(?:自评分数|score|评分)\s*[:：]\s*(\d{1,2})\s*(?:/\s*10)?",
    re.IGNORECASE,
)


def _extract_self_score(content: str) -> int:
    """Extract a free-form self-score from agent output text.

    Searches for ``自评分数``/``score``/``评分`` followed by a colon
    (ASCII or full-width) and a 1-2 digit number, optionally followed by
    ``/10``.  Returns the integer score clamped to ``[0, 10]``.  Returns
    ``0`` when no score is found.
    """
    match = _SCORE_RE.search(content)
    if match is None:
        return 0
    score = int(match.group(1))
    if score < 0:
        return 0
    if score > 10:
        return 10
    return score


# ---------------------------------------------------------------------------
# Event emission helper
# ---------------------------------------------------------------------------


async def _emit(
    emitter: EventEmitter | None,
    event_type: str,
    payload: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    """Emit an event, awaiting if the emitter returns a coroutine."""
    if emitter is None:
        return
    result = emitter.emit(event_type, payload, metadata)
    if asyncio.iscoroutine(result):
        await result


# ---------------------------------------------------------------------------
# Run-request builder
# ---------------------------------------------------------------------------


def _build_run_request(
    config: ArenaWorkflowConfig,
    slot_id: str,
    round: int,
    prev_content: str | None,
    prev_score: int | None,
) -> RunRequest:
    """Build a fresh ``RunRequest`` for one slot in one round.

    Each round gets a new ``turn_id`` of the form
    ``"{arena_id}-{slot_id}-round{round}"`` so that every round uses a
    fresh context (ENGINE-06).  When ``round > 0`` the previous round's
    content and self-score are appended to the instruction so the agent
    can self-optimize.
    """
    instruction = config.task_instruction
    if round > 0 and prev_content is not None:
        instruction = (
            f"{instruction}\n\n上一轮回答：{prev_content}"
            f"\n\n上一轮自评分数：{prev_score}/10，请优化你的回答。"
        )
    return RunRequest(
        turn=AgentTurn(
            turn_id=f"{config.arena_id}-{slot_id}-round{round}",
            conversation_id=f"{config.arena_id}",
            channel="web",
            user_id="arena",
            message_type="text",
            received_at="2026-08-09T00:00:00Z",
            content=instruction,
        ),
        solution=SolutionBinding(solution_id=f"{config.arena_id}-{slot_id}"),
    )


# ---------------------------------------------------------------------------
# Main iteration loop
# ---------------------------------------------------------------------------


async def run_mode2_iteration(
    config: ArenaWorkflowConfig,
    agent_adapters: dict[str, BackendAdapter],
    event_emitter: EventEmitter | None = None,
    artifact_store: ArtifactStore | None = None,
    stop_signal: asyncio.Event | None = None,
) -> Mode2Result:
    """Run a Mode 2 self-score iteration arena.

    Each round runs all agent slots in parallel via
    :class:`asyncio.TaskGroup`, extracts a free-form self-score from each
    slot's output, emits ``arena.score_recorded``, persists the round
    output via :class:`ArtifactStore`, and tracks the best result per
    slot.  The user can stop iteration at any time by setting
    ``stop_signal``; on stop, ``arena.early_stop_triggered`` is emitted
    with ``reason="user_stopped"`` and the best results are preserved.

    No auto-stop on convergence — only a user stop or ``max_rounds``
    ends iteration.
    """
    arena_id = config.arena_id
    best_results: dict[str, IterationState] = {}
    # Track previous round content/score per slot for self-optimization.
    prev_content: dict[str, str | None] = {slot: None for slot in config.agent_slots}
    prev_score: dict[str, int | None] = {slot: None for slot in config.agent_slots}
    rounds_completed = 0

    # Emit workflow_started.
    await _emit(
        event_emitter,
        str(RunEventType.ARENA_WORKFLOW_STARTED),
        asdict(ArenaWorkflowStartedPayload(
            arena_id=arena_id,
            mode="mode2_iteration",
            agent_slots=list(config.agent_slots),
        )),
        {"arena_id": arena_id, "arena_phase": "mode2_iteration"},
    )

    stopped_early = False

    for r in range(config.max_rounds):
        # Check stop signal at the TOP of each round.
        if stop_signal is not None and stop_signal.is_set():
            stopped_early = True
            break

        # Run all slots in parallel for this round.
        round_results: dict[str, Any] = {}

        async def _run_slot(slot_id: str) -> None:
            adapter = agent_adapters[slot_id]
            req = _build_run_request(
                config,
                slot_id,
                r,
                prev_content.get(slot_id),
                prev_score.get(slot_id),
            )
            result = await run_agent_slot(
                slot_id=slot_id,
                adapter=adapter,
                run_request=req,
                timeout=30.0,
                max_retries=2,
            )
            round_results[slot_id] = result

        async with asyncio.TaskGroup() as tg:
            for slot_id in config.agent_slots:
                tg.create_task(_run_slot(slot_id))

        # Process results for this round.
        for slot_id in config.agent_slots:
            result = round_results.get(slot_id)
            if result is None:
                continue
            if result.status != "success" or result.content is None:
                # Slot failed this round — keep previous best, do not
                # overwrite.  Update prev tracking only on success.
                continue

            content = result.content
            score = _extract_self_score(content)

            # Emit arena.score_recorded.
            await _emit(
                event_emitter,
                str(RunEventType.ARENA_SCORE_RECORDED),
                asdict(ArenaScoreRecordedPayload(
                    arena_id=arena_id,
                    agent_slot=slot_id,
                    round=r,
                    score=score,
                )),
                {
                    "agent_slot": slot_id,
                    "arena_id": arena_id,
                    "arena_phase": "mode2_iteration",
                },
            )

            # Persist via ArtifactStore.
            if artifact_store is not None:
                artifact_store.store_round_output(
                    arena_id=arena_id,
                    agent_slot=slot_id,
                    round=r,
                    content=content,
                    metadata={"score": score, "status": result.status},
                )

            # Track best result (highest score wins; first round always
            # sets the initial best).
            current_best = best_results.get(slot_id)
            if current_best is None or score > current_best.score:
                best_results[slot_id] = IterationState(
                    slot_id=slot_id,
                    round=r,
                    score=score,
                    content=content,
                    metadata={"backend_id": result.metadata.get("backend_id")},
                )

            # Update prev tracking for self-optimization in next round.
            prev_content[slot_id] = content
            prev_score[slot_id] = score

        rounds_completed += 1

    # Emit early_stop_triggered if user stopped.
    if stopped_early:
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_EARLY_STOP_TRIGGERED),
            asdict(ArenaEarlyStopTriggeredPayload(
                arena_id=arena_id,
                reason="user_stopped",
                round=rounds_completed,
            )),
            {"arena_id": arena_id, "arena_phase": "mode2_iteration"},
        )

    # Emit workflow_completed.
    status = "stopped_early" if stopped_early else "completed"
    await _emit(
        event_emitter,
        str(RunEventType.ARENA_WORKFLOW_COMPLETED),
        asdict(ArenaWorkflowCompletedPayload(
            arena_id=arena_id,
            mode="mode2_iteration",
            status=status,
            agent_slots=list(config.agent_slots),
        )),
        {"arena_id": arena_id, "arena_phase": "mode2_iteration"},
    )

    return Mode2Result(
        arena_id=arena_id,
        best_results=best_results,
        rounds_completed=rounds_completed,
        stopped_early=stopped_early,
        metadata={"mode": "mode2_iteration"},
    )


__all__ = [
    "IterationState",
    "Mode2Result",
    "_extract_self_score",
    "run_mode2_iteration",
]
