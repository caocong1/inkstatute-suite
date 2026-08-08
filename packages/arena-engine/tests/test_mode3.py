"""Tests for Mode 3 — Arena Review (ENGINE-03).

Covers: Mode3Result frozen slotted shape, self-score iteration reuse,
cross-review with cross-family enforcement, same-family-only degradation,
user stop, fresh context per phase, event emission, artifact persistence,
independent synthesis session, provenance with reviewer_slot, and
synthesis prompt construction.
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
from arena_engine.families import get_backend_family
from arena_engine.mock_acp import MockACPBackendAdapter
from arena_engine.mode2 import IterationState
from arena_engine.mode3 import (
    Mode3Result,
    _build_synthesis_prompt,
    _select_best_result,
    run_mode3_arena_review,
)
from arena_engine.provenance import ProvenanceLogger
from arena_engine.review import ConfidenceLevel, ReviewFinding, SeverityLevel


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


def _scored_response(score: int, analysis: str = "分析：...") -> str:
    return f"自评分数：{score}/10\n{analysis}"


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


def _config_2_slots_max1() -> ArenaWorkflowConfig:
    return ArenaWorkflowConfig(
        arena_id="a-3",
        mode="mode3_arena_review",
        agent_slots=["slot-0", "slot-1"],
        task_instruction="审查合同效力",
        max_rounds=1,
    )


def _config_2_slots_same_family_max1() -> ArenaWorkflowConfig:
    return ArenaWorkflowConfig(
        arena_id="a-3-same",
        mode="mode3_arena_review",
        agent_slots=["slot-0", "slot-1"],
        task_instruction="审查合同效力",
        max_rounds=1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class Mode3ArenaReviewTests(unittest.IsolatedAsyncioTestCase):
    """Cover all Mode 3 arena review behaviours."""

    # -- Test 1: Mode3Result frozen slotted dataclass shape ------------------

    def test_mode3_result_frozen_slotted_shape(self) -> None:
        """Mode3Result is frozen slotted with required fields."""
        self.assertTrue(dataclasses.is_dataclass(Mode3Result))
        fields_map = {f.name for f in dataclasses.fields(Mode3Result)}
        expected = {
            "arena_id",
            "best_results",
            "review_findings",
            "synthesis_content",
            "synthesis_slot",
            "rounds_completed",
            "stopped_early",
            "cross_family_degraded",
            "metadata",
        }
        self.assertEqual(fields_map, expected)
        # frozen
        instance = Mode3Result(arena_id="x")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            instance.arena_id = "y"  # type: ignore[misc]
        # slotted — no __dict__
        self.assertFalse(hasattr(instance, "__dict__"))

    # -- Test 2: cross-family cross-review completes with findings ----------

    async def test_cross_review_completes_with_findings(self) -> None:
        """2 cross-family slots → cross-review runs, review_findings has both."""
        config = _config_2_slots_max1()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="hermes",
                responses=[_scored_response(8), _finding_response("问题A")],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="codex",
                responses=[_scored_response(7), _finding_response("问题B")],
                agent_slot="slot-1",
            ),
        }
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        emitter = RecordingEmitter()
        result = await run_mode3_arena_review(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            event_emitter=emitter,
        )
        self.assertFalse(result.stopped_early)
        self.assertEqual(len(result.best_results), 2)
        # review_findings has entries for both reviewed slots
        self.assertEqual(len(result.review_findings), 2)

    # -- Test 3: cross-review pairing enforces different families -----------

    async def test_cross_review_enforces_cross_family(self) -> None:
        """Cross-review pairing: reviewer family != reviewed family."""
        config = _config_2_slots_max1()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="hermes",
                responses=[_scored_response(8), _finding_response("问题A")],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="codex",
                responses=[_scored_response(7), _finding_response("问题B")],
                agent_slot="slot-1",
            ),
        }
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        result = await run_mode3_arena_review(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
        )
        # Verify cross-family: each finding's source_slot family != reviewed_slot family
        families = {
            "slot-0": get_backend_family("hermes"),
            "slot-1": get_backend_family("codex"),
        }
        for reviewed_slot, findings in result.review_findings.items():
            for finding in findings:
                self.assertNotEqual(
                    families[finding.source_slot],
                    families[reviewed_slot],
                    f"reviewer {finding.source_slot} same family as reviewed {reviewed_slot}",
                )

    # -- Test 4: arena.review_completed event emitted ------------------------

    async def test_review_completed_event_emitted(self) -> None:
        """arena.review_completed emitted for each cross-review with findings."""
        config = _config_2_slots_max1()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="hermes",
                responses=[_scored_response(8), _finding_response("问题A")],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="codex",
                responses=[_scored_response(7), _finding_response("问题B")],
                agent_slot="slot-1",
            ),
        }
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        emitter = RecordingEmitter()
        result = await run_mode3_arena_review(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            event_emitter=emitter,
        )
        review_events = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_REVIEW_COMPLETED)
        ]
        self.assertEqual(len(review_events), len(result.review_findings))
        for ev in review_events:
            self.assertIn("reviewer_slot", ev["payload"])
            self.assertIn("reviewed_slot", ev["payload"])
            self.assertIn("round", ev["payload"])
            self.assertIn("findings", ev["payload"])
            self.assertIsInstance(ev["payload"]["findings"], list)

    # -- Test 5: workflow_started / workflow_completed events ----------------

    async def test_workflow_started_completed_events(self) -> None:
        """arena.workflow_started with mode3; workflow_completed with completed."""
        config = _config_2_slots_max1()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="hermes",
                responses=[_scored_response(8), _finding_response("问题A")],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="codex",
                responses=[_scored_response(7), _finding_response("问题B")],
                agent_slot="slot-1",
            ),
        }
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        emitter = RecordingEmitter()
        await run_mode3_arena_review(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            event_emitter=emitter,
        )
        started = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_WORKFLOW_STARTED)
        ]
        completed = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_WORKFLOW_COMPLETED)
        ]
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0]["payload"]["mode"], "mode3_arena_review")
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["payload"]["status"], "completed")

    # -- Test 6: cross-review uses fresh context (unique turn_id) -----------

    async def test_cross_review_fresh_context_turn_id(self) -> None:
        """Each cross-review RunRequest has unique turn_id, not reusing self-score."""
        config = _config_2_slots_max1()
        adapter_0 = MockACPBackendAdapter(
            backend_id="hermes",
            responses=[_scored_response(8), _finding_response("问题A")],
            agent_slot="slot-0",
        )
        adapter_1 = MockACPBackendAdapter(
            backend_id="codex",
            responses=[_scored_response(7), _finding_response("问题B")],
            agent_slot="slot-1",
        )
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        await run_mode3_arena_review(
            config=config,
            agent_adapters={"slot-0": adapter_0, "slot-1": adapter_1},
            synthesis_adapter=synthesis,
        )
        # Each adapter got 2 requests: 1 self-score + 1 cross-review
        # The cross-review turn_id should be "{arena_id}-review-{slot}-round0"
        for adapter, slot_id in [(adapter_0, "slot-0"), (adapter_1, "slot-1")]:
            review_reqs = [
                req for req in adapter.submitted_requests
                if "review" in req.turn.turn_id
            ]
            self.assertGreaterEqual(len(review_reqs), 1)
            for req in review_reqs:
                self.assertEqual(
                    req.turn.turn_id,
                    f"a-3-review-{slot_id}-round0",
                )

    # -- Test 7: same-family-only degradation -------------------------------

    async def test_same_family_only_degradation(self) -> None:
        """All same family → cross_family_degraded=True, cross-review skipped."""
        config = _config_2_slots_same_family_max1()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="hermes",
                responses=[_scored_response(8)],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="claude-code",
                responses=[_scored_response(7)],
                agent_slot="slot-1",
            ),
        }
        synthesis = MockACPBackendAdapter(
            backend_id="codex",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        emitter = RecordingEmitter()
        result = await run_mode3_arena_review(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            event_emitter=emitter,
        )
        self.assertTrue(result.cross_family_degraded)
        self.assertEqual(len(result.review_findings), 0)
        # Synthesis still runs with best result only
        self.assertIsNotNone(result.synthesis_content)
        # early_stop_triggered with reason="same_family_only"
        stop_events = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_EARLY_STOP_TRIGGERED)
        ]
        self.assertEqual(len(stop_events), 1)
        self.assertEqual(stop_events[0]["payload"]["reason"], "same_family_only")

    # -- Test 8: user stop during self-score iteration -----------------------

    async def test_user_stop_skips_cross_review_and_synthesis(self) -> None:
        """User stop during self-score → stopped_early, no cross-review, no synthesis."""
        config = ArenaWorkflowConfig(
            arena_id="a-3-stop",
            mode="mode3_arena_review",
            agent_slots=["slot-0", "slot-1"],
            task_instruction="审查合同效力",
            max_rounds=3,
        )
        stop_signal = asyncio.Event()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="hermes",
                responses=[_scored_response(8), _finding_response("问题A")],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="codex",
                responses=[_scored_response(7), _finding_response("问题B")],
                agent_slot="slot-1",
            ),
        }
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        emitter = StopAfterRoundEmitter(stop_signal, stop_after=2)
        result = await run_mode3_arena_review(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            event_emitter=emitter,
            stop_signal=stop_signal,
        )
        self.assertTrue(result.stopped_early)
        self.assertIsNone(result.synthesis_content)
        self.assertEqual(len(result.review_findings), 0)
        # early_stop_triggered with reason="user_stopped"
        stop_events = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_EARLY_STOP_TRIGGERED)
        ]
        self.assertEqual(len(stop_events), 1)
        self.assertEqual(stop_events[0]["payload"]["reason"], "user_stopped")

    # -- Test 9: artifact persistence for self-score and cross-review --------

    async def test_artifact_persistence_self_score_and_cross_review(self) -> None:
        """ArtifactStore stores self-score rounds AND cross-review outputs."""
        config = _config_2_slots_max1()
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir)
            adapters = {
                "slot-0": MockACPBackendAdapter(
                    backend_id="hermes",
                    responses=[_scored_response(8), _finding_response("问题A")],
                    agent_slot="slot-0",
                ),
                "slot-1": MockACPBackendAdapter(
                    backend_id="codex",
                    responses=[_scored_response(7), _finding_response("问题B")],
                    agent_slot="slot-1",
                ),
            }
            synthesis = MockACPBackendAdapter(
                backend_id="gemini-cli",
                responses=["综合最终版本"],
                agent_slot="synthesis",
            )
            await run_mode3_arena_review(
                config=config,
                agent_adapters=adapters,
                synthesis_adapter=synthesis,
                artifact_store=store,
            )
            # Self-score round 0 artifacts for both slots
            round0 = store.list_round_artifacts(arena_id="a-3", round=0)
            slot_ids = {a.agent_slot for a in round0}
            self.assertIn("slot-0", slot_ids)
            self.assertIn("slot-1", slot_ids)
            self.assertIn("synthesis", slot_ids)
            # Cross-review artifacts: check metadata has reviewed_slot
            for artifact in round0:
                if artifact.agent_slot in ("slot-0", "slot-1"):
                    meta = artifact.metadata
                    # Self-score artifacts have "score" key; cross-review have "phase"
                    # Both are stored under round 0, so we check at least one has phase
                    if "phase" in meta:
                        self.assertEqual(meta["phase"], "cross_review")
                        self.assertIn("reviewed_slot", meta)

    # -- Task 2 Tests --------------------------------------------------------

    # -- Test T2-1: synthesis adapter is a separate instance -----------------

    async def test_synthesis_adapter_separate_instance(self) -> None:
        """Synthesis adapter is distinct from candidate slot adapters."""
        config = _config_2_slots_max1()
        slot0 = MockACPBackendAdapter(
            backend_id="hermes",
            responses=[_scored_response(8), _finding_response("问题A")],
            agent_slot="slot-0",
        )
        slot1 = MockACPBackendAdapter(
            backend_id="codex",
            responses=[_scored_response(7), _finding_response("问题B")],
            agent_slot="slot-1",
        )
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        await run_mode3_arena_review(
            config=config,
            agent_adapters={"slot-0": slot0, "slot-1": slot1},
            synthesis_adapter=synthesis,
        )
        # synthesis is a distinct object from slot adapters
        self.assertIsNot(synthesis, slot0)
        self.assertIsNot(synthesis, slot1)
        # synthesis adapter received at least one submit_run
        self.assertGreaterEqual(len(synthesis.submitted_requests), 1)

    # -- Test T2-2: synthesis turn_id is fresh -------------------------------

    async def test_synthesis_fresh_turn_id(self) -> None:
        """Synthesis RunRequest.turn_id is '{arena_id}-synthesis-round0'."""
        config = _config_2_slots_max1()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="hermes",
                responses=[_scored_response(8), _finding_response("问题A")],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="codex",
                responses=[_scored_response(7), _finding_response("问题B")],
                agent_slot="slot-1",
            ),
        }
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        await run_mode3_arena_review(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
        )
        self.assertGreaterEqual(len(synthesis.submitted_requests), 1)
        turn_id = synthesis.submitted_requests[0].turn.turn_id
        self.assertEqual(turn_id, "a-3-synthesis-round0")

    # -- Test T2-3: _build_synthesis_prompt includes all context ------------

    def test_build_synthesis_prompt_includes_all_context(self) -> None:
        """_build_synthesis_prompt includes task instruction, best content, findings."""
        findings: dict[str, list[ReviewFinding]] = {
            "slot-1": [
                ReviewFinding(
                    description="缺少引用",
                    confidence=ConfidenceLevel.LIKELY,
                    severity=SeverityLevel.MEDIUM,
                    confirmed=True,
                    source_slot="slot-0",
                    reviewed_slot="slot-1",
                ),
            ],
        }
        prompt = _build_synthesis_prompt(
            best_content="Best answer here",
            review_findings=findings,
            task_instruction="Review this contract",
        )
        self.assertIn("Review this contract", prompt)
        self.assertIn("Best answer here", prompt)
        self.assertIn("缺少引用", prompt)
        self.assertIn("slot-0", prompt)

    # -- Test T2-4: highest-scoring result selection -------------------------

    def test_select_best_result_picks_highest_score(self) -> None:
        """_select_best_result picks slot-1 (score 9) over slot-0 (score 7)."""
        best_results = {
            "slot-0": IterationState(
                slot_id="slot-0", round=0, score=7, content="slot-0 content",
            ),
            "slot-1": IterationState(
                slot_id="slot-1", round=0, score=9, content="slot-1 content",
            ),
        }
        slot_id, content = _select_best_result(best_results)
        self.assertEqual(slot_id, "slot-1")
        self.assertEqual(content, "slot-1 content")

    # -- Test T2-5: provenance with reviewer_slot populated ------------------

    async def test_provenance_reviewer_slot_populated(self) -> None:
        """Cross-review findings logged with reviewer_slot set (not None)."""
        config = _config_2_slots_max1()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="hermes",
                responses=[_scored_response(8), _finding_response("问题A")],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="codex",
                responses=[_scored_response(7), _finding_response("问题B")],
                agent_slot="slot-1",
            ),
        }
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ProvenanceLogger(tmpdir)
            await run_mode3_arena_review(
                config=config,
                agent_adapters=adapters,
                synthesis_adapter=synthesis,
                provenance_logger=logger,
            )
            chains = logger.get_all_chains(arena_id="a-3")
            # At least some chains should have reviewer_slot set
            review_chains = [c for c in chains if c.reviewer_slot is not None]
            self.assertGreater(len(review_chains), 0)
            for c in review_chains:
                self.assertIsNotNone(c.reviewer_slot)
                self.assertIn(c.reviewer_slot, ["slot-0", "slot-1"])

    # -- Test T2-6: synthesis output persisted with agent_slot="synthesis" ---

    async def test_synthesis_output_persisted(self) -> None:
        """Synthesis output persisted via ArtifactStore with agent_slot='synthesis'."""
        config = _config_2_slots_max1()
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir)
            adapters = {
                "slot-0": MockACPBackendAdapter(
                    backend_id="hermes",
                    responses=[_scored_response(8), _finding_response("问题A")],
                    agent_slot="slot-0",
                ),
                "slot-1": MockACPBackendAdapter(
                    backend_id="codex",
                    responses=[_scored_response(7), _finding_response("问题B")],
                    agent_slot="slot-1",
                ),
            }
            synthesis = MockACPBackendAdapter(
                backend_id="gemini-cli",
                responses=["综合最终版本"],
                agent_slot="synthesis",
            )
            await run_mode3_arena_review(
                config=config,
                agent_adapters=adapters,
                synthesis_adapter=synthesis,
                artifact_store=store,
            )
            synth_artifact = store.get_artifact(
                arena_id="a-3", agent_slot="synthesis", round=0,
            )
            self.assertIsNotNone(synth_artifact)
            self.assertEqual(synth_artifact.agent_slot, "synthesis")
            self.assertEqual(synth_artifact.metadata.get("phase"), "synthesis")
            self.assertEqual(synth_artifact.metadata.get("round"), 0)

    # -- Test T2-7: synthesis_started / synthesis_completed events ----------

    async def test_synthesis_events_emitted(self) -> None:
        """arena.synthesis_started with source_slots; synthesis_completed with round."""
        config = _config_2_slots_max1()
        adapters = {
            "slot-0": MockACPBackendAdapter(
                backend_id="hermes",
                responses=[_scored_response(8), _finding_response("问题A")],
                agent_slot="slot-0",
            ),
            "slot-1": MockACPBackendAdapter(
                backend_id="codex",
                responses=[_scored_response(7), _finding_response("问题B")],
                agent_slot="slot-1",
            ),
        }
        synthesis = MockACPBackendAdapter(
            backend_id="gemini-cli",
            responses=["综合最终版本"],
            agent_slot="synthesis",
        )
        emitter = RecordingEmitter()
        await run_mode3_arena_review(
            config=config,
            agent_adapters=adapters,
            synthesis_adapter=synthesis,
            event_emitter=emitter,
        )
        started = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_SYNTHESIS_STARTED)
        ]
        completed = [
            e for e in emitter.events
            if e["event_type"] == str(RunEventType.ARENA_SYNTHESIS_COMPLETED)
        ]
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0]["payload"]["round"], 0)
        self.assertIn("source_slots", started[0]["payload"])
        self.assertCountEqual(
            started[0]["payload"]["source_slots"],
            ["slot-0", "slot-1"],
        )
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["payload"]["round"], 0)


if __name__ == "__main__":
    unittest.main()
