"""Unit tests for the HYBRID strategy in RouterService.

Tests cover:
- Rule layer: classify_intent + registry lookup (confidence ≥0.8 → matched)
- Skill layer: exact skill_id lookup and search (confidence ≥0.8 → matched)
- Skill layer: ambiguous matches (confidence 0.5–0.8 → simple_qa)
- Model layer: ModelClassifierPort provides confidence
- No match + no model classifier (confidence <0.5 → zero_match, fallback)
- Legal-risk override: high-risk forced to Hermes regardless of confidence
- Legal-risk override with high confidence: still forced to Hermes
- No legal-risk classifier: normal cascade (no override)
- Confidence always populated (float 0.0–1.0)
- metadata["router_strategy"] == "hybrid"
- All modes are frozen RouteMode values
- Stateless behavior
- Existing RULE and SKILL strategies unchanged (regression)
"""

from __future__ import annotations

import unittest
from typing import Any, Mapping

from platform_contract import NeutralSkillDescriptor, RouteDecision

from inkstatute_router_service import (
    KeywordLegalRiskClassifier,
    ModelClassificationResult,
    RouterService,
    RouterStrategy,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


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
    """Fake SkillRegistryPort with configurable canned responses."""

    def __init__(
        self,
        skills_by_id: dict[str, NeutralSkillDescriptor] | None = None,
        search_results: dict[str, list[NeutralSkillDescriptor]] | None = None,
        default_search: list[NeutralSkillDescriptor] | None = None,
    ) -> None:
        self._skills_by_id = skills_by_id or {}
        self._search_results = search_results or {}
        self._default_search = default_search if default_search is not None else []

    def list_skills(self) -> list[NeutralSkillDescriptor]:
        return list(self._skills_by_id.values())

    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None:
        return self._skills_by_id.get(skill_id)

    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]:
        if category is not None and category in self._search_results:
            return list(self._search_results[category])
        if name_substring is not None and name_substring in self._search_results:
            return list(self._search_results[name_substring])
        return list(self._default_search)


class _FakeModelClassifier:
    """Fake ModelClassifierPort with a canned confidence and predicted skill."""

    def __init__(
        self,
        confidence: float = 0.0,
        predicted_skill: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._confidence = confidence
        self._predicted_skill = predicted_skill
        self._metadata = metadata or {}

    def classify(self, context: Mapping[str, Any]) -> ModelClassificationResult:
        return ModelClassificationResult(
            confidence=self._confidence,
            predicted_skill=self._predicted_skill,
            metadata=dict(self._metadata),
        )


# ---------------------------------------------------------------------------
# Rule layer tests
# ---------------------------------------------------------------------------


class HybridRuleLayerTests(unittest.TestCase):
    """Verify the Rule layer of the HYBRID cascade."""

    def test_hybrid_rule_match_with_registry(self) -> None:
        """Rule match + registry hit → confidence=0.9, mode=matched."""
        descriptor = _make_descriptor(
            "test/compliance_review",
            name="compliance_review",
            required_tool_refs=["law_search"],
            metadata={"intent": "review"},
        )
        fake = _FakeSkillRegistry(
            skills_by_id={"test/compliance_review": descriptor},
            search_results={"review": [descriptor]},
        )
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
        )
        decision = service.decide({"message": "请审查这份合同"})

        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "test/compliance_review")
        self.assertAlmostEqual(decision.confidence, 0.9)
        self.assertEqual(decision.metadata["router_strategy"], "hybrid")
        self.assertEqual(decision.metadata["cascade_stage"], "rule")
        self.assertEqual(decision.metadata["classified_intent"], "review")

    def test_hybrid_rule_match_no_registry(self) -> None:
        """Rule match but no registry → confidence=0.6, mode=simple_qa (clarify)."""
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=None,
        )
        decision = service.decide({"message": "请问什么是合同"})

        self.assertEqual(decision.mode, "simple_qa")
        self.assertAlmostEqual(decision.confidence, 0.6)
        self.assertIsNone(decision.primary_skill)
        self.assertTrue(decision.metadata["clarification_needed"])


