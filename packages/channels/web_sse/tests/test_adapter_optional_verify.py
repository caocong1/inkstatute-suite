"""Tests for WebSseChannelAdapter optional verify_and_ack capability.

Verifies that the Web/SSE adapter declares verify_and_ack_support=False
and that it still passes ChannelAdapter Protocol validation (GW-06).
"""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_channels_web_sse.adapter import WebSseChannelAdapter
from platform_runtime.protocols import (
    AckResponse,
    ChannelCapabilitySet,
    RawInbound,
)


class TestWebSseOptionalVerify(unittest.TestCase):
    """Tests for Web/SSE adapter's optional verify_and_ack."""

    def test_web_sse_verify_and_ack_support_is_false(self) -> None:
        """WebSseChannelAdapter declares verify_and_ack_support=False."""
        adapter = WebSseChannelAdapter()
        caps = adapter.capabilities()
        self.assertFalse(caps.verify_and_ack_support)

    def test_web_sse_adapter_passes_protocol_check(self) -> None:
        """WebSseChannelAdapter has all required ChannelAdapter methods.

        The verify_and_ack method exists but is not semantically required
        (verify_and_ack_support=False). The adapter still passes Protocol
        validation because it implements all Protocol methods.
        """
        adapter = WebSseChannelAdapter()
        # Verify all required ChannelAdapter methods exist
        self.assertTrue(callable(getattr(adapter, "channel_id", None)))
        self.assertTrue(callable(getattr(adapter, "capabilities", None)))
        self.assertTrue(callable(getattr(adapter, "verify_and_ack", None)))
        self.assertTrue(callable(getattr(adapter, "normalize_inbound", None)))
        self.assertTrue(callable(getattr(adapter, "deliver", None)))
        self.assertTrue(callable(getattr(adapter, "health", None)))

    def test_web_sse_verify_and_ack_is_noop_when_support_false(self) -> None:
        """verify_and_ack still works as a no-op when support is False.

        The method exists for Protocol compliance but is not semantically
        required. It returns a valid AckResponse.
        """
        adapter = WebSseChannelAdapter()
        raw = RawInbound(
            channel_id="web-sse",
            payload_ref="ref://test/payload",
            received_at="2026-01-01T00:00:00Z",
        )
        ack = asyncio.run(adapter.verify_and_ack(raw))
        self.assertIsInstance(ack, AckResponse)
        # The ack may be accepted=True or False depending on config,
        # but it returns a valid AckResponse either way.


if __name__ == "__main__":
    unittest.main()
