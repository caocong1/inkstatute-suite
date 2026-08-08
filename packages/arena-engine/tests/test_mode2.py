"""Tests for Mode 2 — Self-score Iteration (ENGINE-02, ENGINE-07, ENGINE-08).

Covers: full iteration run, user stop via asyncio.Event, free-form
self-score extraction, best-result tracking, fresh context per round,
artifact persistence, frozen slotted dataclass shape, and exception
isolation across slots.
"""

from __future__ import annotations

import asyncio
import dataclasses
import tempfile
import unittest
from typing import Any

from platform_contract.arena_contract import ArenaWorkflowConfig
from platform_contract.enums import RunEventType
from platform_runtime.protocols import RunRequest

from arena_engine.artifact_store import ArtifactStore
from arena_engine.mock_acp import MockACPBackendAdapter
from arena_engine.mode2 import (
    IterationState,
    Mode2Result,
    _extract_self_score,
    run_mode2_iteration,
)


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


class StopAfterRoundEmitter(RecordingEmitter):
    """Sets a stop_signal after the first round's score_recorded events."""

    def __init__(self, stop_signal: asyncio.Event, stop_after: int = 2) -> None:
        super().__init__()
        self._stop_signal = stop_signal
        self._stop_after = stop_after
        self._score_count = 0

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().emit(event_type, payload, metadata)
        if event_type == str(RunEventType.ARENA_SCORE_RECORDED):
            self._score_count += 1
            if self._score_count >= self._stop_after:
                self._stop_signal.set()


