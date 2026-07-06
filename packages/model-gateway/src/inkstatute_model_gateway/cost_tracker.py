"""Per-tenant/matter cost tracking with budget ceilings.

Token usage from provider responses is accumulated per tenant per matter.
When a budget ceiling is exceeded, further requests are rejected with a
clear ``model_gateway_budget_exceeded`` error.

Cost is estimated from ``provider_usage`` token counts multiplied by
per-provider pricing rates.

No external dependencies — ``dependencies = []`` invariant preserved.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from platform_contract.events import JsonObject


@dataclass(frozen=True, slots=True)
class PricingRate:
    """Per-token pricing for a single provider.

    Costs are in arbitrary units (e.g., micro-cents).  The actual currency
    is irrelevant — only the ratio between providers matters for routing
    decisions.
    """

    input_token_cost: float = 0.0
    output_token_cost: float = 0.0


@dataclass(frozen=True, slots=True)
class BudgetCeiling:
    """Budget ceiling for a tenant or tenant+matter scope.

    ``scope`` is either ``"tenant_matter"`` (keyed by ``"{tenant_id}:{matter_id}"``)
    or ``"tenant_global"`` (keyed by ``"{tenant_id}"``).
    """

    max_cost: float
    scope: str = "tenant_matter"


class CostTracker:
    """Accumulates token usage cost per tenant per matter.

    Uses ``asyncio.Lock`` for safe concurrent access.  If no budget is
    configured for a key, all requests are allowed.  If no pricing is
    configured for a provider, cost is zero.
    """

    def __init__(
        self,
        pricing: dict[str, PricingRate] | None = None,
        budgets: dict[str, BudgetCeiling] | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._pricing = dict(pricing or {})
        self._budgets = dict(budgets or {})
        self._accumulated: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _budget_key(self, tenant_id: str, matter_id: str | None) -> str:
        if matter_id is not None:
            return f"{tenant_id}:{matter_id}"
        return tenant_id

    def _calculate_cost(self, provider_id: str, usage: JsonObject) -> float:
        """Calculate cost from usage tokens and pricing rates."""
        rate = self._pricing.get(provider_id)
        if rate is None:
            return 0.0
        input_tokens, output_tokens = _extract_tokens(usage)
        return input_tokens * rate.input_token_cost + output_tokens * rate.output_token_cost

    async def check_budget(
        self,
        tenant_id: str,
        matter_id: str | None = None,
    ) -> tuple[bool, float, float]:
        """Return (within_budget, accumulated_cost, ceiling).

        If no budget is configured for the key, returns (True, accumulated, inf).
        """
        key = self._budget_key(tenant_id, matter_id)
        ceiling = self._budgets.get(key)
        async with self._lock:
            accumulated = self._accumulated.get(key, 0.0)
        if ceiling is None:
            return (True, accumulated, float("inf"))
        return (accumulated < ceiling.max_cost, accumulated, ceiling.max_cost)

    async def record_usage(
        self,
        tenant_id: str,
        matter_id: str | None,
        provider_id: str,
        usage: JsonObject,
    ) -> float:
        """Record token usage and return the cost added."""
        cost = self._calculate_cost(provider_id, usage)
        if cost == 0.0:
            return 0.0
        key = self._budget_key(tenant_id, matter_id)
        async with self._lock:
            self._accumulated[key] = self._accumulated.get(key, 0.0) + cost
        return cost

    async def get_accumulated(self, tenant_id: str, matter_id: str | None = None) -> float:
        """Return accumulated cost for the budget scope."""
        key = self._budget_key(tenant_id, matter_id)
        async with self._lock:
            return self._accumulated.get(key, 0.0)

    def reset(self) -> None:
        """Clear all accumulated costs (for testing)."""
        self._accumulated.clear()


def _extract_tokens(usage: JsonObject) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from a usage dict.

    Handles various key names used by different providers:
    - input_tokens / prompt_tokens
    - output_tokens / completion_tokens
    """

    input_tokens = 0
    output_tokens = 0

    for key in ("input_tokens", "prompt_tokens"):
        val = usage.get(key)
        if isinstance(val, (int, float)):
            input_tokens = int(val)
            break

    for key in ("output_tokens", "completion_tokens"):
        val = usage.get(key)
        if isinstance(val, (int, float)):
            output_tokens = int(val)
            break

    return input_tokens, output_tokens


__all__ = [
    "BudgetCeiling",
    "CostTracker",
    "PricingRate",
]
