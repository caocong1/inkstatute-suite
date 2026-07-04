"""QQBot adapter idempotency proof — Plan 43-02 Task 02.

Proves that repeated ``verify_and_ack`` and ``normalize_inbound`` calls with
the same ``RawInbound`` produce identical ``idempotency_key`` and ``turn_id``
values, and that different raws produce different keys.
"""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from platform_runtime.protocols import RawInbound


def run(coro):
    return asyncio.run(coro)


def make_text_raw(
    *,
    turn_id: str = "turn-idem-001",
    conversation_id: str = "conv-idem-001",
    user_id: str = "user-idem-001",
    idempotency_key: str | None = None,
) -> RawInbound:
    """Construct a RawInbound with a QQBot message payload."""
    return RawInbound(
        channel_id="qqbot",
        payload_ref=f"fixture://qqbot/idem/inbound/{turn_id}",
        received_at="2026-07-04T00:00:00Z",
        idempotency_key=idempotency_key,
        metadata={
            "payload": {
                "type": "message",
                "message_type": "text",
                "turn_id": turn_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "content_ref": "fixture://qqbot/idem/content-001",
            }
        },
    )


def make_feedback_raw(
    *,
    feedback_id: str = "feedback-idem-001",
    action: str = "up",
    conversation_id: str = "conv-idem-001",
    user_id: str = "user-idem-001",
    turn_id: str = "turn-idem-001",
    feedback_target: str = "result-idem-001",
    idempotency_key: str | None = None,
) -> RawInbound:
    """Construct a RawInbound with a QQBot feedback payload."""
    return RawInbound(
        channel_id="qqbot",
        payload_ref=f"fixture://qqbot/idem/feedback/{feedback_id}",
        received_at="2026-07-04T00:00:01Z",
        idempotency_key=idempotency_key,
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


class QQBotIdempotencyTests(unittest.TestCase):
    """Verify that the QQBot adapter is idempotent for duplicate callbacks."""

    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))

    def test_verify_and_ack_idempotent_same_raw(self) -> None:
        """Same RawInbound → same idempotency_key from verify_and_ack."""
        raw = make_text_raw()
        ack1 = run(self.adapter.verify_and_ack(raw))
        ack2 = run(self.adapter.verify_and_ack(raw))

        self.assertTrue(ack1.accepted)
        self.assertTrue(ack2.accepted)
        self.assertEqual(ack1.idempotency_key, ack2.idempotency_key)

    def test_verify_and_ack_different_raw_different_key(self) -> None:
        """Different RawInbound → different idempotency_key from verify_and_ack."""
        raw_a = make_text_raw(turn_id="turn-A")
        raw_b = make_text_raw(turn_id="turn-B")

        ack_a = run(self.adapter.verify_and_ack(raw_a))
        ack_b = run(self.adapter.verify_and_ack(raw_b))

        self.assertNotEqual(ack_a.idempotency_key, ack_b.idempotency_key)

    def test_normalize_inbound_idempotent_same_raw(self) -> None:
        """Same RawInbound → same turn_id and metadata idempotency_key."""
        raw = make_text_raw()
        norm1 = run(self.adapter.normalize_inbound(raw))
        norm2 = run(self.adapter.normalize_inbound(raw))

        self.assertIsNotNone(norm1.message)
        self.assertIsNotNone(norm2.message)
        assert norm1.message is not None and norm2.message is not None
        self.assertEqual(norm1.message.turn_id, norm2.message.turn_id)
        self.assertEqual(
            norm1.metadata.get("idempotency_key"),
            norm2.metadata.get("idempotency_key"),
        )

    def test_normalize_inbound_different_raw_different_turn_id(self) -> None:
        """Different RawInbound → different turn_id from normalize_inbound."""
        raw_a = make_text_raw(turn_id="turn-A")
        raw_b = make_text_raw(turn_id="turn-B")

        norm_a = run(self.adapter.normalize_inbound(raw_a))
        norm_b = run(self.adapter.normalize_inbound(raw_b))

        assert norm_a.message is not None and norm_b.message is not None
        self.assertNotEqual(norm_a.message.turn_id, norm_b.message.turn_id)

    def test_feedback_normalize_idempotent_same_raw(self) -> None:
        """Same feedback RawInbound → same feedback_id and card_button source."""
        raw = make_feedback_raw()
        norm1 = run(self.adapter.normalize_inbound(raw))
        norm2 = run(self.adapter.normalize_inbound(raw))

        self.assertIsNotNone(norm1.feedback)
        self.assertIsNotNone(norm2.feedback)
        assert norm1.feedback is not None and norm2.feedback is not None
        self.assertEqual(norm1.feedback.feedback_id, norm2.feedback.feedback_id)
        self.assertEqual(norm1.feedback.source, "card_button")
        self.assertEqual(norm2.feedback.source, "card_button")

    def test_ack_and_normalize_share_idempotency_key(self) -> None:
        """ACK and normalize with the same raw share the same idempotency key.

        When the raw has a pre-set idempotency_key, both verify_and_ack and
        normalize_inbound use it directly.
        """
        raw = make_text_raw(idempotency_key="qqbot-shared-idem-001")

        ack = run(self.adapter.verify_and_ack(raw))
        norm = run(self.adapter.normalize_inbound(raw))

        self.assertEqual(ack.idempotency_key, "qqbot-shared-idem-001")
        self.assertEqual(
            norm.metadata.get("idempotency_key"),
            "qqbot-shared-idem-001",
        )
        self.assertEqual(ack.idempotency_key, norm.metadata.get("idempotency_key"))

    def test_idempotency_key_starts_with_qqbot_prefix(self) -> None:
        """Derived idempotency keys start with 'qqbot' prefix.

        When the raw has a pre-set idempotency_key, it is used as-is.
        When the raw has no pre-set key, the adapter derives one that
        starts with the 'qqbot' channel prefix.
        """
        # Case 1: pre-set idempotency_key is used directly
        raw_preset = make_text_raw(idempotency_key="qqbot-pre-set-001")
        ack_preset = run(self.adapter.verify_and_ack(raw_preset))
        self.assertEqual(ack_preset.idempotency_key, "qqbot-pre-set-001")

        # Case 2: no pre-set key → adapter derives one with qqbot prefix
        raw_derived = make_text_raw()
        ack_derived = run(self.adapter.verify_and_ack(raw_derived))
        self.assertIsNotNone(ack_derived.idempotency_key)
        assert ack_derived.idempotency_key is not None
        self.assertTrue(
            ack_derived.idempotency_key.startswith("qqbot"),
            f"Expected derived key to start with 'qqbot', got {ack_derived.idempotency_key!r}",
        )


if __name__ == "__main__":
    unittest.main()
