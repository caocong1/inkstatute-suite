"""QQBot feedback source mapping proof — Plan 43-02 Task 03.

Proves that QQBot feedback maps to the existing ``FeedbackSource.CARD_BUTTON``
enum value ("card_button") and that the ``FeedbackSource`` enum remains frozen
at exactly 4 values (SAFETY-02, SAFETY-06, QQBOT-04).
"""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from platform_contract.enums import FeedbackSource
from platform_contract.events import FeedbackEvent
from platform_runtime.protocols import RawInbound


def run(coro):
    return asyncio.run(coro)


def make_feedback_raw(
    *,
    action: str = "up",
    feedback_id: str = "feedback-src-001",
    conversation_id: str = "conv-src-001",
    user_id: str = "user-src-001",
    turn_id: str = "turn-src-001",
    feedback_target: str = "result-src-001",
) -> RawInbound:
    """Construct a RawInbound with a QQBot feedback payload."""
    return RawInbound(
        channel_id="qqbot",
        payload_ref=f"fixture://qqbot/src/feedback/{feedback_id}",
        received_at="2026-07-04T00:00:00Z",
        metadata={
            "payload": {
                "type": "feedback",
                "feedback_id": feedback_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "turn_id": turn_id,
                "feedback_target": feedback_target,
                "action": action,
            }
        },
    )


class FeedbackSourceMappingTests(unittest.TestCase):
    """Verify QQBot feedback maps to CARD_BUTTON and FeedbackSource stays frozen."""

    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))

    def test_feedback_source_is_card_button(self) -> None:
        """QQBot feedback source is 'card_button' (CARD_BUTTON enum value)."""
        normalized = run(self.adapter.normalize_inbound(make_feedback_raw(action="up")))

        self.assertIsNotNone(normalized.feedback)
        assert normalized.feedback is not None
        self.assertEqual(normalized.feedback.source, "card_button")
        self.assertEqual(normalized.feedback.source, FeedbackSource.CARD_BUTTON.value)

    def test_feedback_source_is_valid_enum_member(self) -> None:
        """The source value is a valid FeedbackSource enum member (no ValueError)."""
        normalized = run(self.adapter.normalize_inbound(make_feedback_raw(action="up")))

        assert normalized.feedback is not None
        # Should not raise ValueError — the value is a valid enum member
        source_enum = FeedbackSource(normalized.feedback.source)
        self.assertEqual(source_enum, FeedbackSource.CARD_BUTTON)

    def test_feedback_source_for_down_action(self) -> None:
        """QQBot 'down' feedback still maps to card_button source."""
        normalized = run(self.adapter.normalize_inbound(make_feedback_raw(action="down")))

        assert normalized.feedback is not None
        self.assertEqual(normalized.feedback.source, "card_button")

    def test_feedback_source_for_needs_fix_action(self) -> None:
        """QQBot 'needs_fix' feedback still maps to card_button source."""
        normalized = run(
            self.adapter.normalize_inbound(make_feedback_raw(action="needs_fix"))
        )

        assert normalized.feedback is not None
        self.assertEqual(normalized.feedback.source, "card_button")

    def test_feedback_source_for_route_wrong_action(self) -> None:
        """QQBot 'route_wrong' feedback still maps to card_button source."""
        normalized = run(
            self.adapter.normalize_inbound(make_feedback_raw(action="route_wrong"))
        )

        assert normalized.feedback is not None
        self.assertEqual(normalized.feedback.source, "card_button")

    def test_feedback_source_enum_has_exactly_four_values(self) -> None:
        """FeedbackSource enum has exactly 4 values — no new values added."""
        self.assertEqual(len(list(FeedbackSource)), 4)

    def test_feedback_source_enum_values_unchanged(self) -> None:
        """FeedbackSource values are exactly the 4 frozen values."""
        expected = {"card_button", "text_command", "web_form", "admin_annotation"}
        actual = {member.value for member in FeedbackSource}
        self.assertEqual(actual, expected)

    def test_qqbot_does_not_use_web_form_source(self) -> None:
        """QQBot uses CARD_BUTTON, not WEB_FORM (which is for web_sse)."""
        normalized = run(self.adapter.normalize_inbound(make_feedback_raw(action="up")))

        assert normalized.feedback is not None
        self.assertNotEqual(normalized.feedback.source, "web_form")
        self.assertNotEqual(normalized.feedback.source, FeedbackSource.WEB_FORM.value)

    def test_no_new_feedback_source_enum_values_added(self) -> None:
        """FeedbackSource __members__ keys are exactly the 4 frozen member names."""
        expected_members = {"CARD_BUTTON", "TEXT_COMMAND", "WEB_FORM", "ADMIN_ANNOTATION"}
        actual_members = set(FeedbackSource.__members__.keys())
        self.assertEqual(actual_members, expected_members)


if __name__ == "__main__":
    unittest.main()