# ---------------------------------------------------------------------------
# Skill layer tests
# ---------------------------------------------------------------------------


class HybridSkillLayerTests(unittest.TestCase):
    """Verify the Skill layer of the HYBRID cascade."""

    def test_hybrid_skill_exact_match(self) -> None:
        """skill_id lookup → confidence=1.0, mode=matched."""
        descriptor = _make_descriptor(
            "test/case_qa",
            name="Case QA",
            required_tool_refs=["tool_a"],
        )
        fake = _FakeSkillRegistry(skills_by_id={"test/case_qa": descriptor})
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
        )
        decision = service.decide({"skill_id": "test/case_qa"})

        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "test/case_qa")
        self.assertAlmostEqual(decision.confidence, 1.0)
        self.assertEqual(decision.metadata["cascade_stage"], "skill")
        self.assertEqual(decision.metadata["skill_lookup_method"], "get_skill")

    def test_hybrid_skill_search_single_match(self) -> None:
        """Search single match → confidence=0.85, mode=matched.

        Uses a message that does NOT trigger intent classification, so the
        Rule layer produces no intent and the cascade falls through to the
        Skill layer's name-substring search.
        """
        descriptor = _make_descriptor(
            "test/contract_drafting",
            name="Contract Drafting",
            required_tool_refs=["docx_tool"],
        )
        fake = _FakeSkillRegistry(
            search_results={"Contract": [descriptor]},
            default_search=[],
        )
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
        )
        decision = service.decide({"message": "Contract"})

        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "test/contract_drafting")
        self.assertAlmostEqual(decision.confidence, 0.85)
        self.assertEqual(decision.metadata["cascade_stage"], "skill")

    def test_hybrid_skill_search_ambiguous(self) -> None:
        """Multiple matches → confidence=0.6, mode=simple_qa (clarify).

        Uses a message that does NOT trigger intent classification, so the
        Rule layer produces no intent and the cascade falls through to the
        Skill layer's name-substring search with multiple results.
        """
        descriptors = [
            _make_descriptor("test/qa_1", name="QA 1"),
            _make_descriptor("test/qa_2", name="QA 2"),
            _make_descriptor("test/qa_3", name="QA 3"),
        ]
        fake = _FakeSkillRegistry(
            search_results={"Case": descriptors},
            default_search=[],
        )
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
        )
        decision = service.decide({"message": "Case"})

        self.assertEqual(decision.mode, "simple_qa")
        self.assertAlmostEqual(decision.confidence, 0.6)
        self.assertIsNone(decision.primary_skill)
        self.assertEqual(len(decision.supporting_skills), 3)
        self.assertTrue(decision.metadata["clarification_needed"])
        self.assertEqual(decision.metadata["ambiguous_matches"], 3)


# ---------------------------------------------------------------------------
# Model layer tests
# ---------------------------------------------------------------------------


class HybridModelLayerTests(unittest.TestCase):
    """Verify the Model layer of the HYBRID cascade."""

    def test_hybrid_model_classifier_high_confidence(self) -> None:
        """Model classifier returns 0.9 → mode=matched."""
        model = _FakeModelClassifier(confidence=0.9, predicted_skill="test/custom")
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=None,
            model_classifier=model,
        )
        decision = service.decide({"message": "xyz random"})

        self.assertEqual(decision.mode, "matched")
        self.assertAlmostEqual(decision.confidence, 0.9)
        self.assertEqual(decision.primary_skill, "test/custom")
        self.assertEqual(decision.metadata["cascade_stage"], "model")
        self.assertTrue(decision.metadata["model_classification"])

    def test_hybrid_model_classifier_medium_confidence(self) -> None:
        """Model classifier returns 0.6 → mode=simple_qa (clarify)."""
        model = _FakeModelClassifier(confidence=0.6)
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=None,
            model_classifier=model,
        )
        decision = service.decide({"message": "xyz random"})

        self.assertEqual(decision.mode, "simple_qa")
        self.assertAlmostEqual(decision.confidence, 0.6)
        self.assertTrue(decision.metadata["clarification_needed"])

    def test_hybrid_model_classifier_low_confidence(self) -> None:
        """Model classifier returns 0.3 → mode=zero_match (fallback)."""
        model = _FakeModelClassifier(confidence=0.3)
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=None,
            model_classifier=model,
        )
        decision = service.decide({"message": "xyz random"})

        self.assertEqual(decision.mode, "zero_match")
        self.assertAlmostEqual(decision.confidence, 0.3)
        self.assertTrue(decision.metadata["fallback_to_hermes"])


