"""Tests for the five-phase progress contract and event mapping table.

Covers FivePhase enum, PHASE_ORDER, EVENT_TYPE_TO_PHASE mapping,
PHASE_TO_UI_CONCEPT mapping, and forward-only transition validation.
"""

import unittest

from platform_contract import (
    EVENT_TYPE_TO_PHASE,
    PHASE_ORDER,
    PHASE_TO_UI_CONCEPT,
    FivePhase,
    UiConcept,
    get_phase_for_event_type,
    get_ui_concept_for_phase,
    is_valid_transition,
)


class FivePhaseProgressTests(unittest.TestCase):
    # 1. Enum has exactly 5 members with correct values
    def test_five_phase_enum_has_five_members(self):
        members = list(FivePhase)
        self.assertEqual(len(members), 5)
        values = [m.value for m in members]
        self.assertEqual(
            values,
            ["research", "intake", "retrieval", "draft", "review"],
        )

    # 2. PHASE_ORDER is the canonical forward-only progression
    def test_phase_order_is_correct(self):
        self.assertEqual(
            PHASE_ORDER,
            [
                FivePhase.RESEARCH,
                FivePhase.INTAKE,
                FivePhase.RETRIEVAL,
                FivePhase.DRAFT,
                FivePhase.REVIEW,
            ],
        )

    # 3. thought.delta maps to RESEARCH
    def test_thought_delta_maps_to_research(self):
        self.assertEqual(
            get_phase_for_event_type("thought.delta"),
            FivePhase.RESEARCH,
        )

    # 4. tool_call events map to RETRIEVAL
    def test_tool_call_events_map_to_retrieval(self):
        self.assertEqual(
            get_phase_for_event_type("tool_call.started"),
            FivePhase.RETRIEVAL,
        )
        self.assertEqual(
            get_phase_for_event_type("tool_call.delta"),
            FivePhase.RETRIEVAL,
        )
        self.assertEqual(
            get_phase_for_event_type("tool_call.completed"),
            FivePhase.RETRIEVAL,
        )

    # 5. message events map to DRAFT
    def test_message_events_map_to_draft(self):
        self.assertEqual(
            get_phase_for_event_type("message.delta"),
            FivePhase.DRAFT,
        )
        self.assertEqual(
            get_phase_for_event_type("message.completed"),
            FivePhase.DRAFT,
        )

    # 6. elicitation maps to INTAKE
    def test_elicitation_maps_to_intake(self):
        self.assertEqual(
            get_phase_for_event_type("elicitation.requested"),
            FivePhase.INTAKE,
        )

    # 7. artifact and citation map to REVIEW
    def test_artifact_and_citation_map_to_review(self):
        self.assertEqual(
            get_phase_for_event_type("artifact.created"),
            FivePhase.REVIEW,
        )
        self.assertEqual(
            get_phase_for_event_type("citation.recorded"),
            FivePhase.REVIEW,
        )

    # 8. Unmapped event types return None
    def test_unmapped_event_types_return_none(self):
        self.assertIsNone(get_phase_for_event_type("run.state_changed"))
        self.assertIsNone(get_phase_for_event_type("error"))
        self.assertIsNone(get_phase_for_event_type("phase.changed"))

    # 9. Phase-to-UI-concept mapping covers all 5 phases
    def test_phase_to_ui_concept_mapping(self):
        self.assertEqual(get_ui_concept_for_phase(FivePhase.RESEARCH), UiConcept.THINKING)
        self.assertEqual(get_ui_concept_for_phase(FivePhase.INTAKE), UiConcept.THINKING)
        self.assertEqual(get_ui_concept_for_phase(FivePhase.RETRIEVAL), UiConcept.TOOL)
        self.assertEqual(get_ui_concept_for_phase(FivePhase.DRAFT), UiConcept.STREAMING)
        self.assertEqual(get_ui_concept_for_phase(FivePhase.REVIEW), UiConcept.REVIEW)

    # 10. Forward transitions are valid
    def test_forward_transition_valid(self):
        self.assertTrue(is_valid_transition(FivePhase.RESEARCH, FivePhase.INTAKE))
        self.assertTrue(is_valid_transition(FivePhase.INTAKE, FivePhase.RETRIEVAL))
        self.assertTrue(is_valid_transition(FivePhase.RETRIEVAL, FivePhase.DRAFT))
        self.assertTrue(is_valid_transition(FivePhase.DRAFT, FivePhase.REVIEW))

    # 11. Backward transitions are invalid
    def test_backward_transition_invalid(self):
        self.assertFalse(is_valid_transition(FivePhase.DRAFT, FivePhase.RETRIEVAL))
        self.assertFalse(is_valid_transition(FivePhase.REVIEW, FivePhase.RESEARCH))

    # 12. Same-phase transition is valid
    def test_same_phase_transition_valid(self):
        self.assertTrue(is_valid_transition(FivePhase.RESEARCH, FivePhase.RESEARCH))

    # 13. All mapped event types have valid FivePhase values
    def test_all_mapped_event_types_have_valid_phases(self):
        for event_type, phase in EVENT_TYPE_TO_PHASE.items():
            self.assertIsInstance(
                phase,
                FivePhase,
                f"Event type {event_type!r} maps to {phase!r} which is not a FivePhase member",
            )

    # 14. All phases have a UI concept
    def test_all_phases_have_ui_concept(self):
        for phase, ui_concept in PHASE_TO_UI_CONCEPT.items():
            self.assertIsInstance(
                ui_concept,
                UiConcept,
                f"Phase {phase!r} maps to {ui_concept!r} which is not a UiConcept member",
            )

    # 15. Full phase progression: RESEARCH → INTAKE → RETRIEVAL → DRAFT → REVIEW
    def test_full_phase_progression(self):
        progression = [
            (FivePhase.RESEARCH, FivePhase.INTAKE),
            (FivePhase.INTAKE, FivePhase.RETRIEVAL),
            (FivePhase.RETRIEVAL, FivePhase.DRAFT),
            (FivePhase.DRAFT, FivePhase.REVIEW),
        ]
        for current, next_phase in progression:
            self.assertTrue(
                is_valid_transition(current, next_phase),
                f"Transition {current.value} → {next_phase.value} should be valid",
            )


if __name__ == "__main__":
    unittest.main()
