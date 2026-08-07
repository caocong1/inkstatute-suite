"""Tests for OpenAIStreamProvider with streaming + tool call support."""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_agent_core.model.openai_runner import (
    FakeOpenAITransport,
    OpenAIStreamProvider,
    _ToolCallAccumulator,
    _ProviderError,
    parse_sse_deltas,
)
from inkstatute_agent_core.model.provider import (
    ChatRequest,
    ContentDelta,
    FinishDelta,
    LlmProvider,
    ReasoningDelta,
    ToolCallDelta,
    UsageDelta,
)


def _run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _collect(provider: OpenAIStreamProvider, request: ChatRequest):
    deltas = []
    async for delta in provider.chat_stream(request):
        deltas.append(delta)
    return deltas


def _content_chunk(content: str) -> dict:
    return {"choices": [{"delta": {"content": content}}]}


def _reasoning_chunk(reasoning: str) -> dict:
    return {"choices": [{"delta": {"reasoning_content": reasoning}}]}


def _tool_call_chunk(index: int, tool_call_id: str = "", name: str = "", arguments: str = "") -> dict:
    tc: dict = {"index": index}
    if tool_call_id:
        tc["id"] = tool_call_id
    if name or arguments:
        tc["function"] = {}
        if name:
            tc["function"]["name"] = name
        if arguments:
            tc["function"]["arguments"] = arguments
    return {"choices": [{"delta": {"tool_calls": [tc]}}]}


def _finish_chunk(finish_reason: str) -> dict:
    return {"choices": [{"delta": {}, "finish_reason": finish_reason}]}


def _usage_chunk(usage: dict) -> dict:
    return {"choices": [], "usage": usage}


class TestProtocolCompliance(unittest.TestCase):
    """OpenAIStreamProvider implements LlmProvider Protocol."""

    def test_implements_protocol(self):
        provider = OpenAIStreamProvider()
        self.assertIsInstance(provider, LlmProvider)

    def test_model_name_returns_redacted(self):
        provider = OpenAIStreamProvider()
        self.assertEqual(provider.model_name(), "redacted")

    def test_supports_tools_true(self):
        provider = OpenAIStreamProvider()
        self.assertTrue(provider.supports_tools())


