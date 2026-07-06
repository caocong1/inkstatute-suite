from __future__ import annotations

import unittest
from typing import AsyncIterator

from platform_contract.enums import Channel, MessageType, RunEventType
from platform_contract.events import AgentTurn

from platform_runtime import (
    BoundaryAction,
    DefaultRunRuntime,
    RunRequest,
    RuntimeFeatureFlags,
    SolutionBinding,
)
from platform_runtime.fakes import FakeBackendAdapter
from platform_runtime.protocols import RunEvent


FIXED_NOW = "2026-06-29T03:00:00Z"


def make_run_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-cancellation-001",
            conversation_id="conversation-cancellation-001",
            channel=Channel.WEB,
            user_id="user-cancellation-001",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            content="synthetic request",
            metadata={"raw_payload_ref": "fixture://payloads/turn-cancellation-001"},
        ),
        solution=SolutionBinding(solution_id="solution-cancellation-001", version="1.0.0"),
        tenant_id="tenant-cancellation-001",
        workspace_id="workspace-cancellation-001",
        session_id="session-cancellation-001",
    )


class TrackingFakeBackend(FakeBackendAdapter):
    """Fake backend whose stream_events generator tracks cleanup via a finally block."""

    def __init__(self, *, raise_after_first: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cleanup_called: bool = False
        self.yield_count: int = 0
        self._raise_after_first = raise_after_first

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        self._require_run(run_id)
        try:
            for event in tuple(self.events[run_id]):
                self.yield_count += 1
                yield event
                if self._raise_after_first:
                    raise RuntimeError("backend exploded after first event")
        finally:
            self.cleanup_called = True


class StreamCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_normal_completion_calls_aclose(self) -> None:
        backend = TrackingFakeBackend()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())

        events = [event async for event in runtime.stream(run.run_id)]

        self.assertTrue(len(events) > 0)
        self.assertTrue(backend.cleanup_called)

    async def test_stream_cancellation_propagates_aclose(self) -> None:
        backend = TrackingFakeBackend()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())

        collected: list[RunEvent] = []
        stream = runtime.stream(run.run_id)
        async for event in stream:
            collected.append(event)
            break
        await stream.aclose()

        self.assertEqual(len(collected), 1)
        self.assertTrue(backend.cleanup_called)

    async def test_stream_no_zombie_after_cancellation(self) -> None:
        backend = TrackingFakeBackend()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())

        stream = runtime.stream(run.run_id)
        async for _event in stream:
            break
        await stream.aclose()

        self.assertTrue(backend.cleanup_called)
        self.assertEqual(backend.yield_count, 1)

    async def test_stream_aclose_called_on_exception(self) -> None:
        backend = TrackingFakeBackend(raise_after_first=True)
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())

        raised = False
        try:
            async for _event in runtime.stream(run.run_id):
                pass
        except RuntimeError:
            raised = True

        self.assertTrue(raised)
        self.assertTrue(backend.cleanup_called)

    async def test_stream_boundary_still_applied(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        backend.append_message_delta(run.run_id, "api key invalid", metadata={"scripted": True})

        events = [event async for event in runtime.stream(run.run_id)]
        scripted = [event for event in events if event.metadata.get("scripted")]

        self.assertTrue(len(scripted) > 0)
        self.assertEqual(
            scripted[-1].metadata["output_boundary"]["action"],
            BoundaryAction.BLOCK.value,
        )
        self.assertNotIn("message_delta", scripted[-1].payload)


if __name__ == "__main__":
    unittest.main()
