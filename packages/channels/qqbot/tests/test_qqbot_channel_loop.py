"""Fixture-driven QQBot channel loop proof — Plan 43-02 Task 01.

Proves the full QQBot ChannelAdapter loop end-to-end via a self-contained
JSON fixture with no network IO:

  receive (inbound) -> ACK (verify_and_ack) -> normalize (AgentTurn)
  -> text deliver -> card deliver -> feedback normalize (FeedbackEvent)
"""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from typing import Any

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from platform_contract.events import AgentTurn, FeedbackEvent
from platform_runtime.protocols import (
    AckResponse,
    ChannelDelivery,
    ChannelCapabilitySet,
    ComponentHealth,
    DeliveryResult,
    InboundNormalized,
    RawInbound,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "qqbot_channel_loop.json"


def run(coro):
    return asyncio.run(coro)


def load_fixture() -> dict[str, Any]:
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def raw_inbound_from_fixture(fixture: dict[str, Any], key: str) -> RawInbound:
    """Construct a RawInbound from a fixture section (e.g. qqbot_inbound)."""
    section = fixture[key]
    return RawInbound(
        channel_id=section["channel_id"],
        payload_ref=section["payload_ref"],
        received_at=section["received_at"],
        idempotency_key=section.get("idempotency_key"),
        metadata=section.get("metadata", {}),
    )


def channel_delivery_from_fixture(fixture: dict[str, Any], key: str) -> ChannelDelivery:
    """Construct a ChannelDelivery from a fixture section (e.g. text_delivery).

    The fixture stores delivery parameters inside a ``content`` dict that
    includes ``delivery_type``, ``to_user``, and optionally ``message``.
    The adapter reads ``delivery_type`` from ``metadata`` and the text body
    from the ``content`` field of ``ChannelDelivery``.
    """
    section = fixture[key]
    content_dict = section.get("content", {})
    if isinstance(content_dict, dict):
        message = content_dict.get("message", "")
        extra_metadata = {k: v for k, v in content_dict.items() if k != "message"}
    else:
        message = str(content_dict)
        extra_metadata = {}
    metadata: dict[str, Any] = {}
    metadata.update(extra_metadata)
    metadata.update(section.get("metadata", {}))
    return ChannelDelivery(
        delivery_id=section["delivery_id"],
        channel_id=section["channel_id"],
        run_id=section.get("run_id"),
        content=message,
        artifact_refs=list(section.get("artifact_refs", [])),
        metadata=metadata,
    )


class QQBotChannelLoopTests(unittest.TestCase):
    """End-to-end QQBot channel loop proof driven by a sanitized fixture."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_fixture()

    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))

    # -- Step 1: receive -> ACK ------------------------------------------------

    def test_receive_to_ack(self) -> None:
        """Inbound message callback is accepted and ACKed with the fixture key."""
        raw = raw_inbound_from_fixture(self.fixture, "qqbot_inbound")
        ack = run(self.adapter.verify_and_ack(raw))

        self.assertIsInstance(ack, AckResponse)
        self.assertEqual(ack.accepted, self.fixture["ack"]["accepted"])
        self.assertEqual(ack.status_code, self.fixture["ack"]["status_code"])
        self.assertEqual(ack.idempotency_key, self.fixture["ack"]["idempotency_key"])
        self.assertEqual(ack.metadata.get("channel_id"), "qqbot")

    # -- Step 2: ACK -> normalize (AgentTurn) ----------------------------------

    def test_ack_to_normalize_agent_turn(self) -> None:
        """normalize_inbound produces an AgentTurn matching the fixture."""
        raw = raw_inbound_from_fixture(self.fixture, "qqbot_inbound")
        normalized = run(self.adapter.normalize_inbound(raw))

        self.assertIsInstance(normalized, InboundNormalized)
        self.assertIsNotNone(normalized.message)
        self.assertIsInstance(normalized.message, AgentTurn)
        assert normalized.message is not None  # narrow for type checker
        self.assertEqual(normalized.message.channel, "qqbot")
        self.assertEqual(
            normalized.message.conversation_id,
            self.fixture["agent_turn"]["conversation_id"],
        )
        self.assertEqual(
            normalized.message.user_id,
            self.fixture["agent_turn"]["user_id"],
        )
        self.assertEqual(normalized.message.message_type, "text")
        self.assertEqual(
            normalized.message.turn_id,
            self.fixture["agent_turn"]["turn_id"],
        )

    # -- Step 3: normalize -> text delivery ------------------------------------

    def test_normalize_to_text_delivery(self) -> None:
        """Text delivery is accepted and passes output policy (allow)."""
        delivery = channel_delivery_from_fixture(self.fixture, "text_delivery")
        result = run(self.adapter.deliver(delivery))

        self.assertIsInstance(result, DeliveryResult)
        self.assertTrue(result.accepted)
        self.assertEqual(result.metadata.get("message_type"), "text")
        self.assertEqual(result.metadata.get("policy_action"), "allow")
        self.assertEqual(result.metadata.get("envelope", {}).get("msg_type"), 0)
        self.assertFalse(result.metadata.get("network_io", True))

    # -- Step 4: text delivery -> card delivery --------------------------------

    def test_text_delivery_to_card_delivery(self) -> None:
        """Card delivery is accepted and routed as card message type."""
        delivery = channel_delivery_from_fixture(self.fixture, "card_delivery")
        result = run(self.adapter.deliver(delivery))

        self.assertTrue(result.accepted)
        self.assertEqual(result.metadata.get("message_type"), "card")
        self.assertEqual(result.metadata.get("policy_action"), "allow")
        envelope = result.metadata.get("envelope") or {}
        self.assertEqual(envelope.get("msg_type"), 2)
        self.assertIn("keyboard", envelope)
        self.assertFalse(result.metadata.get("network_io", True))

    # -- Step 5: card -> feedback normalize (FeedbackEvent) --------------------

    def test_card_to_feedback_normalize(self) -> None:
        """Feedback callback normalizes to a FeedbackEvent with card_button source."""
        raw = raw_inbound_from_fixture(self.fixture, "qqbot_feedback_callback")
        normalized = run(self.adapter.normalize_inbound(raw))

        self.assertIsNotNone(normalized.feedback)
        self.assertIsInstance(normalized.feedback, FeedbackEvent)
        assert normalized.feedback is not None
        self.assertEqual(normalized.feedback.source, "card_button")
        self.assertEqual(normalized.feedback.event_type, "rating")
        self.assertEqual(normalized.feedback.action, "up")
        self.assertEqual(normalized.feedback.status, "pending")
        self.assertEqual(normalized.feedback.rating, 1.0)
        self.assertEqual(
            normalized.feedback.feedback_id,
            self.fixture["feedback_event"]["feedback_id"],
        )

    # -- Full loop sequence ----------------------------------------------------

    def test_full_loop_sequence(self) -> None:
        """Run all 5 steps in sequence and verify each feeds the next."""
        # Step 1: receive -> ACK
        inbound_raw = raw_inbound_from_fixture(self.fixture, "qqbot_inbound")
        ack = run(self.adapter.verify_and_ack(inbound_raw))
        self.assertTrue(ack.accepted)

        # Step 2: ACK -> normalize (AgentTurn)
        normalized = run(self.adapter.normalize_inbound(inbound_raw))
        self.assertIsNotNone(normalized.message)
        assert normalized.message is not None
        turn = normalized.message
        self.assertEqual(turn.channel, "qqbot")

        # Step 3: AgentTurn -> text deliver
        text_delivery = channel_delivery_from_fixture(self.fixture, "text_delivery")
        text_result = run(self.adapter.deliver(text_delivery))
        self.assertTrue(text_result.accepted)

        # Step 4: text deliver -> card deliver
        card_delivery = channel_delivery_from_fixture(self.fixture, "card_delivery")
        card_result = run(self.adapter.deliver(card_delivery))
        self.assertTrue(card_result.accepted)

        # Step 5: card deliver -> feedback normalize (FeedbackEvent)
        feedback_raw = raw_inbound_from_fixture(self.fixture, "qqbot_feedback_callback")
        feedback_normalized = run(self.adapter.normalize_inbound(feedback_raw))
        self.assertIsNotNone(feedback_normalized.feedback)
        assert feedback_normalized.feedback is not None
        self.assertEqual(feedback_normalized.feedback.source, "card_button")
        self.assertEqual(feedback_normalized.feedback.turn_id, turn.turn_id)

    # -- Capabilities and health -----------------------------------------------

    def test_capabilities_match_fixture(self) -> None:
        """Adapter capabilities match the fixture expectations."""
        caps = self.adapter.capabilities()

        self.assertIsInstance(caps, ChannelCapabilitySet)
        self.assertTrue(caps.supports_text)
        self.assertTrue(caps.supports_cards)
        self.assertTrue(caps.supports_files)
        self.assertTrue(caps.supports_images)
        self.assertFalse(caps.supports_voice)
        self.assertFalse(caps.supports_streaming)
        self.assertEqual(caps.ack_deadline_ms, 3000)
        self.assertEqual(caps.idempotency_strategy, "qqbot_callback_metadata")

    def test_health_match_fixture(self) -> None:
        """Health reports ok=True with the correct component_id when enabled."""
        health = run(self.adapter.health())

        self.assertIsInstance(health, ComponentHealth)
        self.assertTrue(health.ok)
        self.assertEqual(health.component_id, "qqbot-channel")

    # -- Privacy / no-network assertions ---------------------------------------

    def test_no_network_io_in_loop(self) -> None:
        """All AckResponse, DeliveryResult, and ComponentHealth metadata has network_io=False."""
        inbound_raw = raw_inbound_from_fixture(self.fixture, "qqbot_inbound")
        ack = run(self.adapter.verify_and_ack(inbound_raw))
        self.assertFalse(ack.metadata.get("network_io", True))

        text_delivery = channel_delivery_from_fixture(self.fixture, "text_delivery")
        text_result = run(self.adapter.deliver(text_delivery))
        self.assertFalse(text_result.metadata.get("network_io", True))

        card_delivery = channel_delivery_from_fixture(self.fixture, "card_delivery")
        card_result = run(self.adapter.deliver(card_delivery))
        self.assertFalse(card_result.metadata.get("network_io", True))

        health = run(self.adapter.health())
        self.assertFalse(health.metadata.get("network_io", True))

    def test_fixture_not_live_acceptance(self) -> None:
        """Fixture declares not_live_acceptance and sanitized evidence scope."""
        self.assertTrue(self.fixture["not_live_acceptance"])
        self.assertEqual(self.fixture["evidence_scope"], "sanitized_fixture_only")


if __name__ == "__main__":
    unittest.main()
