from __future__ import annotations

import unittest
from pathlib import Path

from platform_contract.enums import AsyncTaskState, RunEventType
from platform_contract.events import AgentTurn, Channel, MessageType
from platform_runtime import RunRequest, SolutionBinding

from inkstatute_backends_codex import (
    CodexStreamEvent,
    FakeStreamingCodexRunner,
    parse_codex_jsonl_stream,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


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


def _load_fixture(name: str) -> list[str]:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8").splitlines()


class ParseCodexJsonlStreamTests(unittest.TestCase):
    def test_parse_codex_jsonl_stream_yields_message_deltas(self) -> None:
        lines = _load_fixture("codex_exec_stream.jsonl")
        events = list(parse_codex_jsonl_stream(lines))
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].event_type, RunEventType.MESSAGE_DELTA.value)
        self.assertEqual(events[1].event_type, RunEventType.MESSAGE_DELTA.value)
        self.assertEqual(events[0].payload["message_delta"], "Hello ")
        self.assertEqual(events[1].payload["message_delta"], "world")
        self.assertEqual(events[2].event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(events[2].payload["status"], AsyncTaskState.SUCCEEDED.value)

    def test_parse_codex_jsonl_stream_yields_failed_on_turn_failed(self) -> None:
        lines = [
            '{"type":"turn.failed","error":{"kind":"rate_limit","message":"rate limited"}}',
        ]
        events = list(parse_codex_jsonl_stream(lines))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(events[0].payload["status"], AsyncTaskState.FAILED.value)
        self.assertIn("error", events[0].payload)

    def test_parse_codex_jsonl_stream_skips_unparseable_lines(self) -> None:
        lines = [
            '{"type":"thread.started","thread_id":"thread-001"}',
            "this is not valid json",
            '{"type":"item.completed","item":{"type":"assistant_message","text":"ok"}}',
            "",
            '{"type":"turn.completed","usage":{}}',
        ]
        events = list(parse_codex_jsonl_stream(lines))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event_type, RunEventType.MESSAGE_DELTA.value)
        self.assertEqual(events[1].event_type, RunEventType.STATE_CHANGED.value)
        self.assertEqual(events[1].payload["status"], AsyncTaskState.SUCCEEDED.value)


class FakeStreamingCodexRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_streaming_codex_runner_yields_events(self) -> None:
        events = [
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
        runner = FakeStreamingCodexRunner(events)
        req = make_request()
        yielded = [event async for event in runner.stream(req)]
        self.assertEqual(yielded, events)


if __name__ == "__main__":
    unittest.main()
