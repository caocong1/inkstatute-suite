from __future__ import annotations

import unittest

from platform_contract.enums import Channel, MessageType
from platform_contract.events import AgentTurn
from platform_runtime import RunRequest, SolutionBinding

from inkstatute_backends_provider_model import (
    FakeStreamingProviderModelRunner,
    ProviderModelStreamDelta,
    parse_sse_deltas,
)
from inkstatute_backends_provider_model.openai_runner import parse_sse_deltas as parse_sse_deltas_direct

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


class ParseSseDeltasTests(unittest.TestCase):
    def test_parse_sse_deltas_yields_content_chunks(self) -> None:
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
            'data: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}',
            'data: {"choices":[{"delta":{"content":""},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ]
        deltas = list(parse_sse_deltas(lines))
        self.assertEqual(len(deltas), 3)
        self.assertEqual(deltas[0].content, "Hello")
        self.assertIsNone(deltas[0].finish_reason)
        self.assertEqual(deltas[1].content, " world")
        self.assertIsNone(deltas[1].finish_reason)
        self.assertEqual(deltas[2].content, "")
        self.assertEqual(deltas[2].finish_reason, "stop")

    def test_parse_sse_deltas_skips_non_data_lines(self) -> None:
        lines = [
            ": keepalive",
            "",
            'data: {"choices":[{"delta":{"content":"a"},"finish_reason":null}]}',
            ": another comment",
            "",
            'data: {"choices":[{"delta":{"content":"b"},"finish_reason":"stop"}]}',
        ]
        deltas = list(parse_sse_deltas(lines))
        self.assertEqual(len(deltas), 2)
        self.assertEqual(deltas[0].content, "a")
        self.assertEqual(deltas[1].content, "b")

    def test_parse_sse_deltas_skips_unparseable_json(self) -> None:
        lines = [
            "data: {not valid json}",
            'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}',
        ]
        deltas = list(parse_sse_deltas(lines))
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0].content, "ok")

    def test_parse_sse_deltas_done_marker_not_yielded(self) -> None:
        lines = [
            'data: {"choices":[{"delta":{"content":"done"},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ]
        deltas = list(parse_sse_deltas(lines))
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0].content, "done")


class FakeStreamingProviderModelRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_streaming_provider_model_runner_yields_deltas(self) -> None:
        deltas = [
            ProviderModelStreamDelta(content="Hello "),
            ProviderModelStreamDelta(content="world"),
            ProviderModelStreamDelta(content="", finish_reason="stop"),
        ]
        runner = FakeStreamingProviderModelRunner(deltas)
        req = make_request()
        yielded: list[ProviderModelStreamDelta] = []
        async for delta in runner.stream(req):
            yielded.append(delta)
        self.assertEqual(yielded, deltas)
        self.assertEqual(yielded[0].content, "Hello ")
        self.assertEqual(yielded[1].content, "world")
        self.assertEqual(yielded[2].content, "")
        self.assertEqual(yielded[2].finish_reason, "stop")


class ReexportTests(unittest.TestCase):
    def test_parse_sse_deltas_reexport_matches_direct_import(self) -> None:
        self.assertIs(parse_sse_deltas, parse_sse_deltas_direct)


if __name__ == "__main__":
    unittest.main()
