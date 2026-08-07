"""Tests for LlmProvider Protocol, StreamDelta union types, and UsageAccumulator."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass

from inkstatute_agent_core.model.provider import (
    ChatRequest,
    ContentDelta,
    FinishDelta,
    LlmProvider,
    ReasoningDelta,
    StreamDelta,
    ToolCallDelta,
    UsageAccumulator,
    UsageDelta,
)


class TestStreamDeltaTypes(unittest.TestCase):
    """StreamDelta is a union of 5 frozen dataclass types."""

    def test_content_delta_construction(self):
        d = ContentDelta(content="hello")
        self.assertEqual(d.content, "hello")

    def test_content_delta_is_frozen(self):
        d = ContentDelta(content="hello")
        with self.assertRaises(FrozenInstanceError):
            d.content = "world"  # type: ignore[misc]

    def test_content_delta_is_dataclass(self):
        self.assertTrue(is_dataclass(ContentDelta))

    def test_reasoning_delta_construction(self):
        d = ReasoningDelta(reasoning="thinking...")
        self.assertEqual(d.reasoning, "thinking...")

    def test_reasoning_delta_is_frozen(self):
        d = ReasoningDelta(reasoning="thinking...")
        with self.assertRaises(FrozenInstanceError):
            d.reasoning = "new"  # type: ignore[misc]

    def test_tool_call_delta_construction(self):
        d = ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments='{"q": "test"}')
        self.assertEqual(d.tool_call_id, "tc1")
        self.assertEqual(d.tool_name, "search")
        self.assertEqual(d.arguments, '{"q": "test"}')

    def test_tool_call_delta_is_frozen(self):
        d = ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}")
        with self.assertRaises(FrozenInstanceError):
            d.tool_name = "other"  # type: ignore[misc]

    def test_usage_delta_construction(self):
        d = UsageDelta(usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})
        self.assertEqual(d.usage["prompt_tokens"], 10)

    def test_usage_delta_is_frozen(self):
        d = UsageDelta(usage={"prompt_tokens": 10})
        with self.assertRaises(FrozenInstanceError):
            d.usage = {}  # type: ignore[misc]

    def test_finish_delta_construction(self):
        d = FinishDelta(finish_reason="stop")
        self.assertEqual(d.finish_reason, "stop")

    def test_finish_delta_is_frozen(self):
        d = FinishDelta(finish_reason="stop")
        with self.assertRaises(FrozenInstanceError):
            d.finish_reason = "length"  # type: ignore[misc]

    def test_stream_delta_is_union_of_5_types(self):
        """StreamDelta should accept all 5 delta types."""
        deltas: list[StreamDelta] = [
            ContentDelta(content="text"),
            ReasoningDelta(reasoning="thought"),
            ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
            UsageDelta(usage={"prompt_tokens": 1}),
            FinishDelta(finish_reason="stop"),
        ]
        self.assertEqual(len(deltas), 5)
        self.assertIsInstance(deltas[0], ContentDelta)
        self.assertIsInstance(deltas[1], ReasoningDelta)
        self.assertIsInstance(deltas[2], ToolCallDelta)
        self.assertIsInstance(deltas[3], UsageDelta)
        self.assertIsInstance(deltas[4], FinishDelta)

    def test_all_5_types_are_frozen_dataclasses(self):
        for cls in (ContentDelta, ReasoningDelta, ToolCallDelta, UsageDelta, FinishDelta):
            self.assertTrue(is_dataclass(cls), f"{cls.__name__} is not a dataclass")
            field_names = {f.name for f in fields(cls)}
            # Verify frozen by checking the dataclass __dataclass_params__
            self.assertTrue(
                cls.__dataclass_params__.frozen,  # type: ignore[attr-defined]
                f"{cls.__name__} is not frozen",
            )


class TestChatRequest(unittest.TestCase):
    """ChatRequest is a frozen dataclass with stream=True default."""

    def test_default_stream_is_true(self):
        req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        self.assertTrue(req.stream)

    def test_construction_with_all_fields(self):
        req = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "search"}}],
            model="gpt-4o",
            max_tokens=4096,
            temperature=0.7,
            stream=True,
        )
        self.assertEqual(req.model, "gpt-4o")
        self.assertEqual(req.max_tokens, 4096)
        self.assertEqual(req.temperature, 0.7)
        self.assertEqual(len(req.tools), 1)

    def test_optional_fields_default_none(self):
        req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        self.assertIsNone(req.tools)
        self.assertIsNone(req.model)
        self.assertIsNone(req.max_tokens)
        self.assertIsNone(req.temperature)

    def test_is_frozen(self):
        req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        with self.assertRaises(FrozenInstanceError):
            req.stream = False  # type: ignore[misc]

    def test_is_dataclass(self):
        self.assertTrue(is_dataclass(ChatRequest))


class TestUsageAccumulator(unittest.TestCase):
    """UsageAccumulator correctly sums tokens from multiple UsageDelta events."""

    def test_empty_accumulator(self):
        acc = UsageAccumulator()
        self.assertEqual(acc.prompt_tokens, 0)
        self.assertEqual(acc.completion_tokens, 0)
        self.assertEqual(acc.total_tokens, 0)
        self.assertEqual(acc.to_dict(), {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        })

    def test_single_usage_delta(self):
        acc = UsageAccumulator()
        acc.add(UsageDelta(usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }))
        self.assertEqual(acc.prompt_tokens, 100)
        self.assertEqual(acc.completion_tokens, 50)
        self.assertEqual(acc.total_tokens, 150)

    def test_multiple_usage_deltas_summed(self):
        acc = UsageAccumulator()
        acc.add(UsageDelta(usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }))
        acc.add(UsageDelta(usage={
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "total_tokens": 300,
        }))
        self.assertEqual(acc.prompt_tokens, 300)
        self.assertEqual(acc.completion_tokens, 150)
        self.assertEqual(acc.total_tokens, 450)

    def test_anthropic_style_keys(self):
        """UsageAccumulator handles Anthropic-style key names."""
        acc = UsageAccumulator()
        acc.add(UsageDelta(usage={
            "input_tokens": 100,
            "output_tokens": 50,
        }))
        self.assertEqual(acc.prompt_tokens, 100)
        self.assertEqual(acc.completion_tokens, 50)

    def test_to_dict(self):
        acc = UsageAccumulator()
        acc.add(UsageDelta(usage={
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }))
        d = acc.to_dict()
        self.assertEqual(d["prompt_tokens"], 10)
        self.assertEqual(d["completion_tokens"], 20)
        self.assertEqual(d["total_tokens"], 30)

    def test_non_dict_usage_ignored(self):
        acc = UsageAccumulator()
        acc.add(UsageDelta(usage="not a dict"))  # type: ignore[arg-type]
        self.assertEqual(acc.prompt_tokens, 0)

    def test_missing_keys_handled(self):
        acc = UsageAccumulator()
        acc.add(UsageDelta(usage={}))
        self.assertEqual(acc.prompt_tokens, 0)
        self.assertEqual(acc.completion_tokens, 0)
        self.assertEqual(acc.total_tokens, 0)


class TestLlmProviderProtocol(unittest.TestCase):
    """LlmProvider Protocol has chat_stream(), model_name(), supports_tools()."""

    def test_protocol_is_runtime_checkable(self):
        self.assertTrue(hasattr(LlmProvider, "_is_runtime_protocol"))

    def test_protocol_has_chat_stream(self):
        self.assertTrue(hasattr(LlmProvider, "chat_stream"))

    def test_protocol_has_model_name(self):
        self.assertTrue(hasattr(LlmProvider, "model_name"))

    def test_protocol_has_supports_tools(self):
        self.assertTrue(hasattr(LlmProvider, "supports_tools"))

    def test_class_implementing_protocol_is_recognized(self):
        """A class implementing all three methods should be recognized as LlmProvider."""

        class FakeProvider:
            async def chat_stream(self, request: ChatRequest):
                yield ContentDelta(content="test")

            def model_name(self) -> str:
                return "fake"

            def supports_tools(self) -> bool:
                return True

        provider = FakeProvider()
        self.assertIsInstance(provider, LlmProvider)


if __name__ == "__main__":
    unittest.main()
