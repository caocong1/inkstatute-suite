"""Tests for Mode 4 — Adversarial (ENGINE-04).

Covers: Mode4Result and SynthesisRound frozen slotted shape, adversarial
challenge with separate adapter, multi-round synthesis, early stopping
(convergence + hard round cap + user stop), event emission, fresh context
per round, and partial result preservation on user stop.
"""

from __future__ import annotations

import asyncio
import dataclasses
import unittest
from typing import Any

from platform_contract.arena_contract import ArenaWorkflowConfig
from platform_contract.enums import RunEventType

from arena_engine.mock_acp import MockACPBackendAdapter
from arena_engine.mode3 import Mode3Result
from arena_engine.mode4 import (
    Mode4Result,
    SynthesisRound,
    _should_stop_early,
    run_mode4_adversarial,
)
from arena_engine.review import SeverityLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecordingEmitter:
    """Synchronous emitter that captures all events for assertions."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "payload": dict(payload),
                "metadata": dict(metadata) if metadata else {},
            }
        )


class StopAfterAdversarialEmitter(RecordingEmitter):
    """Sets a stop_signal after the first adversarial_challenge_completed event."""

    def __init__(self, stop_signal: asyncio.Event) -> None:
        super().__init__()
        self._stop_signal = stop_signal

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().emit(event_type, payload, metadata)
        if event_type == str(RunEventType.ARENA_ADVERSARIAL_CHALLENGE_COMPLETED):
            self._stop_signal.set()


def _scored_response(score: int, analysis: str = "分析：...") -> str:
    return f"自评分数：{score}/10\n{analysis}"


def _synth_response(score: int, content: str = "综合最终版本") -> str:
    """A synthesis response with an embedded self-score."""
    return f"自评分数：{score}/10\n{content}"


def _finding_response(
    description: str = "缺少引用",
    confidence: str = "Likely",
    severity: str = "Medium",
    confirmed: bool = True,
) -> str:
    return (
        f"[FINDING]\n"
        f"description: {description}\n"
        f"confidence: {confidence}\n"
        f"severity: {severity}\n"
        f"confirmed: {confirmed}\n"
        f"[/FINDING]"
    )


def _finding_high_response(description: str = "严重逻辑错误") -> str:
    return _finding_response(description=description, severity="High")


def _no_finding_response() -> str:
    """Adversarial response with no [FINDING] blocks — no issues found."""
    return "未发现严重问题。综合回答质量良好。"


def _config_2_slots(max_rounds: int = 2) -> ArenaWorkflowConfig:
    return ArenaWorkflowConfig(
        arena_id="a-4",
        mode="mode4_adversarial",
        agent_slots=["slot-0", "slot-1"],
        task_instruction="审查合同效力",
        max_rounds=max_rounds,
    )


def _make_cross_family_adapters(
    slot0_responses: list[str],
    slot1_responses: list[str],
) -> dict[str, MockACPBackendAdapter]:
    """Create 2 cross-family candidate slot adapters."""
    return {
        "slot-0": MockACPBackendAdapter(
            backend_id="hermes",
            responses=slot0_responses,
            agent_slot="slot-0",
        ),
        "slot-1": MockACPBackendAdapter(
            backend_id="codex",
            responses=slot1_responses,
            agent_slot="slot-1",
        ),
    }


def _make_synthesis_adapter(responses: list[str]) -> MockACPBackendAdapter:
    return MockACPBackendAdapter(
        backend_id="gemini-cli",
        responses=responses,
        agent_slot="synthesis",
    )


def _make_adversarial_adapter(responses: list[str]) -> MockACPBackendAdapter:
    return MockACPBackendAdapter(
        backend_id="inkstatute-agent",
        responses=responses,
        agent_slot="adversarial",
    )


# ---------------------------------------------------------------------------
# Mode 4 Adversarial Tests
# ---------------------------------------------------------------------------


class Mode4AdversarialTests(unittest.IsolatedAsyncioTestCase):
    """Cover all Mode 4 adversarial arena behaviours."""

    # -- Test 1: Mode4Result frozen slotted dataclass shape -------------------

    def test_mode4_result_frozen_slotted_shape(self) -> None:
        """Mode4Result is frozen slotted with required fields."""
        self.assertTrue(dataclasses.is_dataclass(Mode4Result))
        fields_map = {f.name for f in dataclasses.fields(Mode4Result)}
        expected = {
            "arena_id",
            "mode3_result",
            "synthesis_rounds",
            "adversarial_findings",
            "final_synthesis_content",
            "final_synthesis_score",
            "rounds_completed",
            "stopped_early",
            "stop_reason",
            "metadata",
        }
        self.assertEqual(fields_map, expected)
        # frozen
        instance = Mode4Result(
            arena_id="x",
            mode3_result=Mode3Result(arena_id="x"),
            synthesis_rounds=[],
            adversarial_findings=[],
            final_synthesis_content=None,
            final_synthesis_score=0,
            rounds_completed=0,
            stopped_early=False,
            stop_reason="",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            instance.arena_id = "y"  # type: ignore[misc]
        # slotted — no __dict__
        self.assertFalse(hasattr(instance, "__dict__"))

    # -- Test 2: SynthesisRound frozen slotted dataclass shape ----------------

    def test_synthesis_round_frozen_slotted_shape(self) -> None:
        """SynthesisRound is frozen slotted with required fields."""
        self.assertTrue(dataclasses.is_dataclass(SynthesisRound))
        fields_map = {f.name for f in dataclasses.fields(SynthesisRound)}
        expected = {
            "round",
            "synthesis_content",
            "synthesis_score",
            "adversarial_findings",
            "high_severity_count",
        }
        self.assertEqual(fields_map, expected)
        # frozen
        instance = SynthesisRound(
            round=0,
            synthesis_content="x",
            synthesis_score=8,
            adversarial_findings=[],
            high_severity_count=0,
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            instance.round = 1  # type: ignore[misc]
        # slotted — no __dict__
        self.assertFalse(hasattr(instance, "__dict__"))

    # -- Test 3: convergence early stop ---------------------------------------

    async def test_convergence_early_stop(self) -> None:
        """Score >=8 and no high-severity → converged, stopped_early=True."""
        config = _config_2_slots(max_rounds=2)
        # Mode 3 self-score: 2 rounds × 2 slots = 4 responses, + 2 cross-review
        adapters = _make_cross_family_adapters(
            slot0_responses=[
                _scored_response(8), _scored_response(8),
                _finding_response("问题A"),
            ],
            slot1_responses=[
                _scored_response(7), _scored_response(7),
                _finding_response("问题B"),
            ],
        )
        synthesis = _make_synthesis_adapter([_synth_response(8, "综合v1")])
        adversarial = _make_adversarial_adapter([_no_finding_response()])
        emitter = RecordingEmitter()
        result = await run_mode4_adversarial(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            adversarial_adapter=adversarial,
            event_emitter=emitter,
        )
        self.assertTrue(result.stopped_early)
        self.assertEqual(result.stop_reason, "converged")
        self.assertEqual(result.rounds_completed, 1)
        self.assertGreaterEqual(len(result.synthesis_rounds), 1)

    # -- Test 4: adversarial_challenge_completed event ------------------------

    async def test_adversarial_challenge_completed_event(self) -> None:
        """arena.adversarial_challenge_completed emitted with correct payload."""
        config = _config_2_slots(max_rounds=2)
        adapters = _make_cross_family_adapters(
            slot0_responses=[
                _scored_response(8), _scored_response(8),
                _finding_response("问题A"),
            ],
            slot1_responses=[
                _scored_response(7), _scored_response(7),
                _finding_response("问题B"),
            ],
        )
        synthesis = _make_synthesis_adapter([_synth_response(8, "综合v1")])
        adversarial = _make_adversarial_adapter([_no_finding_response()])
        emitter = RecordingEmitter()
        await run_mode4_adversarial(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            adversarial_adapter=adversarial,
            event_emitter=emitter,
        )
        adv_events = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_ADVERSARIAL_CHALLENGE_COMPLETED)
        ]
        self.assertGreaterEqual(len(adv_events), 1)
        for ev in adv_events:
            self.assertEqual(ev["payload"]["challenger_slot"], "adversarial")
            self.assertEqual(ev["payload"]["challenged_slot"], "synthesis")
            self.assertIn("round", ev["payload"])
            self.assertIsInstance(ev["payload"]["findings"], list)

    # -- Test 5: early_stop_triggered event with reason ------------------------

    async def test_early_stop_triggered_converged(self) -> None:
        """arena.early_stop_triggered emitted with reason='converged'."""
        config = _config_2_slots(max_rounds=2)
        adapters = _make_cross_family_adapters(
            slot0_responses=[
                _scored_response(8), _scored_response(8),
                _finding_response("问题A"),
            ],
            slot1_responses=[
                _scored_response(7), _scored_response(7),
                _finding_response("问题B"),
            ],
        )
        synthesis = _make_synthesis_adapter([_synth_response(8, "综合v1")])
        adversarial = _make_adversarial_adapter([_no_finding_response()])
        emitter = RecordingEmitter()
        result = await run_mode4_adversarial(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            adversarial_adapter=adversarial,
            event_emitter=emitter,
        )
        stop_events = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_EARLY_STOP_TRIGGERED)
        ]
        self.assertEqual(len(stop_events), 1)
        self.assertEqual(stop_events[0]["payload"]["reason"], "converged")
        self.assertEqual(result.stop_reason, "converged")

    # -- Test 6: multi-round synthesis ----------------------------------------

    async def test_multi_round_synthesis(self) -> None:
        """High-severity in round 0 → re-synthesis; 2 synthesis_rounds entries."""
        config = _config_2_slots(max_rounds=2)
        adapters = _make_cross_family_adapters(
            slot0_responses=[
                _scored_response(8), _scored_response(8),
                _finding_response("问题A"),
            ],
            slot1_responses=[
                _scored_response(7), _scored_response(7),
                _finding_response("问题B"),
            ],
        )
        # synthesis: Mode 3 synthesis (score 8) + re-synthesis (score 6)
        synthesis = _make_synthesis_adapter([
            _synth_response(8, "综合v1"),
            _synth_response(6, "综合v2"),
        ])
        # adversarial: round 0 high-severity, round 1 high-severity
        adversarial = _make_adversarial_adapter([
            _finding_high_response("严重问题A"),
            _finding_high_response("严重问题B"),
        ])
        emitter = RecordingEmitter()
        result = await run_mode4_adversarial(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            adversarial_adapter=adversarial,
            event_emitter=emitter,
        )
        # 2 synthesis_rounds entries (round 0 and round 1)
        self.assertEqual(len(result.synthesis_rounds), 2)
        # Round 0: high-severity found → don't stop → re-synthesis
        self.assertGreater(result.synthesis_rounds[0].high_severity_count, 0)
        # Round 1: hard round cap (1 >= 1)
        self.assertFalse(result.stopped_early)
        self.assertEqual(result.stop_reason, "hard_round_cap")
        # synthesis_started/completed emitted for re-synthesis
        synth_started = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_SYNTHESIS_STARTED)
        ]
        synth_completed = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_SYNTHESIS_COMPLETED)
        ]
        self.assertGreaterEqual(len(synth_started), 1)
        self.assertGreaterEqual(len(synth_completed), 1)

    # -- Test 7: adversarial adapter is separate + fresh context --------------

    async def test_adversarial_adapter_separate_and_fresh_context(self) -> None:
        """Adversarial adapter is a separate instance with fresh turn_id per round."""
        config = _config_2_slots(max_rounds=2)
        adapters = _make_cross_family_adapters(
            slot0_responses=[
                _scored_response(8), _scored_response(8),
                _finding_response("问题A"),
            ],
            slot1_responses=[
                _scored_response(7), _scored_response(7),
                _finding_response("问题B"),
            ],
        )
        synthesis = _make_synthesis_adapter([_synth_response(8, "综合v1")])
        adversarial = _make_adversarial_adapter([_no_finding_response()])
        await run_mode4_adversarial(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            adversarial_adapter=adversarial,
        )
        # Adversarial is a distinct object from slot adapters and synthesis
        self.assertIsNot(adversarial, adapters["slot-0"])
        self.assertIsNot(adversarial, adapters["slot-1"])
        self.assertIsNot(adversarial, synthesis)
        # Adversarial adapter received at least one submit_run
        self.assertGreaterEqual(len(adversarial.submitted_requests), 1)
        # Fresh context: turn_id follows pattern "{arena_id}-adversarial-round{r}"
        for i, req in enumerate(adversarial.submitted_requests):
            expected_turn_id = f"a-4-adversarial-round{i}"
            self.assertEqual(req.turn.turn_id, expected_turn_id)

    # -- Test 8: user stop during adversarial loop ----------------------------

    async def test_user_stop_during_adversarial_loop(self) -> None:
        """User stop via stop_signal → stopped_early=True, user_stopped, partial results."""
        config = _config_2_slots(max_rounds=3)
        stop_signal = asyncio.Event()
        adapters = _make_cross_family_adapters(
            slot0_responses=[
                _scored_response(8), _scored_response(8),
                _scored_response(8),
                _finding_response("问题A"),
            ],
            slot1_responses=[
                _scored_response(7), _scored_response(7),
                _scored_response(7),
                _finding_response("问题B"),
            ],
        )
        # synthesis: Mode 3 synthesis + re-synthesis responses
        synthesis = _make_synthesis_adapter([
            _synth_response(8, "综合v1"),
            _synth_response(6, "综合v2"),
            _synth_response(6, "综合v3"),
        ])
        # adversarial: round 0 finds high-severity → re-synthesis →
        # round 1 adversarial_challenge_completed → stop_signal set
        adversarial = _make_adversarial_adapter([
            _finding_high_response("严重问题A"),
            _finding_high_response("严重问题B"),
            _finding_high_response("严重问题C"),
        ])
        emitter = StopAfterAdversarialEmitter(stop_signal)
        result = await run_mode4_adversarial(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            adversarial_adapter=adversarial,
            event_emitter=emitter,
            stop_signal=stop_signal,
        )
        self.assertTrue(result.stopped_early)
        self.assertEqual(result.stop_reason, "user_stopped")
        # Partial results preserved — at least 1 synthesis round completed
        self.assertGreaterEqual(len(result.synthesis_rounds), 1)
        # early_stop_triggered with reason="user_stopped"
        stop_events = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_EARLY_STOP_TRIGGERED)
            and e["payload"]["reason"] == "user_stopped"
        ]
        self.assertEqual(len(stop_events), 1)

    # -- Integration: hard round cap exhaustion (Task 2 Test 6) ---------------

    async def test_hard_round_cap_exhaustion(self) -> None:
        """max_rounds=4, always high-severity, never ≥8 → hard_round_cap, not early."""
        config = _config_2_slots(max_rounds=4)
        n_rounds = config.max_rounds
        adapters = _make_cross_family_adapters(
            slot0_responses=[
                _scored_response(5) for _ in range(n_rounds)
            ] + [_finding_response("问题A")],
            slot1_responses=[
                _scored_response(4) for _ in range(n_rounds)
            ] + [_finding_response("问题B")],
        )
        # synthesis: Mode 3 synthesis (score 5) + 3 re-synthesis responses
        synthesis = _make_synthesis_adapter([
            _synth_response(5, f"综合v{i}")
            for i in range(n_rounds)
        ])
        # adversarial: always finds high-severity
        adversarial = _make_adversarial_adapter([
            _finding_high_response(f"严重问题{i}")
            for i in range(n_rounds)
        ])
        result = await run_mode4_adversarial(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            adversarial_adapter=adversarial,
        )
        self.assertFalse(result.stopped_early)
        self.assertEqual(result.stop_reason, "hard_round_cap")
        self.assertEqual(result.rounds_completed, n_rounds)

    # -- Integration: convergence at round 0 (Task 2 Test 7) ------------------

    async def test_convergence_at_round_0(self) -> None:
        """Round 0 adversarial finds no high-severity, score ≥8 → converged."""
        config = _config_2_slots(max_rounds=4)
        n_rounds = config.max_rounds
        adapters = _make_cross_family_adapters(
            slot0_responses=[
                _scored_response(8) for _ in range(n_rounds)
            ] + [_finding_response("问题A")],
            slot1_responses=[
                _scored_response(7) for _ in range(n_rounds)
            ] + [_finding_response("问题B")],
        )
        synthesis = _make_synthesis_adapter([_synth_response(8, "综合v1")])
        adversarial = _make_adversarial_adapter([_no_finding_response()])
        result = await run_mode4_adversarial(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            adversarial_adapter=adversarial,
        )
        self.assertTrue(result.stopped_early)
        self.assertEqual(result.stop_reason, "converged")
        self.assertEqual(result.rounds_completed, 1)

    # -- Integration: early_stop_triggered payload (Task 2 Test 8) ------------

    async def test_early_stop_triggered_payload_round(self) -> None:
        """arena.early_stop_triggered payload has reason and round."""
        config = _config_2_slots(max_rounds=2)
        adapters = _make_cross_family_adapters(
            slot0_responses=[
                _scored_response(8), _scored_response(8),
                _finding_response("问题A"),
            ],
            slot1_responses=[
                _scored_response(7), _scored_response(7),
                _finding_response("问题B"),
            ],
        )
        synthesis = _make_synthesis_adapter([_synth_response(8, "综合v1")])
        adversarial = _make_adversarial_adapter([_no_finding_response()])
        emitter = RecordingEmitter()
        result = await run_mode4_adversarial(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            adversarial_adapter=adversarial,
            event_emitter=emitter,
        )
        stop_events = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_EARLY_STOP_TRIGGERED)
        ]
        self.assertEqual(len(stop_events), 1)
        self.assertEqual(stop_events[0]["payload"]["reason"], result.stop_reason)
        self.assertEqual(stop_events[0]["payload"]["round"], 0)


# ---------------------------------------------------------------------------
# Early Stopping Unit Tests (pure function — no async)
# ---------------------------------------------------------------------------


class EarlyStoppingTests(unittest.TestCase):
    """Unit tests for _should_stop_early — pure function, no I/O."""

    # -- Test 1: convergence — score ≥8 AND zero high-severity ----------------

    def test_convergence_score_ge_8_zero_high_severity(self) -> None:
        """score=9, high=0, round=0, max=4 → (True, 'converged')."""
        result = _should_stop_early(
            round=0, max_rounds=4, synthesis_score=9, high_severity_count=0,
        )
        self.assertEqual(result, (True, "converged"))

    # -- Test 2: high-severity present → no stop ------------------------------

    def test_high_severity_present_no_stop(self) -> None:
        """score=9, high=1 → (False, '') — high-severity prevents convergence."""
        result = _should_stop_early(
            round=0, max_rounds=4, synthesis_score=9, high_severity_count=1,
        )
        self.assertEqual(result, (False, ""))

    # -- Test 3: score < 8 → no stop even with zero high-severity -------------

    def test_score_below_8_no_stop(self) -> None:
        """score=7, high=0 → (False, '') — score <8 prevents convergence."""
        result = _should_stop_early(
            round=0, max_rounds=4, synthesis_score=7, high_severity_count=0,
        )
        self.assertEqual(result, (False, ""))

    # -- Test 4: hard round cap reached ---------------------------------------

    def test_hard_round_cap_reached(self) -> None:
        """round=3, max=4, score=5, high=3 → (True, 'hard_round_cap')."""
        result = _should_stop_early(
            round=3, max_rounds=4, synthesis_score=5, high_severity_count=3,
        )
        self.assertEqual(result, (True, "hard_round_cap"))

    # -- Test 5: hard cap takes precedence over convergence -------------------

    def test_hard_cap_precedence_over_converged(self) -> None:
        """round=4, max=4, score=9, high=0 → (True, 'hard_round_cap') — cap first."""
        result = _should_stop_early(
            round=4, max_rounds=4, synthesis_score=9, high_severity_count=0,
        )
        self.assertEqual(result, (True, "hard_round_cap"))


if __name__ == "__main__":
    unittest.main()
