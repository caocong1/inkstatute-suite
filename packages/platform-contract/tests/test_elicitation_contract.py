"""Tests for the elicitation contract — ask-user protocol and RunInterrupt interconversion.

Covers EVT-03: clarification question contract matching
``ai-for-china-legal/shared/inkstatute-integration/ASK-USER-PROTOCOL.md``
(2-4 questions, single-select / multi-select / free-text, ``allow_multiple``)
and bidirectional conversion between ``ElicitationRequestedPayload`` and
V2 ``RunInterrupt``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

from platform_contract.elicitation import (
    elicitation_to_run_interrupt,
    format_answer_display,
    run_interrupt_to_elicitation,
    validate_question_count,
)
from platform_contract.enums import InterruptStatus
from platform_contract.events import RunInterrupt
from platform_contract.unified_events import (
    ElicitationOption,
    ElicitationQuestion,
    ElicitationRequestedPayload,
)


def _two_questions() -> list[ElicitationQuestion]:
    return [
        ElicitationQuestion(id="q1", question="贵方在本交易中是甲方还是乙方？"),
        ElicitationQuestion(id="q2", question="本次涉及哪类合同？"),
    ]


def _make_payload(**kwargs) -> ElicitationRequestedPayload:
    defaults: dict = {
        "interrupt_id": "i1",
        "intro": "起草前需确认以下要点。",
        "questions": _two_questions(),
        "resume_state_ref": "rs1",
        "expires_at": "2026-08-08T00:00:00Z",
    }
    defaults.update(kwargs)
    return ElicitationRequestedPayload(**defaults)


class ElicitationContractTests(unittest.TestCase):
    # --- validate_question_count (tests 1-4) ---

    def test_two_questions_valid(self):
        validate_question_count(_two_questions())

    def test_four_questions_valid(self):
        questions = [
            ElicitationQuestion(id=f"q{i}", question=f"question {i}")
            for i in range(1, 5)
        ]
        validate_question_count(questions)

    def test_one_question_invalid(self):
        with self.assertRaises(ValueError):
            validate_question_count(
                [ElicitationQuestion(id="q1", question="a")]
            )

    def test_five_questions_invalid(self):
        with self.assertRaises(ValueError):
            validate_question_count(
                [ElicitationQuestion(id=f"q{i}", question=f"q{i}") for i in range(5)]
            )

    # --- ElicitationQuestion field semantics (tests 5-8) ---

    def test_allow_multiple_default_false(self):
        q = ElicitationQuestion(id="q1", question="test")
        self.assertFalse(q.allow_multiple)

    def test_allow_multiple_true(self):
        q = ElicitationQuestion(id="q1", question="test", allow_multiple=True)
        self.assertTrue(q.allow_multiple)

    def test_free_text_question_has_no_options(self):
        q = ElicitationQuestion(id="q1", question="test")
        self.assertEqual(q.options, [])

    def test_options_with_label_and_value(self):
        q = ElicitationQuestion(
            id="q1",
            question="test",
            options=[ElicitationOption(label="甲方", value="party_a")],
        )
        self.assertEqual(q.options[0].label, "甲方")
        self.assertEqual(q.options[0].value, "party_a")

    # --- elicitation_to_run_interrupt field mapping (tests 9-10) ---

    def test_elicitation_to_run_interrupt_field_mapping(self):
        payload = _make_payload()
        ri = elicitation_to_run_interrupt(
            payload, run_id="r1", session_id="s1", created_at="2026-08-07T00:00:00Z"
        )
        self.assertEqual(ri.interrupt_id, "i1")
        self.assertEqual(str(ri.status), InterruptStatus.WAITING_FOR_USER.value)
        self.assertEqual(ri.reason, "clarification")
        self.assertEqual(ri.prompt_ref, "elicitation://i1")
        self.assertEqual(ri.resume_state_ref, "rs1")
        self.assertIn("elicitation_question", ri.expected_response_schema_ref)
        self.assertEqual(ri.run_id, "r1")
        self.assertEqual(ri.session_id, "s1")
        self.assertEqual(ri.expires_at, "2026-08-08T00:00:00Z")

    def test_run_interrupt_to_elicitation_roundtrip(self):
        payload = _make_payload()
        ri = elicitation_to_run_interrupt(
            payload, run_id="r1", session_id="s1", created_at="2026-08-07T00:00:00Z"
        )
        restored = run_interrupt_to_elicitation(ri)
        self.assertEqual(restored.interrupt_id, payload.interrupt_id)
        self.assertEqual(restored.intro, payload.intro)
        self.assertEqual(len(restored.questions), len(payload.questions))
        self.assertEqual(restored.resume_state_ref, payload.resume_state_ref)
        self.assertEqual(restored.expires_at, payload.expires_at)

    # --- interconversion preserves allow_multiple and options (tests 11-12) ---

    def test_interconversion_preserves_allow_multiple(self):
        payload = _make_payload(
            questions=[
                ElicitationQuestion(
                    id="q1",
                    question="multi?",
                    allow_multiple=True,
                    options=[ElicitationOption(label="A", value="a")],
                ),
                ElicitationQuestion(id="q2", question="single?"),
            ]
        )
        ri = elicitation_to_run_interrupt(
            payload, run_id="r1", session_id="s1", created_at="2026-08-07T00:00:00Z"
        )
        restored = run_interrupt_to_elicitation(ri)
        self.assertTrue(restored.questions[0].allow_multiple)
        self.assertFalse(restored.questions[1].allow_multiple)

    def test_interconversion_preserves_options(self):
        opts = [
            ElicitationOption(label="租赁合同", value="lease"),
            ElicitationOption(label="买卖合同", value="sale"),
            ElicitationOption(label="服务合同", value="service"),
        ]
        payload = _make_payload(
            questions=[
                ElicitationQuestion(id="q1", question="types?", options=opts),
                ElicitationQuestion(id="q2", question="other?"),
            ]
        )
        ri = elicitation_to_run_interrupt(
            payload, run_id="r1", session_id="s1", created_at="2026-08-07T00:00:00Z"
        )
        restored = run_interrupt_to_elicitation(ri)
        self.assertEqual(len(restored.questions[0].options), 3)
        self.assertEqual(restored.questions[0].options[0].label, "租赁合同")
        self.assertEqual(restored.questions[0].options[0].value, "lease")
        self.assertEqual(restored.questions[0].options[2].value, "service")

    # --- format_answer_display (tests 13-15) ---

    def test_format_answer_display_single_select(self):
        questions = [
            ElicitationQuestion(
                id="q1",
                question="贵方在本交易中是甲方还是乙方？",
                options=[
                    ElicitationOption(label="甲方", value="party_a"),
                    ElicitationOption(label="乙方", value="party_b"),
                ],
            ),
        ]
        display = format_answer_display(questions, {"q1": "party_a"})
        self.assertIn("甲方", display)
        # The answer line should show the selected label, not the raw value.
        self.assertIn("回答：甲方", display)
        self.assertNotIn("party_a", display)

    def test_format_answer_display_multi_select(self):
        questions = [
            ElicitationQuestion(
                id="q1",
                question="本次涉及哪类合同？",
                allow_multiple=True,
                options=[
                    ElicitationOption(label="租赁合同", value="lease"),
                    ElicitationOption(label="买卖合同", value="sale"),
                ],
            ),
        ]
        display = format_answer_display(questions, {"q1": "lease|sale"})
        self.assertIn("租赁合同", display)
        self.assertIn("买卖合同", display)
        self.assertIn("、", display)

    def test_format_answer_display_free_text(self):
        questions = [
            ElicitationQuestion(id="q1", question="请描述案情"),
        ]
        display = format_answer_display(questions, {"q1": "some free text"})
        self.assertIn("some free text", display)

    # --- reference-first prompt_ref (test 16) ---

    def test_prompt_ref_is_reference_not_full_text(self):
        payload = _make_payload(intro="起草前需确认以下要点，以便选用合适模板与检索策略。")
        ri = elicitation_to_run_interrupt(
            payload, run_id="r1", session_id="s1", created_at="2026-08-07T00:00:00Z"
        )
        self.assertTrue(ri.prompt_ref.startswith("elicitation://"))
        self.assertNotIn(payload.intro, ri.prompt_ref)


if __name__ == "__main__":
    unittest.main()
