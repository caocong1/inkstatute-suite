"""Unit tests for gate_before/gate_after → gates_before/gates_after mapping.

Verifies that the strong-signal rules and soft matcher correctly populate
``gates_before`` and ``gates_after`` on the ``RouteDecision`` event.

Mapping rules:
- ``gate_before`` (str|None) → ``gates_before`` (list[str], wrap in list if
  not None, empty list if None)
- ``gate_after`` (str|None) → ``gates_after`` (list[str], same wrapping)
- ``skip_clarification`` is stored in ``metadata["skip_clarification"]``
  (not a top-level field — contract freeze)
- No new top-level fields added to ``RouteDecision``
"""

from __future__ import annotations

import unittest

from platform_contract import NeutralSkillDescriptor, RouteDecision

from inkstatute_router_service import RouterService, RouterStrategy


class _SimpleFakeRegistry:
    """Minimal fake registry for gate mapping tests."""

    def __init__(self, descriptors: list[NeutralSkillDescriptor] | None = None) -> None:
        self._descriptors = descriptors or []

    def list_skills(self) -> list[NeutralSkillDescriptor]:
        return list(self._descriptors)

    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None:
        for d in self._descriptors:
            if d.skill_id == skill_id:
                return d
        return None

    def search(self, **kwargs) -> list[NeutralSkillDescriptor]:
        return []


class TestGateMapping(unittest.TestCase):
    """Verify gate_before/gate_after → gates_before/gates_after mapping."""

    def setUp(self) -> None:
        self.service = RouterService(strategy=RouterStrategy.RULE)

    # ── Strong-signal rule gate mapping ────────────────────────────────

    def test_court_sms_gates(self) -> None:
        """court_sms → gates_before=[], gates_after=['legal-de-ai-polish']."""
        decision = self.service.decide({"message": "法院短信送达文书"})
        self.assertEqual(decision.matched_rule, "court_sms")
        self.assertEqual(decision.gates_before, [])
        self.assertEqual(decision.gates_after, ["legal-de-ai-polish"])

    def test_new_case_gates(self) -> None:
        """new_case → gates_before=['ask-user-enforcement'], gates_after=[]."""
        decision = self.service.decide({"message": "我新接了一个案子"})
        self.assertEqual(decision.matched_rule, "new_case")
        self.assertEqual(decision.gates_before, ["ask-user-enforcement"])
        self.assertEqual(decision.gates_after, [])

    def test_docx_contract_review_gates(self) -> None:
        """docx_contract_review → both gates."""
        decision = self.service.decide({"message": "帮我审一下这份合同"})
        self.assertEqual(decision.matched_rule, "docx_contract_review")
        self.assertEqual(decision.gates_before, ["ask-user-enforcement"])
        self.assertEqual(decision.gates_after, ["legal-de-ai-polish"])

    def test_judgment_or_transcript_no_gates(self) -> None:
        """judgment_or_transcript → gates_before=[], gates_after=[] (no gates)."""
        decision = self.service.decide({"message": "判决书已经下来了，帮我分析"})
        self.assertEqual(decision.matched_rule, "judgment_or_transcript")
        self.assertEqual(decision.gates_before, [])
        self.assertEqual(decision.gates_after, [])

    # ── Soft match gate mapping ────────────────────────────────────────

    def test_soft_match_score_below_07_has_ask_user_gate(self) -> None:
        """Soft match with score < 0.7 → gates_before=['ask-user-enforcement']."""
        # Create a descriptor with 2 triggers, message matches only 1 → score ~0.5
        desc = NeutralSkillDescriptor(
            skill_id="test-soft-low",
            name="Test Soft Low",
            description=None,
            metadata={"skill_type": "leaf", "host_assumptions": ["商标", "专利"]},
        )
        registry = _SimpleFakeRegistry([desc])
        service = RouterService(strategy=RouterStrategy.RULE, skill_registry=registry)
        # Message ≥ 12 chars, matches only '商标' → score = 0.5
        decision = service.decide({"message": "商标咨询问题需要处理呢啊"})
        self.assertEqual(decision.matched_rule, "soft_trigger_match")
        self.assertEqual(decision.gates_before, ["ask-user-enforcement"])
        self.assertEqual(decision.gates_after, ["legal-de-ai-polish"])
        self.assertFalse(decision.metadata["skip_clarification"])

    def test_soft_match_score_above_07_skips_clarification(self) -> None:
        """Soft match with score ≥ 0.7 → gates_before=[] (skip clarification)."""
        desc = NeutralSkillDescriptor(
            skill_id="test-soft-high",
            name="Test Soft High",
            description=None,
            metadata={"skill_type": "leaf", "host_assumptions": ["商标", "专利"]},
        )
        registry = _SimpleFakeRegistry([desc])
        service = RouterService(strategy=RouterStrategy.RULE, skill_registry=registry)
        # Message ≥ 12 chars, matches both triggers → score = 1.0
        decision = service.decide({"message": "商标专利咨询问题需要处理呢"})
        self.assertEqual(decision.matched_rule, "soft_trigger_match")
        self.assertEqual(decision.gates_before, [])
        self.assertEqual(decision.gates_after, ["legal-de-ai-polish"])
        self.assertTrue(decision.metadata["skip_clarification"])

    # ── Factual short-circuit gate mapping ────────────────────────────

    def test_factual_short_circuit_no_gates(self) -> None:
        """Factual short-circuit → gates_before=[], gates_after=[]."""
        decision = self.service.decide({"message": "民法典第 1062 条是什么？"})
        self.assertEqual(decision.matched_rule, "factual_short_circuit")
        self.assertEqual(decision.gates_before, [])
        self.assertEqual(decision.gates_after, [])

    # ── Contract freeze verification ──────────────────────────────────

    def test_skip_clarification_in_metadata_not_top_level(self) -> None:
        """skip_clarification must be in metadata, not a top-level field."""
        desc = NeutralSkillDescriptor(
            skill_id="test-skip",
            name="Test Skip",
            description=None,
            metadata={"skill_type": "leaf", "host_assumptions": ["商标", "专利"]},
        )
        registry = _SimpleFakeRegistry([desc])
        service = RouterService(strategy=RouterStrategy.RULE, skill_registry=registry)
        decision = service.decide({"message": "商标专利咨询问题需要处理呢"})
        self.assertIn("skip_clarification", decision.metadata)
        # RouteDecision must NOT have a top-level skip_clarification field
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(RouteDecision)}
        self.assertNotIn("skip_clarification", field_names)

    def test_no_new_top_level_fields_added(self) -> None:
        """RouteDecision must have exactly the frozen schema fields."""
        import dataclasses
        expected_fields = {
            "route_decision_id",
            "turn_id",
            "primary_skill",
            "confidence",
            "mode",
            "created_at",
            "supporting_skills",
            "gates_before",
            "gates_after",
            "required_tools",
            "matched_rule",
            "reason",
            "route_mismatch",
            "industry_context",
            "metadata",
        }
        actual_fields = {f.name for f in dataclasses.fields(RouteDecision)}
        self.assertEqual(actual_fields, expected_fields,
                         f"Field drift: extra={actual_fields - expected_fields}, "
                         f"missing={expected_fields - actual_fields}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
