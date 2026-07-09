from __future__ import annotations

import asyncio
import unittest
from dataclasses import asdict

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from platform_contract.events import AgentTurn, FeedbackEvent
from platform_runtime.protocols import ChannelDelivery, RawInbound


def run(coro):
    return asyncio.run(coro)


def text_raw() -> RawInbound:
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


def feedback_raw() -> RawInbound:
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


def text_delivery() -> ChannelDelivery:
    return ChannelDelivery(
        delivery_id="delivery-qqbot-1",
        channel_id="qqbot",
        run_id="run-1",
        content="根据《民法典》第五百六十三条，若对方根本违约，你方通常可以主张解除合同。",
        metadata={"delivery_type": "text", "to_user": "lawyer-1"},
    )


def card_delivery() -> ChannelDelivery:
    return ChannelDelivery(
        delivery_id="delivery-qqbot-card-1",
        channel_id="qqbot",
        run_id="run-1",
        content="请评价本次回复",
        metadata={"delivery_type": "card", "to_user": "lawyer-1", "feedback_target": "result-1"},
    )


class QQBotChannelConfigTests(unittest.TestCase):
    def test_config_defaults_to_disabled(self) -> None:
        self.assertFalse(QQBotChannelConfig().enabled)

    def test_from_env_enables_only_explicit_truthy_values(self) -> None:
        enabled = QQBotChannelConfig.from_env({"INKSTATUTE_QQBOT_CHANNEL_ENABLED": "true"})
        also_enabled = QQBotChannelConfig.from_env({"INKSTATUTE_QQBOT_CHANNEL_ENABLED": "1"})
        also_enabled_yes = QQBotChannelConfig.from_env({"INKSTATUTE_QQBOT_CHANNEL_ENABLED": "yes"})
        disabled_on = QQBotChannelConfig.from_env({"INKSTATUTE_QQBOT_CHANNEL_ENABLED": "on"})

        self.assertTrue(enabled.enabled)
        self.assertTrue(also_enabled.enabled)
        self.assertTrue(also_enabled_yes.enabled)
        self.assertFalse(disabled_on.enabled)

    def test_config_keeps_secret_refs_only(self) -> None:
        config = QQBotChannelConfig.from_env(
            {
                "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "1",
                "INKSTATUTE_QQBOT_APP_ID_REF": "secret://qqbot/app-id",
                "INKSTATUTE_QQBOT_APP_SECRET_REF": "secret://qqbot/app-secret",
                "INKSTATUTE_QQBOT_TOKEN_SECRET_REF": "secret://qqbot/token",
            }
        )

        self.assertEqual(config.app_id_ref, "secret://qqbot/app-id")
        self.assertEqual(config.app_secret_ref, "secret://qqbot/app-secret")
        self.assertEqual(config.token_secret_ref, "secret://qqbot/token")
        rendered = str(asdict(config))
        self.assertNotIn("raw-token", rendered)
        self.assertNotIn("access_token", rendered)
        self.assertNotIn("BEGIN PRIVATE KEY", rendered)


class QQBotChannelAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))

    def test_channel_id_reports_qqbot(self) -> None:
        self.assertEqual(self.adapter.channel_id(), "qqbot")

    def test_capabilities_mark_text_and_cards(self) -> None:
        capabilities = self.adapter.capabilities()
        self.assertTrue(capabilities.supports_text)
        self.assertTrue(capabilities.supports_cards)
        self.assertFalse(capabilities.supports_files)
        self.assertFalse(capabilities.supports_streaming)
        self.assertEqual(capabilities.idempotency_strategy, "qqbot_callback_metadata")
        self.assertTrue(capabilities.metadata["fixture_only"])
        self.assertFalse(capabilities.metadata["network_io"])

    def test_text_message_normalizes_to_agent_turn(self) -> None:
        normalized = run(self.adapter.normalize_inbound(text_raw()))

        self.assertIsNone(normalized.feedback)
        self.assertIsInstance(normalized.message, AgentTurn)
        self.assertEqual(normalized.message.channel, "qqbot")
        self.assertEqual(normalized.message.message_type, "text")
        self.assertEqual(normalized.message.conversation_id, "conv-qqbot-1")
        self.assertEqual(normalized.message.user_id, "lawyer-1")
        self.assertEqual(
            normalized.message.metadata["payload_ref"],
            "fixture://qqbot/inbound/msg-text-1",
        )
        self.assertNotIn("raw_payload", str(asdict(normalized.message)))

    def test_feedback_callback_normalizes_to_feedback_event(self) -> None:
        normalized = run(self.adapter.normalize_inbound(feedback_raw()))

        self.assertIsNone(normalized.message)
        self.assertIsInstance(normalized.feedback, FeedbackEvent)
        self.assertEqual(normalized.feedback.source, "card_button")
        self.assertEqual(normalized.feedback.event_type, "rating")
        self.assertEqual(normalized.feedback.action, "up")
        self.assertEqual(normalized.feedback.status, "pending")
        self.assertEqual(normalized.feedback.rating, 1.0)
        self.assertEqual(normalized.feedback.feedback_target, "result-msg-1")

    def test_route_wrong_feedback_attaches_skill_candidate(self) -> None:
        raw = RawInbound(
            channel_id="qqbot",
            payload_ref="fixture://qqbot/inbound/feedback-route-1",
            received_at="2026-07-04T00:00:02Z",
            metadata={
                "payload": {
                    "type": "feedback",
                    "conversation_id": "conv-qqbot-1",
                    "user_id": "lawyer-1",
                    "turn_id": "turn-qqbot-1",
                    "feedback_target": "result-msg-1",
                    "action": "route_wrong",
                    "proposed_skill": "qqbot.route_review_candidate",
                }
            },
        )

        normalized = run(self.adapter.normalize_inbound(raw))

        self.assertIsNotNone(normalized.feedback)
        self.assertEqual(normalized.feedback.event_type, "route_mismatch")
        self.assertTrue(normalized.feedback.skill_candidate.requires_human_review)
        self.assertEqual(normalized.feedback.skill_candidate.risk_level, "high")

    def test_ack_records_payload_ref_and_idempotency_key(self) -> None:
        ack = run(self.adapter.verify_and_ack(text_raw()))

        self.assertTrue(ack.accepted)
        self.assertEqual(ack.metadata["channel_id"], "qqbot")
        self.assertEqual(ack.metadata["payload_ref"], "fixture://qqbot/inbound/msg-text-1")
        self.assertEqual(ack.idempotency_key, "qqbot-idem-1")
        self.assertTrue(ack.metadata["fixture_only"])

    def test_ack_is_rejected_when_channel_disabled(self) -> None:
        disabled = QQBotChannelAdapter(QQBotChannelConfig(enabled=False))

        ack = run(disabled.verify_and_ack(text_raw()))

        self.assertFalse(ack.accepted)
        self.assertEqual(ack.status_code, 503)

    def test_text_delivery_applies_output_policy(self) -> None:
        result = run(self.adapter.deliver(text_delivery()))

        self.assertTrue(result.accepted)
        self.assertEqual(result.metadata["delivery_type"], "text")
        self.assertEqual(result.metadata["message_type"], "text")
        self.assertEqual(result.metadata["policy_action"], "allow")
        self.assertFalse(result.metadata["network_io"])
        envelope = result.metadata["envelope"]
        self.assertEqual(envelope["msg_type"], 0)
        self.assertIn("content", envelope)

    def test_card_delivery_builds_card_envelope(self) -> None:
        result = run(self.adapter.deliver(card_delivery()))

        self.assertTrue(result.accepted)
        self.assertEqual(result.metadata["delivery_type"], "card")
        self.assertEqual(result.metadata["message_type"], "card")
        envelope = result.metadata["envelope"]
        self.assertEqual(envelope["msg_type"], 2)
        self.assertIn("keyboard", envelope)
        self.assertNotIn("template_card", envelope)
        rows = envelope["keyboard"]["content"]["rows"]
        self.assertTrue(rows)
        self.assertIn("buttons", rows[0])

    def test_markdown_delivery_builds_markdown_envelope(self) -> None:
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-md-1",
            channel_id="qqbot",
            run_id="run-1",
            content="## 结论\n根据《民法典》可主张解除合同。",
            metadata={"delivery_type": "markdown", "to_user": "lawyer-1"},
        )
        result = run(self.adapter.deliver(delivery))

        self.assertTrue(result.accepted)
        self.assertEqual(result.metadata["delivery_type"], "markdown")
        self.assertEqual(result.metadata["message_type"], "markdown")
        envelope = result.metadata["envelope"]
        self.assertEqual(envelope["msg_type"], 2)
        self.assertIn("markdown", envelope)
        self.assertIn("content", envelope["markdown"])
        self.assertFalse(result.metadata["network_io"])

    def test_window_expired_delivery_fails_with_owned_notice(self) -> None:
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-window-1",
            channel_id="qqbot",
            run_id="run-1",
            content="迟到回复",
            metadata={
                "delivery_type": "text",
                "msg_id": "msg-expired-1",
                "scene": "group",
                "received_at": "2020-01-01T00:00:00Z",
                "reply_count": 0,
            },
        )
        result = run(self.adapter.deliver(delivery))

        self.assertFalse(result.accepted)
        self.assertEqual(
            result.metadata["issue_code"], "qqbot_passive_reply_window_expired"
        )
        self.assertTrue(result.metadata.get("interim_notice"))
        self.assertFalse(result.metadata["network_io"])

    def test_window_gate_fails_closed_when_msg_id_without_received_at(self) -> None:
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-window-missing-received-at",
            channel_id="qqbot",
            run_id="run-1",
            content="缺少 received_at",
            metadata={
                "delivery_type": "text",
                "msg_id": "msg-no-received-at",
                "scene": "c2c",
                "reply_count": 0,
            },
        )
        result = run(self.adapter.deliver(delivery))

        self.assertFalse(result.accepted)
        self.assertEqual(
            result.metadata["issue_code"], "qqbot_passive_reply_window_expired"
        )
        self.assertTrue(result.metadata.get("interim_notice"))
        self.assertFalse(result.metadata["network_io"])

    def test_delivery_blocks_internal_notice(self) -> None:
        blocked = ChannelDelivery(
            delivery_id="delivery-qqbot-blocked-1",
            channel_id="qqbot",
            run_id="run-1",
            content="ADMIN_NOTICE: delivery debug stack trace token=secret",
            metadata={"delivery_type": "text", "to_user": "lawyer-1"},
        )
        result = run(self.adapter.deliver(blocked))

        self.assertFalse(result.accepted)
        self.assertEqual(result.metadata["policy_action"], "block")

    def test_health_reports_enabled_status(self) -> None:
        health = run(self.adapter.health())
        self.assertTrue(health.ok)
        self.assertEqual(health.component_id, "qqbot-channel")

        disabled = QQBotChannelAdapter(QQBotChannelConfig(enabled=False))
        disabled_health = run(disabled.health())
        self.assertFalse(disabled_health.ok)
        self.assertEqual(disabled_health.component_id, "qqbot-channel")


if __name__ == "__main__":
    unittest.main()
