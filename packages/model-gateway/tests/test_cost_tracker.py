"""Tests for CostTracker — per-tenant/matter cost tracking with budget ceilings."""

from __future__ import annotations

import unittest

from platform_contract.events import JsonObject

from inkstatute_model_gateway.cost_tracker import BudgetCeiling, CostTracker, PricingRate


class TestCostCalculation(unittest.IsolatedAsyncioTestCase):
    """Cost calculation from usage tokens and pricing rates."""

    async def test_record_usage_calculates_cost(self) -> None:
        pricing = {"provider-a": PricingRate(input_token_cost=0.01, output_token_cost=0.02)}
        tracker = CostTracker(pricing)
        usage: JsonObject = {"input_tokens": 100, "output_tokens": 50}
        cost = await tracker.record_usage("tenant-1", "matter-1", "provider-a", usage)
        # 100 * 0.01 + 50 * 0.02 = 1.0 + 1.0 = 2.0
        self.assertAlmostEqual(cost, 2.0)

    async def test_accumulated_cost_persists(self) -> None:
        pricing = {"provider-a": PricingRate(input_token_cost=0.01, output_token_cost=0.0)}
        tracker = CostTracker(pricing)
        usage: JsonObject = {"input_tokens": 100, "output_tokens": 0}
        await tracker.record_usage("tenant-1", "matter-1", "provider-a", usage)
        cost2 = await tracker.record_usage("tenant-1", "matter-1", "provider-a", usage)
        accumulated = await tracker.get_accumulated("tenant-1", "matter-1")
        self.assertAlmostEqual(accumulated, 2.0)
        self.assertAlmostEqual(cost2, 1.0)

    async def test_record_usage_no_pricing_zero_cost(self) -> None:
        tracker = CostTracker({})
        usage: JsonObject = {"input_tokens": 100, "output_tokens": 50}
        cost = await tracker.record_usage("tenant-1", "matter-1", "unknown-provider", usage)
        self.assertAlmostEqual(cost, 0.0)

    async def test_extract_tokens_handles_alternate_keys(self) -> None:
        pricing = {"provider-a": PricingRate(input_token_cost=0.01, output_token_cost=0.02)}
        tracker = CostTracker(pricing)
        usage: JsonObject = {"prompt_tokens": 100, "completion_tokens": 50}
        cost = await tracker.record_usage("tenant-1", "matter-1", "provider-a", usage)
        self.assertAlmostEqual(cost, 2.0)

    async def test_extract_tokens_missing_keys(self) -> None:
        pricing = {"provider-a": PricingRate(input_token_cost=0.01, output_token_cost=0.02)}
        tracker = CostTracker(pricing)
        usage: JsonObject = {}
        cost = await tracker.record_usage("tenant-1", "matter-1", "provider-a", usage)
        self.assertAlmostEqual(cost, 0.0)


class TestBudgetCeiling(unittest.IsolatedAsyncioTestCase):
    """Budget ceiling enforcement tests."""

    async def test_check_budget_within_limit(self) -> None:
        budgets = {"tenant-1:matter-1": BudgetCeiling(max_cost=100.0)}
        tracker = CostTracker(budgets=budgets)
        within, accumulated, ceiling = await tracker.check_budget("tenant-1", "matter-1")
        self.assertTrue(within)
        self.assertAlmostEqual(accumulated, 0.0)
        self.assertAlmostEqual(ceiling, 100.0)

    async def test_check_budget_exceeded(self) -> None:
        budgets = {"tenant-1:matter-1": BudgetCeiling(max_cost=100.0)}
        pricing = {"provider-a": PricingRate(input_token_cost=1.0, output_token_cost=0.0)}
        tracker = CostTracker(pricing=pricing, budgets=budgets)
        # Record 100 cost
        await tracker.record_usage("tenant-1", "matter-1", "provider-a", {"input_tokens": 100, "output_tokens": 0})
        within, accumulated, ceiling = await tracker.check_budget("tenant-1", "matter-1")
        self.assertFalse(within)
        self.assertAlmostEqual(accumulated, 100.0)

    async def test_check_budget_no_config_always_allowed(self) -> None:
        tracker = CostTracker()
        within, accumulated, ceiling = await tracker.check_budget("tenant-1", "matter-1")
        self.assertTrue(within)
        self.assertEqual(ceiling, float("inf"))

    async def test_tenant_matter_scope_isolated(self) -> None:
        """Different matter_ids have separate accumulated costs."""
        budgets = {
            "tenant-1:matter-1": BudgetCeiling(max_cost=100.0),
            "tenant-1:matter-2": BudgetCeiling(max_cost=50.0),
        }
        pricing = {"provider-a": PricingRate(input_token_cost=1.0, output_token_cost=0.0)}
        tracker = CostTracker(pricing=pricing, budgets=budgets)
        # Use 80 in matter-1
        await tracker.record_usage("tenant-1", "matter-1", "provider-a", {"input_tokens": 80, "output_tokens": 0})
        # matter-2 should be unaffected
        within_m2, _, _ = await tracker.check_budget("tenant-1", "matter-2")
        self.assertTrue(within_m2)
        # matter-1 should still be within (80 < 100)
        within_m1, _, _ = await tracker.check_budget("tenant-1", "matter-1")
        self.assertTrue(within_m1)

    async def test_tenant_global_scope(self) -> None:
        """matter_id=None uses tenant-level budget key."""
        budgets = {"tenant-1": BudgetCeiling(max_cost=100.0)}
        pricing = {"provider-a": PricingRate(input_token_cost=1.0, output_token_cost=0.0)}
        tracker = CostTracker(pricing=pricing, budgets=budgets)
        await tracker.record_usage("tenant-1", None, "provider-a", {"input_tokens": 80, "output_tokens": 0})
        within, accumulated, _ = await tracker.check_budget("tenant-1", None)
        self.assertTrue(within)
        self.assertAlmostEqual(accumulated, 80.0)

    async def test_get_accumulated_no_data(self) -> None:
        tracker = CostTracker()
        accumulated = await tracker.get_accumulated("tenant-1", "matter-1")
        self.assertAlmostEqual(accumulated, 0.0)


class TestCostTrackerReset(unittest.IsolatedAsyncioTestCase):
    """Reset clears accumulated costs."""

    async def test_reset_clears_accumulated(self) -> None:
        pricing = {"provider-a": PricingRate(input_token_cost=1.0, output_token_cost=0.0)}
        tracker = CostTracker(pricing)
        await tracker.record_usage("tenant-1", "matter-1", "provider-a", {"input_tokens": 50, "output_tokens": 0})
        accumulated = await tracker.get_accumulated("tenant-1", "matter-1")
        self.assertAlmostEqual(accumulated, 50.0)
        tracker.reset()
        accumulated_after = await tracker.get_accumulated("tenant-1", "matter-1")
        self.assertAlmostEqual(accumulated_after, 0.0)


if __name__ == "__main__":
    unittest.main()