# ---------------------------------------------------------------------------
# No match tests
# ---------------------------------------------------------------------------


class HybridNoMatchTests(unittest.TestCase):
    """Verify fallback when no layer matches."""

    def test_hybrid_no_match_no_model(self) -> None:
        """No rule/skill match, no model classifier → confidence=0.0, mode=zero_match."""
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=None,
        )
        decision = service.decide({"message": "xyz random"})

        self.assertEqual(decision.mode, "zero_match")
        self.assertAlmostEqual(decision.confidence, 0.0)
        self.assertIsNone(decision.primary_skill)
        self.assertTrue(decision.metadata["fallback_to_hermes"])
        self.assertEqual(decision.metadata["cascade_stage"], "no_match")

    def test_hybrid_no_match_with_registry(self) -> None:
        """No rule/skill match with registry configured → confidence=0.0, fallback."""
        fake = _FakeSkillRegistry(default_search=[])
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
        )
        decision = service.decide({"message": "xyz random"})

        self.assertEqual(decision.mode, "zero_match")
        self.assertAlmostEqual(decision.confidence, 0.0)
        self.assertTrue(decision.metadata["fallback_to_hermes"])


# ---------------------------------------------------------------------------
# Legal-risk override tests
# ---------------------------------------------------------------------------


class HybridLegalRiskOverrideTests(unittest.TestCase):
    """Verify the legal-risk classifier forces high-risk to Hermes."""

    def test_hybrid_high_risk_forced_to_hermes(self) -> None:
        """High-risk legal query → forced to Hermes regardless of confidence."""
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=None,
            legal_risk_classifier=KeywordLegalRiskClassifier(),
        )
        decision = service.decide({"message": "我要提起诉讼"})

        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "hermes")
        self.assertTrue(decision.metadata["forced_to_hermes"])
        self.assertEqual(decision.metadata["cascade_stage"], "legal_risk_override")
        self.assertIn("legal_risk_assessment", decision.metadata)
        self.assertEqual(decision.metadata["legal_risk_assessment"]["risk_level"], "high")
        self.assertTrue(decision.metadata["legal_risk_assessment"]["is_high_risk"])

    def test_hybrid_high_risk_overrides_high_confidence(self) -> None:
        """High-risk query that would normally route to a skill → forced to Hermes."""
        descriptor = _make_descriptor(
            "test/compliance_review",
            name="compliance_review",
            required_tool_refs=["law_search"],
            metadata={"intent": "review"},
        )
        fake = _FakeSkillRegistry(
            skills_by_id={"test/compliance_review": descriptor},
            search_results={"review": [descriptor]},
        )
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
            legal_risk_classifier=KeywordLegalRiskClassifier(),
        )
        # "合规审查" is both a review-intent keyword AND a high-risk keyword
        decision = service.decide({"message": "请进行合规审查"})

        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "hermes")
        self.assertTrue(decision.metadata["forced_to_hermes"])
        # Confidence is still populated (from the cascade)
        self.assertGreater(decision.confidence, 0.0)

    def test_hybrid_high_risk_with_low_confidence(self) -> None:
        """High-risk query with no cascade match → still forced to Hermes."""
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=None,
            legal_risk_classifier=KeywordLegalRiskClassifier(),
        )
        decision = service.decide({"message": "诉讼"})

        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "hermes")
        self.assertTrue(decision.metadata["forced_to_hermes"])

    def test_hybrid_no_legal_risk_classifier(self) -> None:
        """legal_risk_classifier=None → no override, normal cascade."""
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=None,
            legal_risk_classifier=None,
        )
        decision = service.decide({"message": "诉讼"})

        # No override — "诉讼" doesn't match any intent keyword, so it falls
        # through to zero_match (fallback).
        self.assertNotIn("forced_to_hermes", decision.metadata)
        self.assertNotIn("legal_risk_assessment", decision.metadata)

    def test_hybrid_low_risk_no_override(self) -> None:
        """Low-risk query → no legal-risk override, normal cascade."""
        descriptor = _make_descriptor(
            "test/legal_qa",
            name="legal_qa",
            required_tool_refs=["law_search"],
            metadata={"intent": "factual_qa"},
        )
        fake = _FakeSkillRegistry(
            skills_by_id={"test/legal_qa": descriptor},
            search_results={"factual_qa": [descriptor]},
        )
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
            legal_risk_classifier=KeywordLegalRiskClassifier(),
        )
        decision = service.decide({"message": "请问什么是合同"})

        # "合同" is medium-risk, not high-risk → no override
        self.assertNotIn("forced_to_hermes", decision.metadata)
        self.assertEqual(decision.mode, "matched")
        self.assertEqual(decision.primary_skill, "test/legal_qa")
        # Legal risk assessment is still recorded in metadata
        self.assertIn("legal_risk_assessment", decision.metadata)
        self.assertEqual(decision.metadata["legal_risk_assessment"]["risk_level"], "medium")


