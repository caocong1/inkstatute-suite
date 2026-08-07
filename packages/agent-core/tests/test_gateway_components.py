"""Tests for GatewayComponents and ProtectedProvider."""

from __future__ import annotations

import asyncio
import unittest
from typing import Callable

from inkstatute_model_gateway.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
)
from inkstatute_model_gateway.cost_tracker import BudgetCeiling, CostTracker, PricingRate
from inkstatute_model_gateway.rate_limiter import RateLimitConfig, RateLimiter

from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.gateway_components import (
    GatewayComponents,
    ProtectedProvider,
    ProviderBlockedError,
)
from inkstatute_agent_core.model.provider import (
    ChatRequest,
    ContentDelta,
    FinishDelta,
    LlmProvider,
    UsageDelta,
)


def _run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _collect(provider, request):
    deltas = []
    async for delta in provider.chat_stream(request):
        deltas.append(delta)
    return deltas


class TestGatewayComponentsPassthrough(unittest.TestCase):
    """Default (no config) mode is pass-through — all checks pass."""

    def test_default_before_call_returns_true(self):
        gw = GatewayComponents()
        result = _run_async(gw.before_call("test-provider"))
        self.assertTrue(result)

    def test_default_after_call_succeeds(self):
        gw = GatewayComponents()
        _run_async(gw.after_call("test-provider", success=True, usage={"prompt_tokens": 10}))

    def test_default_usage_summary_empty(self):
        gw = GatewayComponents()
        self.assertEqual(gw.get_usage_summary(), {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        })

    def test_imports_from_model_gateway(self):
        """GatewayComponents imports CircuitBreakerRegistry, RateLimiter, CostTracker."""
        from inkstatute_agent_core.model.gateway_components import (
            CircuitBreakerRegistry,
            CostTracker,
            RateLimiter,
        )
        # Just verify they're accessible
        self.assertTrue(hasattr(CircuitBreakerRegistry, "can_execute"))
        self.assertTrue(hasattr(RateLimiter, "check_rpm"))
        self.assertTrue(hasattr(CostTracker, "record_usage"))


class TestCircuitBreakerIntegration(unittest.TestCase):
    """Circuit breaker open/closed behavior."""

    def test_before_call_false_when_circuit_open(self):
        # Create a registry with low threshold
        registry = CircuitBreakerRegistry(
            CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=60.0),
        )
        gw = GatewayComponents(circuit_registry=registry)

        # Record a failure to trip the breaker
        registry.record_failure("test-provider")

        result = _run_async(gw.before_call("test-provider"))
        self.assertFalse(result)

    def test_before_call_true_when_circuit_closed(self):
        registry = CircuitBreakerRegistry()
        gw = GatewayComponents(circuit_registry=registry)

        result = _run_async(gw.before_call("test-provider"))
        self.assertTrue(result)

    def test_after_call_records_success(self):
        registry = CircuitBreakerRegistry(
            CircuitBreakerConfig(failure_threshold=2),
        )
        gw = GatewayComponents(circuit_registry=registry)

        # Record a failure first
        registry.record_failure("test-provider")
        self.assertEqual(registry.get_state("test-provider"), CircuitState.CLOSED)

        # Record success — should reset failure count
        _run_async(gw.after_call("test-provider", success=True))
        breaker = registry.get_or_create("test-provider")
        self.assertEqual(breaker.consecutive_failures, 0)

    def test_after_call_records_failure(self):
        registry = CircuitBreakerRegistry(
            CircuitBreakerConfig(failure_threshold=3),
        )
        gw = GatewayComponents(circuit_registry=registry)

        _run_async(gw.after_call("test-provider", success=False))
        breaker = registry.get_or_create("test-provider")
        self.assertEqual(breaker.consecutive_failures, 1)


