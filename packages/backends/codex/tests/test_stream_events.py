from __future__ import annotations

import unittest

from platform_contract.enums import AsyncTaskState, Channel, MessageType, RunEventType
from platform_contract.events import AgentResult, AgentTurn, ReplyType
from platform_runtime import RunEvent, RunRequest, SolutionBinding

from inkstatute_backends_codex import (
    CodexBackendAdapter,
    CodexBackendConfig,
    CodexExecResult,
    CodexStreamEvent,
    FakeStreamingCodexRunner,
)


def make_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-001",
            conversation_id="conversation-001",
            channel=Channel.WEB,
            user_id="user-001",
            message_type=MessageType.TEXT,
            received_at="2026-06-29T00:00:00Z",
            content="synthetic request",
            metadata={"raw_payload_ref": "fixture://raw/turn-001"},
        ),
        solution=SolutionBinding(solution_id="codex-solution", backend_id="codex-prototype"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
    )


class FakeCodexExecRunner:
    def __init__(self) -> None:
        self.calls: list[RunRequest] = []

    async def invoke(self, req: RunRequest) -> CodexExecResult:
        self.calls.append(req)
        return CodexExecResult(
            status=AsyncTaskState.SUCCEEDED,
            result=AgentResult(
                result_id="result-001",
                turn_id="turn-001",
                status="success",
                reply_type=ReplyType.TEXT,
                content="Sanitized legal analysis result.",
            ),
        )


class StreamEventsTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_events_without_streaming_runner_yields_single_terminal(self) -> None:
        adapter = CodexBackendAdapter(runner=FakeCodexExecRunner())
        handle = await adapter.submit_run(make_request())
        events = [event async for event in adapter.stream_events(handle.run_id)]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(events[0].payload["status"], AsyncTaskState.SUCCEEDED.value)
        self.assertNotIn("completed", str(events[0].payload["status"]))

    async def test_stream_events_with_streaming_runner_yields_deltas_and_terminal(self) -> None:
        stream_events = [
            CodexStreamEvent(
                event_type=RunEventType.MESSAGE_DELTA.value,
                payload={"message_delta": "chunk-1"},
            ),
            CodexStreamEvent(
                event_type=RunEventType.MESSAGE_DELTA.value,
                payload={"message_delta": "chunk-2"},
            ),
            CodexStreamEvent(
                event_type=RunEventType.STATE_CHANGED.value,
                payload={"status": AsyncTaskState.SUCCEEDED.value},
            ),
        ]
        adapter = CodexBackendAdapter(
            runner=FakeCodexExecRunner(),
            streaming_runner=FakeStreamingCodexRunner(stream_events),
        )
        handle = await adapter.submit_run(make_request())
        events = [event async for event in adapter.stream_events(handle.run_id)]
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0].event_type, RunEventType.MESSAGE_DELTA.value)
        self.assertEqual(events[1].event_type, RunEventType.MESSAGE_DELTA.value)
        self.assertEqual(events[2].event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(events[3].event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(events[3].payload["status"], AsyncTaskState.SUCCEEDED.value)
        self.assertEqual([e.seq for e in events], [0, 1, 2, 3])

    async def test_stream_events_terminal_never_says_completed(self) -> None:
        stream_events = [
            CodexStreamEvent(
                event_type=RunEventType.MESSAGE_DELTA.value,
                payload={"message_delta": "hello"},
            ),
            CodexStreamEvent(
                event_type=RunEventType.STATE_CHANGED.value,
                payload={"status": AsyncTaskState.SUCCEEDED.value},
            ),
        ]
        adapter = CodexBackendAdapter(
            runner=FakeCodexExecRunner(),
            streaming_runner=FakeStreamingCodexRunner(stream_events),
        )
        handle = await adapter.submit_run(make_request())
        events = [event async for event in adapter.stream_events(handle.run_id)]
        statuses = {str(e.payload.get("status")) for e in events}
        self.assertNotIn("completed", statuses)

    async def test_stream_events_on_exception_yields_failed_terminal(self) -> None:
        class RaisingStreamingRunner:
            async def stream(self, req: RunRequest):
                raise RuntimeError("stream blew up")
                yield  # pragma: no cover

        adapter = CodexBackendAdapter(
            runner=FakeCodexExecRunner(),
            streaming_runner=RaisingStreamingRunner(),
        )
        handle = await adapter.submit_run(make_request())
        events = [event async for event in adapter.stream_events(handle.run_id)]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(events[0].payload["status"], AsyncTaskState.FAILED.value)

    async def test_stream_events_unknown_run_raises(self) -> None:
        adapter = CodexBackendAdapter(runner=FakeCodexExecRunner())
        with self.assertRaises(KeyError):
            async for _ in adapter.stream_events("nonexistent-run"):
                pass

    def test_capabilities_reflects_streaming_runner(self) -> None:
        adapter_without = CodexBackendAdapter(runner=FakeCodexExecRunner())
        self.assertFalse(adapter_without.capabilities().stream_event_support)

        adapter_with = CodexBackendAdapter(
            runner=FakeCodexExecRunner(),
            streaming_runner=FakeStreamingCodexRunner([]),
        )
        self.assertTrue(adapter_with.capabilities().stream_event_support)


if __name__ == "__main__":
    unittest.main()
