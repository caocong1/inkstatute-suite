"""Tests for RouterStrategy enum, classify_intent, and RULE strategy RouteMode mapping.

Verifies that:
1. RouterStrategy has exactly RULE and SKILL values (NOT RouteMode values).
2. classify_intent correctly classifies messages via keyword/regex matching.
3. RULE strategy produces RouteDecision with frozen RouteMode values only.
"""

from __future__ import annotations

import unittest

from platform_contract import NeutralSkillDescriptor

from inkstatute_router_service import RouterService, RouterStrategy, classify_intent


# --- Fake registry for integration tests ---


class _FakeSkillRegistry:
    """Fake SkillRegistryPort for testing."""

    def __init__(self, skills: list[NeutralSkillDescriptor] | None = None) -> None:
        self._skills = skills or []
        self._by_id = {s.skill_id: s for s in self._skills}

    def list_skills(self) -> list[NeutralSkillDescriptor]:
        return list(self._skills)

    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None:
        return self._by_id.get(skill_id)

    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]:
        results = self._skills
        if category is not None:
            results = [s for s in results if s.metadata.get("intent") == category]
        return list(results)


def _make_factual_qa_registry() -> _FakeSkillRegistry:
    """Create a fake registry with a factual_qa-category skill."""
    return _FakeSkillRegistry([
        NeutralSkillDescriptor(
            skill_id="lawfirm/legal_qa",
            name="legal_qa",
            required_tool_refs=["law_search"],
            metadata={"intent": "factual_qa"},
        ),
    ])


# --- RouterStrategy enum tests ---


class TestRouterStrategyEnum(unittest.TestCase):
    """Verify RouterStrategy enum values and contract freeze safety."""

    def test_router_strategy_rule_value(self) -> None:
        self.assertEqual(RouterStrategy.RULE.value, "rule")

    def test_router_strategy_skill_value(self) -> None:
        self.assertEqual(RouterStrategy.SKILL.value, "skill")

    def test_router_strategy_is_str_enum(self) -> None:
        self.assertEqual(RouterStrategy.RULE, "rule")

    def test_router_strategy_has_exactly_three_values(self) -> None:
        self.assertEqual(len(list(RouterStrategy)), 3)

    def test_router_strategy_hybrid_value(self) -> None:
        self.assertEqual(RouterStrategy.HYBRID.value, "hybrid")

    def test_router_strategy_not_in_route_mode(self) -> None:
        """RouterStrategy values must NOT be in the frozen RouteMode set."""
        frozen_route_modes = ["matched", "simple_qa", "skipped", "zero_match"]
        self.assertNotIn("rule", frozen_route_modes)
        self.assertNotIn("skill", frozen_route_modes)
        self.assertNotIn("hybrid", frozen_route_modes)


# --- classify_intent function tests ---


class TestClassifyIntent(unittest.TestCase):
    """Verify classify_intent keyword/regex classification."""

    def test_classify_intent_factual_qa(self) -> None:
        self.assertEqual(classify_intent("请问什么是合同"), "factual_qa")

    def test_classify_intent_drafting(self) -> None:
        self.assertEqual(classify_intent("请起草一份合同"), "drafting")

    def test_classify_intent_analysis(self) -> None:
        self.assertEqual(classify_intent("请分析这份文件"), "analysis")

    def test_classify_intent_review(self) -> None:
        self.assertEqual(classify_intent("请审查这份合同"), "review")

    def test_classify_intent_no_match(self) -> None:
        self.assertIsNone(classify_intent("xyz random text"))

    def test_classify_intent_empty_message(self) -> None:
        self.assertIsNone(classify_intent(""))

    def test_classify_intent_none_message(self) -> None:
        self.assertIsNone(classify_intent(None))

    def test_classify_intent_case_insensitive(self) -> None:
        """English keyword matching must be case-insensitive."""
        self.assertEqual(classify_intent("Please REVIEW this"), "review")


# --- RULE strategy RouteMode mapping integration tests ---


class TestRuleStrategyRouteModeMapping(unittest.TestCase):
    """Verify RULE strategy maps to frozen RouteMode values, not strategy names."""

    def test_rule_strategy_maps_to_frozen_route_mode(self) -> None:
        """RULE strategy with keyword match -> mode=matched (frozen), strategy in metadata."""
        registry = _make_factual_qa_registry()
        service = RouterService(strategy=RouterStrategy.RULE, skill_registry=registry)
        decision = service.decide({"message": "请问什么是合同"})
        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.metadata["router_strategy"], "rule")

    def test_rule_strategy_no_match_maps_to_zero_match(self) -> None:
        """RULE strategy with no keyword match -> mode=zero_match (frozen)."""
        service = RouterService(strategy=RouterStrategy.RULE)
        decision = service.decide({"message": "xyz random"})
        self.assertEqual(decision.mode, "zero_match")
        self.assertEqual(decision.metadata["router_strategy"], "rule")


if __name__ == "__main__":
    unittest.main()
