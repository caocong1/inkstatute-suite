"""Tests for MockACPBackendAdapter — deterministic offline BackendAdapter."""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.enums import AsyncTaskState, RunEventType
from platform_contract.events import AgentTurn
from platform_runtime.fakes import FakeIdFactory
from platform_runtime.protocols import RunRequest, SolutionBinding

from arena_engine.mock_acp import MockACPBackendAdapter


def _make_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="t-1",
            conversation_id="c-1",
            channel="web",
            user_id="u-1",
            message_type="text",
            received_at="2026-06-29T00:00:00Z",
            content="test",
        ),
        solution=SolutionBinding(solution_id="s-1"),
    )


class MockACPAdapterTests(unittest.IsolatedAsyncioTestCase):
    """Cover all 6 MockACPBackendAdapter behaviours."""

    async def test_deterministic_run_id_pattern(self) -> None:
        """Test 1: submit_run returns RunHandle with run_id matching mock-run-001."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a"],
        )
        handle = await adapter.submit_run(_make_request())
        self.assertEqual(handle.run_id, "mock-run-001")

    async def test_stream_events_have_agent_slot_metadata(self) -> None:
        """Test 2: stream_events yields RunEvents with agent_slot in metadata."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a"],
        )
        handle = await adapter.submit_run(_make_request())
        events = [e async for e in adapter.stream_events(handle.run_id)]
        self.assertGreaterEqual(len(events), 1)
        completed = [e for e in events if e.event_type == str(RunEventType.MESSAGE_COMPLETED)]
        self.assertGreaterEqual(len(completed), 1)
        for event in events:
            self.assertIn("agent_slot", event.metadata)

    async def test_crash_on_stream_records_crash(self) -> None:
        """Test 3: crash_on_stream raises RuntimeError and records crash in metadata."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a"],
            crash_on_stream=True,
        )
        handle = await adapter.submit_run(_make_request())
        with self.assertRaises(RuntimeError):
            [e async for e in adapter.stream_events(handle.run_id)]
        run = await adapter.get_run(handle.run_id)
        self.assertEqual(run.status, AsyncTaskState.FAILED)
        self.assertIn("crash", run.metadata)

    async def test_timeout_simulated_by_delay(self) -> None:
        """Test 4: delay > timeout yields no events; run stays RUNNING not SUCCEEDED."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a"],
            timeout_seconds=0.01,
            delay=0.05,
        )
        handle = await adapter.submit_run(_make_request())
        # Simulate timeout: collect events with a short deadline
        events: list = []
        try:
            async with asyncio.timeout(0.02):
                async for e in adapter.stream_events(handle.run_id):
                    events.append(e)
        except (asyncio.TimeoutError, TimeoutError):
            pass
        self.assertEqual(len(events), 0)
        run = await adapter.get_run(handle.run_id)
        self.assertNotEqual(run.status, AsyncTaskState.SUCCEEDED)

    async def test_incrementing_run_ids(self) -> None:
        """Test 5: second submit_run returns mock-run-002."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a", "result-b"],
        )
        h1 = await adapter.submit_run(_make_request())
        h2 = await adapter.submit_run(_make_request())
        self.assertEqual(h1.run_id, "mock-run-001")
        self.assertEqual(h2.run_id, "mock-run-002")

    async def test_cancel_sets_cancelled_status(self) -> None:
        """Test 6: cancel_run sets CANCELLED and records cancelled_run_ids."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a"],
        )
        handle = await adapter.submit_run(_make_request())
        run = await adapter.cancel_run(handle.run_id)
        self.assertEqual(run.status, AsyncTaskState.CANCELLED)
        self.assertIn(handle.run_id, adapter.cancelled_run_ids)


class MockACPBackendFamilyTests(unittest.TestCase):
    """Cover backend_family() behaviours for MockACPBackendAdapter."""

    def test_explicit_backend_family_returned(self) -> None:
        """Test 2: explicit backend_family parameter is returned directly."""
        adapter = MockACPBackendAdapter(
            backend_id="hermes",
            responses=["test"],
            backend_family="claude",
        )
        self.assertEqual(adapter.backend_family(), "claude")

    def test_auto_derive_from_known_backend_id(self) -> None:
        """Test 3: without backend_family, auto-derives from backend_id via DEFAULT_FAMILY_MAP."""
        adapter = MockACPBackendAdapter(
            backend_id="hermes",
            responses=["test"],
        )
        self.assertEqual(adapter.backend_family(), "claude")

    def test_auto_derive_unknown_backend_defaults_to_own_id(self) -> None:
        """Test 4: unknown backend_id defaults to its own ID as family."""
        adapter = MockACPBackendAdapter(
            backend_id="unknown-backend",
            responses=["test"],
        )
        self.assertEqual(adapter.backend_family(), "unknown-backend")

    def test_existing_backend_id_unchanged(self) -> None:
        """Test 5: backend_id() still returns the original ID with backend_family set."""
        adapter = MockACPBackendAdapter(
            backend_id="hermes",
            responses=["test"],
            backend_family="claude",
        )
        self.assertEqual(adapter.backend_id(), "hermes")


if __name__ == "__main__":
    unittest.main()
