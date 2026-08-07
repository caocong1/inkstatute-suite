"""Tests for AnthropicStreamProvider with streaming + tool call support."""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_agent_core.model.anthropic_runner import (
    AnthropicStreamProvider,
    FakeAnthropicTransport,
    _convert_tools_to_anthropic,
    _extract_system_prompt,
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


async def _collect(provider: AnthropicStreamProvider, request: ChatRequest):
    deltas = []
    async for delta in provider.chat_stream(request):
        deltas.append(delta)
    return deltas


# Anthropic SSE event helpers

def _text_delta_event(index: int, text: str) -> dict:
    return {
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "text_delta", "text": text},
    }


def _thinking_delta_event(index: int, thinking: str) -> dict:
    return {
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "thinking_delta", "thinking": thinking},
    }


def _text_block_start(index: int) -> dict:
    return {
        "type": "content_block_start",
        "index": index,
        "content_block": {"type": "text", "text": ""},
    }


def _tool_use_start(index: int, tool_id: str, name: str) -> dict:
    return {
        "type": "content_block_start",
        "index": index,
        "content_block": {"type": "tool_use", "id": tool_id, "name": name, "input": {}},
    }


def _input_json_delta(index: int, partial: str) -> dict:
    return {
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "input_json_delta", "partial_json": partial},
    }


def _content_block_stop(index: int) -> dict:
    return {"type": "content_block_stop", "index": index}


def _message_delta(usage: dict | None = None) -> dict:
    event: dict = {"type": "message_delta", "delta": {}}
    if usage:
        event["delta"]["usage"] = usage
    return event


def _message_stop() -> dict:
    return {"type": "message_stop"}


class TestProtocolCompliance(unittest.TestCase):
    """AnthropicStreamProvider implements LlmProvider Protocol."""

    def test_implements_protocol(self):
        provider = AnthropicStreamProvider()
        self.assertIsInstance(provider, LlmProvider)

    def test_model_name_returns_redacted(self):
        provider = AnthropicStreamProvider()
        self.assertEqual(provider.model_name(), "redacted")

    def test_supports_tools_true(self):
        provider = AnthropicStreamProvider()
        self.assertTrue(provider.supports_tools())


