"""Tests for OllamaStreamProvider with streaming support."""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_agent_core.model.ollama_runner import (
    FakeOllamaTransport,
    OllamaHTTPError,
    OllamaStreamProvider,
)
from inkstatute_agent_core.model.openai_runner import _ProviderError
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


async def _collect(provider: OllamaStreamProvider, request: ChatRequest):
    deltas = []
    async for delta in provider.chat_stream(request):
        deltas.append(delta)
    return deltas


def _content_chunk(content: str) -> dict:
    return {"choices": [{"delta": {"content": content}}]}


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
    """OllamaStreamProvider implements LlmProvider Protocol."""

    def test_implements_protocol(self):
        provider = OllamaStreamProvider()
        self.assertIsInstance(provider, LlmProvider)

    def test_model_name_returns_redacted(self):
        provider = OllamaStreamProvider()
        self.assertEqual(provider.model_name(), "redacted")

    def test_supports_tools_true(self):
        provider = OllamaStreamProvider()
        self.assertTrue(provider.supports_tools())


class TestContentStreaming(unittest.TestCase):
    """Content streaming from Ollama's OpenAI-compatible SSE."""

    def test_single_content_chunk(self):
        transport = FakeOllamaTransport(stream_chunks=[
            _content_chunk("Hello"),
            _finish_chunk("stop"),
        ])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        content_deltas = [d for d in result if isinstance(d, ContentDelta)]
        self.assertEqual(len(content_deltas), 1)
        self.assertEqual(content_deltas[0].content, "Hello")

        finish_deltas = [d for d in result if isinstance(d, FinishDelta)]
        self.assertEqual(len(finish_deltas), 1)

    def test_multiple_content_chunks(self):
        transport = FakeOllamaTransport(stream_chunks=[
            _content_chunk("Hello"),
            _content_chunk(" world"),
            _finish_chunk("stop"),
        ])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        content_deltas = [d for d in result if isinstance(d, ContentDelta)]
        self.assertEqual(len(content_deltas), 2)


class TestToolCallStreaming(unittest.TestCase):
    """Tool call streaming reuses OpenAI tool call accumulation."""

    def test_single_tool_call(self):
        transport = FakeOllamaTransport(stream_chunks=[
            _tool_call_chunk(0, tool_call_id="call_1", name="search"),
            _tool_call_chunk(0, arguments='{"q":"law"}'),
            _finish_chunk("tool_calls"),
        ])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        tool_call_deltas = [d for d in result if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(tool_call_deltas), 1)
        self.assertEqual(tool_call_deltas[0].tool_call_id, "call_1")
        self.assertEqual(tool_call_deltas[0].tool_name, "search")
        self.assertEqual(tool_call_deltas[0].arguments, '{"q":"law"}')


class TestReasoningStreaming(unittest.TestCase):
    """Reasoning content streaming."""

    def test_reasoning_delta(self):
        transport = FakeOllamaTransport(stream_chunks=[
            {"choices": [{"delta": {"reasoning_content": "thinking..."}}]},
            _finish_chunk("stop"),
        ])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        reasoning_deltas = [d for d in result if isinstance(d, ReasoningDelta)]
        self.assertEqual(len(reasoning_deltas), 1)
        self.assertEqual(reasoning_deltas[0].reasoning, "thinking...")


class TestUsageExtraction(unittest.TestCase):
    """Usage data is extracted and yielded as UsageDelta."""

    def test_usage_in_final_chunk(self):
        transport = FakeOllamaTransport(stream_chunks=[
            _content_chunk("Hello"),
            _finish_chunk("stop"),
            _usage_chunk({"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}),
        ])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        usage_deltas = [d for d in result if isinstance(d, UsageDelta)]
        self.assertEqual(len(usage_deltas), 1)
        self.assertEqual(usage_deltas[0].usage["prompt_tokens"], 5)
        self.assertEqual(usage_deltas[0].usage["total_tokens"], 15)


class TestErrorHandling(unittest.TestCase):
    """Error handling and normalization."""

    def test_transport_error_raises_provider_error(self):
        transport = FakeOllamaTransport(error=ConnectionError("connection refused"))
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(_ProviderError) as ctx:
            _run_async(_collect(provider, request))
        self.assertEqual(ctx.exception.error_info.details["provider"], "ollama")

    def test_http_error_with_status_code(self):
        err = OllamaHTTPError("rate limited", status_code=429)
        transport = FakeOllamaTransport(error=err)
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(_ProviderError) as ctx:
            _run_async(_collect(provider, request))
        self.assertEqual(ctx.exception.error_info.code, "provider_model_rate_limit")
        self.assertEqual(ctx.exception.error_info.details["status_code"], 429)

    def test_auth_error_with_status_code(self):
        err = OllamaHTTPError("unauthorized", status_code=401)
        transport = FakeOllamaTransport(error=err)
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(_ProviderError) as ctx:
            _run_async(_collect(provider, request))
        self.assertEqual(ctx.exception.error_info.code, "provider_model_auth_error")

    def test_server_error_with_status_code(self):
        err = OllamaHTTPError("internal error", status_code=500)
        transport = FakeOllamaTransport(error=err)
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(_ProviderError) as ctx:
            _run_async(_collect(provider, request))
        self.assertEqual(ctx.exception.error_info.code, "provider_model_api_error")


class TestRequestBuilding(unittest.TestCase):
    """Request payload building includes tools and parameters."""

    def test_stream_always_true(self):
        transport = FakeOllamaTransport(stream_chunks=[_finish_chunk("stop")])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        _run_async(_collect(provider, request))

        self.assertTrue(transport.last_request["stream"])

    def test_tools_included(self):
        transport = FakeOllamaTransport(stream_chunks=[_finish_chunk("stop")])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "search"}}],
        )
        _run_async(_collect(provider, request))

        self.assertIn("tools", transport.last_request)


class TestLazyImport(unittest.TestCase):
    """Package imports cleanly without external HTTP library."""

    def test_import_without_httpx(self):
        from inkstatute_agent_core.model import ollama_runner
        self.assertTrue(hasattr(ollama_runner, "OllamaStreamProvider"))


class TestMultiTurn(unittest.TestCase):
    """Multiple chat_stream calls work correctly."""

    def test_two_turns(self):
        transport = FakeOllamaTransport(stream_chunks=[
            _content_chunk("turn 1"),
            _finish_chunk("stop"),
        ])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        result1 = _run_async(_collect(provider, request))
        content1 = [d for d in result1 if isinstance(d, ContentDelta)]
        self.assertEqual(len(content1), 1)

        transport.stream_chunks = [
            _content_chunk("turn 2"),
            _finish_chunk("stop"),
        ]
        result2 = _run_async(_collect(provider, request))
        content2 = [d for d in result2 if isinstance(d, ContentDelta)]
        self.assertEqual(content2[0].content, "turn 2")


class TestOllamaHTTPError(unittest.TestCase):
    """OllamaHTTPError carries status code for normalization."""

    def test_status_code_attribute(self):
        err = OllamaHTTPError("error", status_code=500)
        self.assertEqual(err.status_code, 500)

    def test_is_exception(self):
        err = OllamaHTTPError("error", status_code=500)
        self.assertIsInstance(err, Exception)


if __name__ == "__main__":
    unittest.main()
