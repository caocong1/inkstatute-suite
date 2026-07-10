"""HOST-03: disabled composed wiring refuses live IO without transport calls."""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_channels_qqbot.sender import FakeMessageTransport
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
from platform_runtime.fakes import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import ChannelDelivery, RawInbound
from qqbot_service.config import QQBotHostConfig
from qqbot_service.wiring import build_qqbot_wired_runtime


def run(coro):
    return asyncio.run(coro)


def make_text_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/inbound/msg-text-host03-1",
        received_at="2026-07-10T00:00:00Z",
        idempotency_key="qqbot-host03-idem-1",
        metadata={
            "payload": {
                "type": "message",
                "conversation_id": "conv-qqbot-host03-1",
                "user_id": "lawyer-1",
                "message_type": "text",
                "turn_id": "turn-qqbot-host03-1",
                "content_ref": "fixture://qqbot/content/msg-text-host03-1",
                "content_hash": "b" * 64,
            }
        },
    )


def make_text_delivery() -> ChannelDelivery:
    return ChannelDelivery(
        delivery_id="delivery-qqbot-host03-1",
        channel_id="qqbot",
        run_id="run-host03-1",
        content="根据《民法典》第五百六十三条，若对方根本违约，你方通常可以主张解除合同。",
        metadata={
            "delivery_type": "text",
            "scene": "c2c",
            "user_openid": "FIXTURE_USER_OPENID_C2C_HOST03",
            "msg_id": "ROBOT1.0_fixture_c2c_host03_001",
            "received_at": "2026-07-10T11:59:00Z",
            "reply_count": 0,
        },
    )


def _live_fakes() -> tuple[TokenManager, FakeMessageTransport, FakeTokenTransport]:
    token_transport = FakeTokenTransport(
        response={"access_token": "fixture-token", "expires_in": 7200}
    )
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=token_transport,
    )
    message_transport = FakeMessageTransport(
        response={"id": "msg-host03-ok", "status": 200}
    )
    return token_manager, message_transport, token_transport


class WiringDisabledRefuseTests(unittest.TestCase):
    """HOST-03: composed path refuses when flags/config OFF; no OpenAPI calls."""

    def test_disabled_wiring_ack_returns_503(self) -> None:
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(),  # qqbot OFF
            host_config=QQBotHostConfig(),
        )
        ack = run(wired.adapter.verify_and_ack(make_text_raw()))
        self.assertIs(ack.accepted, False)
        self.assertEqual(ack.status_code, 503)

    def test_disabled_wiring_deliver_refused(self) -> None:
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(),
            host_config=QQBotHostConfig(),
        )
        result = run(wired.adapter.deliver(make_text_delivery()))
        self.assertIs(result.accepted, False)

    def test_disabled_wiring_ignores_supplied_fakes_no_transport_calls(self) -> None:
        token_manager, message_transport, token_transport = _live_fakes()
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=False),
            host_config=QQBotHostConfig(enabled=True),
            token_manager=token_manager,
            transport=message_transport,
        )
        ack = run(wired.adapter.verify_and_ack(make_text_raw()))
        result = run(wired.adapter.deliver(make_text_delivery()))
        self.assertIs(ack.accepted, False)
        self.assertEqual(ack.status_code, 503)
        self.assertIs(result.accepted, False)
        self.assertEqual(message_transport.call_count, 0)
        self.assertEqual(token_transport.call_count, 0)

    def test_enabled_wiring_with_fakes_can_exercise_deliver_without_network(self) -> None:
        token_manager, message_transport, token_transport = _live_fakes()
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=True),
            host_config=QQBotHostConfig(
                app_id_ref="secret://qqbot/app-id",
                app_secret_ref="secret://qqbot/app-secret",
                bot_secret_ref="secret://qqbot/bot-secret",
            ),
            token_manager=token_manager,
            transport=message_transport,
        )
        self.assertIs(wired.live_io_ready, True)
        # Contrast: enabled+Fake may invoke FakeMessageTransport — never Urllib*
        result = run(wired.adapter.deliver(make_text_delivery()))
        self.assertNotIn("Urllib", type(wired.adapter._transport).__name__)
        self.assertNotIn("Urllib", type(token_manager._transport).__name__)
        # Disabled path never increments; enabled Fake path may.
        # Accept either accepted deliver or gated refusal, but Fake-only.
        self.assertIsInstance(message_transport, FakeMessageTransport)
        if result.accepted:
            self.assertGreaterEqual(message_transport.call_count, 1)
        # No real network classes constructed on the composed adapter.
        self.assertEqual(type(wired.adapter._transport).__name__, "FakeMessageTransport")

    def test_disabled_capabilities_network_io_false(self) -> None:
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(),
            host_config=QQBotHostConfig(),
        )
        caps = wired.adapter.capabilities()
        self.assertFalse(caps.metadata.get("network_io", True))
        self.assertTrue(caps.metadata.get("fixture_only"))


if __name__ == "__main__":
    unittest.main()
