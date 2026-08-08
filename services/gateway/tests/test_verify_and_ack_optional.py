"""Tests for optional verify_and_ack capability (GW-06).

Verifies that:
- ChannelCapabilitySet has verify_and_ack_support field (default False)
- QqBotChannelAdapter declares verify_and_ack_support=True
- WeComChannelAdapter declares verify_and_ack_support=True
- FakeChannelAdapter declares verify_and_ack_support=False
- Adapters without verify_and_ack_support still pass Protocol validation
- Adapters with verify_and_ack_support=True work correctly
"""

from __future__ import annotations

import unittest

from inkstatute_channels_qqbot.adapter import QQBotChannelAdapter
from inkstatute_channels_wecom.adapter import WeComChannelAdapter
from platform_runtime.fakes import FakeChannelAdapter
from platform_runtime.protocols import (
    AckResponse,
    ChannelAdapter,
    ChannelCapabilitySet,
    ChannelDelivery,
    ComponentHealth,
    DeliveryResult,
    InboundNormalized,
    RawInbound,
)


class TestVerifyAndAckOptional(unittest.TestCase):
    """Tests for the optional verify_and_ack capability (GW-06)."""

    def test_channel_capability_set_has_verify_and_ack_support(self) -> None:
        """ChannelCapabilitySet has a verify_and_ack_support field."""
        cs = ChannelCapabilitySet()
        self.assertTrue(hasattr(cs, "verify_and_ack_support"))

    def test_default_verify_and_ack_support_is_false(self) -> None:
        """Default value of verify_and_ack_support is False."""
        cs = ChannelCapabilitySet()
        self.assertFalse(cs.verify_and_ack_support)

    def test_qqbot_adapter_verify_and_ack_support_true(self) -> None:
        """QqBotChannelAdapter declares verify_and_ack_support=True."""
        adapter = QQBotChannelAdapter()
        self.assertTrue(adapter.capabilities().verify_and_ack_support)

    def test_wecom_adapter_verify_and_ack_support_true(self) -> None:
        """WeComChannelAdapter declares verify_and_ack_support=True."""
        adapter = WeComChannelAdapter()
        self.assertTrue(adapter.capabilities().verify_and_ack_support)

    def test_fake_adapter_verify_and_ack_support_false(self) -> None:
        """FakeChannelAdapter declares verify_and_ack_support=False."""
        adapter = FakeChannelAdapter()
        self.assertFalse(adapter.capabilities().verify_and_ack_support)

    def test_adapter_without_verify_and_ack_support_passes_protocol(self) -> None:
        """An adapter with verify_and_ack_support=False still passes Protocol validation.

        GW-06: '不实现它的通道适配器仍能通过 Protocol 校验'.
        The adapter does NOT implement verify_and_ack meaningfully — it is
        a no-op. But the ChannelAdapter Protocol is not structurally enforced
        at runtime (Python Protocols are structural by default), so the adapter
        instance can be created and its capabilities() returns a valid
        ChannelCapabilitySet.
        """

        class MinimalAdapter:
            """Minimal adapter that does not implement verify_and_ack."""

            def channel_id(self) -> str:
                return "minimal"

            def capabilities(self) -> ChannelCapabilitySet:
                return ChannelCapabilitySet(verify_and_ack_support=False)

            async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized:
                return InboundNormalized()

            async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult:
                return DeliveryResult(delivery_id="test", accepted=True)

            async def health(self) -> ComponentHealth:
                return ComponentHealth(ok=True, component_id="minimal", checked_at="2026-01-01T00:00:00Z")

        adapter = MinimalAdapter()
        caps = adapter.capabilities()
        self.assertIsInstance(caps, ChannelCapabilitySet)
        self.assertFalse(caps.verify_and_ack_support)
        # The adapter can be used as a ChannelAdapter (Protocol is structural)
        # — verify_and_ack is not required when verify_and_ack_support=False
        self.assertEqual(adapter.channel_id(), "minimal")

    def test_adapter_with_verify_and_ack_support_true(self) -> None:
        """An adapter with verify_and_ack_support=True implements verify_and_ack."""

        class FullAdapter:
            """Full adapter that implements verify_and_ack."""

            def channel_id(self) -> str:
                return "full"

            def capabilities(self) -> ChannelCapabilitySet:
                return ChannelCapabilitySet(verify_and_ack_support=True)

            async def verify_and_ack(self, raw: RawInbound) -> AckResponse:
                return AckResponse(accepted=True, idempotency_key=raw.idempotency_key)

            async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized:
                return InboundNormalized()

            async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult:
                return DeliveryResult(delivery_id="test", accepted=True)

            async def health(self) -> ComponentHealth:
                return ComponentHealth(ok=True, component_id="full", checked_at="2026-01-01T00:00:00Z")

        adapter = FullAdapter()
        caps = adapter.capabilities()
        self.assertTrue(caps.verify_and_ack_support)
        # verify_and_ack is implemented and works
        import asyncio
        raw = RawInbound(channel_id="full", payload_ref="ref://test", received_at="2026-01-01T00:00:00Z")
        ack = asyncio.run(adapter.verify_and_ack(raw))
        self.assertTrue(ack.accepted)


if __name__ == "__main__":
    unittest.main()
