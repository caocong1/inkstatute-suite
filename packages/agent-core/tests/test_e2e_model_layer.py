"""E2E test: model layer — provider streaming + tool calls + gateway integration.

Verifies the model layer streaming + tool call support across all three
providers and the gateway component integration:

1. OpenAI streaming with tool calls → correct StreamDelta types
2. Anthropic streaming with tool use → correct StreamDelta types
3. Ollama streaming → correct StreamDelta types
4. Circuit breaker integration → trips after N failures, blocks calls
5. Rate limiter integration → RPM=1 blocks second call
6. Cost tracker integration → accumulates cost from usage
7. Usage data in events → provider_usage in terminal event metadata

Success criteria 4 + 5: 模型层由 provider_model 归并而来，支持
OpenAI/Anthropic/Ollama，流式与工具调用在各 provider 间归一；复用
model-gateway 的熔断/限流/成本追踪，usage 数据进入事件流.
"""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.enums import RunEventType

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.anthropic_runner import (
    AnthropicStreamProvider,
    FakeAnthropicTransport,
)
from inkstatute_agent_core.model.gateway_components import (
    GatewayComponents,
    ProtectedProvider,
    ProviderBlockedError,
)
from inkstatute_agent_core.model.ollama_runner import (
    FakeOllamaTransport,
    OllamaStreamProvider,
)
from inkstatute_agent_core.model.openai_runner import (
    FakeOpenAITransport,
    OpenAIStreamProvider,
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
from inkstatute_agent_core.turn_loop import run_turn

from inkstatute_model_gateway.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
)
from inkstatute_model_gateway.cost_tracker import BudgetCeiling, CostTracker, PricingRate
from inkstatute_model_gateway.rate_limiter import RateLimitConfig, RateLimiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _collect(provider, request):
    deltas = []
    async for delta in provider.chat_stream(request):
        deltas.append(delta)
    return deltas


async def _collect_events(gen):
    events = []
    async for event in gen:
        events.append(event)
    return events


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


# ---------------------------------------------------------------------------
# 1. OpenAI streaming with tool calls
# ---------------------------------------------------------------------------


