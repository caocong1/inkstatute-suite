"""Tests for SubprocessController and ACPBackendAdapter.get_active_pids (SVC-06).

Covers liveness check, per-run timeout with cleanup, partial-result
acceptance, and PID tracking from the ACP adapter's StdioACPTransport.
"""

from __future__ import annotations

import asyncio
import os
import unittest
from dataclasses import fields, is_dataclass
from typing import Any
from unittest.mock import MagicMock, patch

from arena_engine.slot_runner import SlotResult
from arena_service.subprocess_control import PartialResult, SubprocessController


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class FakeTransport:
    """Minimal transport stub exposing a ``pid`` property."""

    def __init__(self, pid: int | None) -> None:
        self._pid = pid

    @property
    def pid(self) -> int | None:
        return self._pid


class FakeACPClient:
    """Minimal ACPClient stub exposing ``_transport``."""

    def __init__(self, transport: FakeTransport) -> None:
        self._transport = transport


class FakeACPBackendAdapter:
    """Adapter stub that mimics ACPBackendAdapter._sessions + get_active_pids.

    ``_sessions`` is a ``dict[str, FakeACPClient]`` mirroring the real
    adapter so ``get_active_pids`` can iterate over clients and read
    transport PIDs.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, FakeACPClient] = {}

    def get_active_pids(self) -> set[int]:
        pids: set[int] = set()
        for client in self._sessions.values():
            transport = getattr(client, "_transport", None)
            if transport is not None:
                pid = getattr(transport, "pid", None)
                if pid is not None:
                    pids.add(pid)
        return pids

    def add_session(self, run_id: str, pid: int | None) -> None:
        self._sessions[run_id] = FakeACPClient(FakeTransport(pid))

    def remove_session(self, run_id: str) -> None:
        self._sessions.pop(run_id, None)

    def clear_sessions(self) -> None:
        self._sessions.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class SubprocessControlTests(unittest.IsolatedAsyncioTestCase):
    """Tests 1-11: get_active_pids + SubprocessController behaviours."""

    # -- Test 1: get_active_pids returns empty set when no sessions -----

    def test_get_active_pids_empty_when_no_sessions(self):
        # Test 1: no sessions → empty set.
        adapter = FakeACPBackendAdapter()
        self.assertEqual(adapter.get_active_pids(), set())

    # -- Test 2: get_active_pids returns PIDs from all sessions ---------

    def test_get_active_pids_returns_all_session_pids(self):
        # Test 2: 2 active sessions → 2 PIDs.
        adapter = FakeACPBackendAdapter()
        adapter.add_session("run-1", 1001)
        adapter.add_session("run-2", 1002)
        self.assertEqual(adapter.get_active_pids(), {1001, 1002})

    # -- Test 3: SubprocessController defaults --------------------------

    def test_controller_defaults(self):
        # Test 3: default timeout and liveness interval.
        ctrl = SubprocessController()
        # Defaults are stored internally; verify via behaviour.
        # We check the attributes indirectly through construction.
        ctrl2 = SubprocessController(timeout_seconds=120.0, liveness_check_interval=3.0)
        # No public getters required by plan, but we can verify run_with_timeout
        # uses the default by completing a fast coroutine.
        self.assertEqual(ctrl._timeout_seconds, 300.0)
        self.assertEqual(ctrl._liveness_check_interval, 5.0)
        self.assertEqual(ctrl2._timeout_seconds, 120.0)
        self.assertEqual(ctrl2._liveness_check_interval, 3.0)

    # -- Test 4: check_liveness returns True when all alive -------------

    def test_check_liveness_true_when_all_alive(self):
        # Test 4: all PIDs alive → True.
        adapter = FakeACPBackendAdapter()
        adapter.add_session("run-1", 1001)
        adapter.add_session("run-2", 1002)
        ctrl = SubprocessController()
        with patch("arena_service.subprocess_control.os.kill") as mock_kill:
            # os.kill(pid, 0) succeeds → process alive
            mock_kill.return_value = None
            result = ctrl.check_liveness(adapter)
        self.assertTrue(result)
        # Should have been called for each PID
        self.assertEqual(mock_kill.call_count, 2)

    # -- Test 4b: check_liveness returns False when any dead ------------

    def test_check_liveness_false_when_any_dead(self):
        # Test 4 (negative): one PID dead → False.
        adapter = FakeACPBackendAdapter()
        adapter.add_session("run-1", 1001)
        adapter.add_session("run-2", 1002)
        ctrl = SubprocessController()

        def fake_kill(pid: int, sig: int) -> None:
            if pid == 1001:
                raise ProcessLookupError("no such process")
            # 1002 is alive

        with patch("arena_service.subprocess_control.os.kill", side_effect=fake_kill):
            result = ctrl.check_liveness(adapter)
        self.assertFalse(result)

    # -- Test 4c: check_liveness True when no sessions ------------------

    def test_check_liveness_true_when_no_sessions(self):
        # No sessions → vacuously True.
        adapter = FakeACPBackendAdapter()
        ctrl = SubprocessController()
        self.assertTrue(ctrl.check_liveness(adapter))

    # -- Test 5: run_with_timeout completes within timeout --------------

    async def test_run_with_timeout_completes_within_timeout(self):
        # Test 5: coroutine finishes before timeout → returns result.
        ctrl = SubprocessController(timeout_seconds=5.0)

        async def quick() -> str:
            await asyncio.sleep(0.01)
            return "done"

        result = await ctrl.run_with_timeout(quick())
        self.assertEqual(result, "done")

    # -- Test 6: run_with_timeout raises TimeoutError + cleanup ---------

    async def test_run_with_timeout_raises_timeout_and_calls_cleanup(self):
        # Test 6: timeout → TimeoutError + cleanup callback invoked.
        cleanup_called = asyncio.Event()

        async def cleanup() -> None:
            cleanup_called.set()

        ctrl = SubprocessController(timeout_seconds=0.05)
        ctrl.set_cleanup_callback(cleanup)

        async def slow() -> str:
            await asyncio.sleep(10.0)
            return "never"

        with self.assertRaises(asyncio.TimeoutError):
            await ctrl.run_with_timeout(slow())
        # Cleanup must have been called.
        self.assertTrue(cleanup_called.is_set())

    # -- Test 7: accept_partial_result for timeout ----------------------

    def test_accept_partial_result_timeout(self):
        # Test 7: timeout status → accepted, marked.
        ctrl = SubprocessController()
        slot = SlotResult(
            slot_id="slot-0",
            status="timeout",
            content="partial content",
            metadata={"error": "timeout", "partial": True},
        )
        pr = ctrl.accept_partial_result(slot)
        self.assertTrue(pr.accepted)
        self.assertEqual(pr.status, "timeout")
        self.assertEqual(pr.content, "partial content")
        self.assertTrue(pr.marked)

    # -- Test 8: accept_partial_result for failed -----------------------

    def test_accept_partial_result_failed(self):
        # Test 8: failed status → accepted, marked.
        ctrl = SubprocessController()
        slot = SlotResult(
            slot_id="slot-1",
            status="failed",
            content="crash output",
            metadata={"error": "RuntimeError", "partial": True},
        )
        pr = ctrl.accept_partial_result(slot)
        self.assertTrue(pr.accepted)
        self.assertEqual(pr.status, "failed")
        self.assertEqual(pr.content, "crash output")
        self.assertTrue(pr.marked)

    # -- Test 9: accept_partial_result for success ----------------------

    def test_accept_partial_result_success_not_marked(self):
        # Test 9: success status → accepted, NOT marked.
        ctrl = SubprocessController()
        slot = SlotResult(
            slot_id="slot-2",
            status="success",
            content="full answer",
            metadata={"backend_id": "hermes"},
        )
        pr = ctrl.accept_partial_result(slot)
        self.assertTrue(pr.accepted)
        self.assertEqual(pr.status, "success")
        self.assertEqual(pr.content, "full answer")
        self.assertFalse(pr.marked)

    # -- Test 10: PartialResult is frozen slotted dataclass --------------

    def test_partial_result_is_frozen_slotted_dataclass(self):
        # Test 10: frozen + slots + expected fields.
        self.assertTrue(is_dataclass(PartialResult))
        pr = PartialResult(
            accepted=True,
            status="timeout",
            content="x",
            marked=True,
        )
        # frozen: assignment must raise
        with self.assertRaises(Exception):
            pr.accepted = False  # type: ignore[misc]
        # slotted: no __dict__
        self.assertFalse(hasattr(pr, "__dict__"))
        # expected fields
        field_names = {f.name for f in fields(PartialResult)}
        self.assertEqual(
            field_names,
            {"accepted", "status", "content", "marked", "metadata"},
        )
        # metadata defaults to empty dict
        self.assertEqual(pr.metadata, {})

    # -- Test 11: after timeout cleanup, get_active_pids is empty -------

    async def test_no_orphans_after_timeout_cleanup(self):
        # Test 11: timeout → cleanup clears sessions → get_active_pids empty.
        adapter = FakeACPBackendAdapter()
        adapter.add_session("run-1", 2001)
        adapter.add_session("run-2", 2002)
        self.assertEqual(adapter.get_active_pids(), {2001, 2002})

        async def cleanup() -> None:
            # Simulate engine.cancel() → adapter.shutdown()
            adapter.clear_sessions()

        ctrl = SubprocessController(timeout_seconds=0.05)
        ctrl.set_cleanup_callback(cleanup)

        async def slow() -> str:
            await asyncio.sleep(10.0)
            return "never"

        with self.assertRaises(asyncio.TimeoutError):
            await ctrl.run_with_timeout(slow())

        # After cleanup, no PIDs remain — no orphans.
        self.assertEqual(adapter.get_active_pids(), set())


if __name__ == "__main__":
    unittest.main()
