"""Mode 3 — Arena Review (Self-score + Cross-review + Independent Synthesis).

Mode 3 builds on Mode 2's self-score iteration, then adds multi-agent
cross-review (each agent's best output reviewed by a different-family
agent, enforced by :func:`_pair_cross_family`) and finally an independent
agent session (fresh context) that takes the highest-scoring result plus
all review findings to produce the final synthesized version.

The orchestrator **never produces content** — synthesis is done by a
separate ``synthesis_adapter`` :class:`BackendAdapter` instance.

Three phases
------------
1. **Self-score iteration** — reuses :func:`run_mode2_iteration` from
   ``mode2.py``.  Extracts ``best_results`` from the ``Mode2Result``.
2. **Cross-review** — each agent's best output is reviewed by a
   different-family agent.  Cross-family pairing is enforced by
   :func:`_pair_cross_family` from ``families.py`` (SAFE-06).  Review
   findings are parsed via :func:`_parse_review_findings` from
   ``review.py``.
3. **Synthesis** — an independent agent session (separate
   ``synthesis_adapter``) takes the highest-scoring result plus all
   review findings and produces the final version.  Fresh context
   (new ``turn_id``).

ENGINE-05: this module imports zero LLM provider packages.
ENGINE-06: this module never calls ``session/resume`` or
``resume_session`` — every phase uses a fresh ``RunRequest`` with a new
``turn_id``.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from platform_contract.arena_contract import ArenaWorkflowConfig
from platform_contract.enums import RunEventType
from platform_contract.events import AgentTurn
from platform_contract.unified_events import (
    ArenaEarlyStopTriggeredPayload,
    ArenaReviewCompletedPayload,
    ArenaSynthesisCompletedPayload,
    ArenaSynthesisStartedPayload,
    ArenaWorkflowCompletedPayload,
    ArenaWorkflowStartedPayload,
)
from platform_runtime.protocols import BackendAdapter, RunRequest, SolutionBinding

from .artifact_store import ArtifactStore
from .families import CrossFamilyPairingResult, _pair_cross_family, get_backend_family
from .mode1 import EventEmitter
from .mode2 import IterationState, Mode2Result, run_mode2_iteration
from .review import ReviewFinding, _parse_review_findings
from .slot_runner import run_agent_slot


# ---------------------------------------------------------------------------
# Dataclasses (frozen, slotted)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Mode3Result:
    """Frozen slotted result of a Mode 3 arena review run.

    Fields
    ------
    arena_id
        Identifier of the arena workflow.
    best_results
        Per-slot best :class:`IterationState` from the self-score
        iteration (reused from Mode 2).
    review_findings
        Mapping of reviewed slot → list of :class:`ReviewFinding`.
    synthesis_content
        The final synthesized content, or ``None`` when synthesis was
        skipped (user stop or same-family-only degradation).
    synthesis_slot
        The slot ID of the synthesis agent (``"synthesis"``), or
        ``None`` when synthesis was skipped.
    rounds_completed
        Number of self-score rounds completed.
    stopped_early
        ``True`` when the user stopped during self-score iteration.
    cross_family_degraded
        ``True`` when cross-review was degraded (same-family-only or
        partial same-family).
    metadata
        Additional structured metadata.
    """

    arena_id: str
    best_results: dict[str, IterationState] = field(default_factory=dict)
    review_findings: dict[str, list[ReviewFinding]] = field(default_factory=dict)
    synthesis_content: str | None = None
    synthesis_slot: str | None = None
    rounds_completed: int = 0
    stopped_early: bool = False
    cross_family_degraded: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


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
# Helpers
# ---------------------------------------------------------------------------


def _select_best_result(
    best_results: dict[str, IterationState],
) -> tuple[str, str]:
    """Select the highest-scoring slot's content for synthesis.

    Returns ``(slot_id, content)`` for the :class:`IterationState` with
    the highest ``score``.  Ties are broken by first occurrence (insertion
    order of the dict).
    """
    best_slot: str | None = None
    best_score: int = -1
    for slot_id, state in best_results.items():
        if state.score > best_score:
            best_score = state.score
            best_slot = slot_id
    if best_slot is None:
        raise ValueError("best_results is empty — cannot select a best result")
    return best_slot, best_results[best_slot].content


def _build_synthesis_prompt(
    best_content: str,
    review_findings: dict[str, list[ReviewFinding]],
    task_instruction: str,
) -> str:
    """Construct the synthesis prompt for the independent synthesis agent.

    Includes: (1) the original task instruction, (2) the highest-scoring
    result's content labeled as "最高分回答", (3) all review findings
    formatted as structured text with description, confidence, severity,
    confirmed/disproved status, and which reviewer produced them.

    The prompt instructs the synthesis agent to produce a final version
    incorporating the best answer and addressing all review findings.
    """
    lines: list[str] = [
        f"原始任务：{task_instruction}",
        "",
        "最高分回答：",
        best_content,
        "",
        "评审意见汇总：",
    ]

    if not review_findings:
        lines.append("（无评审意见）")
    else:
        for reviewed_slot, findings in review_findings.items():
            for finding in findings:
                status = "已确认" if finding.confirmed else "已反驳"
                lines.append(
                    f"- 评审者：{finding.source_slot}（评审对象：{reviewed_slot}）"
                    f" | 严重程度：{finding.severity.value}"
                    f" | 置信度：{finding.confidence.value}"
                    f" | 状态：{status}"
                    f" | 描述：{finding.description}"
                )

    lines.extend([
        "",
        "请综合最高分回答和所有评审意见，产出最终版本。"
        "保留最高分回答中的正确内容，并根据评审意见修正不足之处。",
    ])
    return "\n".join(lines)


def _build_review_run_request(
    config: ArenaWorkflowConfig,
    reviewer_slot: str,
    reviewed_slot: str,
    reviewed_content: str,
) -> RunRequest:
    """Build a fresh ``RunRequest`` for a cross-review execution.

    Each cross-review gets a new ``turn_id`` of the form
    ``"{arena_id}-review-{reviewer_slot}-round0"`` so that cross-review
    uses fresh context (ENGINE-06).
    """
    instruction = (
        f"请评审以下回答，找出问题并给出结构化评审意见。\n\n"
        f"被评审回答（来自 {reviewed_slot}）：\n{reviewed_content}\n\n"
        f"请使用以下格式输出评审意见：\n"
        f"[FINDING]\n"
        f"description: 问题描述\n"
        f"confidence: Certain/Likely/Possible\n"
        f"severity: High/Medium/Low\n"
        f"confirmed: true/false\n"
        f"[/FINDING]"
    )
    return RunRequest(
        turn=AgentTurn(
            turn_id=f"{config.arena_id}-review-{reviewer_slot}-round0",
            conversation_id=f"{config.arena_id}",
            channel="web",
            user_id="arena",
            message_type="text",
            received_at=datetime.now(UTC).isoformat(),
            content=instruction,
        ),
        solution=SolutionBinding(
            solution_id=f"{config.arena_id}-review-{reviewer_slot}",
        ),
    )


def _build_synthesis_run_request(
    config: ArenaWorkflowConfig,
    synthesis_instruction: str,
) -> RunRequest:
    """Build a fresh ``RunRequest`` for the synthesis agent.

    The synthesis agent gets a new ``turn_id`` of the form
    ``"{arena_id}-synthesis-round0"`` so that synthesis uses fresh
    context (ENGINE-06) — no session reuse.
    """
    return RunRequest(
        turn=AgentTurn(
            turn_id=f"{config.arena_id}-synthesis-round0",
            conversation_id=f"{config.arena_id}",
            channel="web",
            user_id="arena",
            message_type="text",
            received_at=datetime.now(UTC).isoformat(),
            content=synthesis_instruction,
        ),
        solution=SolutionBinding(
            solution_id=f"{config.arena_id}-synthesis",
        ),
    )


# ---------------------------------------------------------------------------
# Filtered emitter — forwards only score_recorded events to the real emitter
# ---------------------------------------------------------------------------


class _ScoreOnlyEmitter:
    """Wrapper emitter that forwards only ``arena.score_recorded`` events.

    Used when calling :func:`run_mode2_iteration` from Mode 3 so that
    stop-signal logic (which listens for score events) works, while
    suppressing Mode 2's own ``workflow_started`` / ``workflow_completed``
    events (Mode 3 emits its own lifecycle events).
    """

    def __init__(self, inner: EventEmitter | None) -> None:
        self._inner = inner

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        if self._inner is None:
            return
        if event_type == str(RunEventType.ARENA_SCORE_RECORDED):
            result = self._inner.emit(event_type, payload, metadata)
            if asyncio.iscoroutine(result):
                await result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_mode3_arena_review(
    config: ArenaWorkflowConfig,
    agent_adapters: dict[str, BackendAdapter],
    synthesis_adapter: BackendAdapter,
    event_emitter: EventEmitter | None = None,
    stop_signal: asyncio.Event | None = None,
    artifact_store: ArtifactStore | None = None,
    backend_families: dict[str, str] | None = None,
    provenance_logger: Any | None = None,
) -> Mode3Result:
    """Run a Mode 3 arena review: self-score + cross-review + synthesis.

    Parameters
    ----------
    config
        Arena workflow configuration.
    agent_adapters
        Mapping of slot ID → :class:`BackendAdapter` for candidate agents.
    synthesis_adapter
        A **separate** :class:`BackendAdapter` for the independent
        synthesis session.  This must NOT be one of the candidate slot
        adapters — the orchestrator never produces content.
    event_emitter
        Optional callback for emitting arena lifecycle events.
    stop_signal
        Optional :class:`asyncio.Event` for user-initiated stop.
    artifact_store
        Optional :class:`ArtifactStore` for persistence.
    backend_families
        Optional explicit slot → family mapping.  When ``None``, families
        are derived from ``adapter.backend_id()`` via
        :func:`get_backend_family`.
    provenance_logger
        Optional :class:`ProvenanceLogger` for cross-review provenance
        with ``reviewer_slot`` populated.

    Returns
    -------
    Mode3Result
        The complete Mode 3 result with best results, review findings,
        and synthesis content.
    """
    arena_id = config.arena_id

    # Emit arena.workflow_started.
    await _emit(
        event_emitter,
        str(RunEventType.ARENA_WORKFLOW_STARTED),
        asdict(ArenaWorkflowStartedPayload(
            arena_id=arena_id,
            mode="mode3_arena_review",
            agent_slots=list(config.agent_slots),
        )),
        {"arena_id": arena_id, "arena_phase": "mode3_arena_review"},
    )

    # ------------------------------------------------------------------
    # Phase 1 — Self-score iteration (reuse Mode 2)
    # ------------------------------------------------------------------
    # Forward only score_recorded events to the real emitter so that
    # stop-signal logic (which listens for score events) works, while
    # suppressing Mode 2's own workflow_started/completed events (Mode 3
    # emits its own).
    score_emitter = _ScoreOnlyEmitter(event_emitter)
    mode2_result: Mode2Result = await run_mode2_iteration(
        config=config,
        agent_adapters=agent_adapters,
        event_emitter=score_emitter,
        artifact_store=artifact_store,
        stop_signal=stop_signal,
    )
    best_results = mode2_result.best_results
    rounds_completed = mode2_result.rounds_completed
    stopped_early = mode2_result.stopped_early

    # If user stopped during self-score iteration, skip cross-review and
    # synthesis, return early.
    if stopped_early:
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_EARLY_STOP_TRIGGERED),
            asdict(ArenaEarlyStopTriggeredPayload(
                arena_id=arena_id,
                reason="user_stopped",
                round=rounds_completed,
            )),
            {"arena_id": arena_id, "arena_phase": "mode3_arena_review"},
        )
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_WORKFLOW_COMPLETED),
            asdict(ArenaWorkflowCompletedPayload(
                arena_id=arena_id,
                mode="mode3_arena_review",
                status="stopped_early",
                agent_slots=list(config.agent_slots),
            )),
            {"arena_id": arena_id, "arena_phase": "mode3_arena_review"},
        )
        return Mode3Result(
            arena_id=arena_id,
            best_results=best_results,
            review_findings={},
            synthesis_content=None,
            synthesis_slot=None,
            rounds_completed=rounds_completed,
            stopped_early=True,
            cross_family_degraded=False,
            metadata={"mode": "mode3_arena_review"},
        )

    # ------------------------------------------------------------------
    # Phase 2 — Cross-review
    # ------------------------------------------------------------------
    review_findings: dict[str, list[ReviewFinding]] = {}
    cross_family_degraded = False

    # Build families dict.
    if backend_families is not None:
        families = dict(backend_families)
    else:
        families = {}
        for slot_id in config.agent_slots:
            adapter = agent_adapters[slot_id]
            families[slot_id] = get_backend_family(adapter.backend_id())

    pairing: CrossFamilyPairingResult = _pair_cross_family(
        list(config.agent_slots),
        families,
    )

    if pairing.degraded and pairing.reason == "same_family_only":
        # Same-family-only → skip cross-review, emit warning.
        cross_family_degraded = True
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_EARLY_STOP_TRIGGERED),
            asdict(ArenaEarlyStopTriggeredPayload(
                arena_id=arena_id,
                reason="same_family_only",
                round=0,
            )),
            {"arena_id": arena_id, "arena_phase": "mode3_arena_review"},
        )
    elif pairing.degraded and pairing.reason == "partial_same_family":
        # Partial same-family → proceed with available pairs, emit warning.
        cross_family_degraded = True
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_EARLY_STOP_TRIGGERED),
            asdict(ArenaEarlyStopTriggeredPayload(
                arena_id=arena_id,
                reason="partial_same_family",
                round=0,
            )),
            {"arena_id": arena_id, "arena_phase": "mode3_arena_review"},
        )

    # Run cross-review for each (reviewer_slot, reviewed_slot) pair.
    if not pairing.degraded or pairing.reason == "partial_same_family":
        for reviewer_slot, reviewed_slot in pairing.pairs.items():
            reviewed_state = best_results.get(reviewed_slot)
            if reviewed_state is None:
                continue

            review_req = _build_review_run_request(
                config,
                reviewer_slot,
                reviewed_slot,
                reviewed_state.content,
            )
            review_result = await run_agent_slot(
                slot_id=reviewer_slot,
                adapter=agent_adapters[reviewer_slot],
                run_request=review_req,
                timeout=30.0,
                max_retries=2,
            )

            if review_result.status != "success" or review_result.content is None:
                continue

            findings = _parse_review_findings(
                review_result.content,
                source_slot=reviewer_slot,
                reviewed_slot=reviewed_slot,
            )

            # Accumulate findings per reviewed slot.
            if reviewed_slot not in review_findings:
                review_findings[reviewed_slot] = []
            review_findings[reviewed_slot].extend(findings)

            # Emit arena.review_completed.
            await _emit(
                event_emitter,
                str(RunEventType.ARENA_REVIEW_COMPLETED),
                asdict(ArenaReviewCompletedPayload(
                    arena_id=arena_id,
                    reviewer_slot=reviewer_slot,
                    reviewed_slot=reviewed_slot,
                    round=0,
                    findings=[f.to_json() for f in findings],
                )),
                {
                    "arena_id": arena_id,
                    "arena_phase": "mode3_arena_review",
                    "reviewer_slot": reviewer_slot,
                    "reviewed_slot": reviewed_slot,
                },
            )

            # Persist cross-review output via ArtifactStore.
            if artifact_store is not None:
                artifact_store.store_round_output(
                    arena_id=arena_id,
                    agent_slot=reviewer_slot,
                    round=0,
                    content=review_result.content,
                    metadata={
                        "phase": "cross_review",
                        "reviewed_slot": reviewed_slot,
                        "reviewer_slot": reviewer_slot,
                    },
                )

            # Provenance logging with reviewer_slot populated.
            if provenance_logger is not None:
                for finding in findings:
                    provenance_logger.log_claim(
                        arena_id=arena_id,
                        claim=finding.description,
                        agent_slot=reviewed_slot,
                        reviewer_slot=reviewer_slot,
                    )

    # ------------------------------------------------------------------
    # Phase 3 — Synthesis (independent agent session, fresh context)
    # ------------------------------------------------------------------
    synthesis_content: str | None = None
    synthesis_slot: str | None = None

    if best_results:
        best_slot, best_content = _select_best_result(best_results)
        synthesis_instruction = _build_synthesis_prompt(
            best_content=best_content,
            review_findings=review_findings,
            task_instruction=config.task_instruction,
        )
        synthesis_req = _build_synthesis_run_request(config, synthesis_instruction)

        # Emit arena.synthesis_started.
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_SYNTHESIS_STARTED),
            asdict(ArenaSynthesisStartedPayload(
                arena_id=arena_id,
                round=0,
                source_slots=list(best_results.keys()),
            )),
            {"arena_id": arena_id, "arena_phase": "mode3_arena_review"},
        )

        synthesis_result = await run_agent_slot(
            slot_id="synthesis",
            adapter=synthesis_adapter,
            run_request=synthesis_req,
            timeout=30.0,
            max_retries=2,
        )

        if synthesis_result.status == "success" and synthesis_result.content is not None:
            synthesis_content = synthesis_result.content
            synthesis_slot = "synthesis"

            # Persist synthesis output via ArtifactStore.
            if artifact_store is not None:
                artifact_store.store_round_output(
                    arena_id=arena_id,
                    agent_slot="synthesis",
                    round=0,
                    content=synthesis_content,
                    metadata={"phase": "synthesis", "round": 0},
                )

        # Emit arena.synthesis_completed.
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_SYNTHESIS_COMPLETED),
            asdict(ArenaSynthesisCompletedPayload(
                arena_id=arena_id,
                round=0,
            )),
            {"arena_id": arena_id, "arena_phase": "mode3_arena_review"},
        )

    # ------------------------------------------------------------------
    # Emit arena.workflow_completed
    # ------------------------------------------------------------------
    status = "completed"
    await _emit(
        event_emitter,
        str(RunEventType.ARENA_WORKFLOW_COMPLETED),
        asdict(ArenaWorkflowCompletedPayload(
            arena_id=arena_id,
            mode="mode3_arena_review",
            status=status,
            agent_slots=list(config.agent_slots),
        )),
        {"arena_id": arena_id, "arena_phase": "mode3_arena_review"},
    )

    return Mode3Result(
        arena_id=arena_id,
        best_results=best_results,
        review_findings=review_findings,
        synthesis_content=synthesis_content,
        synthesis_slot=synthesis_slot,
        rounds_completed=rounds_completed,
        stopped_early=stopped_early,
        cross_family_degraded=cross_family_degraded,
        metadata={"mode": "mode3_arena_review"},
    )


__all__ = [
    "Mode3Result",
    "_build_synthesis_prompt",
    "_select_best_result",
    "run_mode3_arena_review",
]