class _CrashAfterRoundAdapter(MockACPBackendAdapter):
    """Mock that crashes on every submit_run call for rounds >= crash_round.

    Because ``run_agent_slot`` retries up to ``max_retries`` times, the
    adapter must crash on *all* attempts within each crashing round (not
    just the first call) so the slot genuinely fails that round.  The
    crash persists for all rounds >= ``crash_round`` so the slot's best
    result retains its last successful round.
    """

    def __init__(self, crash_round: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._crash_round = crash_round

    async def submit_run(self, req: RunRequest):  # type: ignore[override]
        # Extract the round number from the turn_id pattern "{arena}-{slot}-round{r}"
        turn_id = req.turn.turn_id
        if "round" in turn_id:
            round_str = turn_id.rsplit("round", 1)[-1]
            try:
                r = int(round_str)
            except ValueError:
                r = -1
            if r >= self._crash_round:
                self._crash_on_stream = True
            else:
                self._crash_on_stream = False
        else:
            self._crash_on_stream = False
        return await super().submit_run(req)


def _config_2_slots_max3() -> ArenaWorkflowConfig:
    return ArenaWorkflowConfig(
        arena_id="a-2",
        mode="mode2_iteration",
        agent_slots=["slot-0", "slot-1"],
        task_instruction="分析合同效力",
        max_rounds=3,
    )


def _scored_response(score: int, analysis: str = "分析：...") -> str:
    return f"自评分数：{score}/10\n{analysis}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class Mode2IterationTests(unittest.IsolatedAsyncioTestCase):
    """Cover all 9 Mode 2 iteration behaviours."""

    # -- Test 1: full run, no stop -------------------------------------------

    async def test_full_run_completes_max_rounds(self) -> None:
        """stop_event never set → 3 rounds, score_recorded per slot, 2 best."""
        config = _config_2_slots_max3()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="mock-0",
                responses=[_scored_response(7), _scored_response(8), _scored_response(9)],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="mock-1",
                responses=[_scored_response(6), _scored_response(7), _scored_response(8)],
                agent_slot="slot-1",
            ),
        }
        emitter = RecordingEmitter()
        result = await run_mode2_iteration(
            config=config,
            agent_adapters=adapters,
            event_emitter=emitter,
        )
        self.assertEqual(result.rounds_completed, 3)
        self.assertFalse(result.stopped_early)
        self.assertEqual(len(result.best_results), 2)
        # 3 rounds × 2 slots = 6 score_recorded events
        score_events = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_SCORE_RECORDED)
        ]
        self.assertEqual(len(score_events), 6)

    # -- Test 2: user stop after round 0 -------------------------------------

    async def test_user_stop_preserves_best_results(self) -> None:
        """stop_event set after round 0 → stops, early_stop with round=1."""
        config = _config_2_slots_max3()
        stop_signal = asyncio.Event()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="mock-0",
                responses=[_scored_response(8), _scored_response(9), _scored_response(10)],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="mock-1",
                responses=[_scored_response(7), _scored_response(8), _scored_response(9)],
                agent_slot="slot-1",
            ),
        }
        # Stop after 2 score_recorded events (round 0 complete for both slots).
        emitter = StopAfterRoundEmitter(stop_signal, stop_after=2)
        result = await run_mode2_iteration(
            config=config,
            agent_adapters=adapters,
            event_emitter=emitter,
            stop_signal=stop_signal,
        )
        self.assertTrue(result.stopped_early)
        self.assertEqual(result.rounds_completed, 1)
        # early_stop_triggered emitted with reason="user_stopped", round=1
        stop_events = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_EARLY_STOP_TRIGGERED)
        ]
        self.assertEqual(len(stop_events), 1)
        self.assertEqual(stop_events[0]["payload"]["reason"], "user_stopped")
        self.assertEqual(stop_events[0]["payload"]["round"], 1)
        # best_results has entries from round 0
        self.assertEqual(len(result.best_results), 2)
        self.assertEqual(result.best_results["slot-0"].score, 8)
        self.assertEqual(result.best_results["slot-0"].round, 0)

    # -- Test 3: extract self-score from Chinese text ------------------------

    def test_extract_self_score_chinese(self) -> None:
        """_extract_self_score parses '自评分数：8/10' → 8."""
        self.assertEqual(_extract_self_score("自评分数：8/10\n分析：..."), 8)

    # -- Test 4: no score found → 0 ------------------------------------------

    def test_extract_self_score_no_score(self) -> None:
        """_extract_self_score returns 0 when no score pattern found."""
        self.assertEqual(_extract_self_score("no score here"), 0)

    # -- Test 5: best result tracking across rounds --------------------------

    async def test_best_result_tracking_highest_score(self) -> None:
        """round 0=5, round 1=8, round 2=6 → best score=8, round=1."""
        config = _config_2_slots_max3()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="mock-0",
                responses=[_scored_response(5), _scored_response(8), _scored_response(6)],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="mock-1",
                responses=[_scored_response(7), _scored_response(7), _scored_response(7)],
                agent_slot="slot-1",
            ),
        }
        result = await run_mode2_iteration(
            config=config,
            agent_adapters=adapters,
        )
        self.assertEqual(result.best_results["slot-0"].score, 8)
        self.assertEqual(result.best_results["slot-0"].round, 1)

    # -- Test 6: fresh context per round (distinct turn_ids) -----------------

    async def test_fresh_context_distinct_turn_ids(self) -> None:
        """Each round uses a new turn_id — 3 distinct values per slot."""
        config = _config_2_slots_max3()
        adapter_0 = MockACPBackendAdapter(
            backend_id="mock-0",
            responses=[_scored_response(7), _scored_response(8), _scored_response(9)],
            agent_slot="slot-0",
        )
        adapter_1 = MockACPBackendAdapter(
            backend_id="mock-1",
            responses=[_scored_response(6), _scored_response(7), _scored_response(8)],
            agent_slot="slot-1",
        )
        await run_mode2_iteration(
            config=config,
            agent_adapters={"slot-0": adapter_0, "slot-1": adapter_1},
        )
        # 3 submit_run calls per adapter → 3 distinct turn_ids
        turn_ids_0 = {req.turn.turn_id for req in adapter_0.submitted_requests}
        turn_ids_1 = {req.turn.turn_id for req in adapter_1.submitted_requests}
        self.assertEqual(len(turn_ids_0), 3)
        self.assertEqual(len(turn_ids_1), 3)
        # Verify the pattern
        for r in range(3):
            self.assertIn(f"a-2-slot-0-round{r}", turn_ids_0)
            self.assertIn(f"a-2-slot-1-round{r}", turn_ids_1)

    # -- Test 7: artifact persistence per round ------------------------------

    async def test_artifact_store_persists_each_round(self) -> None:
        """ArtifactStore persists 2 entries per round for rounds 0 and 1."""
        config = _config_2_slots_max3()
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir)
            adapters = {
                "slot-0": MockACPBackendAdapter(
                    backend_id="mock-0",
                    responses=[_scored_response(7), _scored_response(8), _scored_response(9)],
                    agent_slot="slot-0",
                ),
                "slot-1": MockACPBackendAdapter(
                    backend_id="mock-1",
                    responses=[_scored_response(6), _scored_response(7), _scored_response(8)],
                    agent_slot="slot-1",
                ),
            }
            await run_mode2_iteration(
                config=config,
                agent_adapters=adapters,
                artifact_store=store,
            )
            round0 = store.list_round_artifacts(arena_id="a-2", round=0)
            round1 = store.list_round_artifacts(arena_id="a-2", round=1)
            self.assertEqual(len(round0), 2)
            self.assertEqual(len(round1), 2)

    # -- Test 8: Mode2Result frozen slotted dataclass shape ------------------

    def test_mode2_result_frozen_slotted_shape(self) -> None:
        """Mode2Result is frozen slotted with required fields."""
        self.assertTrue(dataclasses.is_dataclass(Mode2Result))
        fields_map = {f.name for f in dataclasses.fields(Mode2Result)}
        expected = {"arena_id", "best_results", "rounds_completed", "stopped_early", "metadata"}
        self.assertEqual(fields_map, expected)
        # frozen
        instance = Mode2Result(arena_id="x")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            instance.arena_id = "y"  # type: ignore[misc]
        # slotted — no __dict__
        self.assertFalse(hasattr(instance, "__dict__"))

    # -- Test 9: one slot crashes in round 1, other continues ----------------

    async def test_slot_crash_isolation(self) -> None:
        """slot-0 crashes from round 1 onward → slot-1 continues; best retains round 0."""
        config = _config_2_slots_max3()
        crash_adapter = _CrashAfterRoundAdapter(
            crash_round=1,
            backend_id="mock-crash",
            responses=[_scored_response(7), _scored_response(8), _scored_response(9)],
            agent_slot="slot-0",
        )
        healthy_adapter = MockACPBackendAdapter(
            backend_id="mock-healthy",
            responses=[_scored_response(6), _scored_response(7), _scored_response(8)],
            agent_slot="slot-1",
        )
        result = await run_mode2_iteration(
            config=config,
            agent_adapters={"slot-0": crash_adapter, "slot-1": healthy_adapter},
        )
        # All 3 rounds attempted; rounds_completed counts completed rounds
        self.assertEqual(result.rounds_completed, 3)
        # slot-0 crashed from round 1 onward → best retains round 0 result (score=7)
        self.assertIn("slot-0", result.best_results)
        self.assertEqual(result.best_results["slot-0"].score, 7)
        self.assertEqual(result.best_results["slot-0"].round, 0)
        # slot-1 continued through all rounds → best score=8 at round 2
        self.assertEqual(result.best_results["slot-1"].score, 8)


if __name__ == "__main__":
    unittest.main()
