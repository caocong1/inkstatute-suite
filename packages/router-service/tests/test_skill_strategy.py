"""Unit tests for the SKILL strategy in RouterService.

Tests cover:
- Direct skill_id lookup via get_skill() (matched and not-found)
- Intent-based search(category=<intent>) with single match
- Ambiguous multiple matches (→ simple_qa with supporting_skills)
- Zero match when search returns no results
- Registry not configured (→ zero_match with registry_not_configured)
- Stateless behavior verification
- Frozen RouteMode value verification
"""

from __future__ import annotations

import unittest

from platform_contract import NeutralSkillDescriptor, RouteDecision

from inkstatute_router_service import RouterService, RouterStrategy


def _make_descriptor(
    skill_id: str,
    name: str = "",
    required_tool_refs: list[str] | None = None,
    metadata: dict | None = None,
) -> NeutralSkillDescriptor:
    """Create a NeutralSkillDescriptor for testing."""
    return NeutralSkillDescriptor(
        skill_id=skill_id,
        name=name,
        required_tool_refs=required_tool_refs or [],
        metadata=metadata or {},
    )


class _FakeSkillRegistry:
    """Fake SkillRegistryPort with configurable canned responses.

    Tracks call counts to verify stateless behavior.
    """

    def __init__(
        self,
        skills_by_id: dict[str, NeutralSkillDescriptor] | None = None,
        search_results: dict[str, list[NeutralSkillDescriptor]] | None = None,
        default_search: list[NeutralSkillDescriptor] | None = None,
    ) -> None:
        self._skills_by_id = skills_by_id or {}
        self._search_results = search_results or {}
        self._default_search = default_search if default_search is not None else []
        self.get_skill_calls: list[str] = []
        self.search_calls: list[dict] = []

    def list_skills(self) -> list[NeutralSkillDescriptor]:
        return list(self._skills_by_id.values())

    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None:
        self.get_skill_calls.append(skill_id)
        return self._skills_by_id.get(skill_id)

    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]:
        call = {"tag": tag, "category": category, "name_substring": name_substring}
        self.search_calls.append(call)
        if category is not None and category in self._search_results:
            return list(self._search_results[category])
        if name_substring is not None and name_substring in self._search_results:
            return list(self._search_results[name_substring])
        return list(self._default_search)


class SkillStrategyMatchedByIdTests(unittest.TestCase):
    def test_skill_lookup_by_id_matched(self) -> None:
        descriptor = _make_descriptor(
            "lawfirm/case_qa",
            name="Case QA",
            required_tool_refs=["tool_a"],
        )
        fake = _FakeSkillRegistry(skills_by_id={"lawfirm/case_qa": descriptor})
        service = RouterService(strategy=RouterStrategy.SKILL, skill_registry=fake)
        decision = service.decide({"skill_id": "lawfirm/case_qa"})

        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "lawfirm/case_qa")
        self.assertEqual(decision.confidence, 1.0)
        self.assertEqual(decision.metadata["router_strategy"], "skill")
        self.assertEqual(decision.metadata["skill_lookup_method"], "get_skill")
        self.assertEqual(decision.matched_rule, "skill:lawfirm/case_qa")
        self.assertEqual(decision.required_tools, ["tool_a"])

    def test_skill_lookup_by_id_not_found(self) -> None:
        fake = _FakeSkillRegistry(skills_by_id={})
        service = RouterService(strategy=RouterStrategy.SKILL, skill_registry=fake)
        decision = service.decide({"skill_id": "unknown"})

        self.assertEqual(decision.mode, "zero_match")
        self.assertIsNone(decision.primary_skill)
        self.assertEqual(decision.confidence, 0.0)
        self.assertTrue(decision.metadata["skill_not_found"])
        self.assertEqual(decision.metadata["skill_lookup_method"], "get_skill")


