"""Configuration for the Model Provider Gateway composite adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platform_contract.events import JsonObject

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
    """

    gateway_id: str = "model-provider-gateway"
    enabled: bool = False
    fallback_chain: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


__all__ = ["ModelProviderGatewayConfig"]