class TestRateLimiterIntegration(unittest.TestCase):
    """Rate limit (RPM) exceeded behavior."""

    def test_before_call_false_when_rate_limited(self):
        # Create a rate limiter with RPM=1
        limiter = RateLimiter(
            configs={"test-provider": RateLimitConfig(rpm=1)},
        )
        gw = GatewayComponents(rate_limiter=limiter)

        # First call should pass
        result1 = _run_async(gw.before_call("test-provider"))
        self.assertTrue(result1)

        # Record the request to fill the window
        _run_async(limiter.record_request("default", "test-provider"))

        # Second call should be rate limited
        result2 = _run_async(gw.before_call("test-provider"))
        self.assertFalse(result2)

    def test_before_call_true_when_no_rate_limit_config(self):
        limiter = RateLimiter()
        gw = GatewayComponents(rate_limiter=limiter)

        result = _run_async(gw.before_call("test-provider"))
        self.assertTrue(result)


class TestCostTrackerIntegration(unittest.TestCase):
    """Cost tracking with usage data."""

    def test_after_call_records_usage(self):
        tracker = CostTracker(
            pricing={"test-provider": PricingRate(input_token_cost=0.01, output_token_cost=0.02)},
        )
        gw = GatewayComponents(cost_tracker=tracker)

        usage = {"prompt_tokens": 100, "completion_tokens": 50}
        _run_async(gw.after_call("test-provider", success=True, usage=usage))

        accumulated = _run_async(tracker.get_accumulated("default"))
        # 100 * 0.01 + 50 * 0.02 = 1.0 + 1.0 = 2.0
        self.assertEqual(accumulated, 2.0)

    def test_usage_summary_accumulated(self):
        gw = GatewayComponents()
        _run_async(gw.after_call("test-provider", success=True, usage={
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }))
        summary = gw.get_usage_summary()
        self.assertEqual(summary["prompt_tokens"], 10)
        self.assertEqual(summary["completion_tokens"], 20)
        self.assertEqual(summary["total_tokens"], 30)

    def test_usage_summary_multiple_calls(self):
        gw = GatewayComponents()
        _run_async(gw.after_call("test-provider", success=True, usage={
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }))
        _run_async(gw.after_call("test-provider", success=True, usage={
            "prompt_tokens": 5,
            "completion_tokens": 15,
            "total_tokens": 20,
        }))
        summary = gw.get_usage_summary()
        self.assertEqual(summary["prompt_tokens"], 15)
        self.assertEqual(summary["completion_tokens"], 35)
        self.assertEqual(summary["total_tokens"], 50)