class SkillStrategySearchTests(unittest.TestCase):
    def test_skill_lookup_by_intent_search_single_match(self) -> None:
        descriptor = _make_descriptor(
            "lawfirm/contract_drafting",
            name="Contract Drafting",
            required_tool_refs=["docx_tool"],
        )
        fake = _FakeSkillRegistry(
            search_results={"drafting": [descriptor]},
            default_search=[],
        )
        service = RouterService(strategy=RouterStrategy.SKILL, skill_registry=fake)
        decision = service.decide({"message": "请起草一份合同文件的内容"})

        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "lawfirm/contract_drafting")
        self.assertEqual(decision.confidence, 0.7)
        self.assertEqual(decision.metadata["skill_lookup_method"], "search")
        self.assertEqual(decision.required_tools, ["docx_tool"])

    def test_skill_lookup_ambiguous_multiple_matches(self) -> None:
        descriptors = [
            _make_descriptor("lawfirm/qa_1", name="QA 1"),
            _make_descriptor("lawfirm/qa_2", name="QA 2"),
            _make_descriptor("lawfirm/qa_3", name="QA 3"),
        ]
        fake = _FakeSkillRegistry(
            search_results={"factual_qa": descriptors},
            default_search=[],
        )
        service = RouterService(strategy=RouterStrategy.SKILL, skill_registry=fake)
        decision = service.decide({"message": "请问这个条款是否有效力呢"})

        self.assertEqual(decision.mode, "simple_qa")
        self.assertEqual(decision.confidence, 0.5)
        self.assertIsNone(decision.primary_skill)
        self.assertEqual(len(decision.supporting_skills), 3)
        self.assertEqual(decision.metadata["ambiguous_matches"], 3)
        self.assertEqual(decision.metadata["skill_lookup_method"], "search")

    def test_skill_lookup_no_match_zero_match(self) -> None:
        fake = _FakeSkillRegistry(default_search=[])
        service = RouterService(strategy=RouterStrategy.SKILL, skill_registry=fake)
        decision = service.decide({"message": "xyz random text"})

        self.assertEqual(decision.mode, "zero_match")
        self.assertEqual(decision.confidence, 0.0)
        self.assertIsNone(decision.primary_skill)


class SkillStrategyRegistryNotConfiguredTests(unittest.TestCase):
    def test_skill_lookup_registry_not_configured(self) -> None:
        service = RouterService(strategy=RouterStrategy.SKILL, skill_registry=None)
        decision = service.decide({"skill_id": "any"})

        self.assertEqual(decision.mode, "zero_match")
        self.assertTrue(decision.metadata["registry_not_configured"])
        self.assertEqual(decision.confidence, 0.0)


class SkillStrategyStatelessTests(unittest.TestCase):
    def test_skill_strategy_is_stateless(self) -> None:
        descriptor = _make_descriptor("lawfirm/case_qa", name="Case QA")
        fake = _FakeSkillRegistry(skills_by_id={"lawfirm/case_qa": descriptor})
        service = RouterService(strategy=RouterStrategy.SKILL, skill_registry=fake)

        context = {"skill_id": "lawfirm/case_qa", "turn_id": "turn-001"}
        decision1 = service.decide(context)
        decision2 = service.decide(context)

        self.assertEqual(decision1, decision2)
        self.assertEqual(len(fake.get_skill_calls), 2)
        self.assertEqual(fake.get_skill_calls, ["lawfirm/case_qa", "lawfirm/case_qa"])


class SkillStrategyFrozenModeTests(unittest.TestCase):
    def test_skill_decision_mode_is_frozen_value(self) -> None:
        valid_modes = {"matched", "simple_qa", "skipped", "zero_match"}
        descriptor = _make_descriptor("lawfirm/skill_1", name="Skill 1")
        fake = _FakeSkillRegistry(
            skills_by_id={"lawfirm/skill_1": descriptor},
            search_results={"drafting": [descriptor]},
            default_search=[],
        )
        service = RouterService(strategy=RouterStrategy.SKILL, skill_registry=fake)

        contexts = [
            {"skill_id": "lawfirm/skill_1"},
            {"skill_id": "nonexistent"},
            {"message": "请起草一份合同"},
            {"message": "xyz random"},
        ]
        for ctx in contexts:
            decision = service.decide(ctx)
            self.assertIsInstance(decision, RouteDecision)
            self.assertIn(decision.mode, valid_modes)

        # Also test with no registry
        service_no_reg = RouterService(strategy=RouterStrategy.SKILL, skill_registry=None)
        decision = service_no_reg.decide({"skill_id": "any"})
        self.assertIn(decision.mode, valid_modes)


if __name__ == "__main__":
    unittest.main()
