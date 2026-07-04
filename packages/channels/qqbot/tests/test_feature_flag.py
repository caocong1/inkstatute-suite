"""Feature flag default-off tests (QQBOT-04, SAFETY-04).

Verifies that ``qqbot_channel_enabled`` defaults to ``False`` in
``RuntimeFeatureFlags`` and that the QQBot adapter refuses ACK and
delivery when the flag is off (i.e. when ``QQBotChannelConfig.enabled``
is ``False``).

The feature flag already exists in ``feature_flags.py`` — this test does
NOT modify it.  It verifies the default-off behaviour and the adapter's
refusal behaviour.
"""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import fields

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import ChannelDelivery, RawInbound


def run(coro):
    return asyncio.run(coro)


def make_text_raw() -> RawInbound:
    """Construct a ``RawInbound`` with a QQBot text-message payload."""
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/inbound/msg-text-flag-1",
        received_at="2026-07-04T00:00:00Z",
        idempotency_key="qqbot-flag-idem-1",
        metadata={
            "payload": {
                "type": "message",
                "conversation_id": "conv-qqbot-flag-1",
                "user_id": "lawyer-1",
                "message_type": "text",
                "turn_id": "turn-qqbot-flag-1",
                "content_ref": "fixture://qqbot/content/msg-text-flag-1",
                "content_hash": "a" * 64,
            }
        },
    )


def make_text_delivery() -> ChannelDelivery:
    """Construct a ``ChannelDelivery`` with ``delivery_type="text"``."""
    return ChannelDelivery(
        delivery_id="delivery-qqbot-flag-1",
        channel_id="qqbot",
        run_id="run-1",
        content="根据《民法典》第五百六十三条，若对方根本违约，你方通常可以主张解除合同。",
        metadata={"delivery_type": "text", "to_user": "lawyer-1"},
    )


class FeatureFlagDefaultOffTests(unittest.TestCase):
    """Verify ``qqbot_channel_enabled`` defaults off and adapter refuses when disabled."""

    # ------------------------------------------------------------------
    # Feature flag default-off (RuntimeFeatureFlags)
    # ------------------------------------------------------------------

    def test_qqbot_channel_enabled_defaults_to_false(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertIs(flags.qqbot_channel_enabled, False)

    def test_qqbot_channel_enabled_field_exists_in_runtime_feature_flags(self) -> None:
        field_names = [f.name for f in fields(RuntimeFeatureFlags)]
        self.assertIn("qqbot_channel_enabled", field_names)

    # ------------------------------------------------------------------
    # Disabled adapter behaviour
    # ------------------------------------------------------------------

    def test_disabled_config_ack_rejected(self) -> None:
        adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=False))
        ack = run(adapter.verify_and_ack(make_text_raw()))
        self.assertIs(ack.accepted, False)
        self.assertEqual(ack.status_code, 503)

    def test_disabled_config_health_reports_not_ok(self) -> None:
        adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=False))
        health = run(adapter.health())
        self.assertIs(health.ok, False)
        self.assertEqual(health.component_id, "qqbot-channel")

    def test_disabled_config_delivery_refused(self) -> None:
        adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=False))
        result = run(adapter.deliver(make_text_delivery()))
        self.assertIs(result.accepted, False)

    # ------------------------------------------------------------------
    # Config defaults
    # ------------------------------------------------------------------

    def test_default_config_is_disabled(self) -> None:
        config = QQBotChannelConfig()
        self.assertIs(config.enabled, False)

    def test_from_env_does_not_enable_by_default(self) -> None:
        config = QQBotChannelConfig.from_env({})
        self.assertIs(config.enabled, False)

    def test_from_env_enables_only_explicit_truthy(self) -> None:
        enabled = QQBotChannelConfig.from_env({"INKSTATUTE_QQBOT_CHANNEL_ENABLED": "true"})
        self.assertIs(enabled.enabled, True)

        disabled = QQBotChannelConfig.from_env({"INKSTATUTE_QQBOT_CHANNEL_ENABLED": "false"})
        self.assertIs(disabled.enabled, False)

    # ------------------------------------------------------------------
    # All M2 feature flags default False (SAFETY-04)
    # ------------------------------------------------------------------

    def test_all_m2_feature_flags_default_false(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertIs(flags.router_service_enabled, False)
        self.assertIs(flags.skill_registry_enabled, False)
        self.assertIs(flags.admin_api_enabled, False)
        self.assertIs(flags.qqbot_channel_enabled, False)
        self.assertIs(flags.codex_backend_enabled, False)
        self.assertIs(flags.provider_model_backend_enabled, False)


if __name__ == "__main__":
    unittest.main()
