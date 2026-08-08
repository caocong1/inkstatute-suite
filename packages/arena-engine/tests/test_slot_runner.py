"""Tests for SlotRunner — exception isolation, retry, timeout, concurrency."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace

from platform_contract.enums import AsyncTaskState
from platform_contract.events import AgentTurn
from platform_runtime.protocols import RunRequest, SolutionBinding

from arena_engine.mock_acp import MockACPBackendAdapter
from arena_engine.slot_runner import SlotResult, run_agent_slot


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


class _FlakyMockAdapter(MockACPBackendAdapter):
    """Mock that crashes on the first N submit_run calls then succeeds."""

    def __init__(self, *, crash_count: int, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._crash_count = crash_count
        self._call_count = 0

    async def submit_run(self, req: RunRequest):  # type: ignore[override]
        self._call_count += 1
        if self._call_count <= self._crash_count:
            # Simulate a crash: create a run but mark stream as crashing
            self._crash_on_stream = True
        else:
            self._crash_on_stream = False
        return await super().submit_run(req)


class SlotRunnerFailureTests(unittest.IsolatedAsyncioTestCase):
    """Cover all 6 SlotRunner behaviours."""

    async def test_healthy_slot_returns_success(self) -> None:
        """Test 1: healthy mock returns SlotResult(status=success, content=result-a)."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a"],
        )
        result = await run_agent_slot(
            slot_id="slot-0",
            adapter=adapter,
            run_request=_make_request(),
            timeout=5.0,
        )
        self.assertEqual(result.slot_id, "slot-0")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.content, "result-a")

    async def test_crash_does_not_propagate(self) -> None:
        """Test 2: crash_on_stream returns SlotResult(status=failed), no exception."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a"],
            crash_on_stream=True,
        )
        result = await run_agent_slot(
            slot_id="slot-0",
            adapter=adapter,
            run_request=_make_request(),
            timeout=5.0,
            max_retries=0,
        )
        self.assertEqual(result.status, "failed")
        self.assertIn("error", result.metadata)
        self.assertTrue(result.metadata.get("partial"))

    async def test_timeout_does_not_propagate(self) -> None:
        """Test 3: timeout with delay returns SlotResult(status=timeout)."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a"],
            delay=0.05,
        )
        result = await run_agent_slot(
            slot_id="slot-0",
            adapter=adapter,
            run_request=_make_request(),
            timeout=0.01,
            max_retries=0,
        )
        self.assertEqual(result.status, "timeout")
        self.assertTrue(result.metadata.get("partial"))

    async def test_retry_succeeds_after_initial_crash(self) -> None:
        """Test 4: max_retries=2, crashes first then succeeds — returns success."""
        adapter = _FlakyMockAdapter(
            crash_count=1,
            backend_id="mock-a",
            responses=["result-a"],
        )
        result = await run_agent_slot(
            slot_id="slot-0",
            adapter=adapter,
            run_request=_make_request(),
            timeout=5.0,
            max_retries=2,
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.content, "result-a")
        # First attempt crashed, second succeeded → at least 2 submit_run calls
        self.assertGreaterEqual(len(adapter.submitted_requests), 2)

    async def test_concurrent_isolation_with_taskgroup(self) -> None:
        """Test 5: TaskGroup with crashing + healthy slots — no exception propagates."""

        crash_adapter = MockACPBackendAdapter(
            backend_id="mock-crash",
            responses=["result-crash"],
            crash_on_stream=True,
        )
        healthy_adapter = MockACPBackendAdapter(
            backend_id="mock-healthy",
            responses=["result-healthy"],
        )

        results: dict[str, SlotResult] = {}

        async def _run_slot(slot_id: str, adapter: MockACPBackendAdapter) -> None:
            results[slot_id] = await run_agent_slot(
                slot_id=slot_id,
                adapter=adapter,
                run_request=_make_request(),
                timeout=5.0,
                max_retries=0,
            )

        # TaskGroup must NOT raise even though slot-0 crashes
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_run_slot("slot-0", crash_adapter))
            tg.create_task(_run_slot("slot-1", healthy_adapter))

        self.assertEqual(results["slot-0"].status, "failed")
        self.assertEqual(results["slot-1"].status, "success")
        self.assertEqual(results["slot-1"].content, "result-healthy")

    async def test_events_collected_with_agent_slot(self) -> None:
        """Test 6: SlotResult.events retains metadata.agent_slot from stream."""
        adapter = MockACPBackendAdapter(
            backend_id="mock-a",
            responses=["result-a"],
            agent_slot="slot-0",
        )
        result = await run_agent_slot(
            slot_id="slot-0",
            adapter=adapter,
            run_request=_make_request(),
            timeout=5.0,
            max_retries=0,
        )
        self.assertEqual(result.status, "success")
        self.assertGreaterEqual(len(result.events), 1)
        for event in result.events:
            self.assertEqual(event.metadata.get("agent_slot"), "slot-0")


if __name__ == "__main__":
    unittest.main()
