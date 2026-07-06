from __future__ import annotations

import unittest

from platform_contract.enums import AsyncTaskState, Channel, MessageType, RunEventType
from platform_contract.events import AgentResult, AgentTurn, ReplyType
from platform_runtime import RunEvent, RunRequest, SolutionBinding

from inkstatute_backends_provider_model import (
    FakeStreamingProviderModelRunner,
    ProviderModelBackendAdapter,
    ProviderModelExecResult,
    ProviderModelStreamDelta,
)

RAW_REQUEST = "synthetic privileged legal request that must not leak"


def make_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-001",
            conversation_id="conversation-001",
            channel=Channel.WEB,
            user_id="user-001",
            message_type=MessageType.TEXT,
            received_at="2026-07-04T00:00:00Z",
            content=RAW_REQUEST,
            metadata={"raw_payload_ref": "fixture://raw/turn-001"},
        ),
        solution=SolutionBinding(
            solution_id="provider-model-solution",
            backend_id="provider-model-prototype",
        ),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
    )


class FakeProviderModelRunner:
    def __init__(self) -> None:
        self.calls: list[RunRequest] = []

    async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
        self.calls.append(req)
        return ProviderModelExecResult(
            status=AsyncTaskState.SUCCEEDED,
            result=AgentResult(
                result_id="result-001",
                turn_id="turn-001",
                status="success",
                reply_type=ReplyType.TEXT,
                content="Sanitized legal analysis result.",
            ),
            completion_id="completion-001",
            raw_payload_ref="fixture://raw/result-001",
            metadata={"provider_completion_id": "completion-001"},
        )


class RaisingStreamingRunner:
    async def stream(self, req: RunRequest):
        raise RuntimeError("stream blew up")
        yield  # pragma: no cover - make this an async generator


async def _collect(events_gen) -> list[RunEvent]:
    collected: list[RunEvent] = []
    async for event in events_gen:
        collected.append(event)
    return collected


class StreamEventsTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_events_without_streaming_runner_yields_single_terminal(self) -> None:
        adapter = ProviderModelBackendAdapter(runner=FakeProviderModelRunner())
        handle = await adapter.submit_run(make_request())
        events = await _collect(adapter.stream_events(handle.run_id))
        self.assertEqual(len(events), 1)
        terminal = events[0]
        self.assertEqual(terminal.event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(terminal.payload["status"], AsyncTaskState.SUCCEEDED.value)
        self.assertNotIn("completed", str(terminal.payload.get("status")))

    async def test_stream_events_with_streaming_runner_yields_deltas_and_terminal(self) -> None:
        deltas = [
            ProviderModelStreamDelta(content="Hello "),
            ProviderModelStreamDelta(content="world"),
            ProviderModelStreamDelta(content="", finish_reason="stop"),
        ]
        streaming_runner = FakeStreamingProviderModelRunner(deltas)
        adapter = ProviderModelBackendAdapter(
            runner=FakeProviderModelRunner(),
            streaming_runner=streaming_runner,
        )
        handle = await adapter.submit_run(make_request())
        events = await _collect(adapter.stream_events(handle.run_id))
        self.assertEqual(len(events), 4)
        for i in range(3):
            self.assertEqual(events[i].event_type, RunEventType.MESSAGE_DELTA.value)
            self.assertEqual(events[i].payload["message_delta"], deltas[i].content)
            self.assertEqual(events[i].payload["status"], "running")
            self.assertEqual(events[i].seq, i)
        terminal = events[3]
        self.assertEqual(terminal.event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(terminal.payload["status"], AsyncTaskState.SUCCEEDED.value)
        self.assertEqual(terminal.seq, 3)
        self.assertEqual(terminal.event_id, f"event-{handle.run_id}-terminal")

    async def test_stream_events_terminal_never_says_completed(self) -> None:
        deltas = [
            ProviderModelStreamDelta(content="Hello "),
            ProviderModelStreamDelta(content="world"),
            ProviderModelStreamDelta(content="", finish_reason="stop"),
        ]
        adapter = ProviderModelBackendAdapter(
            runner=FakeProviderModelRunner(),
            streaming_runner=FakeStreamingProviderModelRunner(deltas),
        )
        handle = await adapter.submit_run(make_request())
        events = await _collect(adapter.stream_events(handle.run_id))
        statuses = {str(e.payload.get("status")) for e in events}
        self.assertNotIn("completed", statuses)

    async def test_stream_events_on_exception_yields_failed_terminal(self) -> None:
        adapter = ProviderModelBackendAdapter(
            runner=FakeProviderModelRunner(),
            streaming_runner=RaisingStreamingRunner(),
        )
        handle = await adapter.submit_run(make_request())
        events = await _collect(adapter.stream_events(handle.run_id))
        self.assertEqual(len(events), 1)
        terminal = events[0]
        self.assertEqual(terminal.event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(terminal.payload["status"], AsyncTaskState.FAILED.value)
        self.assertEqual(terminal.payload["error"]["code"], "provider_model_stream_error")

    async def test_stream_events_unknown_run_raises(self) -> None:
        adapter = ProviderModelBackendAdapter(runner=FakeProviderModelRunner())
        with self.assertRaises(KeyError):
            await _collect(adapter.stream_events("unknown-run-id"))

    def test_capabilities_reflects_streaming_runner(self) -> None:
        adapter_without = ProviderModelBackendAdapter(runner=FakeProviderModelRunner())
        self.assertIs(adapter_without.capabilities().stream_event_support, False)
        adapter_with = ProviderModelBackendAdapter(
            runner=FakeProviderModelRunner(),
            streaming_runner=FakeStreamingProviderModelRunner([]),
        )
        self.assertIs(adapter_with.capabilities().stream_event_support, True)


if __name__ == "__main__":
    unittest.main()
