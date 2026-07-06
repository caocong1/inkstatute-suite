"""Tests for the legal-risk classifier (KeywordLegalRiskClassifier).

Tests cover:
- High-risk Chinese keyword detection (e.g. 诉讼, 合规审查)
- High-risk English keyword detection (e.g. litigation, criminal)
- Medium-risk keyword detection (e.g. 合同, contract)
- Low-risk text with no legal keywords
- None and empty message handling
- LegalRiskAssessment is a frozen dataclass
- Evidence list is populated with matched keywords
- KeywordLegalRiskClassifier satisfies LegalRiskClassifierPort (structural)
"""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from inkstatute_router_service import (
    KeywordLegalRiskClassifier,
    LegalRiskAssessment,
    LegalRiskClassifierPort,
    LegalRiskLevel,
)


class TestKeywordLegalRiskClassifier(unittest.TestCase):
    """Verify KeywordLegalRiskClassifier classification behavior."""

    def setUp(self) -> None:
        self.classifier = KeywordLegalRiskClassifier()

    def test_high_risk_chinese_keyword(self) -> None:
        """Chinese high-risk keyword '诉讼' → is_high_risk=True, risk_level='high'."""
        result = self.classifier.classify("我要提起诉讼")
        self.assertTrue(result.is_high_risk)
        self.assertEqual(result.risk_level, "high")
        self.assertIn("诉讼", result.evidence)

    def test_high_risk_english_keyword(self) -> None:
        """English high-risk keyword 'litigation' → is_high_risk=True."""
        result = self.classifier.classify("I need help with litigation")
        self.assertTrue(result.is_high_risk)
        self.assertEqual(result.risk_level, "high")
        self.assertIn("litigation", result.evidence)

    def test_high_risk_english_keyword_case_insensitive(self) -> None:
        """English high-risk keyword matching is case-insensitive."""
        result = self.classifier.classify("CRIMINAL charges")
        self.assertTrue(result.is_high_risk)
        self.assertEqual(result.risk_level, "high")

    def test_high_risk_compliance_review(self) -> None:
        """Chinese '合规审查' → high-risk."""
        result = self.classifier.classify("请进行合规审查")
        self.assertTrue(result.is_high_risk)
        self.assertEqual(result.risk_level, "high")

    def test_medium_risk_chinese_keyword(self) -> None:
        """Chinese medium-risk keyword '合同' → is_high_risk=False, risk_level='medium'."""
        result = self.classifier.classify("这是一份合同")
        self.assertFalse(result.is_high_risk)
        self.assertEqual(result.risk_level, "medium")
        self.assertIn("合同", result.evidence)

    def test_medium_risk_english_keyword(self) -> None:
        """English medium-risk keyword 'contract' → risk_level='medium'."""
        result = self.classifier.classify("review this contract please")
        self.assertFalse(result.is_high_risk)
        self.assertEqual(result.risk_level, "medium")

    def test_low_risk_text(self) -> None:
        """Non-legal text → risk_level='low', is_high_risk=False, evidence empty."""
        result = self.classifier.classify("hello world how are you")
        self.assertFalse(result.is_high_risk)
        self.assertEqual(result.risk_level, "low")
        self.assertEqual(result.evidence, [])

    def test_none_message(self) -> None:
        """None message → risk_level='low', is_high_risk=False."""
        result = self.classifier.classify(None)
        self.assertFalse(result.is_high_risk)
        self.assertEqual(result.risk_level, "low")
        self.assertEqual(result.evidence, [])

    def test_empty_message(self) -> None:
        """Empty string → risk_level='low', is_high_risk=False."""
        result = self.classifier.classify("")
        self.assertFalse(result.is_high_risk)
        self.assertEqual(result.risk_level, "low")
        self.assertEqual(result.evidence, [])

    def test_high_risk_takes_precedence_over_medium(self) -> None:
        """Message with both high and medium keywords → high-risk."""
        result = self.classifier.classify("这份合同的诉讼问题")
        self.assertTrue(result.is_high_risk)
        self.assertEqual(result.risk_level, "high")

    def test_evidence_list_populated(self) -> None:
        """Evidence list contains all matched high-risk keywords."""
        result = self.classifier.classify("诉讼和仲裁都需要")
        self.assertTrue(result.is_high_risk)
        self.assertIn("诉讼", result.evidence)
        self.assertIn("仲裁", result.evidence)

    def test_metadata_contains_matched_keywords(self) -> None:
        """metadata['matched_keywords'] contains the matched keywords."""
        result = self.classifier.classify("诉讼")
        self.assertTrue(result.is_high_risk)
        self.assertIn("matched_keywords", result.metadata)
        self.assertIn("诉讼", result.metadata["matched_keywords"])


class TestLegalRiskAssessmentFrozen(unittest.TestCase):
    """Verify LegalRiskAssessment is a frozen dataclass."""

    def test_assessment_is_frozen(self) -> None:
        """LegalRiskAssessment attributes cannot be mutated."""
        assessment = LegalRiskAssessment(
            risk_level="high",
            is_high_risk=True,
            evidence=["诉讼"],
        )
        with self.assertRaises(FrozenInstanceError):
            assessment.is_high_risk = False  # type: ignore[misc]

    def test_assessment_default_evidence_empty(self) -> None:
        """Default evidence is an empty list."""
        assessment = LegalRiskAssessment(
            risk_level="low",
            is_high_risk=False,
        )
        self.assertEqual(assessment.evidence, [])

    def test_assessment_default_metadata_empty(self) -> None:
        """Default metadata is an empty dict."""
        assessment = LegalRiskAssessment(
            risk_level="low",
            is_high_risk=False,
        )
        self.assertEqual(assessment.metadata, {})


class TestLegalRiskLevelEnum(unittest.TestCase):
    """Verify LegalRiskLevel enum values."""

    def test_low_value(self) -> None:
        self.assertEqual(LegalRiskLevel.LOW.value, "low")

    def test_medium_value(self) -> None:
        self.assertEqual(LegalRiskLevel.MEDIUM.value, "medium")

    def test_high_value(self) -> None:
        self.assertEqual(LegalRiskLevel.HIGH.value, "high")


class TestStructuralProtocolConformance(unittest.TestCase):
    """Verify KeywordLegalRiskClassifier satisfies LegalRiskClassifierPort."""

    def test_classifier_satisfies_protocol(self) -> None:
        """KeywordLegalRiskClassifier has the classify method required by the Protocol."""
        classifier: LegalRiskClassifierPort = KeywordLegalRiskClassifier()
        result = classifier.classify("诉讼")
        self.assertIsInstance(result, LegalRiskAssessment)


if __name__ == "__main__":
    unittest.main()
