"""Configuration for the Model Provider Gateway composite adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platform_contract.events import JsonObject

from .circuit_breaker import CircuitBreakerConfig
from .cost_tracker import BudgetCeiling, PricingRate
from .rate_limiter import RateLimitConfig

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ModelProviderGatewayConfig:
    """Configuration for the composite Model Provider Gateway.

    ``enabled`` defaults to ``False`` — when disabled, the gateway is
    transparent (pass-through) with no rate limiting, circuit breaking,
    fallback, or cost tracking.

    ``fallback_chain`` is an ordered list of ``backend_id`` values that
    the gateway tries when the primary provider fails or its circuit
    breaker is open.

    ``rate_limit_configs`` maps provider_id to RateLimitConfig for
    per-tenant/provider RPM/TPM/concurrency limits.

    ``circuit_breaker_config`` configures the failure threshold and
    cooldown for all provider circuit breakers.

    ``pricing`` maps provider_id to PricingRate for cost estimation.

    ``budgets`` maps budget keys to BudgetCeiling for budget enforcement.
    Keys are ``"{tenant_id}:{matter_id}"`` for tenant_matter scope or
    ``"{tenant_id}"`` for tenant_global scope.
    """

    gateway_id: str = "model-provider-gateway"
    enabled: bool = False
    fallback_chain: list[str] = field(default_factory=list)
    rate_limit_configs: dict[str, RateLimitConfig] = field(default_factory=dict)
    circuit_breaker_config: CircuitBreakerConfig | None = None
    pricing: dict[str, PricingRate] = field(default_factory=dict)
    budgets: dict[str, BudgetCeiling] = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


__all__ = ["ModelProviderGatewayConfig"]
