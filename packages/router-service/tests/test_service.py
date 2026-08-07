"""Tests for RouterService.decide() with the RULE strategy."""

from __future__ import annotations

import unittest

from platform_contract import NeutralSkillDescriptor, RouteDecision

from inkstatute_router_service import RouterService, RouterStrategy


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


def _make_review_registry() -> _FakeSkillRegistry:
    """Create a fake registry with a review-category skill."""
    return _FakeSkillRegistry([
        NeutralSkillDescriptor(
            skill_id="lawfirm/compliance_review",
            name="compliance_review",
            required_tool_refs=["law_search"],
            metadata={"intent": "review"},
        ),
    ])


class TestRouterServiceRuleStrategy(unittest.TestCase):
    """RouterService RULE strategy tests."""

    def test_decide_rule_strategy_matched(self) -> None:
        """RULE strategy with a keyword match and registry hit -> mode=matched."""
        registry = _make_review_registry()
        service = RouterService(strategy=RouterStrategy.RULE, skill_registry=registry)
        decision = service.decide({"message": "请审查这份合同文件的内容"})
        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "lawfirm/compliance_review")
        self.assertAlmostEqual(decision.confidence, 0.7)
        self.assertEqual(decision.metadata["router_strategy"], "rule")

    def test_decide_rule_strategy_zero_match(self) -> None:
        """RULE strategy with no keyword match -> mode=zero_match."""
        service = RouterService(strategy=RouterStrategy.RULE)
        decision = service.decide({"message": "xyz random text"})
        self.assertEqual(decision.mode, "zero_match")
        self.assertIsNone(decision.primary_skill)
        self.assertAlmostEqual(decision.confidence, 0.0)

    def test_decide_rule_strategy_simple_qa_no_registry(self) -> None:
        """RULE strategy with keyword match but no registry -> mode=simple_qa."""
        service = RouterService(strategy=RouterStrategy.RULE, skill_registry=None)
        decision = service.decide({"message": "请问这个条款是否有效力呢"})
        self.assertEqual(decision.mode, "simple_qa")
        self.assertAlmostEqual(decision.confidence, 0.5)

    def test_decide_is_stateless(self) -> None:
        """Two calls with the same context must return equal RouteDecision objects."""
        service = RouterService(strategy=RouterStrategy.RULE)
        ctx = {"message": "请问什么是合同", "turn_id": "t1", "route_decision_id": "rd1"}
        d1 = service.decide(ctx)
        d2 = service.decide(ctx)
        self.assertEqual(d1, d2)

    def test_route_decision_mode_is_frozen_value(self) -> None:
        """All produced mode values must be in the frozen RouteMode set."""
        frozen_modes = {"matched", "simple_qa", "skipped", "zero_match"}
        registry = _make_review_registry()
        service = RouterService(strategy=RouterStrategy.RULE, skill_registry=registry)
        contexts = [
            {"message": "请审查这份合同"},
            {"message": "请问什么是合同"},
            {"message": "xyz random text"},
        ]
        for ctx in contexts:
            decision = service.decide(ctx)
            self.assertIn(decision.mode, frozen_modes)

    def test_metadata_includes_router_strategy(self) -> None:
        """metadata['router_strategy'] must be 'rule' for RULE strategy."""
        service = RouterService(strategy=RouterStrategy.RULE)
        decision = service.decide({"message": "请问什么是合同"})
        self.assertEqual(decision.metadata["router_strategy"], "rule")

    def test_metadata_includes_router_service_version(self) -> None:
        """metadata['router_service_version'] must be '0.1.0'."""
        service = RouterService(strategy=RouterStrategy.RULE)
        decision = service.decide({"message": "请问什么是合同"})
        self.assertEqual(decision.metadata["router_service_version"], "0.1.0")


class TestRouterServiceRealIndex(unittest.TestCase):
    """Verify RouterService works with a real-index SkillRegistry."""

    def test_real_index_strong_signal_produces_valid_decision(self) -> None:
        """RouterService with a real-index SkillRegistry produces valid RouteDecision.

        The primary_skill must be a real skill_id from the index (not a fake
        name like 'case_qa' or 'contract_draft').
        """
        from _real_index_fixture import build_real_index_registry

        registry = build_real_index_registry()
        service = RouterService(
            strategy=RouterStrategy.RULE,
            skill_registry=registry,
        )
        # Strong-signal: court SMS → legal-court-sms
        decision = service.decide(
            {"message": "[法院短信] 您有新的送达文书，案号 (2025)京0105民初1234号"}
        )
        self.assertIsInstance(decision, RouteDecision)
        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "legal-court-sms")
        self.assertEqual(decision.matched_rule, "court_sms")
        self.assertAlmostEqual(decision.confidence, 0.95)

    def test_real_index_skill_lookup(self) -> None:
        """Real-index SkillRegistry can look up a skill by skill_id."""
        from _real_index_fixture import build_real_index_registry

        registry = build_real_index_registry()
        # legal-court-sms is a real skill in the index
        descriptor = registry.get_skill("legal-court-sms")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.skill_id, "legal-court-sms")

    def test_real_index_does_not_use_fake_names(self) -> None:
        """The 4 fake skill names must NOT appear in real-index assertions."""
        from _real_index_fixture import build_real_index_registry

        registry = build_real_index_registry()
        fake_names = {"case_qa", "contract_draft", "litigation_summary", "compliance_review"}
        for skill in registry.list_skills():
            # The fake names should not be skill_ids in the real index
            self.assertNotIn(skill.skill_id, fake_names)


if __name__ == "__main__":
    unittest.main()