class TestTextStreaming(unittest.TestCase):
    """Text content streaming from Anthropic SSE events."""

    def test_single_text_block(self):
        transport = FakeAnthropicTransport(stream_events=[
            _text_block_start(0),
            _text_delta_event(0, "Hello"),
            _text_delta_event(0, " world"),
            _content_block_stop(0),
            _message_stop(),
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        content_deltas = [d for d in result if isinstance(d, ContentDelta)]
        self.assertEqual(len(content_deltas), 2)
        self.assertEqual(content_deltas[0].content, "Hello")
        self.assertEqual(content_deltas[1].content, " world")

        finish_deltas = [d for d in result if isinstance(d, FinishDelta)]
        self.assertEqual(len(finish_deltas), 1)


class TestReasoningStreaming(unittest.TestCase):
    """Thinking/reasoning deltas are yielded as ReasoningDelta."""

    def test_thinking_delta(self):
        transport = FakeAnthropicTransport(stream_events=[
            _text_block_start(0),
            _thinking_delta_event(0, "Let me think..."),
            _content_block_stop(0),
            _message_stop(),
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, result if False else request))

        reasoning_deltas = [d for d in result if isinstance(d, ReasoningDelta)]
        self.assertEqual(len(reasoning_deltas), 1)
        self.assertEqual(reasoning_deltas[0].reasoning, "Let me think...")


class TestToolUseStreaming(unittest.TestCase):
    """Tool use blocks are accumulated and yielded as ToolCallDelta."""

    def test_single_tool_use(self):
        transport = FakeAnthropicTransport(stream_events=[
            _tool_use_start(0, "toolu_1", "search"),
            _input_json_delta(0, '{"q":'),
            _input_json_delta(0, '"law"}'),
            _content_block_stop(0),
            _message_stop(),
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        tool_call_deltas = [d for d in result if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(tool_call_deltas), 1)
        self.assertEqual(tool_call_deltas[0].tool_call_id, "toolu_1")
        self.assertEqual(tool_call_deltas[0].tool_name, "search")
        self.assertEqual(tool_call_deltas[0].arguments, '{"q":"law"}')

    def test_multiple_tool_uses(self):
        transport = FakeAnthropicTransport(stream_events=[
            _tool_use_start(0, "toolu_1", "search"),
            _input_json_delta(0, '{"q":"a"}'),
            _content_block_stop(0),
            _tool_use_start(1, "toolu_2", "read_file"),
            _input_json_delta(1, '{"path":"b"}'),
            _content_block_stop(1),
            _message_stop(),
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        tool_call_deltas = [d for d in result if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(tool_call_deltas), 2)
        self.assertEqual(tool_call_deltas[0].tool_call_id, "toolu_1")
        self.assertEqual(tool_call_deltas[0].arguments, '{"q":"a"}')
        self.assertEqual(tool_call_deltas[1].tool_call_id, "toolu_2")
        self.assertEqual(tool_call_deltas[1].arguments, '{"path":"b"}')

    def test_text_then_tool_use(self):
        transport = FakeAnthropicTransport(stream_events=[
            _text_block_start(0),
            _text_delta_event(0, "Let me search..."),
            _content_block_stop(0),
            _tool_use_start(1, "toolu_1", "search"),
            _input_json_delta(1, '{"q":"x"}'),
            _content_block_stop(1),
            _message_stop(),
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        content_deltas = [d for d in result if isinstance(d, ContentDelta)]
        tool_call_deltas = [d for d in result if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(content_deltas), 1)
        self.assertEqual(len(tool_call_deltas), 1)


class TestUsageExtraction(unittest.TestCase):
    """Usage data is extracted from message_delta events."""

    def test_usage_in_message_delta(self):
        transport = FakeAnthropicTransport(stream_events=[
            _text_block_start(0),
            _text_delta_event(0, "Hello"),
            _content_block_stop(0),
            _message_delta(usage={"input_tokens": 10, "output_tokens": 20}),
            _message_stop(),
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect(provider, request))

        usage_deltas = [d for d in result if isinstance(d, UsageDelta)]
        self.assertEqual(len(usage_deltas), 1)
        self.assertEqual(usage_deltas[0].usage["input_tokens"], 10)
        self.assertEqual(usage_deltas[0].usage["output_tokens"], 20)


class TestSystemPromptExtraction(unittest.TestCase):
    """System prompt is extracted from messages and sent as top-level parameter."""

    def test_system_prompt_extracted(self):
        transport = FakeAnthropicTransport(stream_events=[_message_stop()])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[
            {"role": "system", "content": "You are a legal assistant."},
            {"role": "user", "content": "hi"},
        ])
        _run_async(_collect(provider, request))

        self.assertIn("system", transport.last_request)
        self.assertEqual(transport.last_request["system"], "You are a legal assistant.")

    def test_no_system_prompt(self):
        transport = FakeAnthropicTransport(stream_events=[_message_stop()])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        _run_async(_collect(provider, request))

        self.assertNotIn("system", transport.last_request)

    def test_multiple_system_messages_concatenated(self):
        transport = FakeAnthropicTransport(stream_events=[_message_stop()])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[
            {"role": "system", "content": "Rule 1."},
            {"role": "system", "content": "Rule 2."},
            {"role": "user", "content": "hi"},
        ])
        _run_async(_collect(provider, request))

        self.assertIn("system", transport.last_request)
        self.assertIn("Rule 1.", transport.last_request["system"])
        self.assertIn("Rule 2.", transport.last_request["system"])

    def test_extract_system_prompt_function(self):
        system_prompt, remaining = _extract_system_prompt([
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ])
        self.assertEqual(system_prompt, "You are helpful.")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["role"], "user")


class TestToolConversion(unittest.TestCase):
    """OpenAI tool format is converted to Anthropic tool format."""

    def test_openai_to_anthropic_conversion(self):
        openai_tools = [
            {"type": "function", "function": {
                "name": "search",
                "description": "Search the web",
                "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
            }},
        ]
        result = _convert_tools_to_anthropic(openai_tools)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "search")
        self.assertEqual(result[0]["description"], "Search the web")
        self.assertIn("input_schema", result[0])

    def test_already_anthropic_format(self):
        anthropic_tools = [
            {"name": "search", "description": "Search", "input_schema": {"type": "object"}},
        ]
        result = _convert_tools_to_anthropic(anthropic_tools)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "search")

    def test_none_tools(self):
        result = _convert_tools_to_anthropic(None)
        self.assertIsNone(result)

    def test_tools_in_request(self):
        transport = FakeAnthropicTransport(stream_events=[_message_stop()])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "search"}}],
        )
        _run_async(_collect(provider, request))

        self.assertIn("tools", transport.last_request)
        self.assertEqual(transport.last_request["tools"][0]["name"], "search")


class TestErrorHandling(unittest.TestCase):
    """Error handling and normalization."""

    def test_transport_error_raises_provider_error(self):
        transport = FakeAnthropicTransport(error=ConnectionError("network down"))
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(_ProviderError) as ctx:
            _run_async(_collect(provider, request))
        self.assertIn("network", ctx.exception.error_info.message.lower())
        self.assertEqual(ctx.exception.error_info.details["provider"], "anthropic")

    def test_rate_limit_error(self):
        class RateLimitError(Exception):
            pass

        transport = FakeAnthropicTransport(error=RateLimitError("rate limited"))
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(_ProviderError) as ctx:
            _run_async(_collect(provider, request))
        self.assertEqual(ctx.exception.error_info.code, "provider_model_rate_limit")


class TestLazyImport(unittest.TestCase):
    """Package imports cleanly without anthropic SDK installed."""

    def test_import_without_anthropic(self):
        from inkstatute_agent_core.model import anthropic_runner
        self.assertTrue(hasattr(anthropic_runner, "AnthropicStreamProvider"))


class TestMultiTurn(unittest.TestCase):
    """Multiple chat_stream calls work correctly."""

    def test_two_turns(self):
        transport = FakeAnthropicTransport(stream_events=[
            _text_block_start(0),
            _text_delta_event(0, "turn 1"),
            _content_block_stop(0),
            _message_stop(),
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        result1 = _run_async(_collect(provider, request))
        content1 = [d for d in result1 if isinstance(d, ContentDelta)]
        self.assertEqual(len(content1), 1)

        transport.stream_events = [
            _text_block_start(0),
            _text_delta_event(0, "turn 2"),
            _content_block_stop(0),
            _message_stop(),
        ]
        result2 = _run_async(_collect(provider, request))
        content2 = [d for d in result2 if isinstance(d, ContentDelta)]
        self.assertEqual(len(content2), 1)
        self.assertEqual(content2[0].content, "turn 2")


if __name__ == "__main__":
    unittest.main()
