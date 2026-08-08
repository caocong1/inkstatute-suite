"""Tests for the hand-written TypeScript event type definitions.

The tests are stdlib-only Python. The TypeScript file is inspected as text
so the suite does not require a TypeScript toolchain.
"""

from __future__ import annotations

import unittest
from pathlib import Path

EVENTS_TS = (
    Path(__file__).resolve().parents[1] / "src" / "events.ts"
)


class EventTypesTsTests(unittest.TestCase):
    """Assert events.ts contains the expected interfaces and union type."""

    def setUp(self) -> None:
        self.assertTrue(EVENTS_TS.exists(), f"events.ts not found at {EVENTS_TS}")
        self.source = EVENTS_TS.read_text(encoding="utf-8")

    def test_contains_session_started_payload(self) -> None:
        self.assertIn("export interface SessionStartedPayload", self.source)

    def test_contains_elicitation_requested_payload(self) -> None:
        self.assertIn("export interface ElicitationRequestedPayload", self.source)

    def test_contains_run_event_envelope(self) -> None:
        self.assertIn("export interface RunEventEnvelope", self.source)

    def test_contains_unified_event_payload_union(self) -> None:
        self.assertIn("UnifiedEventPayload", self.source)

    def test_contains_five_phase_enum(self) -> None:
        self.assertIn(
            '"research" | "intake" | "retrieval" | "draft" | "review"',
            self.source,
        )

    def test_no_auto_approve_field(self) -> None:
        self.assertNotIn("auto_approve", self.source)

    def test_no_default_decision_field(self) -> None:
        self.assertNotIn("default_decision", self.source)

    def test_contains_all_13_payload_interfaces(self) -> None:
        expected = [
            "SessionStartedPayload",
            "MessageDeltaPayload",
            "MessageCompletedPayload",
            "ThoughtDeltaPayload",
            "ToolCallStartedPayload",
            "ToolCallDeltaPayload",
            "ToolCallCompletedPayload",
            "PlanUpdatedPayload",
            "PhaseChangedPayload",
            "ElicitationRequestedPayload",
            "PermissionRequestedPayload",
            "ArtifactCreatedPayload",
            "CitationRecordedPayload",
            "RunStateChangedPayload",
            "ErrorEventPayload",
        ]
        for name in expected:
            self.assertIn(f"export interface {name}", self.source)

    def test_contains_citation_record(self) -> None:
        self.assertIn("export interface CitationRecord", self.source)

    def test_contains_elicitation_option_and_question(self) -> None:
        self.assertIn("export interface ElicitationOption", self.source)
        self.assertIn("export interface ElicitationQuestion", self.source)

    def test_contains_all_8_arena_payload_interfaces(self) -> None:
        expected = [
            "ArenaWorkflowStartedPayload",
            "ArenaWorkflowCompletedPayload",
            "ArenaScoreRecordedPayload",
            "ArenaReviewCompletedPayload",
            "ArenaSynthesisStartedPayload",
            "ArenaSynthesisCompletedPayload",
            "ArenaAdversarialChallengeCompletedPayload",
            "ArenaEarlyStopTriggeredPayload",
        ]
        for name in expected:
            self.assertIn(f"export interface {name}", self.source)

    def test_contains_arena_mode_type(self) -> None:
        self.assertIn("export type ArenaMode", self.source)
        self.assertIn('"standard" | "self_score" | "arena_review" | "adversarial"', self.source)

    def test_unified_event_payload_union_includes_arena_types(self) -> None:
        arena_names = [
            "ArenaWorkflowStartedPayload",
            "ArenaWorkflowCompletedPayload",
            "ArenaScoreRecordedPayload",
            "ArenaReviewCompletedPayload",
            "ArenaSynthesisStartedPayload",
            "ArenaSynthesisCompletedPayload",
            "ArenaAdversarialChallengeCompletedPayload",
            "ArenaEarlyStopTriggeredPayload",
        ]
        for name in arena_names:
            self.assertIn(name, self.source)

    def test_contains_arena_contract_interfaces(self) -> None:
        expected = [
            "ArenaWorkflowConfig",
            "ArenaHandle",
            "ArenaStatus",
            "ArenaUserAction",
        ]
        for name in expected:
            self.assertIn(f"export interface {name}", self.source)


if __name__ == "__main__":
    unittest.main()
