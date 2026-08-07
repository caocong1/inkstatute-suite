"""ADAPTER-01 real-IO metadata honesty across all 6 ChannelAdapter methods.

Covers live vs fixture Fake injection for capabilities/health/normalize/
deliver/verify_and_ack/channel_id behind the default-OFF `_live_io_ready` gate.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from inkstatute_channels_qqbot.sender import FakeMessageTransport
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
from platform_runtime.protocols import ChannelDelivery, RawInbound

from packages.channels.qqbot.tests.test_adapter_two_tier_ack import make_signed_raw

FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "bot_secret",
        "client_secret",
        "app_secret",
    }
)
FORBIDDEN_SECRET_VALUES = (
    "fixture-token",
    "fixture-client-secret",
)
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def run(coro):
    return asyncio.run(coro)


def _collect_keys(value: Any, found: set[str] | None = None) -> set[str]:
    keys = found if found is not None else set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).lower())
            _collect_keys(child, keys)
    elif isinstance(value, list):
        for child in value:
            _collect_keys(child, keys)
    return keys


def _assert_no_secrets(testcase: unittest.TestCase, metadata: Any) -> None:
    keys = _collect_keys(metadata)
    for forbidden in FORBIDDEN_SECRET_KEYS:
        testcase.assertNotIn(forbidden, keys)
    dumped = str(metadata)
    for fragment in FORBIDDEN_SECRET_VALUES:
        testcase.assertNotIn(fragment, dumped)
    # Header-style Authorization must never appear in metadata dumps.
    testcase.assertNotIn("Authorization", dumped)
    testcase.assertNotIn("access_token", dumped)


def _live_adapter(
    *,
    transport: FakeMessageTransport | None = None,
) -> tuple[QQBotChannelAdapter, FakeMessageTransport]:
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=FakeTokenTransport(
            response={"access_token": "fixture-token", "expires_in": 7200}
        ),
    )
    message_transport = transport or FakeMessageTransport(
        response={"id": "msg-real-io-ok", "status": 200}
    )
    adapter = QQBotChannelAdapter(
        QQBotChannelConfig(
            enabled=True,
            bot_secret_ref="ref://qqbot/bot-secret",
            app_id_ref="ref://qqbot/app-id",
            app_secret_ref="ref://qqbot/app-secret",
        ),
        token_manager=token_manager,
        transport=message_transport,
    )
    return adapter, message_transport


def _c2c_gateway_raw() -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/inbound/real-io-normalize",
        received_at="2026-07-09T00:00:00Z",
        idempotency_key="qqbot-real-io-norm-1",
        metadata={
            "payload": {
                "op": 0,
                "t": "C2C_MESSAGE_CREATE",
                "id": "evt-real-io-c2c-001",
                "s": 1,
                "d": {
                    "author": {"user_openid": "FIXTURE_USER_OPENID_C2C_001"},
                    "content": "test",
                    "id": "ROBOT1.0_fixture_c2c_msg_001",
                    "timestamp": "2026-07-09T12:00:00+08:00",
                    "attachments": [],
                },
            }
        },
    )


def _text_delivery() -> ChannelDelivery:
    return ChannelDelivery(
        delivery_id="deliv-real-io-1",
        channel_id="qqbot",
        run_id="run-real-io-1",
        content="根据《民法典》……",
        metadata={
            "delivery_type": "text",
            "scene": "c2c",
            "user_openid": "FIXTURE_USER_OPENID_C2C_001",
            "msg_id": "ROBOT1.0_fixture_c2c_msg_001",
            "received_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reply_count": 0,
        },
    )


class AdapterRealIoTests(unittest.TestCase):
    """ADAPTER-01: honest live vs fixture metadata across six Protocol methods."""

    # -- channel_id ------------------------------------------------------------

    def test_channel_id_unchanged(self) -> None:
        self.assertEqual(QQBotChannelAdapter().channel_id(), "qqbot")
        adapter, _ = _live_adapter()
        self.assertEqual(adapter.channel_id(), "qqbot")
        self.assertEqual(adapter.channel_id(), adapter._config.channel_id)

    # -- capabilities ----------------------------------------------------------

    def test_capabilities_fixture_when_disabled(self) -> None:
        caps = QQBotChannelAdapter().capabilities()
        self.assertTrue(caps.metadata.get("fixture_only"))
        self.assertFalse(caps.metadata.get("network_io"))
        self.assertFalse(caps.metadata.get("enabled"))
        self.assertEqual(caps.metadata.get("ack_strategy"), "webhook_op12_only")
        _assert_no_secrets(self, caps.metadata)

    def test_capabilities_live_when_ready(self) -> None:
        adapter, _ = _live_adapter()
        caps = adapter.capabilities()
        self.assertFalse(caps.metadata.get("fixture_only"))
        self.assertTrue(caps.metadata.get("network_io"))
        self.assertTrue(caps.metadata.get("enabled"))
        ack_strategy = str(caps.metadata.get("ack_strategy") or "")
        self.assertEqual(ack_strategy, "op12_plus_interaction_put")
        self.assertIn("op12", ack_strategy)
        self.assertIn("interaction_put", ack_strategy)
        _assert_no_secrets(self, caps.metadata)

    # -- health (A5: presence-only, no get_token) ------------------------------

    def test_health_presence_only_when_live(self) -> None:
        adapter, _ = _live_adapter()
        health = run(adapter.health())
        self.assertTrue(health.ok)
        self.assertTrue(health.metadata.get("live_io_ready"))
        self.assertTrue(health.metadata.get("token_manager_present"))
        self.assertTrue(health.metadata.get("transport_present"))
        self.assertFalse(health.metadata.get("network_io"))
        self.assertFalse(health.metadata.get("fixture_only"))
        _assert_no_secrets(self, health.metadata)

    def test_health_presence_only_when_disabled(self) -> None:
        health = run(QQBotChannelAdapter().health())
        self.assertFalse(health.ok)
        self.assertFalse(health.metadata.get("live_io_ready"))
        self.assertFalse(health.metadata.get("token_manager_present"))
        self.assertFalse(health.metadata.get("transport_present"))
        self.assertFalse(health.metadata.get("network_io"))
        self.assertTrue(health.metadata.get("fixture_only"))
        _assert_no_secrets(self, health.metadata)

    # -- normalize_inbound (local; no network_io claim) ------------------------

    def test_normalize_inbound_metadata_honesty_live(self) -> None:
        adapter, _ = _live_adapter()
        inbound = run(adapter.normalize_inbound(_c2c_gateway_raw()))
        self.assertIsNotNone(inbound.message)
        self.assertFalse(inbound.metadata.get("fixture_only"))
        # Normalize is local — must not claim network_io.
        self.assertFalse(inbound.metadata.get("network_io", False))
        _assert_no_secrets(self, inbound.metadata)

    def test_normalize_inbound_metadata_honesty_fixture(self) -> None:
        inbound = run(QQBotChannelAdapter().normalize_inbound(_c2c_gateway_raw()))
        self.assertIsNotNone(inbound.message)
        self.assertTrue(inbound.metadata.get("fixture_only"))
        self.assertFalse(inbound.metadata.get("network_io", False))

    # -- deliver ---------------------------------------------------------------

    def test_deliver_text_live_sets_network_io(self) -> None:
        adapter, transport = _live_adapter()
        result = run(adapter.deliver(_text_delivery()))
        self.assertTrue(result.accepted)
        self.assertTrue(result.metadata.get("network_io"))
        self.assertFalse(result.metadata.get("fixture_only"))
        self.assertGreaterEqual(transport.call_count, 1)
        _assert_no_secrets(self, result.metadata)

    def test_deliver_refuses_or_fixture_when_disabled(self) -> None:
        transport = FakeMessageTransport(response={"id": "should-not-send"})
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=False),
            token_manager=TokenManager(
                app_id="fixture-app-id",
                client_secret="fixture-client-secret",
                transport=FakeTokenTransport(
                    response={"access_token": "fixture-token", "expires_in": 7200}
                ),
            ),
            transport=transport,
        )
        result = run(adapter.deliver(_text_delivery()))
        self.assertFalse(result.accepted)
        self.assertFalse(result.metadata.get("network_io", False))
        self.assertEqual(transport.call_count, 0)
        _assert_no_secrets(self, result.metadata)

    def test_deliver_refuses_when_enabled_without_live_io(self) -> None:
        """enabled=True without transport/token must not report accepted delivery."""
        adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))
        result = run(adapter.deliver(_text_delivery()))
        self.assertFalse(result.accepted)
        self.assertIsNone(result.delivered_at)
        self.assertEqual(result.metadata.get("issue_code"), "live_io_not_ready")
        self.assertFalse(result.metadata.get("network_io", False))
        self.assertTrue(result.metadata.get("fixture_only"))
        _assert_no_secrets(self, result.metadata)

    # -- verify_and_ack (privacy on Ack metadata) ------------------------------

    def test_verify_and_ack_disabled_metadata_privacy(self) -> None:
        adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=False))
        ack = run(
            adapter.verify_and_ack(
                RawInbound(
                    channel_id="qqbot",
                    payload_ref="fixture://qqbot/ack/disabled",
                    received_at="2026-07-09T00:00:00Z",
                    idempotency_key="qqbot-real-io-ack-disabled",
                    metadata={"payload": {"type": "message"}},
                )
            )
        )
        self.assertFalse(ack.accepted)
        self.assertEqual(ack.status_code, 503)
        self.assertFalse(ack.metadata.get("network_io", False))
        self.assertTrue(ack.metadata.get("fixture_only"))
        _assert_no_secrets(self, ack.metadata)

    def test_verify_and_ack_live_metadata_privacy(self) -> None:
        """T-65-08: live Fake ACK metadata must not leak tokens/Authorization."""
        with open(FIXTURES_DIR / "qqbot_interaction_create.json", encoding="utf-8") as fh:
            envelope = json.load(fh)["envelope"]
        adapter, transport = _live_adapter(
            transport=FakeMessageTransport(response={"code": 0})
        )
        ack = run(adapter.verify_and_ack(make_signed_raw(payload=envelope)))
        self.assertTrue(ack.accepted)
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(ack.metadata.get("interaction_ack_status"), "sent")
        self.assertGreaterEqual(transport.call_count, 1)
        _assert_no_secrets(self, ack.metadata)
        # Explicit case-insensitive key + dump scan (acceptance: fail if present).
        keys = _collect_keys(ack.metadata)
        self.assertNotIn("access_token", keys)
        self.assertNotIn("authorization", keys)
        self.assertNotIn("bot_secret", keys)
        dumped = json.dumps(ack.metadata, default=str)
        self.assertNotIn("Authorization", dumped)
        self.assertNotIn("access_token", dumped)
        self.assertNotIn("fixture-token", dumped)

    def test_deliver_live_metadata_privacy_rejects_secret_keys(self) -> None:
        """T-65-08: DeliveryResult.metadata after live Fake deliver is secret-free."""
        adapter, transport = _live_adapter()
        result = run(adapter.deliver(_text_delivery()))
        self.assertTrue(result.accepted)
        self.assertGreaterEqual(transport.call_count, 1)
        _assert_no_secrets(self, result.metadata)
        keys = _collect_keys(result.metadata)
        for forbidden in ("access_token", "authorization", "bot_secret"):
            self.assertNotIn(forbidden, keys)
        dumped = json.dumps(result.metadata, default=str)
        self.assertNotIn("Authorization", dumped)
        self.assertNotIn("access_token", dumped)
        self.assertNotIn("fixture-token", dumped)

    def test_privacy_helper_rejects_forbidden_metadata_keys(self) -> None:
        """Guard: _assert_no_secrets must fail when secrets appear in metadata."""
        with self.assertRaises(AssertionError):
            _assert_no_secrets(self, {"access_token": "leaked"})
        with self.assertRaises(AssertionError):
            _assert_no_secrets(self, {"Authorization": "Bearer x"})
        with self.assertRaises(AssertionError):
            _assert_no_secrets(self, {"nested": {"bot_secret": "raw"}})

    # -- _live_io_ready helper -------------------------------------------------

    def test_live_io_ready_helper_exists(self) -> None:
        adapter, _ = _live_adapter()
        self.assertTrue(hasattr(adapter, "_live_io_ready"))
        self.assertTrue(adapter._live_io_ready())
        self.assertFalse(QQBotChannelAdapter()._live_io_ready())


if __name__ == "__main__":
    unittest.main()