class TestContentStreaming(unittest.TestCase):
    """Content-only streaming."""

    def test_single_content_chunk(self):
        transport = FakeOpenAITransport(stream_chunks=[
            _content_chunk("Hello"),
            _finish_chunk("stop"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], ContentDelta)
        self.assertEqual(result[0].content, "Hello")
        self.assertIsInstance(result[1], FinishDelta)
        self.assertEqual(result[1].finish_reason, "stop")

    def test_multiple_content_chunks(self):
        transport = FakeOpenAITransport(stream_chunks=[
            _content_chunk("Hello"),
            _content_chunk(" world"),
            _content_chunk("!"),
            _finish_chunk("stop"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        content_deltas = [d for d in result if isinstance(d, ContentDelta)]
        self.assertEqual(len(content_deltas), 3)
        self.assertEqual(content_deltas[0].content, "Hello")
        self.assertEqual(content_deltas[1].content, " world")
        self.assertEqual(content_deltas[2].content, "!")


class TestReasoningStreaming(unittest.TestCase):
    """Reasoning content streaming."""

    def test_reasoning_delta(self):
        transport = FakeOpenAITransport(stream_chunks=[
            _reasoning_chunk("Let me think..."),
            _content_chunk("Here is the answer"),
            _finish_chunk("stop"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        reasoning_deltas = [d for d in result if isinstance(d, ReasoningDelta)]
        self.assertEqual(len(reasoning_deltas), 1)
        self.assertEqual(reasoning_deltas[0].reasoning, "Let me think...")


class TestToolCallStreaming(unittest.TestCase):
    """Tool call fragment accumulation."""

    def test_single_tool_call_accumulated(self):
        transport = FakeOpenAITransport(stream_chunks=[
            _tool_call_chunk(0, tool_call_id="call_1", name="search"),
            _tool_call_chunk(0, arguments='{"q":'),
            _tool_call_chunk(0, arguments='"law"}'),
            _finish_chunk("tool_calls"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        tool_call_deltas = [d for d in result if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(tool_call_deltas), 1)
        self.assertEqual(tool_call_deltas[0].tool_call_id, "call_1")
        self.assertEqual(tool_call_deltas[0].tool_name, "search")
        self.assertEqual(tool_call_deltas[0].arguments, '{"q":"law"}')

    def test_multiple_tool_calls(self):
        transport = FakeOpenAITransport(stream_chunks=[
            _tool_call_chunk(0, tool_call_id="call_1", name="search"),
            _tool_call_chunk(0, arguments='{"q":"a"}'),
            _tool_call_chunk(1, tool_call_id="call_2", name="read_file"),
            _tool_call_chunk(1, arguments='{"path":"b"}'),
            _finish_chunk("tool_calls"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        tool_call_deltas = [d for d in result if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(tool_call_deltas), 2)
        self.assertEqual(tool_call_deltas[0].tool_call_id, "call_1")
        self.assertEqual(tool_call_deltas[0].tool_name, "search")
        self.assertEqual(tool_call_deltas[0].arguments, '{"q":"a"}')
        self.assertEqual(tool_call_deltas[1].tool_call_id, "call_2")
        self.assertEqual(tool_call_deltas[1].tool_name, "read_file")
        self.assertEqual(tool_call_deltas[1].arguments, '{"path":"b"}')

    def test_tool_call_finalized_on_finish(self):
        """Tool calls are finalized when finish_reason appears."""
        transport = FakeOpenAITransport(stream_chunks=[
            _tool_call_chunk(0, tool_call_id="call_1", name="search", arguments='{"q":"x"}'),
            _finish_chunk("tool_calls"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, result if False else request))

        tool_call_deltas = [d for d in result if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(tool_call_deltas), 1)
        self.assertEqual(tool_call_deltas[0].arguments, '{"q":"x"}')


class TestUsageExtraction(unittest.TestCase):
    """Usage data is extracted and yielded as UsageDelta."""

    def test_usage_in_final_chunk(self):
        transport = FakeOpenAITransport(stream_chunks=[
            _content_chunk("Hello"),
            _finish_chunk("stop"),
            _usage_chunk({"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        usage_deltas = [d for d in result if isinstance(d, UsageDelta)]
        self.assertEqual(len(usage_deltas), 1)
        self.assertEqual(usage_deltas[0].usage["prompt_tokens"], 10)
        self.assertEqual(usage_deltas[0].usage["completion_tokens"], 20)
        self.assertEqual(usage_deltas[0].usage["total_tokens"], 30)


class TestErrorHandling(unittest.TestCase):
    """Error handling and normalization."""

    def test_transport_error_raises_provider_error(self):
        transport = FakeOpenAITransport(error=ConnectionError("network down"))
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(_ProviderError) as ctx:
            _run_async(_collect(provider, request))
        self.assertIn("network", ctx.exception.error_info.message.lower())

    def test_rate_limit_error(self):
        # Use a class with RateLimit in the name (matching SDK pattern)
        class RateLimitError(Exception):
            pass

        transport = FakeOpenAITransport(error=RateLimitError("rate limited"))
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(_ProviderError) as ctx:
            _run_async(_collect(provider, request))
        self.assertEqual(ctx.exception.error_info.code, "provider_model_rate_limit")


class TestRequestBuilding(unittest.TestCase):
    """Request payload building includes tools and parameters."""

    def test_tools_included_in_request(self):
        transport = FakeOpenAITransport(stream_chunks=[_finish_chunk("stop")])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "search"}}],
        )
        _run_async(_collect(provider, request))

        self.assertIn("tools", transport.last_request)
        self.assertEqual(len(transport.last_request["tools"]), 1)

    def test_max_tokens_included(self):
        transport = FakeOpenAITransport(stream_chunks=[_finish_chunk("stop")])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=4096,
        )
        _run_async(_collect(provider, request))

        self.assertEqual(transport.last_request["max_tokens"], 4096)

    def test_temperature_included(self):
        transport = FakeOpenAITransport(stream_chunks=[_finish_chunk("stop")])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7,
        )
        _run_async(_collect(provider, request))

        self.assertEqual(transport.last_request["temperature"], 0.7)

    def test_stream_always_true(self):
        transport = FakeOpenAITransport(stream_chunks=[_finish_chunk("stop")])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        _run_async(_collect(provider, request))

        self.assertTrue(transport.last_request["stream"])


class TestMultiTurn(unittest.TestCase):
    """Multiple chat_stream calls work correctly."""

    def test_two_turns(self):
        transport = FakeOpenAITransport(stream_chunks=[
            _content_chunk("turn 1"),
            _finish_chunk("stop"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        result1 = _run_async(_collect(provider, request))
        self.assertEqual(len(result1), 2)

        # Reset transport for second turn
        transport.stream_chunks = [
            _content_chunk("turn 2"),
            _finish_chunk("stop"),
        ]
        result2 = _run_async(_collect(provider, request))
        self.assertEqual(len(result2), 2)
        self.assertEqual(result2[0].content, "turn 2")


class TestParseSseDeltas(unittest.TestCase):
    """parse_sse_deltas parses raw SSE lines into JSON dicts."""

    def test_basic_parsing(self):
        import json
        lines = [
            'data: {"choices": [{"delta": {"content": "hi"}}]}',
            "data: [DONE]",
            "",
            ": comment",
        ]
        results = list(parse_sse_deltas(lines))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["choices"][0]["delta"]["content"], "hi")

    def test_unparseable_json_skipped(self):
        lines = ["data: not json", "data: {valid: true}"]
        results = list(parse_sse_deltas(lines))
        # "not json" is unparseable, "{valid: true}" is also not valid JSON
        # (keys need quotes in strict JSON)
        self.assertEqual(len(results), 0)

    def test_empty_lines_skipped(self):
        lines = ["", "  ", "data: [DONE]"]
        results = list(parse_sse_deltas(lines))
        self.assertEqual(len(results), 0)


class TestToolCallAccumulator(unittest.TestCase):
    """Direct unit tests for _ToolCallAccumulator."""

    def test_single_tool_call(self):
        acc = _ToolCallAccumulator()
        # First chunk: id + name
        completed = acc.process_chunk([
            {"index": 0, "id": "call_1", "function": {"name": "search"}}
        ])
        self.assertEqual(completed, [])  # Not finalized yet

        # Second chunk: arguments fragment
        completed = acc.process_chunk([
            {"index": 0, "function": {"arguments": '{"q":"'}}
        ])
        self.assertEqual(completed, [])

        # Third chunk: arguments fragment
        completed = acc.process_chunk([
            {"index": 0, "function": {"arguments": 'law"}'}}
        ])
        self.assertEqual(completed, [])

        # Finalize
        finalized = acc.finalize_all()
        self.assertEqual(len(finalized), 1)
        self.assertEqual(finalized[0].tool_call_id, "call_1")
        self.assertEqual(finalized[0].tool_name, "search")
        self.assertEqual(finalized[0].arguments, '{"q":"law"}')

    def test_new_index_finalizes_previous(self):
        acc = _ToolCallAccumulator()
        acc.process_chunk([{"index": 0, "id": "call_1", "function": {"name": "search", "arguments": '{"q":"a"}'}}])
        acc.process_chunk([{"index": 1, "id": "call_2", "function": {"name": "read", "arguments": '{"f":"b"}'}}])
        finalized = acc.finalize_all()

        # First should be finalized when index 1 appears
        # Second should be finalized by finalize_all
        all_tc = list(acc._pending.keys())  # Should be empty after finalize_all
        # We need to check the completed list from process_chunk
        # Let's redo more carefully
        acc2 = _ToolCallAccumulator()
        completed1 = acc2.process_chunk([{"index": 0, "id": "call_1", "function": {"name": "search", "arguments": '{"q":"a"}'}}])
        self.assertEqual(completed1, [])
        completed2 = acc2.process_chunk([{"index": 1, "id": "call_2", "function": {"name": "read", "arguments": '{"f":"b"}'}}])
        # Index 0 should be finalized when index 1 appears
        self.assertEqual(len(completed2), 1)
        self.assertEqual(completed2[0].tool_call_id, "call_1")
        finalized = acc2.finalize_all()
        self.assertEqual(len(finalized), 1)
        self.assertEqual(finalized[0].tool_call_id, "call_2")


class TestLazyImport(unittest.TestCase):
    """Package imports cleanly without openai SDK installed."""

    def test_import_without_openai(self):
        # The module should import without the openai package
        from inkstatute_agent_core.model import openai_runner
        self.assertTrue(hasattr(openai_runner, "OpenAIStreamProvider"))


if __name__ == "__main__":
    unittest.main()
