"""Tests for ColdStartInterviewOrchestrator and interview definitions.

Covers PROF-03 (cold-start interview via ``elicitation.requested``).

Verifies:
- ``start`` returns initial state
- ``get_current_elicitation`` returns valid payload with 2-4 questions
- ``submit_answers`` advances step
- ``is_complete`` returns False mid-interview and True after all 5 steps
- ``finalize`` creates a ``PracticeProfile`` with ``temporary_mode=False``
  and stores it
- ``finalize`` raises on incomplete interview
- ``validate_question_count`` passes for all steps
- Full 5-step flow end-to-end
- ``interrupt_id`` is deterministic and unique per step
"""

from __future__ import annotations

import dataclasses
import unittest

from platform_contract.elicitation import validate_question_count
from platform_contract.unified_events import (
    ElicitationQuestion,
    ElicitationRequestedPayload,
)

from inkstatute_practice_profile import (
    COMMERCIAL_LEGAL_INTERVIEW_STEPS,
    ColdStartInterviewOrchestrator,
    InMemoryPracticeProfileStore,
    InterviewState,
    InterviewStep,
    PracticeProfile,
)


# ---------------------------------------------------------------------------
# InterviewStep / InterviewState dataclass tests
# ---------------------------------------------------------------------------


class InterviewStepDataclassTests(unittest.TestCase):
    def test_is_frozen_dataclass_with_slots(self) -> None:
        self.assertTrue(dataclasses.is_dataclass(InterviewStep))
        step = InterviewStep(
            step_id="test", intro="intro",
            questions=[ElicitationQuestion(id="q1", question="a")],
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            step.step_id = "other"  # type: ignore[misc]

    def test_has_three_fields(self) -> None:
        field_names = {f.name for f in dataclasses.fields(InterviewStep)}
        self.assertEqual(field_names, {"step_id", "intro", "questions"})


class InterviewStateDataclassTests(unittest.TestCase):
    def test_is_frozen_dataclass_with_slots(self) -> None:
        self.assertTrue(dataclasses.is_dataclass(InterviewState))
        state = InterviewState(tenant_id="t1", plugin="commercial-legal")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            state.tenant_id = "t2"  # type: ignore[misc]

    def test_has_five_fields(self) -> None:
        field_names = {f.name for f in dataclasses.fields(InterviewState)}
        self.assertEqual(
            field_names,
            {"tenant_id", "plugin", "current_step_index",
             "completed_steps", "answers"},
        )

    def test_defaults(self) -> None:
        state = InterviewState(tenant_id="t1", plugin="commercial-legal")
        self.assertEqual(state.current_step_index, 0)
        self.assertEqual(state.completed_steps, [])
        self.assertEqual(state.answers, {})


# ---------------------------------------------------------------------------
# COMMERCIAL_LEGAL_INTERVIEW_STEPS definition tests
# ---------------------------------------------------------------------------


class InterviewDefinitionsTests(unittest.TestCase):
    def test_has_exactly_five_steps(self) -> None:
        self.assertEqual(len(COMMERCIAL_LEGAL_INTERVIEW_STEPS), 5)

    def test_step_ids_in_order(self) -> None:
        step_ids = [s.step_id for s in COMMERCIAL_LEGAL_INTERVIEW_STEPS]
        self.assertEqual(
            step_ids,
            ["identity-team", "review-stance", "escalation-rules",
             "document-style", "jurisdiction-profile"],
        )

    def test_each_step_has_2_to_4_questions(self) -> None:
        for step in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            n = len(step.questions)
            self.assertGreaterEqual(n, 2, f"{step.step_id} has too few questions")
            self.assertLessEqual(n, 4, f"{step.step_id} has too many questions")

    def test_validate_question_count_passes_for_all_steps(self) -> None:
        for step in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            # Should not raise
            validate_question_count(step.questions)

    def test_unique_question_ids_within_step(self) -> None:
        for step in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            ids = [q.id for q in step.questions]
            self.assertEqual(
                len(ids), len(set(ids)),
                f"Duplicate question IDs in {step.step_id}: {ids}",
            )

    def test_step1_identity_team_has_4_questions(self) -> None:
        step = COMMERCIAL_LEGAL_INTERVIEW_STEPS[0]
        self.assertEqual(step.step_id, "identity-team")
        self.assertEqual(len(step.questions), 4)

    def test_step1_has_company_name_free_text(self) -> None:
        step = COMMERCIAL_LEGAL_INTERVIEW_STEPS[0]
        q = next(q for q in step.questions if q.id == "identity-team.company_name")
        self.assertEqual(q.options, [])
        self.assertFalse(q.allow_multiple)

    def test_step1_has_entity_type_with_options(self) -> None:
        step = COMMERCIAL_LEGAL_INTERVIEW_STEPS[0]
        q = next(q for q in step.questions if q.id == "identity-team.entity_type")
        self.assertTrue(len(q.options) >= 4)
        values = [opt.value for opt in q.options]
        self.assertIn("有限责任公司", values)
        self.assertIn("股份有限公司", values)

    def test_step2_review_stance_has_2_to_4_questions(self) -> None:
        step = COMMERCIAL_LEGAL_INTERVIEW_STEPS[1]
        self.assertEqual(step.step_id, "review-stance")
        self.assertGreaterEqual(len(step.questions), 2)
        self.assertLessEqual(len(step.questions), 4)

    def test_step2_has_risk_appetite_with_options(self) -> None:
        step = COMMERCIAL_LEGAL_INTERVIEW_STEPS[1]
        q = next(q for q in step.questions if q.id == "review-stance.risk_appetite")
        values = [opt.value for opt in q.options]
        self.assertIn("保守型", values)
        self.assertIn("平衡型", values)
        self.assertIn("进取型", values)

    def test_step3_has_auto_escalation_multi_select(self) -> None:
        step = COMMERCIAL_LEGAL_INTERVIEW_STEPS[2]
        q = next(
            q for q in step.questions
            if q.id == "escalation-rules.auto_escalation_triggers"
        )
        self.assertTrue(q.allow_multiple)
        self.assertTrue(len(q.options) >= 2)

    def test_step4_has_revision_tone_with_options(self) -> None:
        step = COMMERCIAL_LEGAL_INTERVIEW_STEPS[3]
        q = next(
            q for q in step.questions
            if q.id == "document-style.revision_tone"
        )
        values = [opt.value for opt in q.options]
        self.assertIn("温和但有立场", values)

    def test_step5_has_special_zones_multi_select(self) -> None:
        step = COMMERCIAL_LEGAL_INTERVIEW_STEPS[4]
        q = next(
            q for q in step.questions
            if q.id == "jurisdiction-profile.special_zones"
        )
        self.assertTrue(q.allow_multiple)
        values = [opt.value for opt in q.options]
        self.assertIn("经济特区", values)
        self.assertIn("港澳台", values)

    def test_all_option_questions_have_allow_multiple_false_except_multi(self) -> None:
        for step in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            for q in step.questions:
                if q.allow_multiple:
                    self.assertTrue(
                        q.options,
                        f"{q.id} is allow_multiple but has no options",
                    )

    def test_question_text_is_chinese(self) -> None:
        for step in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            for q in step.questions:
                # Should contain at least one CJK character
                self.assertTrue(
                    any("\u4e00" <= c <= "\u9fff" for c in q.question),
                    f"Question {q.id} text is not Chinese: {q.question}",
                )

    def test_intro_is_chinese(self) -> None:
        for step in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            self.assertTrue(
                any("\u4e00" <= c <= "\u9fff" for c in step.intro),
                f"Step {step.step_id} intro is not Chinese: {step.intro}",
            )


# ---------------------------------------------------------------------------
# ColdStartInterviewOrchestrator — start / get_current_elicitation
# ---------------------------------------------------------------------------


class StartAndElicitationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryPracticeProfileStore()
        self.orch = ColdStartInterviewOrchestrator(
            self.store, COMMERCIAL_LEGAL_INTERVIEW_STEPS
        )

    def test_start_returns_initial_state(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        self.assertEqual(state.tenant_id, "t1")
        self.assertEqual(state.plugin, "commercial-legal")
        self.assertEqual(state.current_step_index, 0)
        self.assertEqual(state.completed_steps, [])
        self.assertEqual(state.answers, {})

    def test_get_current_elicitation_returns_payload(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        payload = self.orch.get_current_elicitation(state)
        self.assertIsInstance(payload, ElicitationRequestedPayload)
        self.assertEqual(payload.intro, COMMERCIAL_LEGAL_INTERVIEW_STEPS[0].intro)
        self.assertEqual(
            len(payload.questions),
            len(COMMERCIAL_LEGAL_INTERVIEW_STEPS[0].questions),
        )

    def test_interrupt_id_is_deterministic(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        payload = self.orch.get_current_elicitation(state)
        self.assertEqual(
            payload.interrupt_id,
            "interview-t1-commercial-legal-identity-team",
        )

    def test_interrupt_id_unique_per_step(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        ids = []
        for _ in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            payload = self.orch.get_current_elicitation(state)
            ids.append(payload.interrupt_id)
            state = self.orch.submit_answers(state, {})
        self.assertEqual(len(ids), len(set(ids)))

    def test_get_elicitation_on_complete_raises(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        for _ in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            state = self.orch.submit_answers(state, {})
        with self.assertRaises(ValueError):
            self.orch.get_current_elicitation(state)


# ---------------------------------------------------------------------------
# ColdStartInterviewOrchestrator — submit_answers / is_complete
# ---------------------------------------------------------------------------


class SubmitAndCompleteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryPracticeProfileStore()
        self.orch = ColdStartInterviewOrchestrator(
            self.store, COMMERCIAL_LEGAL_INTERVIEW_STEPS
        )

    def test_submit_answers_advances_step(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        new_state = self.orch.submit_answers(
            state, {"identity-team.company_name": "某律所"}
        )
        self.assertEqual(new_state.current_step_index, 1)
        self.assertIn("identity-team", new_state.completed_steps)

    def test_submit_answers_records_answers(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        new_state = self.orch.submit_answers(
            state, {"identity-team.company_name": "某律所"}
        )
        self.assertEqual(
            new_state.answers["identity-team"]["identity-team.company_name"],
            "某律所",
        )

    def test_submit_answers_preserves_previous_answers(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        state = self.orch.submit_answers(state, {"q1": "a1"})
        state = self.orch.submit_answers(state, {"q2": "a2"})
        # First step answers should still be there
        self.assertIn("identity-team", state.answers)
        self.assertIn("review-stance", state.answers)

    def test_is_complete_false_mid_interview(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        self.assertFalse(self.orch.is_complete(state))
        state = self.orch.submit_answers(state, {})
        self.assertFalse(self.orch.is_complete(state))

    def test_is_complete_true_after_all_steps(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        for _ in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            state = self.orch.submit_answers(state, {})
        self.assertTrue(self.orch.is_complete(state))

    def test_submit_on_complete_raises(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        for _ in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            state = self.orch.submit_answers(state, {})
        with self.assertRaises(ValueError):
            self.orch.submit_answers(state, {})


# ---------------------------------------------------------------------------
# ColdStartInterviewOrchestrator — finalize
# ---------------------------------------------------------------------------


class FinalizeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryPracticeProfileStore()
        self.orch = ColdStartInterviewOrchestrator(
            self.store, COMMERCIAL_LEGAL_INTERVIEW_STEPS
        )

    def test_finalize_raises_on_incomplete(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        with self.assertRaises(ValueError):
            self.orch.finalize(state)

    def test_finalize_creates_profile_with_temporary_mode_false(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        for _ in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            state = self.orch.submit_answers(state, {})
        profile = self.orch.finalize(state)
        self.assertFalse(profile.temporary_mode)
        self.assertEqual(profile.tenant_id, "t1")
        self.assertEqual(profile.plugin, "commercial-legal")

    def test_finalize_stores_profile(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        for _ in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            state = self.orch.submit_answers(state, {})
        self.orch.finalize(state)
        stored = self.store.get("t1", "commercial-legal")
        self.assertIsNotNone(stored)

    def test_finalize_maps_answers_to_profile_fields(self) -> None:
        state = self.orch.start("t1", "commercial-legal")
        answers_map = {
            "identity-team": {
                "identity-team.company_name": "某律所",
                "identity-team.entity_type": "有限责任公司",
                "identity-team.team_size": "5",
                "identity-team.counterparty_type": "大客户",
            },
            "review-stance": {
                "review-stance.risk_appetite": "平衡型",
                "review-stance.primary_side": "甲方",
            },
            "escalation-rules": {
                "escalation-rules.junior_threshold": "¥50万",
                "escalation-rules.auto_escalation_triggers": "无限责任条款|知识产权全部转让",
            },
            "document-style": {
                "document-style.revision_tone": "温和但有立场",
                "document-style.citation_preference": "含法条引用",
            },
            "jurisdiction-profile": {
                "jurisdiction-profile.governing_law": "中国大陆法律",
                "jurisdiction-profile.special_zones": "经济特区|自贸区",
            },
        }
        for _ in COMMERCIAL_LEGAL_INTERVIEW_STEPS:
            step_id = COMMERCIAL_LEGAL_INTERVIEW_STEPS[
                state.current_step_index
            ].step_id
            state = self.orch.submit_answers(state, answers_map[step_id])
        profile = self.orch.finalize(state)
        self.assertEqual(profile.identity["org_name"], "某律所")
        self.assertEqual(profile.identity["entity_type"], "有限责任公司")
        self.assertEqual(
            profile.plugin_configs["commercial-legal"]["风险偏好"], "平衡型"
        )
        self.assertEqual(
            profile.escalation_matrix["junior_threshold"], "¥50万"
        )
        self.assertEqual(
            profile.document_style["revision_tone"], "温和但有立场"
        )
        self.assertEqual(
            profile.shared_guardrails["jurisdiction_identification"],
            "中国大陆法律",
        )


# ---------------------------------------------------------------------------
# End-to-end full flow test
# ---------------------------------------------------------------------------


class EndToEndFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryPracticeProfileStore()
        self.orch = ColdStartInterviewOrchestrator(
            self.store, COMMERCIAL_LEGAL_INTERVIEW_STEPS
        )

    def test_full_5_step_flow(self) -> None:
        """start → 5× (get_elicitation + submit_answers) →
        is_complete=True → finalize → store.get returns the profile."""
        state = self.orch.start("t1", "commercial-legal")

        answers_map = {
            "identity-team": {
                "identity-team.company_name": "某律所",
                "identity-team.entity_type": "有限责任公司",
                "identity-team.team_size": "5",
                "identity-team.counterparty_type": "大客户",
            },
            "review-stance": {
                "review-stance.risk_appetite": "平衡型",
                "review-stance.primary_side": "甲方",
            },
            "escalation-rules": {
                "escalation-rules.junior_threshold": "¥50万",
                "escalation-rules.auto_escalation_triggers": "无限责任条款",
            },
            "document-style": {
                "document-style.revision_tone": "温和但有立场",
                "document-style.citation_preference": "含法条引用",
            },
            "jurisdiction-profile": {
                "jurisdiction-profile.governing_law": "中国大陆法律",
                "jurisdiction-profile.special_zones": "经济特区",
            },
        }

        for i, step in enumerate(COMMERCIAL_LEGAL_INTERVIEW_STEPS):
            self.assertFalse(self.orch.is_complete(state))
            payload = self.orch.get_current_elicitation(state)
            self.assertEqual(payload.intro, step.intro)
            state = self.orch.submit_answers(state, answers_map[step.step_id])
            self.assertEqual(state.current_step_index, i + 1)

        self.assertTrue(self.orch.is_complete(state))
        profile = self.orch.finalize(state)
        self.assertFalse(profile.temporary_mode)

        stored = self.store.get("t1", "commercial-legal")
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.identity["org_name"], "某律所")

    def test_interrupt_id_deterministic_across_calls(self) -> None:
        """Same step should produce same interrupt_id for same tenant/plugin."""
        state1 = self.orch.start("t1", "commercial-legal")
        state2 = self.orch.start("t1", "commercial-legal")
        p1 = self.orch.get_current_elicitation(state1)
        p2 = self.orch.get_current_elicitation(state2)
        self.assertEqual(p1.interrupt_id, p2.interrupt_id)

    def test_interrupt_id_differs_for_different_tenants(self) -> None:
        state1 = self.orch.start("t1", "commercial-legal")
        state2 = self.orch.start("t2", "commercial-legal")
        p1 = self.orch.get_current_elicitation(state1)
        p2 = self.orch.get_current_elicitation(state2)
        self.assertNotEqual(p1.interrupt_id, p2.interrupt_id)


# ---------------------------------------------------------------------------
# Orchestrator does not create RunEvent
# ---------------------------------------------------------------------------


class NoRunEventTests(unittest.TestCase):
    def test_orchestrator_module_does_not_import_run_event(self) -> None:
        import inkstatute_practice_profile.interview as interview_module
        self.assertFalse(hasattr(interview_module, "RunEvent"))

    def test_get_current_elicitation_returns_payload_not_event(self) -> None:
        store = InMemoryPracticeProfileStore()
        orch = ColdStartInterviewOrchestrator(
            store, COMMERCIAL_LEGAL_INTERVIEW_STEPS
        )
        state = orch.start("t1", "commercial-legal")
        payload = orch.get_current_elicitation(state)
        self.assertIsInstance(payload, ElicitationRequestedPayload)
        self.assertFalse(hasattr(payload, "event_id"))
        self.assertFalse(hasattr(payload, "run_id"))


if __name__ == "__main__":
    unittest.main()
