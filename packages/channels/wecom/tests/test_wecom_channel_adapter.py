from __future__ import annotations

import asyncio
import unittest
from dataclasses import asdict
from pathlib import Path

from inkstatute_channels_wecom import WeComChannelAdapter, WeComChannelConfig
from platform_contract.events import AgentResult, AgentTurn, FeedbackEvent
from platform_runtime.protocols import ChannelDelivery, RawInbound
from wecom_service.protocol import RawPayloadForbiddenError


PHASE_ROOT = Path(__file__).resolve().parents[1]


def run(coro):
    return asyncio.run(coro)


def text_raw() -> RawInbound:
    return RawInbound(
        channel_id="wecom",
        payload_ref="fixture://wecom/callback/msg-text-1",
        received_at="2026-06-28T04:00:00Z",
        idempotency_key="idem-1",
        metadata={
            "callback": {
                "MsgId": "msg-text-1",
                "FromUserName": "lawyer-1",
                "ConversationId": "conv-1",
                "MsgType": "text",
                "CreateTime": "1782628800",
                "Content": "请检索合同解除的裁判观点。",
                "raw_payload_ref": "fixture://wecom/callback/msg-text-1",
            }
        },
    )


class WeComChannelConfigTests(unittest.TestCase):
    def test_config_defaults_to_disabled(self) -> None:
        self.assertFalse(WeComChannelConfig().enabled)

    def test_from_env_enables_only_explicit_truthy_values(self) -> None:
        enabled = WeComChannelConfig.from_env({"INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED": "true"})
        disabled = WeComChannelConfig.from_env({"INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED": "on"})

        self.assertTrue(enabled.enabled)
        self.assertFalse(disabled.enabled)

    def test_config_keeps_secret_refs_only(self) -> None:
        config = WeComChannelConfig.from_env(
            {
                "INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED": "1",
                "INKSTATUTE_WECOM_TOKEN_SECRET_REF": "secret://wecom/token",
                "INKSTATUTE_WECOM_AES_KEY_SECRET_REF": "secret://wecom/aes",
                "INKSTATUTE_WECOM_CORP_ID_REF": "secret://wecom/corp-id",
                "INKSTATUTE_WECOM_TOKEN": "raw-token-should-be-ignored",
            }
        )

        self.assertEqual(config.token_secret_ref, "secret://wecom/token")
        self.assertEqual(config.encoding_aes_key_secret_ref, "secret://wecom/aes")
        self.assertEqual(config.corp_id_ref, "secret://wecom/corp-id")
        self.assertNotIn("raw-token-should-be-ignored", str(asdict(config)))


class WeComChannelAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = WeComChannelAdapter(WeComChannelConfig(enabled=True))

    def test_verify_and_ack_uses_existing_ack_response(self) -> None:
        ack = run(self.adapter.verify_and_ack(text_raw()))

        self.assertTrue(ack.accepted)
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(ack.idempotency_key, "idem-1")
        self.assertEqual(ack.metadata["ack_body"], "success")
        self.assertEqual(ack.metadata["raw_payload_ref"], "fixture://wecom/callback/msg-text-1")

    def test_text_callback_normalizes_to_agent_turn(self) -> None:
        normalized = run(self.adapter.normalize_inbound(text_raw()))

        self.assertIsInstance(normalized.message, AgentTurn)
        self.assertIsNone(normalized.feedback)
        self.assertEqual(normalized.message.channel, "wecom")
        self.assertEqual(normalized.message.message_type, "text")
        self.assertEqual(normalized.message.content, "请检索合同解除的裁判观点。")
        self.assertEqual(
            normalized.message.metadata["raw_payload_ref"],
            "fixture://wecom/callback/msg-text-1",
        )

    def test_feedback_callback_normalizes_to_feedback_event(self) -> None:
        raw = RawInbound(
            channel_id="wecom",
            payload_ref="fixture://wecom/callback/feedback-1",
            received_at="2026-06-28T04:00:02Z",
            metadata={
                "callback": {
                    "CallbackId": "callback-1",
                    "FromUserName": "lawyer-3",
                    "ConversationId": "conv-3",
                    "Event": "click",
                    "EventKey": "feedback:route_wrong",
                    "TurnId": "turn-3",
                    "feedback_target": "result-msg-3",
                    "raw_payload_ref": "fixture://wecom/callback/feedback-1",
                }
            },
        )

        normalized = run(self.adapter.normalize_inbound(raw))

        self.assertIsNone(normalized.message)
        self.assertIsInstance(normalized.feedback, FeedbackEvent)
        self.assertEqual(normalized.feedback.source, "card_button")
        self.assertEqual(normalized.feedback.status, "pending")
        self.assertEqual(normalized.feedback.action, "route_wrong")
        self.assertTrue(normalized.feedback.skill_candidate.requires_human_review)

    def test_raw_payload_keys_are_rejected_by_existing_parser(self) -> None:
        raw = RawInbound(
            channel_id="wecom",
            payload_ref="fixture://wecom/callback/raw",
            received_at="2026-06-28T04:00:00Z",
            metadata={"callback": {"MsgId": "msg-raw", "raw_payload": "<xml>secret</xml>"}},
        )

        with self.assertRaises(RawPayloadForbiddenError):
            run(self.adapter.normalize_inbound(raw))

    def test_text_delivery_builds_policy_checked_envelope_without_io(self) -> None:
        result = run(
            self.adapter.deliver(
                ChannelDelivery(
                    delivery_id="delivery-1",
                    channel_id="wecom",
                    content="根据《民法典》第五百六十三条，可结合根本违约主张解除。",
                    metadata={"to_user": "lawyer-1"},
                )
            )
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.metadata["message_type"], "text")
        self.assertFalse(result.metadata["network_io"])
        self.assertEqual(result.metadata["envelope"]["policy"]["action"], "allow")

    def test_unsafe_text_delivery_is_blocked_by_existing_output_policy(self) -> None:
        result = run(
            self.adapter.deliver(
                ChannelDelivery(
                    delivery_id="delivery-block",
                    channel_id="wecom",
                    content="Hermes gateway disconnected: token=abc",
                    metadata={"to_user": "lawyer-1"},
                )
            )
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.metadata["envelope"]["policy"]["action"], "block")
        self.assertNotIn("text", result.metadata["envelope"])
        self.assertNotIn("Hermes gateway disconnected", str(result.metadata["envelope"]))
        self.assertNotIn("token=abc", str(result.metadata["envelope"]))

    def test_file_and_card_delivery_build_sanitized_envelopes(self) -> None:
        turn = AgentTurn(
            turn_id="turn-1",
            conversation_id="conv-1",
            channel="wecom",
            user_id="lawyer-1",
            message_type="text",
            received_at="2026-06-28T04:00:00Z",
        )
        agent_result = AgentResult(
            result_id="result-1",
            turn_id=turn.turn_id,
            status="completed",
            reply_type="answer",
            feedback_target="result-1",
        )

        file_result = run(
            self.adapter.deliver(
                ChannelDelivery(
                    delivery_id="delivery-file",
                    channel_id="wecom",
                    content="合同修订稿已生成。",
                    artifact_refs=["media-1"],
                    metadata={"to_user": "lawyer-1", "delivery_type": "file"},
                )
            )
        )
        card_result = run(
            self.adapter.deliver(
                ChannelDelivery(
                    delivery_id="delivery-card",
                    channel_id="wecom",
                    result=agent_result,
                    content="请评价本次回复",
                    metadata={
                        "to_user": "lawyer-1",
                        "delivery_type": "card",
                        "card_id": "card-1",
                    },
                )
            )
        )

        self.assertEqual(file_result.metadata["envelope"]["msgtype"], "file")
        self.assertEqual(file_result.metadata["envelope"]["file"]["media_id"], "media-1")
        self.assertEqual(card_result.metadata["envelope"]["msgtype"], "template_card")
        self.assertEqual(
            card_result.metadata["envelope"]["template_card"]["feedback_target"],
            "result-1",
        )

    def test_capabilities_and_health_do_not_expose_secret_values(self) -> None:
        adapter = WeComChannelAdapter(
            WeComChannelConfig(
                enabled=True,
                token_secret_ref="secret://wecom/token",
                encoding_aes_key_secret_ref="secret://wecom/aes",
                corp_id_ref="secret://wecom/corp-id",
            )
        )

        capabilities = adapter.capabilities()
        health = run(adapter.health())

        self.assertTrue(capabilities.supports_text)
        self.assertTrue(capabilities.supports_files)
        self.assertTrue(capabilities.supports_cards)
        self.assertNotIn("no_channel_io", str(asdict(capabilities)))
        self.assertNotIn("raw-token", str(asdict(health)))
        self.assertEqual(health.component_id, "wecom-channel")

    def test_channel_package_does_not_import_concrete_backend_code(self) -> None:
        forbidden = ("BackendAdapter", "backends", "inkstatute_backends_hermes")
        for path in (PHASE_ROOT / "src").rglob("*.py"):
            source = path.read_text()
            for marker in forbidden:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()
