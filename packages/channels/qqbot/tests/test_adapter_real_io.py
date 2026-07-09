"""Wave 0 RED stubs for ADAPTER-01 live vs fixture metadata (Plan 02 greens).

Documents expected honesty for capabilities/health/normalize/deliver/verify_and_ack
when `_live_io_ready()` is true vs fixture-only default-OFF path.
"""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from inkstatute_channels_qqbot.sender import FakeMessageTransport
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
from platform_runtime.protocols import ChannelDelivery, RawInbound


def run(coro):
    return asyncio.run(coro)


def _live_adapter() -> QQBotChannelAdapter:
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=FakeTokenTransport(
            response={"access_token": "fixture-token", "expires_in": 7200}
        ),
    )
    return QQBotChannelAdapter(
        QQBotChannelConfig(
            enabled=True,
            bot_secret_ref="ref://qqbot/bot-secret",
            app_id_ref="ref://qqbot/app-id",
            app_secret_ref="ref://qqbot/app-secret",
        ),
        token_manager=token_manager,
        transport=FakeMessageTransport(),
    )


class AdapterRealIoStubTests(unittest.TestCase):
    """Plan 02: capabilities/health advertise fixture_only/network_io via live gate."""

    def test_capabilities_live_ready_advertises_network_io(self) -> None:
        """When enabled+token+transport, capabilities.metadata is not fixture-only."""
        caps = _live_adapter().capabilities()
        self.assertFalse(caps.metadata.get("fixture_only"))
        self.assertTrue(caps.metadata.get("network_io"))
        self.assertTrue(caps.metadata.get("enabled"))

    def test_capabilities_default_off_stays_fixture_only(self) -> None:
        """Default/disabled adapter keeps fixture_only=True and network_io=False."""
        caps = QQBotChannelAdapter().capabilities()
        self.assertTrue(caps.metadata.get("fixture_only"))
        self.assertFalse(caps.metadata.get("network_io"))
        self.assertFalse(caps.metadata.get("enabled"))

    def test_health_reports_live_io_ready_without_network_call(self) -> None:
        """health.metadata.live_io_ready True when gated; health itself network_io False."""
        health = run(_live_adapter().health())
        self.assertTrue(health.ok)
        self.assertTrue(health.metadata.get("live_io_ready"))
        self.assertFalse(health.metadata.get("network_io"))
        self.assertFalse(health.metadata.get("fixture_only"))

    def test_normalize_inbound_marks_live_ready_metadata(self) -> None:
        """normalize_inbound metadata fixture_only reflects live readiness (Plan 02)."""
        adapter = _live_adapter()
        raw = RawInbound(
            channel_id="qqbot",
            payload_ref="fixture://qqbot/inbound/real-io-normalize",
            received_at="2026-07-09T00:00:00Z",
            idempotency_key="qqbot-real-io-norm-1",
            metadata={
                "payload": {
                    "type": "message",
                    "conversation_id": "qqbot:c2c:fixture:fixture",
                    "user_id": "FIXTURE_USER_OPENID_C2C_001",
                    "content_ref": "ref://fixture/content",
                }
            },
        )
        inbound = run(adapter.normalize_inbound(raw))
        self.assertFalse(inbound.metadata.get("fixture_only"))

    def test_deliver_live_path_sets_network_io_when_sent(self) -> None:
        """deliver with live gate + scene may set network_io True (existing sender path)."""
        adapter = _live_adapter()
        delivery = ChannelDelivery(
            delivery_id="deliv-real-io-1",
            channel_id="qqbot",
            run_id="run-real-io-1",
            content="根据《民法典》……",
            metadata={
                "delivery_type": "text",
                "scene": "c2c",
                "user_openid": "FIXTURE_USER_OPENID_C2C_001",
                "msg_id": "ROBOT1.0_fixture_c2c_msg_001",
                "received_at": "2026-07-09T11:59:00Z",
                "reply_count": 0,
            },
        )
        result = run(adapter.deliver(delivery))
        self.assertTrue(result.accepted)
        self.assertTrue(result.metadata.get("network_io"))
        self.assertFalse(result.metadata.get("fixture_only"))

    def test_live_io_ready_helper_exists(self) -> None:
        """Plan 02/01 share private _live_io_ready on the adapter."""
        adapter = _live_adapter()
        self.assertTrue(hasattr(adapter, "_live_io_ready"))
        self.assertTrue(adapter._live_io_ready())
        self.assertFalse(QQBotChannelAdapter()._live_io_ready())


if __name__ == "__main__":
    unittest.main()