class TestProtectedProvider(unittest.TestCase):
    """ProtectedProvider wraps LlmProvider with gateway checks."""

    def test_implements_protocol(self):
        fixture = FixtureProvider(script=[TurnScript()])
        gw = GatewayComponents()
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        self.assertIsInstance(protected, LlmProvider)

    def test_delegates_model_name(self):
        fixture = FixtureProvider(script=[TurnScript()], model_name="test-model")
        gw = GatewayComponents()
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        self.assertEqual(protected.model_name(), "test-model")

    def test_delegates_supports_tools(self):
        fixture = FixtureProvider(script=[TurnScript()], supports_tools=False)
        gw = GatewayComponents()
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        self.assertFalse(protected.supports_tools())

    def test_passthrough_streaming(self):
        """In pass-through mode, streaming works normally."""
        fixture = FixtureProvider(script=[TurnScript(deltas=[
            ContentDelta(content="Hello"),
            FinishDelta(finish_reason="stop"),
        ])])
        gw = GatewayComponents()
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        result = _run_async(_collect(protected, request))
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], ContentDelta)

    def test_blocked_when_circuit_open(self):
        """When circuit breaker is OPEN, ProtectedProvider raises ProviderBlockedError."""
        registry = CircuitBreakerRegistry(
            CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=60.0),
        )
        registry.record_failure("test")
        gw = GatewayComponents(circuit_registry=registry)

        fixture = FixtureProvider(script=[TurnScript(deltas=[ContentDelta(content="x")])])
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(ProviderBlockedError) as ctx:
            _run_async(_collect(protected, request))
        self.assertEqual(ctx.exception.provider_id, "test")
        self.assertEqual(ctx.exception.reason, "circuit_open")

    def test_blocked_when_rate_limited(self):
        """When rate limit is exceeded, ProtectedProvider raises ProviderBlockedError."""
        limiter = RateLimiter(
            configs={"test": RateLimitConfig(rpm=1)},
        )
        gw = GatewayComponents(rate_limiter=limiter)

        # Fill the rate limit window
        _run_async(limiter.record_request("default", "test"))

        fixture = FixtureProvider(script=[TurnScript(deltas=[ContentDelta(content="x")])])
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(ProviderBlockedError) as ctx:
            _run_async(_collect(protected, request))
        self.assertEqual(ctx.exception.reason, "rate_limited")

    def test_usage_recorded_after_successful_stream(self):
        """After a successful stream, usage is recorded in cost tracker."""
        tracker = CostTracker(
            pricing={"test": PricingRate(input_token_cost=0.01, output_token_cost=0.01)},
        )
        gw = GatewayComponents(cost_tracker=tracker)

        fixture = FixtureProvider(script=[TurnScript(deltas=[
            ContentDelta(content="Hello"),
            UsageDelta(usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}),
            FinishDelta(finish_reason="stop"),
        ])])
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        _run_async(_collect(protected, request))

        accumulated = _run_async(tracker.get_accumulated("default"))
        # 10 * 0.01 + 20 * 0.01 = 0.1 + 0.2 = 0.3
        self.assertAlmostEqual(accumulated, 0.3, places=5)

    def test_failure_recorded_on_error(self):
        """When the wrapped provider raises, failure is recorded."""
        registry = CircuitBreakerRegistry(
            CircuitBreakerConfig(failure_threshold=3),
        )
        gw = GatewayComponents(circuit_registry=registry)

        fixture = FixtureProvider(script=[TurnScript(error=RuntimeError("LLM error"))])
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        request = ChatRequest(messages=[{"role": "user", "content": "hi"}])

        with self.assertRaises(RuntimeError):
            _run_async(_collect(protected, request))

        breaker = registry.get_or_create("test")
        self.assertEqual(breaker.consecutive_failures, 1)

    def test_wrapped_provider_property(self):
        fixture = FixtureProvider(script=[TurnScript()])
        gw = GatewayComponents()
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        self.assertIs(protected.wrapped_provider, fixture)

    def test_gateway_property(self):
        fixture = FixtureProvider(script=[TurnScript()])
        gw = GatewayComponents()
        protected = ProtectedProvider(fixture, gw, provider_id="test")
        self.assertIs(protected.gateway, gw)

    def test_provider_id_property(self):
        fixture = FixtureProvider(script=[TurnScript()])
        gw = GatewayComponents()
        protected = ProtectedProvider(fixture, gw, provider_id="my-provider")
        self.assertEqual(protected.provider_id, "my-provider")


class TestInjectableClocks(unittest.TestCase):
    """Injectable clocks work for deterministic testing."""

    def test_circuit_breaker_with_injectable_clock(self):
        clock_time = [100.0]

        def mock_clock() -> float:
            return clock_time[0]

        registry = CircuitBreakerRegistry(
            CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=10.0),
            clock=mock_clock,
        )
        gw = GatewayComponents(circuit_registry=registry)

        # Trip the breaker
        registry.record_failure("test")
        self.assertEqual(registry.get_state("test"), CircuitState.OPEN)

        # Before cooldown — blocked
        result1 = _run_async(gw.before_call("test"))
        self.assertFalse(result1)

        # After cooldown — allowed (transitions to HALF_OPEN)
        clock_time[0] = 120.0
        result2 = _run_async(gw.before_call("test"))
        self.assertTrue(result2)


if __name__ == "__main__":
    unittest.main()
