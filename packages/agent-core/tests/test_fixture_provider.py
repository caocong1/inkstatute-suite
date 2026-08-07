"""Tests for FixtureProvider with TurnScript."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import FrozenInstanceError, is_dataclass

from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
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
    """Helper to run an async coroutine in tests."""
    return asyncio.new_event_loop().run_until_complete(coro)


async def _collect_deltas(provider: FixtureProvider, request: ChatRequest):
    """Collect all deltas from a provider's chat_stream."""
    deltas = []
    async for delta in provider.chat_stream(request):
        deltas.append(delta)
    return deltas


class TestTurnScript(unittest.TestCase):
    """TurnScript is a frozen dataclass."""

    def test_default_construction(self):
        ts = TurnScript()
        self.assertEqual(ts.deltas, [])
        self.assertEqual(ts.delay_seconds, 0.0)
        self.assertIsNone(ts.error)

    def test_construction_with_deltas(self):
        deltas = [ContentDelta(content="hello"), FinishDelta(finish_reason="stop")]
        ts = TurnScript(deltas=deltas)
        self.assertEqual(len(ts.deltas), 2)

    def test_construction_with_delay(self):
        ts = TurnScript(delay_seconds=0.1)
        self.assertEqual(ts.delay_seconds, 0.1)

    def test_construction_with_error(self):
        err = ValueError("test error")
        ts = TurnScript(error=err)
        self.assertIs(ts.error, err)

    def test_is_frozen(self):
        ts = TurnScript()
        with self.assertRaises(FrozenInstanceError):
            ts.delay_seconds = 1.0  # type: ignore[misc]

    def test_is_dataclass(self):
        self.assertTrue(is_dataclass(TurnScript))


class TestFixtureProviderProtocol(unittest.TestCase):
    """FixtureProvider implements LlmProvider Protocol."""

    def test_implements_protocol(self):
        provider = FixtureProvider(script=[TurnScript()])
        self.assertIsInstance(provider, LlmProvider)

    def test_model_name_default(self):
        provider = FixtureProvider(script=[TurnScript()])
        self.assertEqual(provider.model_name(), "fixture")

    def test_model_name_custom(self):
        provider = FixtureProvider(script=[TurnScript()], model_name="custom-model")
        self.assertEqual(provider.model_name(), "custom-model")

    def test_supports_tools_default_true(self):
        provider = FixtureProvider(script=[TurnScript()])
        self.assertTrue(provider.supports_tools())

    def test_supports_tools_custom_false(self):
        provider = FixtureProvider(script=[TurnScript()], supports_tools=False)
        self.assertFalse(provider.supports_tools())


class TestSingleTurn(unittest.TestCase):
    """Single-turn scripts work correctly."""

    def test_single_content_turn(self):
        deltas = [
            ContentDelta(content="Hello"),
            ContentDelta(content=" world"),
            FinishDelta(finish_reason="stop"),
        ]
        provider = FixtureProvider(script=[TurnScript(deltas=deltas)])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect_deltas(provider, request))
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], ContentDelta)
        self.assertEqual(result[0].content, "Hello")
        self.assertIsInstance(result[2], FinishDelta)

    def test_call_count_increments(self):
        provider = FixtureProvider(script=[TurnScript(deltas=[ContentDelta(content="x")])])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(provider.call_count, 0)
        _run_async(_collect_deltas(provider, request))
        self.assertEqual(provider.call_count, 1)


class TestMultiTurn(unittest.TestCase):
    """Multi-turn scripts work: round 1 yields tool calls, round 2 yields content."""

    def test_multi_turn_tool_then_content(self):
        round1 = TurnScript(deltas=[
            ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments='{"q": "law"}'),
            FinishDelta(finish_reason="tool_calls"),
        ])
        round2 = TurnScript(deltas=[
            ContentDelta(content="Based on the search results..."),
            FinishDelta(finish_reason="stop"),
        ])
        provider = FixtureProvider(script=[round1, round2])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        # Round 1
        result1 = _run_async(_collect_deltas(provider, request))
        self.assertEqual(len(result1), 2)
        self.assertIsInstance(result1[0], ToolCallDelta)
        self.assertEqual(result1[0].tool_name, "search")

        # Round 2
        result2 = _run_async(_collect_deltas(provider, request))
        self.assertEqual(len(result2), 2)
        self.assertIsInstance(result2[0], ContentDelta)
        self.assertEqual(result2[0].content, "Based on the search results...")

        self.assertEqual(provider.call_count, 2)

    def test_three_turns(self):
        scripts = [
            TurnScript(deltas=[ContentDelta(content="turn 0")]),
            TurnScript(deltas=[ContentDelta(content="turn 1")]),
            TurnScript(deltas=[ContentDelta(content="turn 2")]),
        ]
        provider = FixtureProvider(script=scripts)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        for i in range(3):
            result = _run_async(_collect_deltas(provider, request))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].content, f"turn {i}")

        self.assertEqual(provider.call_count, 3)