# ---------------------------------------------------------------------------
# Confidence and metadata invariant tests
# ---------------------------------------------------------------------------


class HybridConfidenceInvariantTests(unittest.TestCase):
    """Verify confidence is always populated for hybrid decisions."""

    def test_hybrid_confidence_always_populated(self) -> None:
        """All hybrid decisions have confidence as float 0.0–1.0."""
        descriptor = _make_descriptor(
            "test/legal_qa",
            name="legal_qa",
            metadata={"intent": "factual_qa"},
        )
        fake = _FakeSkillRegistry(
            skills_by_id={"test/legal_qa": descriptor},
            search_results={"factual_qa": [descriptor]},
        )
        model = _FakeModelClassifier(confidence=0.7)
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
            model_classifier=model,
            legal_risk_classifier=KeywordLegalRiskClassifier(),
        )
        contexts = [
            {"message": "请问什么是合同"},  # rule match
            {"skill_id": "test/legal_qa"},  # skill exact
            {"message": "xyz random"},  # model fallback
            {"message": "诉讼"},  # high-risk override
            {"message": "hello world"},  # no match
        ]
        for ctx in contexts:
            decision = service.decide(ctx)
            self.assertIsInstance(decision.confidence, float)
            self.assertGreaterEqual(decision.confidence, 0.0)
            self.assertLessEqual(decision.confidence, 1.0)

    def test_hybrid_metadata_router_strategy(self) -> None:
        """metadata['router_strategy'] == 'hybrid' for all hybrid decisions."""
        service = RouterService(strategy=RouterStrategy.HYBRID)
        contexts = [
            {"message": "请问什么是合同"},
            {"message": "xyz random"},
            {"message": ""},
        ]
        for ctx in contexts:
            decision = service.decide(ctx)
            self.assertEqual(decision.metadata["router_strategy"], "hybrid")

    def test_hybrid_metadata_router_service_version(self) -> None:
        """metadata['router_service_version'] is present."""
        service = RouterService(strategy=RouterStrategy.HYBRID)
        decision = service.decide({"message": "test"})
        self.assertIn("router_service_version", decision.metadata)


# ---------------------------------------------------------------------------
# Frozen mode and stateless tests
# ---------------------------------------------------------------------------