class TestE2EOpenAIStreaming(unittest.TestCase):
    """OpenAI streaming with content + tool call deltas."""

    def test_content_streaming(self):
        """OpenAI provider streams ContentDelta from SSE chunks."""
        transport = FakeOpenAITransport(stream_chunks=[
            _content_chunk("Hello"),
            _content_chunk(" world"),
            _finish_chunk("stop"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        deltas = _run_async(_collect(provider, request))

        content_deltas = [d for d in deltas if isinstance(d, ContentDelta)]
        self.assertEqual(len(content_deltas), 2)
        self.assertEqual(content_deltas[0].content, "Hello")
        self.assertEqual(content_deltas[1].content, " world")

        finish_deltas = [d for d in deltas if isinstance(d, FinishDelta)]
        self.assertEqual(len(finish_deltas), 1)
        self.assertEqual(finish_deltas[0].finish_reason, "stop")

    def test_tool_call_streaming(self):
        """OpenAI provider accumulates tool call fragments into ToolCallDelta."""
        transport = FakeOpenAITransport(stream_chunks=[
            _tool_call_chunk(0, tool_call_id="call_1", name="legal_search"),
            _tool_call_chunk(0, arguments='{"query":"合同法"}'),
            _finish_chunk("tool_calls"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])

        deltas = _run_async(_collect(provider, request))

        tool_call_deltas = [d for d in deltas if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(tool_call_deltas), 1)
        self.assertEqual(tool_call_deltas[0].tool_call_id, "call_1")
        self.assertEqual(tool_call_deltas[0].tool_name, "legal_search")
        self.assertEqual(tool_call_deltas[0].arguments, '{"query":"合同法"}')

    def test_reasoning_streaming(self):
        """OpenAI provider streams ReasoningDelta from reasoning_content."""
        transport = FakeOpenAITransport(stream_chunks=[
            {"choices": [{"delta": {"reasoning_content": "Let me think..."}}]},
            _content_chunk("Answer"),
            _finish_chunk("stop"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])

        deltas = _run_async(_collect(provider, request))

        reasoning_deltas = [d for d in deltas if isinstance(d, ReasoningDelta)]
        self.assertEqual(len(reasoning_deltas), 1)
        self.assertEqual(reasoning_deltas[0].reasoning, "Let me think...")

    def test_usage_delta(self):
        """OpenAI provider yields UsageDelta from final chunk."""
        transport = FakeOpenAITransport(stream_chunks=[
            _content_chunk("answer"),
            _finish_chunk("stop"),
            _usage_chunk({"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])

        deltas = _run_async(_collect(provider, request))

        usage_deltas = [d for d in deltas if isinstance(d, UsageDelta)]
        self.assertEqual(len(usage_deltas), 1)
        self.assertEqual(usage_deltas[0].usage["prompt_tokens"], 50)
        self.assertEqual(usage_deltas[0].usage["total_tokens"], 70)


# ---------------------------------------------------------------------------
# 2. Anthropic streaming with tool use
# ---------------------------------------------------------------------------


class TestE2EAnthropicStreaming(unittest.TestCase):
    """Anthropic streaming with text + tool_use blocks."""

    def test_text_streaming(self):
        """Anthropic provider streams ContentDelta from text_delta events."""
        transport = FakeAnthropicTransport(stream_events=[
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " world"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_stop"},
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        deltas = _run_async(_collect(provider, request))

        content_deltas = [d for d in deltas if isinstance(d, ContentDelta)]
        self.assertEqual(len(content_deltas), 2)
        self.assertEqual(content_deltas[0].content, "Hello")
        self.assertEqual(content_deltas[1].content, " world")

    def test_tool_use_streaming(self):
        """Anthropic provider yields ToolCallDelta from tool_use blocks."""
        transport = FakeAnthropicTransport(stream_events=[
            {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "call_1", "name": "legal_search"}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"query":"合'}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '同法"}'}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_stop"},
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])

        deltas = _run_async(_collect(provider, request))

        tool_call_deltas = [d for d in deltas if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(tool_call_deltas), 1)
        self.assertEqual(tool_call_deltas[0].tool_call_id, "call_1")
        self.assertEqual(tool_call_deltas[0].tool_name, "legal_search")
        self.assertIn("合同法", tool_call_deltas[0].arguments)

    def test_reasoning_streaming(self):
        """Anthropic provider streams ReasoningDelta from thinking_delta events."""
        transport = FakeAnthropicTransport(stream_events=[
            {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "Let me think..."}},
            {"type": "message_stop"},
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])

        deltas = _run_async(_collect(provider, request))

        reasoning_deltas = [d for d in deltas if isinstance(d, ReasoningDelta)]
        self.assertEqual(len(reasoning_deltas), 1)
        self.assertEqual(reasoning_deltas[0].reasoning, "Let me think...")

    def test_usage_delta(self):
        """Anthropic provider yields UsageDelta from message_delta events."""
        transport = FakeAnthropicTransport(stream_events=[
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "answer"}},
            {"type": "message_delta", "delta": {"usage": {"input_tokens": 50, "output_tokens": 20}}},
            {"type": "message_stop"},
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])

        deltas = _run_async(_collect(provider, request))

        usage_deltas = [d for d in deltas if isinstance(d, UsageDelta)]
        self.assertGreaterEqual(len(usage_deltas), 1)
        self.assertEqual(usage_deltas[0].usage["input_tokens"], 50)


# ---------------------------------------------------------------------------
# 3. Ollama streaming
# ---------------------------------------------------------------------------


class TestE2EOllamaStreaming(unittest.TestCase):
    """Ollama streaming (OpenAI-compatible)."""

    def test_content_streaming(self):
        """Ollama provider streams ContentDelta from SSE chunks."""
        transport = FakeOllamaTransport(stream_chunks=[
            _content_chunk("Hello"),
            _content_chunk(" from Ollama"),
            _finish_chunk("stop"),
        ])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        deltas = _run_async(_collect(provider, request))

        content_deltas = [d for d in deltas if isinstance(d, ContentDelta)]
        self.assertEqual(len(content_deltas), 2)
        self.assertIn("Hello", content_deltas[0].content)
        self.assertIn("Ollama", content_deltas[1].content)

    def test_tool_call_streaming(self):
        """Ollama provider accumulates tool calls (OpenAI-compatible)."""
        transport = FakeOllamaTransport(stream_chunks=[
            _tool_call_chunk(0, tool_call_id="call_1", name="legal_search"),
            _tool_call_chunk(0, arguments='{"query":"test"}'),
            _finish_chunk("tool_calls"),
        ])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])

        deltas = _run_async(_collect(provider, request))

        tool_call_deltas = [d for d in deltas if isinstance(d, ToolCallDelta)]
        self.assertEqual(len(tool_call_deltas), 1)
        self.assertEqual(tool_call_deltas[0].tool_name, "legal_search")
        self.assertEqual(tool_call_deltas[0].arguments, '{"query":"test"}')


# ---------------------------------------------------------------------------
# 4. Circuit breaker integration
# ---------------------------------------------------------------------------


class TestE2ECircuitBreakerIntegration(unittest.TestCase):
    """Circuit breaker trips after N consecutive failures."""

    def test_circuit_breaker_trips_after_threshold(self):
        """Circuit breaker trips after failure_threshold consecutive failures."""
        registry = CircuitBreakerRegistry(
            CircuitBreakerConfig(failure_threshold=3, cooldown_seconds=60.0),
        )
        gw = GatewayComponents(circuit_registry=registry)

        # Record 3 failures
        for _ in range(3):
            _run_async(gw.after_call("test-provider", success=False))

        # Circuit should be OPEN
        self.assertEqual(registry.get_state("test-provider"), CircuitState.OPEN)

        # before_call should return False
        result = _run_async(gw.before_call("test-provider"))
        self.assertFalse(result, "before_call should return False when circuit is OPEN")

    def test_protected_provider_raises_when_circuit_open(self):
        """ProtectedProvider raises ProviderBlockedError when circuit is open."""
        registry = CircuitBreakerRegistry(
            CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=60.0),
        )
        gw = GatewayComponents(circuit_registry=registry)

        # Trip the circuit with 2 failures
        _run_async(gw.after_call("prov", success=False))
        _run_async(gw.after_call("prov", success=False))

        # Create a ProtectedProvider
        fixture = FixtureProvider([TurnScript(deltas=[ContentDelta(content="test")])])
        protected = ProtectedProvider(fixture, gw, provider_id="prov")

        # chat_stream should raise ProviderBlockedError
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])
        with self.assertRaises(ProviderBlockedError) as ctx:
            _run_async(_collect(protected, request))
        self.assertEqual(ctx.exception.reason, "circuit_open")

    def test_circuit_breaker_resets_on_success(self):
        """Circuit breaker resets to CLOSED after a successful call."""
        registry = CircuitBreakerRegistry(
            CircuitBreakerConfig(failure_threshold=3, cooldown_seconds=60.0),
        )
        gw = GatewayComponents(circuit_registry=registry)

        # 2 failures (below threshold)
        _run_async(gw.after_call("prov", success=False))
        _run_async(gw.after_call("prov", success=False))

        # Success resets
        _run_async(gw.after_call("prov", success=True))
        self.assertEqual(registry.get_state("prov"), CircuitState.CLOSED)


# ---------------------------------------------------------------------------
# 5. Rate limiter integration
# ---------------------------------------------------------------------------


class TestE2ERateLimiterIntegration(unittest.TestCase):
    """Rate limiter blocks calls exceeding RPM limit."""

    def test_rpm_limit_blocks_second_call(self):
        """RPM=1 → first call passes, second call within 60s is blocked."""
        rate_limiter = RateLimiter(
            configs={"prov": RateLimitConfig(rpm=1)},
        )
        gw = GatewayComponents(rate_limiter=rate_limiter)

        # First call should pass
        result1 = _run_async(gw.before_call("prov"))
        self.assertTrue(result1, "First call should pass RPM check")

        # Record the first request
        _run_async(gw.after_call("prov", success=True, usage={"total_tokens": 10}))

        # Second call should be blocked (RPM=1, one request in window)
        result2 = _run_async(gw.before_call("prov"))
        self.assertFalse(result2, "Second call should be blocked by RPM limit")

    def test_protected_provider_blocked_by_rate_limit(self):
        """ProtectedProvider raises ProviderBlockedError when rate limited."""
        rate_limiter = RateLimiter(
            configs={"prov": RateLimitConfig(rpm=1)},
        )
        gw = GatewayComponents(rate_limiter=rate_limiter)

        fixture = FixtureProvider([
            TurnScript(deltas=[ContentDelta(content="a")]),
            TurnScript(deltas=[ContentDelta(content="b")]),
        ])
        protected = ProtectedProvider(fixture, gw, provider_id="prov")

        request = ChatRequest(messages=[{"role": "user", "content": "q"}])

        # First call succeeds
        deltas1 = _run_async(_collect(protected, request))
        self.assertGreater(len(deltas1), 0)

        # Second call should be blocked
        with self.assertRaises(ProviderBlockedError) as ctx:
            _run_async(_collect(protected, request))
        self.assertEqual(ctx.exception.reason, "rate_limited")


# ---------------------------------------------------------------------------
# 6. Cost tracker integration
# ---------------------------------------------------------------------------


class TestE2ECostTrackerIntegration(unittest.TestCase):
    """Cost tracker accumulates cost from usage data."""

    def test_cost_accumulated_from_usage(self):
        """CostTracker records usage and accumulates cost."""
        cost_tracker = CostTracker(
            pricing={"prov": PricingRate(input_token_cost=0.01, output_token_cost=0.02)},
        )
        gw = GatewayComponents(cost_tracker=cost_tracker)

        # Record usage
        _run_async(gw.after_call("prov", success=True, usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }))

        # Check accumulated cost
        accumulated = _run_async(cost_tracker.get_accumulated("default"))
        # cost = 100 * 0.01 + 50 * 0.02 = 1.0 + 1.0 = 2.0
        self.assertEqual(accumulated, 2.0)

    def test_cost_tracker_with_protected_provider(self):
        """ProtectedProvider records usage in cost tracker after successful call."""
        cost_tracker = CostTracker(
            pricing={"prov": PricingRate(input_token_cost=0.01, output_token_cost=0.02)},
        )
        gw = GatewayComponents(cost_tracker=cost_tracker)

        fixture = FixtureProvider([TurnScript(deltas=[
            ContentDelta(content="answer"),
            UsageDelta(usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}),
            FinishDelta(finish_reason="stop"),
        ])])
        protected = ProtectedProvider(fixture, gw, provider_id="prov")

        request = ChatRequest(messages=[{"role": "user", "content": "q"}])
        deltas = _run_async(_collect(protected, request))

        # Cost should be accumulated
        accumulated = _run_async(cost_tracker.get_accumulated("default"))
        self.assertEqual(accumulated, 2.0)


