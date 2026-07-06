"""Tests for FeedbackHandler — feedback normalization and FeedbackEvent production."""

from __future__ import annotations

import unittest

from lawyer_web_chat.feedback import FeedbackHandler


class FeedbackHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = FeedbackHandler()

    def test_submit_thumbs_up_feedback(self) -> None:
        result = self.handler.submit_feedback(
            conversation_id="conv-1",
            user_id="lawyer-1",
            action="up",
            feedback_target="turn-1",
        )
        self.assertEqual(result.action, "up")
        self.assertEqual(result.event_type, "rating")
        self.assertEqual(result.feedback_event.action, "up")
        self.assertEqual(result.feedback_event.rating, 1.0)
        self.assertEqual(result.feedback_event.source, "web_chat")
        self.assertEqual(result.feedback_event.status, "pending")

    def test_submit_thumbs_up_alias(self) -> None:
        result = self.handler.submit_feedback(
            conversation_id="conv-1",
            user_id="lawyer-1",
            action="thumbs_up",
            feedback_target="turn-1",
        )
        self.assertEqual(result.action, "up")

    def test_submit_needs_fix_feedback(self) -> None:
        result = self.handler.submit_feedback(
            conversation_id="conv-1",
            user_id="lawyer-1",
            action="needs_fix",
            feedback_target="turn-1",
            message="This needs correction",
        )
        self.assertEqual(result.action, "needs_fix")
        self.assertEqual(result.event_type, "correction")
        self.assertEqual(result.feedback_event.message, "This needs correction")

    def test_submit_route_mismatch_feedback(self) -> None:
        result = self.handler.submit_feedback(
            conversation_id="conv-1",
            user_id="lawyer-1",
            action="route_wrong",
            feedback_target="turn-1",
        )
        self.assertEqual(result.action, "route_wrong")
        self.assertEqual(result.event_type, "route_mismatch")
        self.assertTrue(result.feedback_event.route_mismatch)
        self.assertIsNotNone(result.feedback_event.skill_candidate)
        assert result.feedback_event.skill_candidate is not None
        self.assertTrue(result.feedback_event.skill_candidate.requires_human_review)
        self.assertTrue(result.feedback_event.skill_candidate.metadata.get("no_auto_modify"))

    def test_submit_route_mismatch_alias(self) -> None:
        result = self.handler.submit_feedback(
            conversation_id="conv-1",
            user_id="lawyer-1",
            action="route_mismatch",
            feedback_target="turn-1",
        )
        self.assertEqual(result.action, "route_wrong")

    def test_invalid_action_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.handler.submit_feedback(
                conversation_id="conv-1",
                user_id="lawyer-1",
                action="invalid_action",
                feedback_target="turn-1",
            )

    def test_feedback_event_has_reference_only_metadata(self) -> None:
        result = self.handler.submit_feedback(
            conversation_id="conv-1",
            user_id="lawyer-1",
            action="up",
            feedback_target="turn-1",
            tenant_id="tenant-1",
        )
        self.assertIn("payload_ref", result.feedback_event.metadata)
        self.assertTrue(result.feedback_event.metadata["reference_only"])

    def test_feedback_event_source_is_web_chat(self) -> None:
        result = self.handler.submit_feedback(
            conversation_id="conv-1",
            user_id="lawyer-1",
            action="up",
            feedback_target="turn-1",
        )
        self.assertEqual(result.feedback_event.source, "web_chat")

    def test_feedback_event_status_is_pending(self) -> None:
        result = self.handler.submit_feedback(
            conversation_id="conv-1",
            user_id="lawyer-1",
            action="down",
            feedback_target="turn-1",
        )
        self.assertEqual(result.feedback_event.status, "pending")

    def test_down_action_produces_correction(self) -> None:
        result = self.handler.submit_feedback(
            conversation_id="conv-1",
            user_id="lawyer-1",
            action="down",
            feedback_target="turn-1",
        )
        self.assertEqual(result.action, "down")
        self.assertEqual(result.event_type, "correction")


if __name__ == "__main__":
    unittest.main()
