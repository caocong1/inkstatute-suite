"""Tests for review.py — ReviewFinding, ConfidenceLevel, SeverityLevel, parsing.

Covers: enum membership, frozen slotted dataclass shape, finding-block
parsing with defaults, numeric percentage rejection, JSON round-trip
compatibility with ``ArenaReviewCompletedPayload.findings``.
"""

from __future__ import annotations

import dataclasses
import unittest

from arena_engine.review import (
    ConfidenceLevel,
    ReviewFinding,
    SeverityLevel,
    _parse_review_findings,
)


class ReviewFindingTests(unittest.TestCase):
    """Cover all 9 behaviors from Plan 108-01 Task 1."""

    # ------------------------------------------------------------------
    # Test 1: ConfidenceLevel enum has exactly 3 categorical members
    # ------------------------------------------------------------------

    def test_confidence_level_has_three_categorical_members(self) -> None:
        members = list(ConfidenceLevel)
        self.assertEqual(len(members), 3)
        names = {m.name for m in members}
        self.assertEqual(names, {"CERTAIN", "LIKELY", "POSSIBLE"})
        # Values are categorical strings, not numeric.
        for m in members:
            self.assertIsInstance(m.value, str)
            self.assertFalse(m.value.endswith("%"))

    # ------------------------------------------------------------------
    # Test 2: SeverityLevel enum has exactly 3 members
    # ------------------------------------------------------------------

    def test_severity_level_has_three_members(self) -> None:
        members = list(SeverityLevel)
        self.assertEqual(len(members), 3)
        names = {m.name for m in members}
        self.assertEqual(names, {"HIGH", "MEDIUM", "LOW"})

    # ------------------------------------------------------------------
    # Test 3: ReviewFinding is frozen slotted dataclass with correct fields
    # ------------------------------------------------------------------

    def test_review_finding_is_frozen_slotted_dataclass(self) -> None:
        # frozen
        finding = ReviewFinding(
            description="test",
            confidence=ConfidenceLevel.LIKELY,
            severity=SeverityLevel.MEDIUM,
            confirmed=False,
            source_slot="slot-1",
            reviewed_slot="slot-0",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            finding.description = "changed"  # type: ignore[misc]

        # slots
        self.assertTrue(hasattr(ReviewFinding, "__slots__"))
        self.assertNotIn("__dict__", dir(ReviewFinding))

        # fields
        field_names = {f.name for f in dataclasses.fields(ReviewFinding)}
        self.assertEqual(
            field_names,
            {
                "description",
                "confidence",
                "severity",
                "confirmed",
                "source_slot",
                "reviewed_slot",
                "metadata",
            },
        )

    # ------------------------------------------------------------------
    # Test 4: parse a full finding block
    # ------------------------------------------------------------------

    def test_parse_full_finding_block(self) -> None:
        content = (
            "[FINDING]\n"
            "description: Missing citation\n"
            "confidence: Certain\n"
            "severity: High\n"
            "confirmed: true\n"
            "[/FINDING]"
        )
        findings = _parse_review_findings(
            content=content,
            source_slot="slot-1",
            reviewed_slot="slot-0",
        )
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.description, "Missing citation")
        self.assertEqual(f.confidence, ConfidenceLevel.CERTAIN)
        self.assertEqual(f.severity, SeverityLevel.HIGH)
        self.assertTrue(f.confirmed)
        self.assertEqual(f.source_slot, "slot-1")
        self.assertEqual(f.reviewed_slot, "slot-0")

    # ------------------------------------------------------------------
    # Test 5: no [FINDING] blocks → empty list, no crash
    # ------------------------------------------------------------------

    def test_parse_no_finding_blocks_returns_empty(self) -> None:
        content = "This is just regular agent output with no findings."
        findings = _parse_review_findings(
            content=content,
            source_slot="slot-1",
            reviewed_slot="slot-0",
        )
        self.assertEqual(findings, [])

    # ------------------------------------------------------------------
    # Test 6: missing fields default to POSSIBLE/MEDIUM/False
    # ------------------------------------------------------------------

    def test_missing_fields_use_defaults(self) -> None:
        content = (
            "[FINDING]\n"
            "description: Some issue\n"
            "[/FINDING]"
        )
        findings = _parse_review_findings(
            content=content,
            source_slot="slot-1",
            reviewed_slot="slot-0",
        )
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.confidence, ConfidenceLevel.POSSIBLE)
        self.assertEqual(f.severity, SeverityLevel.MEDIUM)
        self.assertFalse(f.confirmed)

    # ------------------------------------------------------------------
    # Test 7: numeric confidence "67%" rejected → falls back to POSSIBLE
    # ------------------------------------------------------------------

    def test_numeric_confidence_rejected(self) -> None:
        content = (
            "[FINDING]\n"
            "description: Numeric confidence test\n"
            "confidence: 67%\n"
            "severity: Low\n"
            "[/FINDING]"
        )
        findings = _parse_review_findings(
            content=content,
            source_slot="slot-1",
            reviewed_slot="slot-0",
        )
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.confidence, ConfidenceLevel.POSSIBLE)

    # ------------------------------------------------------------------
    # Test 8: to_json() output compatible with ArenaReviewCompletedPayload.findings
    # ------------------------------------------------------------------

    def test_to_json_compatible_with_payload(self) -> None:
        finding = ReviewFinding(
            description="Missing citation",
            confidence=ConfidenceLevel.CERTAIN,
            severity=SeverityLevel.HIGH,
            confirmed=True,
            source_slot="slot-1",
            reviewed_slot="slot-0",
            metadata={"round": 1},
        )
        d = finding.to_json()
        expected_keys = {
            "description",
            "confidence",
            "severity",
            "confirmed",
            "source_slot",
            "reviewed_slot",
            "metadata",
        }
        self.assertEqual(set(d.keys()), expected_keys)
        self.assertIsInstance(d["confidence"], str)
        self.assertIsInstance(d["severity"], str)
        self.assertEqual(d["confidence"], "Certain")
        self.assertEqual(d["severity"], "High")
        self.assertTrue(d["confirmed"])

    # ------------------------------------------------------------------
    # Test 9: from_json round-trip
    # ------------------------------------------------------------------

    def test_from_json_round_trip(self) -> None:
        original = ReviewFinding(
            description="Missing citation",
            confidence=ConfidenceLevel.LIKELY,
            severity=SeverityLevel.MEDIUM,
            confirmed=False,
            source_slot="slot-2",
            reviewed_slot="slot-1",
            metadata={"round": 2, "tag": "review"},
        )
        round_tripped = ReviewFinding.from_json(original.to_json())
        self.assertEqual(round_tripped, original)


if __name__ == "__main__":
    unittest.main()
