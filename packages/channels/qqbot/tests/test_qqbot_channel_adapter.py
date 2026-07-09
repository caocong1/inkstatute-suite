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
        self.assertFalse(capabilities.supports_streaming)
        self.assertEqual(capabilities.idempotency_strategy, "qqbot_callback_metadata")
        self.assertTrue(capabilities.metadata["fixture_only"])
        self.assertFalse(capabilities.metadata["network_io"])

    def test_capabilities_supports_files_and_images(self) -> None:
        capabilities = self.adapter.capabilities()
        self.assertTrue(capabilities.supports_files)
        self.assertTrue(capabilities.supports_images)
        self.assertFalse(capabilities.supports_voice)
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

        # enabled=True without transport/token must not claim delivery success.
        self.assertFalse(result.accepted)
        self.assertIsNone(result.delivered_at)
        self.assertEqual(result.metadata["issue_code"], "live_io_not_ready")
        self.assertEqual(result.metadata["delivery_type"], "text")
        self.assertEqual(result.metadata["message_type"], "text")
        self.assertEqual(result.metadata["policy_action"], "allow")
        self.assertFalse(result.metadata["network_io"])
        envelope = result.metadata["envelope"]
        self.assertEqual(envelope["msg_type"], 0)
        self.assertIn("content", envelope)

    def test_card_delivery_builds_card_envelope(self) -> None:
        result = run(self.adapter.deliver(card_delivery()))

        self.assertFalse(result.accepted)
        self.assertIsNone(result.delivered_at)
        self.assertEqual(result.metadata["issue_code"], "live_io_not_ready")
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

        self.assertFalse(result.accepted)
        self.assertIsNone(result.delivered_at)
        self.assertEqual(result.metadata["issue_code"], "live_io_not_ready")
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

    def test_window_gate_fails_closed_when_scene_missing(self) -> None:
        """Missing scene must not default to c2c permissive limits."""
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-window-missing-scene",
            channel_id="qqbot",
            run_id="run-1",
            content="缺少 scene",
            metadata={
                "delivery_type": "text",
                "msg_id": "msg-no-scene",
                # Age would still be within C2C 60min if scene were defaulted.
                "received_at": "2026-07-09T11:50:00Z",
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

    def test_live_send_rejects_missing_scene(self) -> None:
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import (
            FakeTokenTransport,
            TokenManager,
        )

        manager = TokenManager(
            app_id="fixture-app-id-001",
            client_secret="fixture-client-secret-001",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-token", "expires_in": 7200}
            ),
        )
        transport = FakeMessageTransport(response={"id": "should-not-send"})
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=manager,
            transport=transport,
        )
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-no-scene-live",
            channel_id="qqbot",
            run_id="run-1",
            content="根据《民法典》……",
            metadata={
                "delivery_type": "text",
                "user_openid": "user-openid-1",
            },
        )
        result = run(adapter.deliver(delivery))

        self.assertFalse(result.accepted)
        self.assertEqual(result.metadata["issue_code"], "qqbot_send_failed")
        self.assertIn("scene", result.metadata["send_error"])
        self.assertEqual(transport.call_count, 0)

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

    def test_empty_content_delivery_not_accepted(self) -> None:
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-empty-1",
            channel_id="qqbot",
            run_id="run-1",
            content="",
            metadata={"delivery_type": "text", "to_user": "lawyer-1"},
        )
        result = run(self.adapter.deliver(delivery))

        self.assertFalse(result.accepted)
        self.assertNotIn("msg_type", result.metadata["envelope"])
        self.assertEqual(result.metadata["policy_action"], "allow")
        self.assertIsNone(result.delivered_at)

    def test_deliver_maps_token_error_to_delivery_failure(self) -> None:
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import (
            FakeTokenTransport,
            TokenError,
            TokenManager,
        )

        manager = TokenManager(
            app_id="fixture-app-id-001",
            client_secret="fixture-client-secret-001",
            transport=FakeTokenTransport(
                error=TokenError("secret-token-leak-xyz", status_code=503)
            ),
        )
        transport = FakeMessageTransport(response={"id": "should-not-send"})
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=manager,
            transport=transport,
        )
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-token-fail",
            channel_id="qqbot",
            run_id="run-1",
            content="根据《民法典》……",
            metadata={
                "delivery_type": "text",
                "scene": "c2c",
                "user_openid": "user-openid-1",
            },
        )
        result = run(adapter.deliver(delivery))

        self.assertFalse(result.accepted)
        self.assertEqual(result.metadata["issue_code"], "qqbot_send_failed")
        self.assertEqual(result.metadata["send_error"], "QQ Bot token unavailable")
        self.assertNotIn("secret-token-leak-xyz", result.metadata["send_error"])
        self.assertEqual(result.metadata.get("send_status_code"), 503)
        self.assertEqual(transport.call_count, 0)

    def test_deliver_file_two_step_with_injected_transport(self) -> None:
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import (
            FakeTokenTransport,
            TokenManager,
        )

        file_url = "https://example.invalid/artifact.docx"
        manager = TokenManager(
            app_id="fixture-app-id-001",
            client_secret="fixture-client-secret-001",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-token", "expires_in": 7200}
            ),
        )
        transport = FakeMessageTransport(
            responses=[
                {
                    "file_uuid": "uuid-adapter-file-1",
                    "file_info": "file-info-adapter-1",
                    "ttl": 3600,
                },
                {"id": "msg-media-adapter-ok", "status": 200},
            ]
        )
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=manager,
            transport=transport,
        )
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-file-1",
            channel_id="qqbot",
            run_id="run-1",
            content="",
            metadata={
                "delivery_type": "file",
                "file_url": file_url,
                "file_type": 4,
                "scene": "c2c",
                "user_openid": "user-openid-1",
                "msg_id": "inbound-file-1",
                "received_at": "2026-07-09T11:55:00Z",
                "reply_count": 0,
            },
        )
        result = run(adapter.deliver(delivery))

        self.assertTrue(result.accepted)
        self.assertEqual(transport.call_count, 2)
        self.assertTrue(
            result.metadata.get("network_io") is True
            or (
                isinstance(result.metadata.get("envelope"), dict)
                and result.metadata["envelope"].get("msg_type") == 7
            )
        )
        self.assertTrue(
            result.metadata.get("rich_media_stage") is not None
            or "file_uuid_hash" in result.metadata
            or "attempts" in result.metadata
        )
        meta_str = str(result.metadata)
        self.assertNotIn("file_data", meta_str)
        self.assertNotIn("access_token", meta_str)
        self.assertNotIn("Authorization", meta_str)
        self.assertNotIn(file_url, meta_str)
        upload_call, send_call = transport.calls
        self.assertTrue(upload_call["url"].endswith("/files"))
        self.assertEqual(upload_call["body"]["file_type"], 4)
        self.assertEqual(send_call["body"]["msg_type"], 7)

    def test_deliver_file_missing_file_url_fails_closed(self) -> None:
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import (
            FakeTokenTransport,
            TokenManager,
        )

        manager = TokenManager(
            app_id="fixture-app-id-001",
            client_secret="fixture-client-secret-001",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-token", "expires_in": 7200}
            ),
        )
        transport = FakeMessageTransport(response={"file_info": "should-not-upload"})
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=manager,
            transport=transport,
        )
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-file-missing-url",
            channel_id="qqbot",
            run_id="run-1",
            content="",
            metadata={
                "delivery_type": "file",
                "scene": "c2c",
                "user_openid": "user-openid-1",
                "msg_id": "inbound-file-missing-url",
                "received_at": "2026-07-09T11:55:00Z",
                "reply_count": 0,
            },
        )
        result = run(adapter.deliver(delivery))

        self.assertFalse(result.accepted)
        self.assertIn("upload", str(result.metadata.get("issue_code", "")).lower())
        self.assertEqual(transport.call_count, 0)

    def test_deliver_file_missing_file_info_classifies_upload_failure(self) -> None:
        """WR-03: upload HTTP success without file_info keeps upload-stage issue_code."""
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import (
            FakeTokenTransport,
            TokenManager,
        )

        manager = TokenManager(
            app_id="fixture-app-id-001",
            client_secret="fixture-client-secret-001",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-token", "expires_in": 7200}
            ),
        )
        transport = FakeMessageTransport(
            response={"file_uuid": "uuid-missing-info", "ttl": 60}
        )
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=manager,
            transport=transport,
        )
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-file-missing-info",
            channel_id="qqbot",
            run_id="run-1",
            content="",
            metadata={
                "delivery_type": "file",
                "file_url": "https://example.invalid/artifact.docx",
                "file_type": 4,
                "scene": "c2c",
                "user_openid": "user-openid-1",
                "msg_id": "inbound-file-missing-info",
                "received_at": "2026-07-09T11:55:00Z",
                "reply_count": 0,
            },
        )
        result = run(adapter.deliver(delivery))

        self.assertFalse(result.accepted)
        self.assertEqual(
            result.metadata.get("issue_code"), "qqbot_rich_media_upload_failed"
        )
        self.assertEqual(result.metadata.get("rich_media_stage"), "upload")
        self.assertEqual(result.metadata.get("attempts"), 1)
        self.assertEqual(transport.call_count, 1)

    def test_deliver_file_window_expired_skips_upload(self) -> None:
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import (
            FakeTokenTransport,
            TokenManager,
        )

        manager = TokenManager(
            app_id="fixture-app-id-001",
            client_secret="fixture-client-secret-001",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-token", "expires_in": 7200}
            ),
        )
        transport = FakeMessageTransport(
            response={
                "file_uuid": "should-not-upload",
                "file_info": "should-not-upload",
                "ttl": 3600,
            }
        )
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=manager,
            transport=transport,
        )
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-file-window-expired",
            channel_id="qqbot",
            run_id="run-1",
            content="",
            metadata={
                "delivery_type": "file",
                "file_url": "https://example.invalid/late.docx",
                "file_type": 4,
                "scene": "group",
                "group_openid": "group-openid-1",
                "msg_id": "msg-file-expired-1",
                "received_at": "2020-01-01T00:00:00Z",
                "reply_count": 0,
            },
        )
        result = run(adapter.deliver(delivery))

        self.assertFalse(result.accepted)
        self.assertEqual(
            result.metadata["issue_code"], "qqbot_passive_reply_window_expired"
        )
        self.assertTrue(result.metadata.get("interim_notice"))
        self.assertEqual(transport.call_count, 0)

    def test_deliver_image_uses_file_type_1_default(self) -> None:
        from inkstatute_channels_qqbot.sender import FakeMessageTransport
        from inkstatute_channels_qqbot.token_manager import (
            FakeTokenTransport,
            TokenManager,
        )

        manager = TokenManager(
            app_id="fixture-app-id-001",
            client_secret="fixture-client-secret-001",
            transport=FakeTokenTransport(
                response={"access_token": "fixture-token", "expires_in": 7200}
            ),
        )
        transport = FakeMessageTransport(
            responses=[
                {
                    "file_uuid": "uuid-adapter-image-1",
                    "file_info": "file-info-adapter-image-1",
                    "ttl": 3600,
                },
                {"id": "msg-image-adapter-ok", "status": 200},
            ]
        )
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True),
            token_manager=manager,
            transport=transport,
        )
        delivery = ChannelDelivery(
            delivery_id="delivery-qqbot-image-1",
            channel_id="qqbot",
            run_id="run-1",
            content="",
            metadata={
                "delivery_type": "image",
                "file_url": "https://example.invalid/photo.png",
                "scene": "c2c",
                "user_openid": "user-openid-1",
                "msg_id": "inbound-image-1",
                "received_at": "2026-07-09T11:55:00Z",
                "reply_count": 0,
            },
        )
        result = run(adapter.deliver(delivery))

        self.assertTrue(result.accepted)
        self.assertGreaterEqual(transport.call_count, 1)
        self.assertEqual(transport.calls[0]["body"]["file_type"], 1)

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
