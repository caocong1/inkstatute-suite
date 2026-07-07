"""Tests for adapter normalize_inbound gateway envelope delegation + legacy backward compat."""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from platform_contract.events import AgentTurn, FeedbackEvent
from platform_runtime.protocols import InboundNormalized, RawInbound


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Gateway envelope RawInbound builders (real QQ Bot {op, t, d} format)
# ---------------------------------------------------------------------------


def c2c_envelope_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/phase60/c2c-001",
        received_at="2026-07-07T04:00:00Z",
        metadata={
            "payload": {
                "op": 0,
                "t": "C2C_MESSAGE_CREATE",
                "id": "evt-c2c-001",
                "s": 1,
                "d": {
                    "author": {
                        "user_openid": "FIXTURE_USER_OPENID_C2C_001",
                    },
                    "content": "test",
                    "id": "ROBOT1.0_fixture_c2c_msg_001",
                    "timestamp": "2026-07-07T12:00:00+08:00",
                    "attachments": [],
                },
            }
        },
    )


def group_envelope_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/phase60/group-001",
        received_at="2026-07-07T04:00:00Z",
        metadata={
            "payload": {
                "op": 0,
                "t": "GROUP_AT_MESSAGE_CREATE",
                "id": "evt-group-001",
                "s": 2,
                "d": {
                    "author": {
                        "member_openid": "FIXTURE_MEMBER_OPENID_001",
                    },
                    "content": " 123",
                    "group_openid": "FIXTURE_GROUP_OPENID_001",
                    "id": "ROBOT1.0_fixture_group_msg_001",
                    "timestamp": "2026-07-07T12:00:00+08:00",
                    "attachments": [],
                },
            }
        },
    )


def interaction_envelope_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/phase60/interaction-001",
        received_at="2026-07-07T04:00:00Z",
        metadata={
            "payload": {
                "op": 0,
                "t": "INTERACTION_CREATE",
                "id": "evt-interaction-001",
                "s": 3,
                "d": {
                    "chat_type": 2,
                    "user_openid": "FIXTURE_USER_OPENID_INTERACTION_001",
                    "data": {
                        "resolved": {
                            "button_data": "up",
                            "button_id": "21",
                            "user_id": "FIXTURE_USER_OPENID_INTERACTION_001",
                        },
                        "type": 11,
                    },
                    "id": "FIXTURE_INTERACTION_ID_001",
                    "type": 11,
                    "version": 1,
                },
            }
        },
    )


def validation_envelope_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/phase60/validation-001",
        received_at="2026-07-07T04:00:00Z",
        metadata={
            "payload": {
                "op": 13,
                "d": {
                    "plain_token": "FIXTURE_PLAIN_TOKEN_001",
                    "event_ts": "FIXTURE_EVENT_TS_001",
                },
            }
        },
    )


def unknown_envelope_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/phase60/unknown-001",
        received_at="2026-07-07T04:00:00Z",
        metadata={
            "payload": {
                "op": 0,
                "t": "FRIEND_ADD",
                "id": "evt-friend-001",
                "s": 4,
                "d": {},
            }
        },
    )


# ---------------------------------------------------------------------------
# Legacy fixture RawInbound builders (pre-normalized format — no op/t/d)
# ---------------------------------------------------------------------------


def legacy_text_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/inbound/msg-text-1",
        received_at="2026-07-04T00:00:00Z",
        idempotency_key="qqbot-idem-1",
        metadata={
            "payload": {
                "type": "message",
                "conversation_id": "conv-qqbot-1",
                "user_id": "lawyer-1",
                "message_type": "text",
                "turn_id": "turn-qqbot-1",
                "content_ref": "fixture://qqbot/content/msg-text-1",
                "content_hash": "a" * 64,
            }
        },
    )


def legacy_feedback_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/inbound/feedback-1",
        received_at="2026-07-04T00:00:01Z",
        idempotency_key="qqbot-feedback-idem-1",
        metadata={
            "payload": {
                "type": "feedback",
                "feedback_id": "feedback-1",
                "conversation_id": "conv-qqbot-1",
                "user_id": "lawyer-1",
                "turn_id": "turn-qqbot-1",
                "feedback_target": "result-msg-1",
                "action": "up",
            }
        },
    )


