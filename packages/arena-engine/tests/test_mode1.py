"""Tests for Mode 1 Standard Parallel — run_mode1_parallel (ENGINE-01).

Covers:
- N agents run concurrently via asyncio.TaskGroup
- Every emitted RunEvent has metadata["agent_slot"]
- arena.workflow_started emitted first, arena.workflow_completed last
- One slot crash does NOT cancel siblings (exception isolation)
- ArtifactStore persists successful slot outputs
- One run_agent_slot call per slot with correct adapter
- Mode1Result is a frozen slotted dataclass
"""

from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path

from platform_contract.arena_contract import ArenaWorkflowConfig
from platform_contract.enums import RunEventType

from arena_engine.artifact_store import ArtifactStore, RoundArtifact
from arena_engine.mock_acp import MockACPBackendAdapter
from arena_engine.mode1 import EventEmitter, Mode1Result, run_mode1_parallel
from arena_engine.slot_runner import SlotResult


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class RecordingEmitter:
    """Records every emit() call for later assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict, dict]] = []

    async def emit(
        self,
        event_type: str,
        payload: dict,
        metadata: dict,
    ) -> None:
        self.events.append((event_type, payload, metadata))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_LIFECYCLE_TYPES = frozenset(
    {
        RunEventType.ARENA_WORKFLOW_STARTED.value,
        RunEventType.ARENA_WORKFLOW_COMPLETED.value,
    }
)


def _make_config(
    *,
    arena_id: str = "a-1",
    agent_slots: list[str] | None = None,
) -> ArenaWorkflowConfig:
    return ArenaWorkflowConfig(
        arena_id=arena_id,
        mode="mode1_parallel",
        agent_slots=agent_slots or ["slot-0", "slot-1", "slot-2"],
        task_instruction="分析合同效力",
    )


def _make_adapters(
    slots: list[str],
    *,
    crash_slot: str | None = None,
) -> dict[str, MockACPBackendAdapter]:
    adapters: dict[str, MockACPBackendAdapter] = {}
    for i, slot_id in enumerate(slots):
        adapters[slot_id] = MockACPBackendAdapter(
            backend_id=f"mock-{slot_id}",
            responses=[f"result-{slot_id}"],
            agent_slot=slot_id,
            crash_on_stream=(slot_id == crash_slot),
        )
    return adapters


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class Mode1ParallelTests(unittest.IsolatedAsyncioTestCase):
    """Seven tests covering Mode 1 Standard Parallel behaviour."""

    async def test_1_all_slots_run_concurrently_and_succeed(self) -> None:
        """Test 1: 3 slots run concurrently; all return status='success'."""
        config = _make_config()
        adapters = _make_adapters(config.agent_slots)
        emitter = RecordingEmitter()

        result = await run_mode1_parallel(
            config=config,
            agent_adapters=adapters,
            event_emitter=emitter,
        )

        self.assertIsInstance(result, Mode1Result)
        self.assertEqual(result.arena_id, "a-1")
        self.assertEqual(len(result.slot_results), 3)
        for slot_id in config.agent_slots:
            slot_result = result.slot_results[slot_id]
            self.assertIsInstance(slot_result, SlotResult)
            self.assertEqual(slot_result.status, "success")
            self.assertEqual(slot_result.content, f"result-{slot_id}")

    async def test_2_every_runevent_has_agent_slot_metadata(self) -> None:
        """Test 2: Every per-slot RunEvent emitted has metadata['agent_slot']."""
        config = _make_config()
        adapters = _make_adapters(config.agent_slots)
        emitter = RecordingEmitter()

        await run_mode1_parallel(
            config=config,
            agent_adapters=adapters,
            event_emitter=emitter,
        )

        # Filter to per-slot events (exclude arena lifecycle events)
        per_slot_events = [
            (et, payload, metadata)
            for et, payload, metadata in emitter.events
            if et not in _LIFECYCLE_TYPES
        ]
        self.assertGreater(len(per_slot_events), 0)
        for event_type, _payload, metadata in per_slot_events:
            self.assertIn(
                "agent_slot",
                metadata,
                msg=f"Event {event_type!r} missing agent_slot metadata",
            )
            self.assertIn(metadata["agent_slot"], config.agent_slots)

    async def test_3_lifecycle_events_first_and_last(self) -> None:
        """Test 3: workflow_started first, workflow_completed last."""
        config = _make_config()
        adapters = _make_adapters(config.agent_slots)
        emitter = RecordingEmitter()

        await run_mode1_parallel(
            config=config,
            agent_adapters=adapters,
            event_emitter=emitter,
        )

        self.assertGreaterEqual(len(emitter.events), 2)
        first_type, first_payload, _ = emitter.events[0]
        last_type, last_payload, _ = emitter.events[-1]

        self.assertEqual(first_type, RunEventType.ARENA_WORKFLOW_STARTED.value)
        self.assertEqual(first_payload["arena_id"], "a-1")
        self.assertEqual(
            first_payload["agent_slots"],
            ["slot-0", "slot-1", "slot-2"],
        )

        self.assertEqual(last_type, RunEventType.ARENA_WORKFLOW_COMPLETED.value)
        self.assertEqual(last_payload["arena_id"], "a-1")
        self.assertEqual(last_payload["status"], "completed")

    async def test_4_one_slot_crash_does_not_cancel_others(self) -> None:
        """Test 4: One slot crashes; other 2 still succeed; TaskGroup does NOT raise."""
        config = _make_config()
        adapters = _make_adapters(config.agent_slots, crash_slot="slot-1")
        emitter = RecordingEmitter()

        # Should NOT raise even though slot-1 crashes
        result = await run_mode1_parallel(
            config=config,
            agent_adapters=adapters,
            event_emitter=emitter,
        )

        self.assertEqual(len(result.slot_results), 3)
        self.assertEqual(result.slot_results["slot-0"].status, "success")
        self.assertEqual(result.slot_results["slot-1"].status, "failed")
        self.assertEqual(result.slot_results["slot-2"].status, "success")
        self.assertEqual(result.slot_results["slot-0"].content, "result-slot-0")
        self.assertEqual(result.slot_results["slot-2"].content, "result-slot-2")

    async def test_5_artifact_store_persists_successful_slots(self) -> None:
        """Test 5: ArtifactStore persists 2 successful slots; crashed slot has None."""
        config = _make_config()
        adapters = _make_adapters(config.agent_slots, crash_slot="slot-1")

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(storage_dir=Path(tmpdir))
            result = await run_mode1_parallel(
                config=config,
                agent_adapters=adapters,
                artifact_store=store,
            )

            # Crashed slot → None; successful slots → RoundArtifact
            self.assertIsNone(result.artifacts["slot-1"])
            self.assertIsInstance(result.artifacts["slot-0"], RoundArtifact)
            self.assertIsInstance(result.artifacts["slot-2"], RoundArtifact)

            # list_round_artifacts returns 2 (crashed slot has no file)
            artifacts = store.list_round_artifacts(
                arena_id=config.arena_id,
                round=0,
            )
            self.assertEqual(len(artifacts), 2)
            stored_slots = {a.agent_slot for a in artifacts}
            self.assertEqual(stored_slots, {"slot-0", "slot-2"})

    async def test_6_one_run_agent_slot_call_per_slot(self) -> None:
        """Test 6: Exactly 3 submit_run calls, one per slot with correct adapter."""
        config = _make_config()
        adapters = _make_adapters(config.agent_slots)

        await run_mode1_parallel(
            config=config,
            agent_adapters=adapters,
        )

        for slot_id in config.agent_slots:
            adapter = adapters[slot_id]
            self.assertEqual(len(adapter.submitted_requests), 1)
            req = adapter.submitted_requests[0]
            expected_turn_id = f"{config.arena_id}-{slot_id}-round0"
            self.assertEqual(req.turn.turn_id, expected_turn_id)
            self.assertEqual(req.turn.content, config.task_instruction)

    async def test_7_mode1_result_is_frozen_slotted_dataclass(self) -> None:
        """Test 7: Mode1Result is frozen, slotted, with required fields."""
        config = _make_config()
        adapters = _make_adapters(config.agent_slots)

        result = await run_mode1_parallel(
            config=config,
            agent_adapters=adapters,
        )

        # Check it's a dataclass
        self.assertTrue(dataclasses.is_dataclass(result))

        # Check frozen
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.arena_id = "mutated"  # type: ignore[misc]

        # Check slotted (no __dict__)
        self.assertFalse(hasattr(result, "__dict__"))

        # Check fields
        field_names = {f.name for f in dataclasses.fields(result)}
        self.assertEqual(
            field_names,
            {"arena_id", "slot_results", "artifacts", "metadata"},
        )

        # Check types
        self.assertIsInstance(result.slot_results, dict)
        self.assertIsInstance(result.artifacts, dict)
        self.assertIsInstance(result.metadata, dict)
        self.assertEqual(result.metadata["mode"], "mode1_parallel")
        self.assertEqual(result.metadata["round"], 0)


if __name__ == "__main__":
    unittest.main()
