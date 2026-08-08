"""Mode 4 — Adversarial (Arena Review + Adversarial + Multi-round + Early Stop).

Mode 4 builds on Mode 3's arena review, then adds:

1. **Adversarial challenge** — a dedicated ``adversarial_adapter`` (a
   separate :class:`BackendAdapter` instance, NOT one of the candidate
   slots or the synthesis adapter) reviews the synthesis output for
   weaknesses using structured ``[FINDING]`` blocks.  Each challenge
   uses fresh context (new ``turn_id`` per round).
2. **Multi-round synthesis** — when the adversarial challenge finds
   high-severity issues, the synthesis adapter re-synthesizes
   incorporating the adversarial findings (fresh context per round).
3. **Early stopping** — three conditions checked by
   :func:`_should_stop_early`:
   - **Hard round cap**: ``round >= max_rounds - 1`` →
     ``"hard_round_cap"`` (checked FIRST, takes precedence).
   - **Convergence**: ``synthesis_score >= 8 AND high_severity_count
     == 0`` → ``"converged"``.
   - **User stop**: ``stop_signal.is_set()`` → ``"user_stopped"``.

The orchestrator **never produces content** — adversarial challenge
and re-synthesis are done by separate adapter instances with fresh
context (new ``turn_id`` per round).

ENGINE-04: Mode 4 adversarial arena.
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
    ArenaAdversarialChallengeCompletedPayload,
    ArenaEarlyStopTriggeredPayload,
    ArenaSynthesisCompletedPayload,
    ArenaSynthesisStartedPayload,
    ArenaWorkflowCompletedPayload,
    ArenaWorkflowStartedPayload,
)
from platform_runtime.protocols import BackendAdapter, RunRequest, SolutionBinding

from .artifact_store import ArtifactStore
from .mode1 import EventEmitter
from .mode2 import _extract_self_score
from .mode3 import Mode3Result, run_mode3_arena_review
from .review import ReviewFinding, SeverityLevel, _parse_review_findings
from .slot_runner import run_agent_slot


# ---------------------------------------------------------------------------
# Dataclasses (frozen, slotted)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SynthesisRound:
    """Per-round synthesis state captured during the adversarial loop.

    Fields
    ------
    round
        The adversarial loop iteration index (0-based).
    synthesis_content
        The synthesis content that was challenged in this round.
    synthesis_score
        The self-score extracted from ``synthesis_content``.
    adversarial_findings
        Structured findings from the adversarial challenge on this
        round's synthesis.
    high_severity_count
        Number of findings with ``severity == SeverityLevel.HIGH``.
    """

    round: int
    synthesis_content: str
    synthesis_score: int
    adversarial_findings: list[ReviewFinding]
    high_severity_count: int


@dataclass(frozen=True, slots=True)
class Mode4Result:
    """Frozen slotted result of a Mode 4 adversarial arena run.

    Fields
    ------
    arena_id
        Identifier of the arena workflow.
    mode3_result
        The complete :class:`Mode3Result` from the initial arena review
        phase.
    synthesis_rounds
        List of :class:`SynthesisRound` entries, one per completed
        adversarial challenge round.
    adversarial_findings
        List of lists of :class:`ReviewFinding`, one list per round.
    final_synthesis_content
        The synthesis content from the last round, or ``None`` when no
        adversarial rounds ran.
    final_synthesis_score
        The self-score from the last synthesis round.
    rounds_completed
        Number of adversarial rounds completed.
    stopped_early
        ``True`` when the loop stopped via convergence or user stop.
        ``False`` for hard round cap (all rounds exhausted).
    stop_reason
        ``"converged"``, ``"hard_round_cap"``, ``"user_stopped"``, or
        ``""`` when no stop occurred.
    metadata
        Additional structured metadata.
    """

    arena_id: str
    mode3_result: Mode3Result
    synthesis_rounds: list[SynthesisRound]
    adversarial_findings: list[list[ReviewFinding]]
    final_synthesis_content: str | None
    final_synthesis_score: int
    rounds_completed: int
    stopped_early: bool
    stop_reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Early stopping logic
# ---------------------------------------------------------------------------


def _should_stop_early(
    round: int,
    max_rounds: int,
    synthesis_score: int,
    high_severity_count: int,
) -> tuple[bool, str]:
    """Check whether the adversarial loop should stop early.

    Three conditions are checked (in priority order):

    1. **Hard round cap** (checked FIRST — takes precedence):
       ``round >= max_rounds - 1`` → ``(True, "hard_round_cap")``.
       Reaching the cap is not "early" — it is the maximum.
    2. **Convergence**: ``synthesis_score >= 8 AND
       high_severity_count == 0`` → ``(True, "converged")``.
       ALL conditions must be met; missing any one means no stop.
    3. Otherwise → ``(False, "")``.

    The user-stop condition (``stop_signal.is_set()``) is checked
    separately at the top of each loop iteration in
    :func:`run_mode4_adversarial`, not in this function.

    Returns
    -------
    tuple[bool, str]
        ``(should_stop, reason)`` — ``reason`` is ``"hard_round_cap"``,
        ``"converged"``, or ``""``.
    """
    # Hard round cap — checked FIRST (takes precedence).
    if round >= max_rounds - 1:
        return (True, "hard_round_cap")
    # Convergence — ALL conditions must be met.
    if synthesis_score >= 8 and high_severity_count == 0:
        return (True, "converged")
    return (False, "")


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
# Filtered emitter — forwards only score_recorded events to Mode 3's emitter
# ---------------------------------------------------------------------------


class _ScoreOnlyForwarder:
    """Wrapper emitter that forwards only ``arena.score_recorded`` events.

    Used when calling :func:`run_mode3_arena_review` from Mode 4 so that
    stop-signal logic (which listens for score events) works, while
    suppressing Mode 3's own ``workflow_started`` / ``workflow_completed``
    / ``early_stop_triggered`` events (Mode 4 emits its own lifecycle
    events).
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
# Prompt builders
# ---------------------------------------------------------------------------