class TestErrorInjection(unittest.TestCase):
    """TurnScript.error causes the provider to raise during streaming."""

    def test_error_raised_during_streaming(self):
        err = RuntimeError("API error")
        provider = FixtureProvider(script=[TurnScript(error=err)])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(RuntimeError) as ctx:
            _run_async(_collect_deltas(provider, request))
        self.assertIn("API error", str(ctx.exception))

    def test_error_increments_call_count(self):
        err = ValueError("fail")
        provider = FixtureProvider(script=[TurnScript(error=err)])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(ValueError):
            _run_async(_collect_deltas(provider, request))
        self.assertEqual(provider.call_count, 1)

    def test_error_after_successful_turn(self):
        provider = FixtureProvider(script=[
            TurnScript(deltas=[ContentDelta(content="ok"), FinishDelta(finish_reason="stop")]),
            TurnScript(error=ConnectionError("network down")),
        ])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        # First turn succeeds
        result = _run_async(_collect_deltas(provider, request))
        self.assertEqual(len(result), 2)

        # Second turn raises
        with self.assertRaises(ConnectionError):
            _run_async(_collect_deltas(provider, request))


class TestDelay(unittest.TestCase):
    """delay_seconds causes asyncio.sleep between delta yields."""

    def test_delay_between_deltas(self):
        deltas = [
            ContentDelta(content="a"),
            ContentDelta(content="b"),
        ]
        provider = FixtureProvider(script=[TurnScript(deltas=deltas, delay_seconds=0.05)])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        import time
        start = time.monotonic()
        result = _run_async(_collect_deltas(provider, request))
        elapsed = time.monotonic() - start

        self.assertEqual(len(result), 2)
        # 2 deltas with 0.05s delay each = ~0.10s minimum
        self.assertGreaterEqual(elapsed, 0.08)

    def test_zero_delay_no_sleep(self):
        deltas = [ContentDelta(content="a")]
        provider = FixtureProvider(script=[TurnScript(deltas=deltas, delay_seconds=0.0)])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        import time
        start = time.monotonic()
        result = _run_async(_collect_deltas(provider, request))
        elapsed = time.monotonic() - start

        self.assertEqual(len(result), 1)
        self.assertLess(elapsed, 0.1)


class TestScriptExhaustion(unittest.TestCase):
    """Script exhaustion raises RuntimeError with clear message."""

    def test_exhausted_script_raises(self):
        provider = FixtureProvider(script=[TurnScript(deltas=[ContentDelta(content="x")])])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        # First call succeeds
        _run_async(_collect_deltas(provider, request))

        # Second call raises
        with self.assertRaises(RuntimeError) as ctx:
            _run_async(_collect_deltas(provider, request))
        self.assertIn("fixture script exhausted", str(ctx.exception))

    def test_empty_script_raises_immediately(self):
        provider = FixtureProvider(script=[])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(RuntimeError) as ctx:
            _run_async(_collect_deltas(provider, request))
        self.assertIn("fixture script exhausted", str(ctx.exception))


class TestComplexScenarios(unittest.TestCase):
    """Complex multi-turn scenarios with mixed delta types."""

    def test_mixed_delta_types_in_single_turn(self):
        deltas = [
            ReasoningDelta(reasoning="Let me think..."),
            ContentDelta(content="Here is the answer"),
            UsageDelta(usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}),
            FinishDelta(finish_reason="stop"),
        ]
        provider = FixtureProvider(script=[TurnScript(deltas=deltas)])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = _run_async(_collect_deltas(provider, request))

        self.assertEqual(len(result), 4)
        self.assertIsInstance(result[0], ReasoningDelta)
        self.assertIsInstance(result[1], ContentDelta)
        self.assertIsInstance(result[2], UsageDelta)
        self.assertIsInstance(result[3], FinishDelta)

    def test_remaining_scripts_property(self):
        provider = FixtureProvider(script=[
            TurnScript(deltas=[ContentDelta(content="a")]),
            TurnScript(deltas=[ContentDelta(content="b")]),
        ])
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        self.assertEqual(provider.remaining_scripts, 2)
        _run_async(_collect_deltas(provider, request))
        self.assertEqual(provider.remaining_scripts, 1)
        _run_async(_collect_deltas(provider, request))
        self.assertEqual(provider.remaining_scripts, 0)


if __name__ == "__main__":
    unittest.main()
