"""Gateway components wrapper for the agent-core model layer.

This module wraps the circuit breaker, rate limiter, and cost tracker
from ``packages/model-gateway`` for use by the agent-core model layer.

The agent-core imports these components directly (not duplicates them).
The ``ModelProviderGateway`` composite adapter pattern is NOT needed
(agent-core is a single backend, not a composite), but the individual
components are reused.

Classes:
- ``GatewayComponents``: Wraps ``CircuitBreakerRegistry``, ``RateLimiter``,
  and ``CostTracker``.  Provides ``before_call()`` and ``after_call()``
  methods for the provider call lifecycle.
- ``ProtectedProvider``: Wraps any ``LlmProvider`` with gateway component
  checks.  Delegates ``chat_stream()`` with circuit breaker / rate limiter
  / cost tracker integration.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Callable

from platform_contract.events import ErrorInfo, JsonObject

from inkstatute_model_gateway.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
)
from inkstatute_model_gateway.cost_tracker import CostTracker
from inkstatute_model_gateway.rate_limiter import RateLimitConfig, RateLimiter

from .provider import (
    ChatRequest,
    LlmProvider,
    StreamDelta,
    UsageAccumulator,
    UsageDelta,
)

# ---------------------------------------------------------------------------
# GatewayComponents
# ---------------------------------------------------------------------------


class GatewayComponents:
    """Wraps model-gateway components for the agent-core model layer.

    If components are ``None``, creates default instances (pass-through
    mode — no limits, no budgets).

    Args:
        circuit_registry: ``CircuitBreakerRegistry`` for per-provider
            circuit breakers.  If ``None``, a default registry is created.
        rate_limiter: ``RateLimiter`` for per-tenant per-provider rate
            limiting.  If ``None``, a default limiter is created (no limits).
        cost_tracker: ``CostTracker`` for per-tenant per-matter cost
            tracking.  If ``None``, a default tracker is created (no budgets).
        tenant_id: Tenant identifier for rate limiting and cost tracking.
        matter_id: Optional matter identifier for cost tracking.
    """

    def __init__(
        self,
        *,
        circuit_registry: CircuitBreakerRegistry | None = None,
        rate_limiter: RateLimiter | None = None,
        cost_tracker: CostTracker | None = None,
        tenant_id: str = "default",
        matter_id: str | None = None,
    ) -> None:
        self._circuit_registry = circuit_registry or CircuitBreakerRegistry()
        self._rate_limiter = rate_limiter or RateLimiter()
        self._cost_tracker = cost_tracker or CostTracker()
        self._tenant_id = tenant_id
        self._matter_id = matter_id
        self._usage_accumulator = UsageAccumulator()

    @property
    def circuit_registry(self) -> CircuitBreakerRegistry:
        return self._circuit_registry

    @property
    def rate_limiter(self) -> RateLimiter:
        return self._rate_limiter

    @property
    def cost_tracker(self) -> CostTracker:
        return self._cost_tracker

    async def before_call(self, provider_id: str) -> bool:
        """Check if a provider call should proceed.

        Checks:
        1. Circuit breaker: ``can_execute(provider_id)``
        2. Rate limit: ``check_rpm(tenant_id, provider_id)``

        Returns:
            ``True`` if the call should proceed, ``False`` if blocked.
        """
        # Check circuit breaker
        if not self._circuit_registry.can_execute(provider_id):
            return False

        # Check rate limit (RPM)
        if not await self._rate_limiter.check_rpm(self._tenant_id, provider_id):
            return False

        return True

    async def after_call(
        self,
        provider_id: str,
        success: bool,
        usage: dict | None = None,
    ) -> None:
        """Record the result of a provider call.

        - Records success/failure in the circuit breaker.
        - Records the request in the rate limiter.
        - Records usage in the cost tracker.
        """
        if success:
            self._circuit_registry.record_success(provider_id)
        else:
            self._circuit_registry.record_failure(provider_id)

        # Record request in rate limiter
        tokens = 0
        if usage:
            for key in ("total_tokens", "prompt_tokens", "completion_tokens"):
                val = usage.get(key)
                if isinstance(val, (int, float)):
                    tokens = int(val)
                    break
        await self._rate_limiter.record_request(
            self._tenant_id, provider_id, tokens=tokens
        )

        # Record usage in cost tracker
        if usage:
            await self._cost_tracker.record_usage(
                self._tenant_id,
                self._matter_id,
                provider_id,
                usage,
            )
            self._usage_accumulator.add(UsageDelta(usage=usage))

    def get_usage_summary(self) -> dict:
        """Return accumulated usage for the current turn."""
        return self._usage_accumulator.to_dict()

    def reset_usage(self) -> None:
        """Reset the usage accumulator for a new turn."""
        self._usage_accumulator = UsageAccumulator()


# ---------------------------------------------------------------------------
# ProtectedProvider
# ---------------------------------------------------------------------------


class ProviderBlockedError(Exception):
    """Raised when a provider call is blocked by gateway components.

    Attributes:
        provider_id: The provider that was blocked.
        reason: Why the call was blocked (``"circuit_open"`` or
            ``"rate_limited"``).
    """

    def __init__(self, provider_id: str, reason: str) -> None:
        self.provider_id = provider_id
        self.reason = reason
        super().__init__(f"provider '{provider_id}' blocked: {reason}")


class ProtectedProvider:
    """Wraps any ``LlmProvider`` with gateway component checks.

    Before each ``chat_stream()`` call:
    1. Checks ``GatewayComponents.before_call()`` — if blocked, raises
       ``ProviderBlockedError``.
    2. Delegates to the wrapped provider's ``chat_stream()``.
    3. After streaming completes, calls ``after_call()`` with success/failure
       and accumulated usage.

    Args:
        provider: The wrapped ``LlmProvider``.
        gateway: ``GatewayComponents`` instance.
        provider_id: Provider identifier for circuit breaker / rate limiter.
    """

    def __init__(
        self,
        provider: LlmProvider,
        gateway: GatewayComponents,
        *,
        provider_id: str = "default",
    ) -> None:
        self._provider = provider
        self._gateway = gateway
        self._provider_id = provider_id

    async def chat_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[StreamDelta]:
        """Delegate to the wrapped provider with gateway checks.

        Raises:
            ProviderBlockedError: If ``before_call()`` returns ``False``.
        """
        allowed = await self._gateway.before_call(self._provider_id)
        if not allowed:
            # Determine the reason
            state = self._gateway.circuit_registry.get_state(self._provider_id)
            if state == CircuitState.OPEN:
                reason = "circuit_open"
            else:
                reason = "rate_limited"
            raise ProviderBlockedError(self._provider_id, reason)

        self._gateway.reset_usage()
        success = True
        try:
            async for delta in self._provider.chat_stream(request):
                # Accumulate usage deltas
                if isinstance(delta, UsageDelta):
                    self._gateway._usage_accumulator.add(delta)
                yield delta
        except Exception:
            success = False
            await self._gateway.after_call(
                self._provider_id, success=False, usage=None
            )
            raise
        else:
            usage = self._gateway.get_usage_summary()
            # Only record if there are actual tokens
            if usage["total_tokens"] > 0 or usage["prompt_tokens"] > 0 or usage["completion_tokens"] > 0:
                await self._gateway.after_call(
                    self._provider_id, success=True, usage=usage
                )
            else:
                await self._gateway.after_call(
                    self._provider_id, success=True, usage=None
                )

    def model_name(self) -> str:
        """Delegate to the wrapped provider."""
        return self._provider.model_name()

    def supports_tools(self) -> bool:
        """Delegate to the wrapped provider."""
        return self._provider.supports_tools()

    @property
    def wrapped_provider(self) -> LlmProvider:
        """Return the wrapped provider."""
        return self._provider

    @property
    def gateway(self) -> GatewayComponents:
        """Return the gateway components."""
        return self._gateway

    @property
    def provider_id(self) -> str:
        """Return the provider identifier."""
        return self._provider_id


__all__ = [
    "GatewayComponents",
    "ProtectedProvider",
    "ProviderBlockedError",
]