def _build_adversarial_prompt(synthesis_content: str) -> str:
    """Construct the adversarial challenge prompt.

    Asks the adversarial agent to find weaknesses in the synthesis
    content using ``[FINDING]`` blocks.
    """
    return (
        f"请审查以下综合回答，找出其中的弱点和问题。\n\n"
        f"综合回答：\n{synthesis_content}\n\n"
        f"请使用以下格式输出你的发现：\n"
        f"[FINDING]\n"
        f"description: 问题描述\n"
        f"confidence: Certain/Likely/Possible\n"
        f"severity: High/Medium/Low\n"
        f"confirmed: true/false\n"
        f"[/FINDING]"
    )


def _build_resynthesis_prompt(
    previous_synthesis: str,
    adversarial_findings: list[ReviewFinding],
    task_instruction: str,
) -> str:
    """Construct the re-synthesis prompt incorporating adversarial findings.

    Includes: (1) the original task instruction, (2) the previous
    synthesis content, (3) all adversarial findings formatted as
    structured text with severity, confidence, and description.
    """
    lines: list[str] = [
        f"原始任务：{task_instruction}",
        "",
        "上一轮综合回答：",
        previous_synthesis,
        "",
        "对抗审查发现的问题：",
    ]

    if not adversarial_findings:
        lines.append("（无问题）")
    else:
        for finding in adversarial_findings:
            lines.append(
                f"- 严重程度：{finding.severity.value}"
                f" | 置信度：{finding.confidence.value}"
                f" | 描述：{finding.description}"
            )

    lines.extend([
        "",
        "请根据对抗审查发现的问题，重新综合产出一个更好的版本。"
        "保留原有回答中的正确内容，并修正发现的问题。",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Run-request builders
# ---------------------------------------------------------------------------


def _build_adversarial_run_request(
    config: ArenaWorkflowConfig,
    round: int,
    instruction: str,
) -> RunRequest:
    """Build a fresh ``RunRequest`` for an adversarial challenge.

    Each adversarial challenge gets a new ``turn_id`` of the form
    ``"{arena_id}-adversarial-round{round}"`` so that every challenge
    uses fresh context (ENGINE-06).
    """
    return RunRequest(
        turn=AgentTurn(
            turn_id=f"{config.arena_id}-adversarial-round{round}",
            conversation_id=f"{config.arena_id}",
            channel="web",
            user_id="arena",
            message_type="text",
            received_at=datetime.now(UTC).isoformat(),
            content=instruction,
        ),
        solution=SolutionBinding(
            solution_id=f"{config.arena_id}-adversarial",
        ),
    )


def _build_resynthesis_run_request(
    config: ArenaWorkflowConfig,
    round: int,
    instruction: str,
) -> RunRequest:
    """Build a fresh ``RunRequest`` for a re-synthesis execution.

    Each re-synthesis gets a new ``turn_id`` of the form
    ``"{arena_id}-synthesis-round{round}"`` so that every re-synthesis
    uses fresh context (ENGINE-06) — no session reuse.
    """
    return RunRequest(
        turn=AgentTurn(
            turn_id=f"{config.arena_id}-synthesis-round{round}",
            conversation_id=f"{config.arena_id}",
            channel="web",
            user_id="arena",
            message_type="text",
            received_at=datetime.now(UTC).isoformat(),
            content=instruction,
        ),
        solution=SolutionBinding(
            solution_id=f"{config.arena_id}-synthesis",
        ),
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_mode4_adversarial(
    config: ArenaWorkflowConfig,
    agent_adapters: dict[str, BackendAdapter],
    synthesis_adapter: BackendAdapter,
    adversarial_adapter: BackendAdapter,
    event_emitter: EventEmitter | None = None,
    stop_signal: asyncio.Event | None = None,
    artifact_store: ArtifactStore | None = None,
    backend_families: dict[str, str] | None = None,
    provenance_logger: Any | None = None,
) -> Mode4Result:
    """Run a Mode 4 adversarial arena: Mode 3 + adversarial + multi-round + early stop.

    Parameters
    ----------
    config
        Arena workflow configuration.  ``max_rounds`` controls both
        Mode 3's self-score iteration and the adversarial loop.
    agent_adapters
        Mapping of slot ID → :class:`BackendAdapter` for candidate agents.
    synthesis_adapter
        A **separate** :class:`BackendAdapter` for synthesis and
        re-synthesis.  Must NOT be one of the candidate slot adapters.
    adversarial_adapter
        A **separate** :class:`BackendAdapter` for adversarial
        challenges.  Must NOT be one of the candidate slot adapters or
        the synthesis adapter — the orchestrator never produces content.
    event_emitter
        Optional callback for emitting arena lifecycle events.
    stop_signal
        Optional :class:`asyncio.Event` for user-initiated stop.
    artifact_store
        Optional :class:`ArtifactStore` for persistence.
    backend_families
        Optional explicit slot → family mapping for Mode 3's cross-review.
    provenance_logger
        Optional :class:`ProvenanceLogger` for Mode 3's provenance logging.

    Returns
    -------
    Mode4Result
        The complete Mode 4 result with Mode 3 result, synthesis rounds,
        adversarial findings, and early-stop metadata.
    """
    arena_id = config.arena_id

    # ------------------------------------------------------------------
    # Emit arena.workflow_started
    # ------------------------------------------------------------------
    await _emit(
        event_emitter,
        str(RunEventType.ARENA_WORKFLOW_STARTED),
        asdict(ArenaWorkflowStartedPayload(
            arena_id=arena_id,
            mode="mode4_adversarial",
            agent_slots=list(config.agent_slots),
        )),
        {"arena_id": arena_id, "arena_phase": "mode4_adversarial"},
    )

    # ------------------------------------------------------------------
    # Phase 1 — Run Mode 3 arena review (self-score + cross-review + synthesis)
    # ------------------------------------------------------------------
    # Forward only score_recorded events to the real emitter so that
    # stop-signal logic works during Mode 3's self-score iteration,
    # while suppressing Mode 3's own lifecycle events (Mode 4 emits
    # its own).
    score_emitter = _ScoreOnlyForwarder(event_emitter)
    mode3_result: Mode3Result = await run_mode3_arena_review(
        config=config,
        agent_adapters=agent_adapters,
        synthesis_adapter=synthesis_adapter,
        event_emitter=score_emitter,
        stop_signal=stop_signal,
        artifact_store=artifact_store,
        backend_families=backend_families,
        provenance_logger=provenance_logger,
    )

    # If Mode 3 was stopped early or produced no synthesis, return early.
    if mode3_result.stopped_early or mode3_result.synthesis_content is None:
        stop_reason = "user_stopped" if mode3_result.stopped_early else ""
        if mode3_result.stopped_early:
            await _emit(
                event_emitter,
                str(RunEventType.ARENA_EARLY_STOP_TRIGGERED),
                asdict(ArenaEarlyStopTriggeredPayload(
                    arena_id=arena_id,
                    reason="user_stopped",
                    round=0,
                )),
                {"arena_id": arena_id, "arena_phase": "mode4_adversarial"},
            )
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_WORKFLOW_COMPLETED),
            asdict(ArenaWorkflowCompletedPayload(
                arena_id=arena_id,
                mode="mode4_adversarial",
                status="stopped_early" if mode3_result.stopped_early else "completed",
                agent_slots=list(config.agent_slots),
            )),
            {"arena_id": arena_id, "arena_phase": "mode4_adversarial"},
        )
        return Mode4Result(
            arena_id=arena_id,
            mode3_result=mode3_result,
            synthesis_rounds=[],
            adversarial_findings=[],
            final_synthesis_content=mode3_result.synthesis_content,
            final_synthesis_score=0,
            rounds_completed=0,
            stopped_early=mode3_result.stopped_early,
            stop_reason=stop_reason,
            metadata={"mode": "mode4_adversarial"},
        )

    # ------------------------------------------------------------------
    # Phase 2 — Adversarial loop with multi-round synthesis + early stop
    # ------------------------------------------------------------------
    current_synthesis: str = mode3_result.synthesis_content
    synthesis_rounds: list[SynthesisRound] = []
    adversarial_findings_all: list[list[ReviewFinding]] = []
    stopped_early = False
    stop_reason = ""

    for r in range(config.max_rounds):
        # a. Check stop_signal at the TOP of each round.
        if stop_signal is not None and stop_signal.is_set():
            stopped_early = True
            stop_reason = "user_stopped"
            await _emit(
                event_emitter,
                str(RunEventType.ARENA_EARLY_STOP_TRIGGERED),
                asdict(ArenaEarlyStopTriggeredPayload(
                    arena_id=arena_id,
                    reason="user_stopped",
                    round=r,
                )),
                {"arena_id": arena_id, "arena_phase": "mode4_adversarial"},
            )
            break

        # b. Run adversarial challenge (fresh context per round).
        adv_instruction = _build_adversarial_prompt(current_synthesis)
        adv_req = _build_adversarial_run_request(config, r, adv_instruction)
        adv_result = await run_agent_slot(
            slot_id="adversarial",
            adapter=adversarial_adapter,
            run_request=adv_req,
            timeout=30.0,
            max_retries=2,
        )

        # Parse adversarial findings.
        findings: list[ReviewFinding] = []
        if adv_result.status == "success" and adv_result.content is not None:
            findings = _parse_review_findings(
                adv_result.content,
                source_slot="adversarial",
                reviewed_slot="synthesis",
            )

        # Count high-severity findings.
        high_count = sum(
            1 for f in findings if f.severity == SeverityLevel.HIGH
        )

        # c. Extract synthesis score from current synthesis content.
        score = _extract_self_score(current_synthesis)

        # f. Append SynthesisRound (captures this round's synthesis +
        #    adversarial findings, before stop check so the round's
        #    data is preserved even when stopping).
        synthesis_rounds.append(SynthesisRound(
            round=r,
            synthesis_content=current_synthesis,
            synthesis_score=score,
            adversarial_findings=findings,
            high_severity_count=high_count,
        ))
        adversarial_findings_all.append(findings)

        # Emit arena.adversarial_challenge_completed.
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_ADVERSARIAL_CHALLENGE_COMPLETED),
            asdict(ArenaAdversarialChallengeCompletedPayload(
                arena_id=arena_id,
                challenger_slot="adversarial",
                challenged_slot="synthesis",
                round=r,
                findings=[f.to_json() for f in findings],
            )),
            {
                "arena_id": arena_id,
                "arena_phase": "mode4_adversarial",
                "challenger_slot": "adversarial",
                "challenged_slot": "synthesis",
            },
        )

        # Persist adversarial output via ArtifactStore.
        if artifact_store is not None and adv_result.content is not None:
            artifact_store.store_round_output(
                arena_id=arena_id,
                agent_slot="adversarial",
                round=r,
                content=adv_result.content,
                metadata={
                    "phase": "adversarial_challenge",
                    "round": r,
                    "high_severity_count": high_count,
                },
            )

        # d. Check _should_stop_early.
        should_stop, reason = _should_stop_early(
            round=r,
            max_rounds=config.max_rounds,
            synthesis_score=score,
            high_severity_count=high_count,
        )
        if should_stop:
            # stopped_early=True only for convergence (genuine early
            # stop).  hard_round_cap means all rounds exhausted → False.
            stopped_early = (reason == "converged")
            stop_reason = reason
            await _emit(
                event_emitter,
                str(RunEventType.ARENA_EARLY_STOP_TRIGGERED),
                asdict(ArenaEarlyStopTriggeredPayload(
                    arena_id=arena_id,
                    reason=reason,
                    round=r,
                )),
                {"arena_id": arena_id, "arena_phase": "mode4_adversarial"},
            )
            break

        # e. Re-synthesize with adversarial findings (fresh context).
        resynth_instruction = _build_resynthesis_prompt(
            previous_synthesis=current_synthesis,
            adversarial_findings=findings,
            task_instruction=config.task_instruction,
        )
        resynth_req = _build_resynthesis_run_request(
            config, r + 1, resynth_instruction,
        )

        # Emit arena.synthesis_started.
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_SYNTHESIS_STARTED),
            asdict(ArenaSynthesisStartedPayload(
                arena_id=arena_id,
                round=r + 1,
                source_slots=["synthesis"],
            )),
            {"arena_id": arena_id, "arena_phase": "mode4_adversarial"},
        )

        resynth_result = await run_agent_slot(
            slot_id="synthesis",
            adapter=synthesis_adapter,
            run_request=resynth_req,
            timeout=30.0,
            max_retries=2,
        )

        if resynth_result.status == "success" and resynth_result.content is not None:
            current_synthesis = resynth_result.content
            # Persist re-synthesis output via ArtifactStore.
            if artifact_store is not None:
                artifact_store.store_round_output(
                    arena_id=arena_id,
                    agent_slot="synthesis",
                    round=r + 1,
                    content=current_synthesis,
                    metadata={
                        "phase": "resynthesis",
                        "round": r + 1,
                    },
                )

        # Emit arena.synthesis_completed.
        await _emit(
            event_emitter,
            str(RunEventType.ARENA_SYNTHESIS_COMPLETED),
            asdict(ArenaSynthesisCompletedPayload(
                arena_id=arena_id,
                round=r + 1,
            )),
            {"arena_id": arena_id, "arena_phase": "mode4_adversarial"},
        )

    # ------------------------------------------------------------------
    # Set final values from the last synthesis round
    # ------------------------------------------------------------------
    if synthesis_rounds:
        last_round = synthesis_rounds[-1]
        final_synthesis_content: str | None = last_round.synthesis_content
        final_synthesis_score: int = last_round.synthesis_score
    else:
        final_synthesis_content = mode3_result.synthesis_content
        final_synthesis_score = 0

    rounds_completed = len(synthesis_rounds)

    # ------------------------------------------------------------------
    # Emit arena.workflow_completed
    # ------------------------------------------------------------------
    status = "stopped_early" if stopped_early else "completed"
    await _emit(
        event_emitter,
        str(RunEventType.ARENA_WORKFLOW_COMPLETED),
        asdict(ArenaWorkflowCompletedPayload(
            arena_id=arena_id,
            mode="mode4_adversarial",
            status=status,
            agent_slots=list(config.agent_slots),
        )),
        {"arena_id": arena_id, "arena_phase": "mode4_adversarial"},
    )

    return Mode4Result(
        arena_id=arena_id,
        mode3_result=mode3_result,
        synthesis_rounds=synthesis_rounds,
        adversarial_findings=adversarial_findings_all,
        final_synthesis_content=final_synthesis_content,
        final_synthesis_score=final_synthesis_score,
        rounds_completed=rounds_completed,
        stopped_early=stopped_early,
        stop_reason=stop_reason,
        metadata={"mode": "mode4_adversarial"},
    )


__all__ = [
    "Mode4Result",
    "SynthesisRound",
    "_should_stop_early",
    "run_mode4_adversarial",
]