class AdapterNormalizeTests(unittest.TestCase):
    """Tests for adapter normalize_inbound gateway delegation + legacy backward compat."""

    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(QQBotChannelConfig(channel_id="qqbot", enabled=True))

    # --- Gateway envelope delegation tests ---

    def test_c2c_envelope_normalizes_to_agent_turn(self) -> None:
        normalized = run(self.adapter.normalize_inbound(c2c_envelope_raw()))

        self.assertIsInstance(normalized, InboundNormalized)
        self.assertIsInstance(normalized.message, AgentTurn)
        self.assertIsNone(normalized.feedback)
        self.assertEqual(
            normalized.message.conversation_id,
            "qqbot:c2c:FIXTURE_USER_OPENID_C2C_001:FIXTURE_USER_OPENID_C2C_001",
        )
        self.assertEqual(normalized.message.channel, "qqbot")
        self.assertEqual(normalized.message.user_id, "FIXTURE_USER_OPENID_C2C_001")
        self.assertEqual(normalized.message.message_type, "text")
        self.assertEqual(normalized.metadata["normalized_type"], "agent_turn")

    def test_group_envelope_normalizes_to_agent_turn(self) -> None:
        normalized = run(self.adapter.normalize_inbound(group_envelope_raw()))

        self.assertIsInstance(normalized.message, AgentTurn)
        self.assertIsNone(normalized.feedback)
        self.assertEqual(
            normalized.message.conversation_id,
            "qqbot:group:FIXTURE_GROUP_OPENID_001:FIXTURE_MEMBER_OPENID_001",
        )
        self.assertEqual(normalized.message.channel, "qqbot")
        self.assertEqual(normalized.message.user_id, "FIXTURE_MEMBER_OPENID_001")
        self.assertEqual(normalized.metadata["normalized_type"], "agent_turn")

    def test_interaction_envelope_normalizes_to_feedback_event(self) -> None:
        normalized = run(self.adapter.normalize_inbound(interaction_envelope_raw()))

        self.assertIsInstance(normalized, InboundNormalized)
        self.assertIsInstance(normalized.feedback, FeedbackEvent)
        self.assertIsNone(normalized.message)
        self.assertEqual(normalized.feedback.source, "card_button")
        self.assertEqual(normalized.feedback.action, "up")
        self.assertEqual(normalized.feedback.event_type, "rating")
        self.assertEqual(normalized.feedback.status, "pending")
        self.assertEqual(normalized.feedback.rating, 1.0)
        self.assertEqual(normalized.metadata["normalized_type"], "feedback_event")

    def test_validation_envelope_returns_empty_normalized(self) -> None:
        normalized = run(self.adapter.normalize_inbound(validation_envelope_raw()))

        self.assertIsNone(normalized.message)
        self.assertIsNone(normalized.feedback)
        self.assertEqual(normalized.metadata["normalized_type"], "validation_challenge")

    def test_unknown_envelope_returns_empty_normalized(self) -> None:
        normalized = run(self.adapter.normalize_inbound(unknown_envelope_raw()))

        self.assertIsNone(normalized.message)
        self.assertIsNone(normalized.feedback)
        self.assertEqual(normalized.metadata["normalized_type"], "unknown")

    # --- Legacy backward compat tests ---

    def test_legacy_fixture_format_still_works(self) -> None:
        normalized = run(self.adapter.normalize_inbound(legacy_text_raw()))

        self.assertIsInstance(normalized.message, AgentTurn)
        self.assertIsNone(normalized.feedback)
        self.assertEqual(normalized.message.conversation_id, "conv-qqbot-1")
        self.assertEqual(normalized.message.user_id, "lawyer-1")
        self.assertEqual(normalized.metadata["normalized_type"], "agent_turn")

    def test_legacy_feedback_fixture_still_works(self) -> None:
        normalized = run(self.adapter.normalize_inbound(legacy_feedback_raw()))

        self.assertIsInstance(normalized.feedback, FeedbackEvent)
        self.assertIsNone(normalized.message)
        self.assertEqual(normalized.feedback.source, "card_button")
        self.assertEqual(normalized.feedback.action, "up")
        self.assertEqual(normalized.metadata["normalized_type"], "feedback_event")


if __name__ == "__main__":
    unittest.main()
