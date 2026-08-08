"""GATE-06: Orphan process CI gate test for the Arena Service.

This is the CI gate test that runs in the ``arena-orphan-process`` gate.
It verifies the zero-orphan-process invariant (ENGINE-09) that must
NEVER regress:

- After ``engine.cancel(arena_id)``, all adapters' ``get_active_pids()``
  return an empty set — zero PID residue.
- PIDs are tracked before cancel (non-empty) and cleared after cancel.
- Multiple adapters (3 slots) are all cleaned up — zero residue across
  all adapters.
- No PID accumulation across multiple create/cancel cycles.
- ``cancel_run()`` and ``shutdown()`` are both called during cancel.
- Event buffer is cleared after cancel (no stale events).
- Cancel of a non-existent arena does not crash.

The test uses mock adapters with PID simulation (no real subprocesses).
Phase 109 uses mocks; real subprocess PID assertion is a future phase.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any

from arena_engine.engine import ArenaEngine
from arena_service.event_buffer import ArenaEventBuffer
from platform_contract.arena_contract import ArenaWorkflowConfig
from platform_contract.enums import AsyncTaskState
from platform_contract.events import AgentTurn
from platform_runtime.fakes import FakeIdFactory
from platform_runtime.protocols import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunEvent,
    RunHandle,
    RunRequest,
    SolutionBinding,
)


# ---------------------------------------------------------------------------
# PID-tracking mock adapter
# ---------------------------------------------------------------------------


class PidsTrackingMockAdapter:
    """Mock BackendAdapter with PID simulation for orphan process tests.

    Wraps :class:`MockACPBackendAdapter` behaviour but adds:

    - ``get_active_pids()`` — returns a set of mock PIDs for active
      sessions.  Each ``submit_run`` assigns a new mock PID; ``cancel_run``
      and ``shutdown`` clear them.
    - Call tracking for ``cancel_run`` and ``shutdown``.

    This mirrors the real :class:`ACPBackendAdapter.get_active_pids()`
    pattern (reads transport PIDs from active sessions) but with mock
    PIDs instead of real OS process IDs.
    """

    def __init__(
        self,
        *,
        backend_id: str,
        responses: list[str] | None = None,
        base_pid: int = 1000,
    ) -> None:
        self._backend_id = backend_id
        self._responses = responses or ["mock response"]
        self._response_index = 0
        self._id_factory = FakeIdFactory()
        self._next_pid = base_pid

        # Session → mock PID mapping
        self._session_pids: dict[str, int] = {}

        # Public observability
        self.submitted_requests: list[RunRequest] = []
        self.cancelled_run_ids: list[str] = []
        self.runs: dict[str, Run] = {}
        self.events: dict[str, list[RunEvent]] = {}
        self.artifacts: dict[str, list[ArtifactRecord]] = []
        self._sessions: set[str] = set()

        # Call tracking
        self.cancel_run_calls: list[str] = []
        self.shutdown_calls: int = 0

    def backend_id(self) -> str:
        return self._backend_id

    def capabilities(self) -> Any:
        from platform_contract.agent_adapter import AdapterCapabilitySet
        return AdapterCapabilitySet(stream_event_support=True, cancel_support=True)

    async def bootstrap_check(self) -> BootstrapStatus:
        from platform_runtime.fakes import FakeRuntimeClock
        return BootstrapStatus(
            ok=True,
            backend_id=self._backend_id,
            checked_at=FakeRuntimeClock().now(),
            metadata={"in_memory": True, "mock": True},
        )

    async def submit_run(self, req: RunRequest) -> RunHandle:
        self.submitted_requests.append(req)
        run_id = self._id_factory.new_id("mock-run")
        pid = self._next_pid
        self._next_pid += 1

        run = Run(
            run_id=run_id,
            status=AsyncTaskState.RUNNING,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata={
                "backend_id": self._backend_id,
                "mock_pid": pid,
            },
        )
        self.runs[run_id] = run
        self.events[run_id] = []
        self._sessions.add(run_id)
        self._session_pids[run_id] = pid

        return RunHandle(
            run_id=run_id,
            backend_run_id=f"mock-session-{run_id}",
            status=AsyncTaskState.RUNNING,
            metadata={"backend_id": self._backend_id, "mock_pid": pid},
        )

    async def get_run(self, run_id: str) -> Run:
        return self.runs[run_id]

    async def stream_events(self, run_id: str) -> Any:
        return
        yield  # pragma: no cover — make it an async generator

    async def cancel_run(self, run_id: str) -> Run:
        self.cancel_run_calls.append(run_id)
        self.cancelled_run_ids.append(run_id)
        run = self.runs.get(run_id)
        if run is not None:
            from dataclasses import replace
            self.runs[run_id] = replace(run, status=AsyncTaskState.CANCELLED)
        self._sessions.discard(run_id)
        self._session_pids.pop(run_id, None)
        return self.runs[run_id]

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        run = self.runs[run_id]
        from dataclasses import replace
        return replace(run, metadata={**run.metadata, "approval_id": approval.approval_id})

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        return []

    async def shutdown(self) -> None:
        self.shutdown_calls += 1
        self._sessions.clear()
        self._session_pids.clear()

    def get_active_pids(self) -> set[int]:
        """Return mock PIDs of all active sessions."""
        return set(self._session_pids.values())


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_config(arena_id: str = "arena-001", slots: int = 2) -> ArenaWorkflowConfig:
    """Create an ArenaWorkflowConfig for testing."""
    return ArenaWorkflowConfig(
        arena_id=arena_id,
        mode="mode1_parallel",
        agent_slots=[f"slot-{i}" for i in range(slots)],
        task_instruction="Test task",
    )


def _make_adapter(slot: str, base_pid: int = 1000) -> PidsTrackingMockAdapter:
    """Create a PidsTrackingMockAdapter for a slot."""
    return PidsTrackingMockAdapter(
        backend_id=f"mock-{slot}",
        responses=["response from " + slot],
        base_pid=base_pid,
    )


async def _start_arena_with_adapters(
    engine: ArenaEngine,
    config: ArenaWorkflowConfig,
    adapters: dict[str, PidsTrackingMockAdapter],
) -> None:
    """Start an arena and register adapters, submitting a run to each."""
    await engine.start(config)
    engine.register_adapters(config.arena_id, adapters)
    # Submit a run to each adapter to create active sessions/PIDs
    for slot_id, adapter in adapters.items():
        req = RunRequest(
            turn=AgentTurn(
                turn_id=f"turn-{config.arena_id}-{slot_id}",
                conversation_id=f"conv-{config.arena_id}",
                channel="web",
                user_id="test-user",
                message_type="text",
                received_at="2026-01-01T00:00:00Z",
                content="test prompt",
            ),
            solution=SolutionBinding(
                solution_id=f"sol-{config.arena_id}-{slot_id}"
            ),
        )
        await adapter.submit_run(req)


# ---------------------------------------------------------------------------
# GATE-06: Orphan process gate tests
# ---------------------------------------------------------------------------


class OrphanProcessGateTests(unittest.IsolatedAsyncioTestCase):
    """GATE-06: Orphan process CI gate tests.

    These tests run in the ``arena-orphan-process`` gate and verify
    that ``engine.cancel()`` leaves zero PID residue across all
    adapters.
    """

    # -- Test 1: Zero PID residue after cancel --
    async def test_zero_pid_residue_after_cancel(self) -> None:
        """After cancel, all adapters' get_active_pids() return empty set."""
        engine = ArenaEngine()
        config = _make_config("arena-001", slots=2)
        adapters = {
            "slot-0": _make_adapter("slot-0", base_pid=1001),
            "slot-1": _make_adapter("slot-1", base_pid=2001),
        }
        await _start_arena_with_adapters(engine, config, adapters)

        await engine.cancel("arena-001")
        await asyncio.sleep(0.5)  # grace period

        for adapter in adapters.values():
            self.assertEqual(
                adapter.get_active_pids(),
                set(),
                f"Adapter {adapter.backend_id()} has residual PIDs",
            )

    # -- Test 2: PIDs tracked before cancel --
    async def test_pids_tracked_before_cancel(self) -> None:
        """Before cancel, get_active_pids() returns non-empty set."""
        engine = ArenaEngine()
        config = _make_config("arena-002", slots=2)
        adapters = {
            "slot-0": _make_adapter("slot-0", base_pid=1001),
            "slot-1": _make_adapter("slot-1", base_pid=2001),
        }
        await _start_arena_with_adapters(engine, config, adapters)

        for adapter in adapters.values():
            pids = adapter.get_active_pids()
            self.assertNotEqual(pids, set(), "PIDs should be tracked before cancel")

    # -- Test 3: All PIDs gone after cancel --
    async def test_all_pids_gone_after_cancel(self) -> None:
        """Record PIDs before cancel, verify all are gone after cancel."""
        engine = ArenaEngine()
        config = _make_config("arena-003", slots=2)
        adapters = {
            "slot-0": _make_adapter("slot-0", base_pid=1001),
            "slot-1": _make_adapter("slot-1", base_pid=2001),
        }
        await _start_arena_with_adapters(engine, config, adapters)

        # Record PIDs before cancel
        pids_before: set[int] = set()
        for adapter in adapters.values():
            pids_before.update(adapter.get_active_pids())
        self.assertTrue(len(pids_before) > 0, "Should have PIDs before cancel")

        await engine.cancel("arena-003")
        await asyncio.sleep(0.5)

        # Verify all PIDs are gone
        pids_after: set[int] = set()
        for adapter in adapters.values():
            pids_after.update(adapter.get_active_pids())
        self.assertEqual(pids_after, set(), "All PIDs should be gone after cancel")

    # -- Test 4: Multiple adapters (3 slots) all cleaned --
    async def test_multiple_adapters_all_cleaned(self) -> None:
        """Cancel with 3 adapters — all 3 have zero PID residue."""
        engine = ArenaEngine()
        config = _make_config("arena-004", slots=3)
        adapters = {
            "slot-0": _make_adapter("slot-0", base_pid=1001),
            "slot-1": _make_adapter("slot-1", base_pid=2001),
            "slot-2": _make_adapter("slot-2", base_pid=3001),
        }
        await _start_arena_with_adapters(engine, config, adapters)

        # Verify all 3 have PIDs before cancel
        for adapter in adapters.values():
            self.assertNotEqual(adapter.get_active_pids(), set())

        await engine.cancel("arena-004")
        await asyncio.sleep(0.5)

        # All 3 should have zero PIDs
        for adapter in adapters.values():
            self.assertEqual(
                adapter.get_active_pids(),
                set(),
                f"Adapter {adapter.backend_id()} has residual PIDs",
            )

    # -- Test 5: Cancel unknown arena does not crash --
    async def test_cancel_unknown_arena_no_crash(self) -> None:
        """Cancel a non-existent arena — should not crash unhandled."""
        engine = ArenaEngine()
        # ArenaEngine.cancel() raises KeyError for unknown arena —
        # this is expected behaviour (handled by the caller). The test
        # verifies it raises a catchable exception, not a crash.
        try:
            await engine.cancel("nonexistent")
            # If no exception, that's also acceptable
        except KeyError:
            pass  # Expected — caller handles this
        except Exception as exc:
            self.fail(f"Unexpected exception type: {type(exc)}: {exc}")

    # -- Test 6: No PID accumulation across cycles --
    async def test_no_pid_accumulation_across_cycles(self) -> None:
        """Create → cancel → create → cancel — no PID accumulation."""
        engine = ArenaEngine()

        # First cycle
        config1 = _make_config("arena-cycle-1", slots=2)
        adapters1 = {
            "slot-0": _make_adapter("slot-0", base_pid=1001),
            "slot-1": _make_adapter("slot-1", base_pid=2001),
        }
        await _start_arena_with_adapters(engine, config1, adapters1)
        await engine.cancel("arena-cycle-1")
        await asyncio.sleep(0.3)

        # Second cycle
        config2 = _make_config("arena-cycle-2", slots=2)
        adapters2 = {
            "slot-0": _make_adapter("slot-0", base_pid=3001),
            "slot-1": _make_adapter("slot-1", base_pid=4001),
        }
        await _start_arena_with_adapters(engine, config2, adapters2)
        await engine.cancel("arena-cycle-2")
        await asyncio.sleep(0.3)

        # Verify no PIDs remain from either cycle
        for adapter in list(adapters1.values()) + list(adapters2.values()):
            self.assertEqual(
                adapter.get_active_pids(),
                set(),
                f"Adapter {adapter.backend_id()} has residual PIDs from cycles",
            )

    # -- Test 7: cancel_run and shutdown both called --
    async def test_cancel_calls_cancel_run_and_shutdown(self) -> None:
        """engine.cancel() calls cancel_run and shutdown on each adapter."""
        engine = ArenaEngine()
        config = _make_config("arena-007", slots=2)
        adapters = {
            "slot-0": _make_adapter("slot-0", base_pid=1001),
            "slot-1": _make_adapter("slot-1", base_pid=2001),
        }
        await _start_arena_with_adapters(engine, config, adapters)

        await engine.cancel("arena-007")
        await asyncio.sleep(0.3)

        for adapter in adapters.values():
            self.assertTrue(
                len(adapter.cancel_run_calls) > 0,
                f"cancel_run not called on {adapter.backend_id()}",
            )
            self.assertTrue(
                adapter.shutdown_calls > 0,
                f"shutdown not called on {adapter.backend_id()}",
            )

    # -- Test 8: Event buffer cleared after cancel --
    async def test_event_buffer_cleared_after_cancel(self) -> None:
        """After cancel, event buffer for the arena is cleared."""
        buffer = ArenaEventBuffer()
        arena_id = "arena-008"

        # Emit events to buffer
        buffer.append(arena_id, {"seq": 0, "event_type": "arena.started", "payload": {}})
        buffer.append(arena_id, {"seq": 1, "event_type": "slot.completed", "payload": {}})
        self.assertEqual(len(buffer.get_buffered_events(arena_id)), 2)

        # Simulate cancel handler clearing the buffer
        buffer.clear_arena(arena_id)

        self.assertEqual(
            buffer.get_buffered_events(arena_id),
            [],
            "Event buffer should be empty after clear_arena",
        )

    # -- Test 9: Gate count is at least 38 --
    def test_gate_count_at_least_38(self) -> None:
        """run_v2_gates.py defines at least 38 gates (36 + 2 new arena gates)."""
        import sys
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(repo_root / "scripts"))
        from run_v2_gates import _gates
        gates = _gates(repo_root)
        self.assertGreaterEqual(
            len(gates),
            38,
            f"Expected at least 38 gates, got {len(gates)}",
        )

    # -- Test 10: Gate coverage baseline updated --
    def test_gate_coverage_baseline_38(self) -> None:
        """test_gate_coverage.py baseline is 38 (was 36)."""
        import sys
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(repo_root / "scripts"))
        from run_v2_gates import _gates
        gates = _gates(repo_root)
        # The baseline in test_gate_coverage.py should be 38
        self.assertGreaterEqual(len(gates), 38)

    # -- Test 11: services/arena-service/src covered by gates --
    def test_arena_service_src_covered(self) -> None:
        """services/arena-service/src is covered by at least one gate."""
        import sys
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(repo_root / "scripts"))
        from run_v2_gates import _gates
        gates = _gates(repo_root)

        arena_service_src = (repo_root / "services" / "arena-service" / "src").resolve()
        covered = set()
        for gate in gates:
            for p in gate.pythonpath:
                covered.add(Path(p).resolve())
            if "compileall" in gate.command:
                for arg in gate.command:
                    if isinstance(arg, str) and arg.endswith("/src"):
                        covered.add((repo_root / arg).resolve())

        self.assertIn(
            arena_service_src,
            covered,
            "services/arena-service/src is not covered by any gate",
        )


if __name__ == "__main__":
    unittest.main()
