"""Tests for the ArenaWorkflow Protocol and FakeArenaWorkflow mock."""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.arena_contract import (
    ArenaHandle,
    ArenaStatus,
    ArenaUserAction,
    ArenaWorkflowConfig,
)

from platform_runtime.fakes import (
    FakeArenaWorkflow,
    FakeIdFactory,
    FakeRuntimeClock,
)
from platform_runtime.protocols import ArenaWorkflow


def _make_config(
    *,
    arena_id: str = "arena-001",
    mode: str = "standard",
    agent_slots: list[str] | None = None,
) -> ArenaWorkflowConfig:
    return ArenaWorkflowConfig(
        arena_id=arena_id,
        mode=mode,
        agent_slots=list(agent_slots or ["slot-a", "slot-b"]),
        task_instruction="Draft a contract review.",
    )


class ArenaWorkflowProtocolTests(unittest.TestCase):
    def test_arena_workflow_is_a_protocol_with_four_async_methods(self) -> None:
        self.assertTrue(getattr(ArenaWorkflow, "_is_protocol", False))
        expected_methods = {"start", "cancel", "submit_user_action", "query_status"}
        self.assertTrue(expected_methods.issubset(vars(ArenaWorkflow)))
        for name in expected_methods:
            method = getattr(ArenaWorkflow, name)
            self.assertTrue(callable(method))

    def test_fake_arena_workflow_implements_all_four_methods(self) -> None:
        fake = FakeArenaWorkflow()
        for name in ("start", "cancel", "submit_user_action", "query_status"):
            self.assertTrue(callable(getattr(fake, name)))

    def test_fake_arena_workflow_passes_isinstance_protocol_check(self) -> None:
        fake = FakeArenaWorkflow()
        self.assertIsInstance(fake, ArenaWorkflow)

    def test_start_returns_handle_with_config_arena_id_and_running_status(self) -> None:
        clock = FakeRuntimeClock(start="2026-08-08T12:00:00Z")
        fake = FakeArenaWorkflow(clock=clock)
        config = _make_config(arena_id="arena-007", mode="adversarial")

        handle = asyncio.run(fake.start(config))

        self.assertIsInstance(handle, ArenaHandle)
        self.assertEqual(handle.arena_id, "arena-007")
        self.assertEqual(handle.status, "running")
        self.assertEqual(handle.created_at, "2026-08-08T12:00:00Z")
        self.assertEqual(fake.started_configs, [config])

    def test_cancel_returns_cancelled_handle_and_records_arena_id(self) -> None:
        clock = FakeRuntimeClock(start="2026-08-08T12:00:00Z")
        fake = FakeArenaWorkflow(clock=clock)
        config = _make_config(arena_id="arena-cancel")
        asyncio.run(fake.start(config))

        handle = asyncio.run(fake.cancel("arena-cancel"))

        self.assertIsInstance(handle, ArenaHandle)
        self.assertEqual(handle.arena_id, "arena-cancel")
        self.assertEqual(handle.status, "cancelled")
        self.assertEqual(fake.cancelled_arena_ids, ["arena-cancel"])
        self.assertEqual(fake.arenas["arena-cancel"].status, "cancelled")

    def test_submit_user_action_returns_handle_and_records_action(self) -> None:
        clock = FakeRuntimeClock(start="2026-08-08T12:00:00Z")
        fake = FakeArenaWorkflow(clock=clock)
        config = _make_config(arena_id="arena-action")
        asyncio.run(fake.start(config))
        action = ArenaUserAction(arena_id="arena-action", action="select", selected_slot="slot-a")

        handle = asyncio.run(fake.submit_user_action("arena-action", action))

        self.assertIsInstance(handle, ArenaHandle)
        self.assertEqual(handle.arena_id, "arena-action")
        self.assertEqual(handle.status, "running")
        self.assertEqual(fake.submitted_actions, [("arena-action", action)])

    def test_query_status_returns_arena_status_from_stored_state(self) -> None:
        fake = FakeArenaWorkflow()
        config = _make_config(
            arena_id="arena-status",
            mode="arena_review",
            agent_slots=["slot-x", "slot-y"],
        )
        asyncio.run(fake.start(config))

        status = asyncio.run(fake.query_status("arena-status"))

        self.assertIsInstance(status, ArenaStatus)
        self.assertEqual(status.arena_id, "arena-status")
        self.assertEqual(status.mode, "arena_review")
        self.assertEqual(status.status, "running")
        self.assertEqual(status.agent_slots, ["slot-x", "slot-y"])
        self.assertEqual(status.current_round, 0)

    def test_query_status_on_unknown_arena_id_raises_key_error(self) -> None:
        fake = FakeArenaWorkflow()

        with self.assertRaises(KeyError):
            asyncio.run(fake.query_status("does-not-exist"))


if __name__ == "__main__":
    unittest.main()
