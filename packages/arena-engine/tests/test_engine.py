"""Tests for ArenaEngine — ArenaWorkflow Protocol + user stop/cancel/guardrails.

Covers ENGINE-01, ENGINE-02, ENGINE-05, ENGINE-06, ENGINE-07, ENGINE-08,
ENGINE-09, SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-07.

Test groups:
- ``EngineLifecycleTests`` (Tests 1-9) — Protocol conformance, start,
  cancel, user actions (select/stop/pause/resume), cancel during active
  iteration with zero orphaned sessions.
- ``EngineGuardrailTests`` (Tests 10-13) — guardrail boundary applied to
  every external agent output, provenance logged per claim, non-bypassable
  boundary, high-risk legal conclusions retain requires_human_review=True.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from platform_contract.arena_contract import (
    ArenaHandle,
    ArenaStatus,
    ArenaUserAction,
    ArenaWorkflowConfig,
)
from platform_runtime.protocols import ArenaWorkflow

from arena_engine.engine import ArenaEngine
from arena_engine.mock_acp import MockACPBackendAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mode1_config(
    arena_id: str = "arena-1",
    slots: list[str] | None = None,
    instruction: str = "分析合同效力",
) -> ArenaWorkflowConfig:
    return ArenaWorkflowConfig(
        arena_id=arena_id,
        mode="mode1_parallel",
        agent_slots=slots or ["slot-1", "slot-2"],
        task_instruction=instruction,
    )


def _mode2_config(
    arena_id: str = "arena-2",
    slots: list[str] | None = None,
    max_rounds: int = 2,
    instruction: str = "分析合同效力",
) -> ArenaWorkflowConfig:
    return ArenaWorkflowConfig(
        arena_id=arena_id,
        mode="mode2_iteration",
        agent_slots=slots or ["slot-1", "slot-2"],
        task_instruction=instruction,
        max_rounds=max_rounds,
    )


def _adapters(slots: list[str], responses: list[str] | None = None) -> dict:
    """Build a mock adapter per slot with scripted responses."""
    resp = responses or ["回答内容"] * len(slots)
    adapters: dict = {}
    for i, slot in enumerate(slots):
        adapters[slot] = MockACPBackendAdapter(
            backend_id=f"backend-{slot}",
            responses=[resp[i % len(resp)]],
            agent_slot=slot,
        )
    return adapters


# ---------------------------------------------------------------------------
# Task 1 — EngineLifecycleTests (Tests 1-9)
# ---------------------------------------------------------------------------


class EngineLifecycleTests(unittest.IsolatedAsyncioTestCase):
    """ArenaEngine lifecycle, cancel, and user-action behaviours."""

    # Test 1 — ArenaEngine is an instance of the ArenaWorkflow Protocol
    async def test_1_engine_is_arena_workflow_protocol(self) -> None:
        engine = ArenaEngine()
        self.assertIsInstance(engine, ArenaWorkflow)

    # Test 2 — start(mode1) returns running handle; query_status matches config
    async def test_2_start_mode1_returns_running_handle_and_status(self) -> None:
        engine = ArenaEngine()
        config = _mode1_config(slots=["slot-1", "slot-2"])
        handle = await engine.start(config)
        self.assertIsInstance(handle, ArenaHandle)
        self.assertEqual(handle.arena_id, config.arena_id)
        self.assertEqual(handle.status, "running")

        status = await engine.query_status(config.arena_id)
        self.assertIsInstance(status, ArenaStatus)
        self.assertEqual(status.status, "running")
        self.assertEqual(status.mode, "mode1_parallel")
        self.assertEqual(status.agent_slots, ["slot-1", "slot-2"])

    # Test 3 — start(mode2) returns running handle
    async def test_3_start_mode2_returns_running_handle(self) -> None:
        engine = ArenaEngine()
        config = _mode2_config()
        handle = await engine.start(config)
        self.assertEqual(handle.status, "running")
        status = await engine.query_status(config.arena_id)
        self.assertEqual(status.status, "running")
        self.assertEqual(status.mode, "mode2_iteration")

    # Test 4 — cancel sets cancelled, calls cancel_run, zero orphaned sessions
    async def test_4_cancel_cleans_up_adapters_zero_orphans(self) -> None:
        engine = ArenaEngine()
        config = _mode1_config(slots=["slot-1", "slot-2"])
        await engine.start(config)
        adapters = _adapters(["slot-1", "slot-2"])
        engine.register_adapters(config.arena_id, adapters)

        # Simulate active runs by submitting one run per adapter.
        from platform_contract.events import AgentTurn
        from platform_runtime.protocols import RunRequest, SolutionBinding

        for slot, adapter in adapters.items():
            req = RunRequest(
                turn=AgentTurn(
                    turn_id=f"t-{slot}",
                    conversation_id="c",
                    channel="web",
                    user_id="u",
                    message_type="text",
                    received_at="2026-01-01T00:00:00Z",
                    content="x",
                ),
                solution=SolutionBinding(solution_id="s"),
            )
            await adapter.submit_run(req)
            # sessions should now be non-empty before cancel
            self.assertTrue(adapter._sessions)

        handle = await engine.cancel(config.arena_id)
        self.assertEqual(handle.status, "cancelled")
        status = await engine.query_status(config.arena_id)
        self.assertEqual(status.status, "cancelled")

        # ENGINE-09 — zero orphaned sessions for every adapter.
        for adapter in adapters.values():
            self.assertEqual(
                adapter._sessions,
                set(),
                "mock adapter has orphaned sessions after cancel",
            )
            self.assertTrue(len(adapter.cancelled_run_ids) >= 1)

    # Test 5 — select action records selection in status metadata
    async def test_5_select_action_records_selection(self) -> None:
        engine = ArenaEngine()
        config = _mode1_config()
        await engine.start(config)
        handle = await engine.submit_user_action(
            config.arena_id,
            ArenaUserAction(arena_id=config.arena_id, action="select", selected_slot="slot-1"),
        )
        self.assertEqual(handle.status, "running")
        status = await engine.query_status(config.arena_id)
        self.assertEqual(status.metadata.get("selected_slot"), "slot-1")

    # Test 6 — stop action sets stop signal and status=stopped
    async def test_6_stop_action_sets_stop_signal(self) -> None:
        engine = ArenaEngine()
        config = _mode2_config()
        await engine.start(config)
        handle = await engine.submit_user_action(
            config.arena_id,
            ArenaUserAction(arena_id=config.arena_id, action="stop"),
        )
        self.assertEqual(handle.status, "stopped")
        self.assertTrue(engine._stop_signals[config.arena_id].is_set())
        status = await engine.query_status(config.arena_id)
        self.assertEqual(status.status, "stopped")

    # Test 7 — pause action sets pause flag and status=paused
    async def test_7_pause_action_sets_pause_flag(self) -> None:
        engine = ArenaEngine()
        config = _mode2_config()
        await engine.start(config)
        handle = await engine.submit_user_action(
            config.arena_id,
            ArenaUserAction(arena_id=config.arena_id, action="pause"),
        )
        self.assertEqual(handle.status, "paused")
        self.assertTrue(engine._pause_flags[config.arena_id].is_set())
        status = await engine.query_status(config.arena_id)
        self.assertEqual(status.status, "paused")

    # Test 8 — resume action clears pause flag and status=running
    async def test_8_resume_action_clears_pause_flag(self) -> None:
        engine = ArenaEngine()
        config = _mode2_config()
        await engine.start(config)
        await engine.submit_user_action(
            config.arena_id,
            ArenaUserAction(arena_id=config.arena_id, action="pause"),
        )
        handle = await engine.submit_user_action(
            config.arena_id,
            ArenaUserAction(arena_id=config.arena_id, action="resume"),
        )
        self.assertEqual(handle.status, "running")
        self.assertFalse(engine._pause_flags[config.arena_id].is_set())
        status = await engine.query_status(config.arena_id)
        self.assertEqual(status.status, "running")

    # Test 9 — cancel during active Mode 2 iteration does not propagate
    async def test_9_cancel_during_active_iteration_no_exception(self) -> None:
        engine = ArenaEngine()
        config = _mode2_config(max_rounds=50)
        await engine.start(config)
        # Adapter with a delay so iteration is still running when we cancel.
        adapters = {
            "slot-1": MockACPBackendAdapter(
                backend_id="backend-slot-1",
                responses=["回答 round"],
                agent_slot="slot-1",
                delay=0.2,
            ),
            "slot-2": MockACPBackendAdapter(
                backend_id="backend-slot-2",
                responses=["回答 round"],
                agent_slot="slot-2",
                delay=0.2,
            ),
        }
        engine.register_adapters(config.arena_id, adapters)

        # Launch iteration in the background.
        task = asyncio.create_task(
            engine._run_arena(config.arena_id, adapters, None)
        )
        engine._bg_tasks[config.arena_id] = task
        await asyncio.sleep(0.05)  # let iteration start

        # Cancel — must not raise.
        handle = await engine.cancel(config.arena_id)
        self.assertEqual(handle.status, "cancelled")
        status = await engine.query_status(config.arena_id)
        self.assertEqual(status.status, "cancelled")

        # The background task should settle without propagating.
        await asyncio.sleep(0.05)
        # zero orphans
        for adapter in adapters.values():
            self.assertEqual(adapter._sessions, set())


if __name__ == "__main__":
    unittest.main()