class HybridFrozenModeTests(unittest.TestCase):
    """Verify all hybrid modes are frozen RouteMode values."""

    def test_hybrid_mode_is_frozen_value(self) -> None:
        valid_modes = {"matched", "simple_qa", "skipped", "zero_match"}
        descriptor = _make_descriptor(
            "test/skill_1",
            name="Skill 1",
            metadata={"intent": "drafting"},
        )
        fake = _FakeSkillRegistry(
            skills_by_id={"test/skill_1": descriptor},
            search_results={"drafting": [descriptor]},
        )
        model = _FakeModelClassifier(confidence=0.6)
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
            model_classifier=model,
            legal_risk_classifier=KeywordLegalRiskClassifier(),
        )
        contexts = [
            {"skill_id": "test/skill_1"},
            {"message": "请起草一份合同"},
            {"message": "xyz random"},
            {"message": "诉讼"},
            {"message": "hello"},
        ]
        for ctx in contexts:
            decision = service.decide(ctx)
            self.assertIsInstance(decision, RouteDecision)
            self.assertIn(decision.mode, valid_modes)


class HybridStatelessTests(unittest.TestCase):
    """Verify HYBRID strategy is stateless."""

    def test_hybrid_strategy_is_stateless(self) -> None:
        """Two calls with the same context must return equal RouteDecision objects."""
        descriptor = _make_descriptor(
            "test/case_qa",
            name="Case QA",
            metadata={"intent": "factual_qa"},
        )
        fake = _FakeSkillRegistry(
            skills_by_id={"test/case_qa": descriptor},
            search_results={"factual_qa": [descriptor]},
        )
        service = RouterService(
            strategy=RouterStrategy.HYBRID,
            skill_registry=fake,
            legal_risk_classifier=KeywordLegalRiskClassifier(),
        )
        context = {"message": "请问什么是合同", "turn_id": "turn-001"}
        decision1 = service.decide(context)
        decision2 = service.decide(context)
        self.assertEqual(decision1, decision2)


# ---------------------------------------------------------------------------
# Regression tests — existing strategies unchanged
# ---------------------------------------------------------------------------


class HybridRegressionTests(unittest.TestCase):
    """Verify existing RULE and SKILL strategies continue to work unchanged."""

    def test_existing_rule_strategy_unchanged(self) -> None:
        """RULE strategy still produces mode=matched with confidence=0.7."""
        descriptor = _make_descriptor(
            "test/compliance_review",
            name="compliance_review",
            required_tool_refs=["law_search"],
            metadata={"intent": "review"},
        )
        fake = _FakeSkillRegistry(
            skills_by_id={"test/compliance_review": descriptor},
            search_results={"review": [descriptor]},
        )
        service = RouterService(
            strategy=RouterStrategy.RULE,
            skill_registry=fake,
            # HYBRID-specific params should be ignored for RULE strategy
            legal_risk_classifier=KeywordLegalRiskClassifier(),
            model_classifier=_FakeModelClassifier(confidence=0.99),
        )
        decision = service.decide({"message": "请审查这份合同"})
        self.assertEqual(decision.mode, "matched")
        self.assertAlmostEqual(decision.confidence, 0.7)
        self.assertEqual(decision.metadata["router_strategy"], "rule")

    def test_existing_skill_strategy_unchanged(self) -> None:
        """SKILL strategy still produces mode=matched with confidence=1.0."""
        descriptor = _make_descriptor(
            "test/case_qa",
            name="Case QA",
            required_tool_refs=["tool_a"],
        )
        fake = _FakeSkillRegistry(skills_by_id={"test/case_qa": descriptor})
        service = RouterService(
            strategy=RouterStrategy.SKILL,
            skill_registry=fake,
            legal_risk_classifier=KeywordLegalRiskClassifier(),
            model_classifier=_FakeModelClassifier(confidence=0.99),
        )
        decision = service.decide({"skill_id": "test/case_qa"})
        self.assertEqual(decision.mode, "matched")
        self.assertAlmostEqual(decision.confidence, 1.0)
        self.assertEqual(decision.metadata["router_strategy"], "skill")

    def test_existing_rule_strategy_zero_match_unchanged(self) -> None:
        """RULE strategy with no match → zero_match, confidence=0.0."""
        service = RouterService(strategy=RouterStrategy.RULE)
        decision = service.decide({"message": "xyz random"})
        self.assertEqual(decision.mode, "zero_match")
        self.assertAlmostEqual(decision.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