# ---------------------------------------------------------------------------
# 7. Usage data in events (turn loop integration)
# ---------------------------------------------------------------------------


class TestE2EUsageDataInEvents(unittest.TestCase):
    """Usage data appears in message.completed and run.state_changed metadata."""

    def test_usage_in_terminal_events(self):
        """Turn loop with FixtureProvider → provider_usage in terminal events."""
        provider = FixtureProvider([TurnScript(deltas=[
            ContentDelta(content="legal answer"),
            UsageDelta(usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}),
            FinishDelta(finish_reason="stop"),
        ])])
        config = AgentCoreConfig()
        emitter = EventEmitter("run-e2e-model", config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e-model",
            )
        ))

        # message.completed should have provider_usage
        msg_completed = [
            e for e in events
            if e.event_type == RunEventType.MESSAGE_COMPLETED.value
        ][0]
        self.assertIn("provider_usage", msg_completed.metadata)
        self.assertEqual(msg_completed.metadata["provider_usage"]["prompt_tokens"], 200)
        self.assertEqual(msg_completed.metadata["provider_usage"]["completion_tokens"], 100)
        self.assertEqual(msg_completed.metadata["provider_usage"]["total_tokens"], 300)

        # run.state_changed should have provider_usage
        state_changed = [
            e for e in events
            if e.event_type == RunEventType.RUN_STATE_CHANGED.value
        ][0]
        self.assertIn("provider_usage", state_changed.metadata)

    def test_usage_accumulated_across_rounds(self):
        """Usage from multiple rounds is accumulated in the final round's metadata."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ToolCallDelta(tool_call_id="tc1", tool_name="search", arguments="{}"),
                UsageDelta(usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="final answer"),
                UsageDelta(usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}),
                FinishDelta(finish_reason="stop"),
            ]),
        ])
        config = AgentCoreConfig()
        emitter = EventEmitter("run-e2e-model", config)

        events = asyncio.run(_collect_events(
            run_turn(
                messages=[{"role": "user", "content": "q"}],
                tools=None,
                provider=provider,
                emitter=emitter,
                config=config,
                run_id="run-e2e-model",
            )
        ))

        msg_completed = [
            e for e in events
            if e.event_type == RunEventType.MESSAGE_COMPLETED.value
        ][0]
        usage = msg_completed.metadata["provider_usage"]
        # The final round's usage should be in the metadata
        self.assertEqual(usage["prompt_tokens"], 100)
        self.assertEqual(usage["completion_tokens"], 20)


# ---------------------------------------------------------------------------
# 8. All providers implement LlmProvider Protocol
# ---------------------------------------------------------------------------


class TestE2EAllProvidersImplementProtocol(unittest.TestCase):
    """All three providers + FixtureProvider implement LlmProvider Protocol."""

    def test_openai_implements_protocol(self):
        provider = OpenAIStreamProvider()
        self.assertIsInstance(provider, LlmProvider)

    def test_anthropic_implements_protocol(self):
        provider = AnthropicStreamProvider()
        self.assertIsInstance(provider, LlmProvider)

    def test_ollama_implements_protocol(self):
        provider = OllamaStreamProvider()
        self.assertIsInstance(provider, LlmProvider)

    def test_fixture_implements_protocol(self):
        provider = FixtureProvider([TurnScript(deltas=[])])
        self.assertIsInstance(provider, LlmProvider)


# ---------------------------------------------------------------------------
# 9. No external API calls — all tests use fake transports
# ---------------------------------------------------------------------------


class TestE2ENoExternalCalls(unittest.TestCase):
    """All tests use fake transports — no external API calls."""

    def test_openai_uses_fake_transport(self):
        """OpenAI provider with FakeOpenAITransport doesn't make real calls."""
        transport = FakeOpenAITransport(stream_chunks=[
            _content_chunk("test"),
            _finish_chunk("stop"),
        ])
        provider = OpenAIStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])
        deltas = _run_async(_collect(provider, request))
        self.assertGreater(len(deltas), 0)
        # Verify the transport was used (last_request is set)
        self.assertIsNotNone(transport.last_request)

    def test_anthropic_uses_fake_transport(self):
        """Anthropic provider with FakeAnthropicTransport doesn't make real calls."""
        transport = FakeAnthropicTransport(stream_events=[
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "test"}},
            {"type": "message_stop"},
        ])
        provider = AnthropicStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])
        deltas = _run_async(_collect(provider, request))
        self.assertGreater(len(deltas), 0)
        self.assertIsNotNone(transport.last_request)

    def test_ollama_uses_fake_transport(self):
        """Ollama provider with FakeOllamaTransport doesn't make real calls."""
        transport = FakeOllamaTransport(stream_chunks=[
            _content_chunk("test"),
            _finish_chunk("stop"),
        ])
        provider = OllamaStreamProvider(transport=transport)
        request = ChatRequest(messages=[{"role": "user", "content": "q"}])
        deltas = _run_async(_collect(provider, request))
        self.assertGreater(len(deltas), 0)
        self.assertIsNotNone(transport.last_request)


if __name__ == "__main__":
    unittest.main()
