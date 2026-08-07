"""Unit tests for ACP capability negotiation."""

from __future__ import annotations

import unittest

from inkstatute_acp_client.capability_negotiation import (
    CapabilityMismatchError,
    CapabilityNegotiationResult,
    RequiredCapabilities,
    build_required_capabilities,
    negotiate,
)
from platform_contract.agent_adapter import AdapterCapabilitySet


class TestCapabilityNegotiation(unittest.TestCase):
    """Tests for the negotiate() function and related types."""

    def test_negotiate_success_all_capabilities(self) -> None:
        """Pass a response with all capabilities true, assert correct AdapterCapabilitySet."""
        response = {
            "protocolVersion": 1,
            "agentInfo": {"name": "hermes", "version": "0.19.0"},
            "capabilities": {
                "streaming": True,
                "elicitation": True,
                "permissions": True,
                "artifacts": True,
                "citations": True,
            },
        }
        required = RequiredCapabilities(
            streaming=True,
            elicitation=True,
            permissions=True,
            artifacts=True,
            citations=True,
        )
        result = negotiate(response, required)
        self.assertIsInstance(result, CapabilityNegotiationResult)
        self.assertEqual(result.protocol_version, 1)
        self.assertEqual(result.agent_name, "hermes")
        self.assertEqual(result.agent_version, "0.19.0")
        caps = result.capabilities
        self.assertIsInstance(caps, AdapterCapabilitySet)
        self.assertTrue(caps.stream_event_support)
        self.assertTrue(caps.approval_support)
        self.assertTrue(caps.live_update_support)
        self.assertTrue(caps.cancel_support)
        self.assertTrue(caps.artifact_return_support)
        self.assertTrue(caps.trace_support)

    def test_negotiate_protocol_version_mismatch(self) -> None:
        """Pass protocolVersion 2, assert CapabilityMismatchError with protocol_version."""
        response = {
            "protocolVersion": 2,
            "agentInfo": {},
            "capabilities": {},
        }
        with self.assertRaises(CapabilityMismatchError) as ctx:
            negotiate(response, RequiredCapabilities(streaming=True))
        self.assertIn("protocol_version", ctx.exception.missing)

    def test_negotiate_missing_streaming(self) -> None:
        """Pass capabilities with streaming=false, required streaming=True, assert error."""
        response = {
            "protocolVersion": 1,
            "agentInfo": {},
            "capabilities": {"streaming": False},
        }
        with self.assertRaises(CapabilityMismatchError) as ctx:
            negotiate(response, RequiredCapabilities(streaming=True))
        self.assertIn("streaming", ctx.exception.missing)

    def test_negotiate_missing_elicitation(self) -> None:
        """Pass capabilities without elicitation, required elicitation=True, assert error."""
        response = {
            "protocolVersion": 1,
            "agentInfo": {},
            "capabilities": {"streaming": True},
        }
        with self.assertRaises(CapabilityMismatchError) as ctx:
            negotiate(response, RequiredCapabilities(streaming=True, elicitation=True))
        self.assertIn("elicitation", ctx.exception.missing)

    def test_negotiate_no_silent_degradation(self) -> None:
        """Verify that when a required capability is missing, negotiate raises."""
        response = {
            "protocolVersion": 1,
            "agentInfo": {"name": "minimal-agent"},
            "capabilities": {"streaming": True},
        }
        required = RequiredCapabilities(
            streaming=True,
            elicitation=True,
            permissions=True,
        )
        with self.assertRaises(CapabilityMismatchError) as ctx:
            negotiate(response, required)
        # Should list ALL missing capabilities, not just the first
        self.assertIn("elicitation", ctx.exception.missing)
        self.assertIn("permissions", ctx.exception.missing)
        # Should NOT silently return a reduced result
        self.assertGreater(len(ctx.exception.missing), 0)

    def test_negotiate_extracts_agent_info(self) -> None:
        """Pass agentInfo with name and version, assert result has correct values."""
        response = {
            "protocolVersion": 1,
            "agentInfo": {"name": "hermes", "version": "0.19.0"},
            "capabilities": {"streaming": True},
        }
        result = negotiate(response, RequiredCapabilities(streaming=True))
        self.assertEqual(result.agent_name, "hermes")
        self.assertEqual(result.agent_version, "0.19.0")

    def test_negotiate_defaults_agent_info(self) -> None:
        """Pass response without agentInfo, assert defaults to 'unknown'."""
        response = {
            "protocolVersion": 1,
            "capabilities": {"streaming": True},
        }
        result = negotiate(response, RequiredCapabilities(streaming=True))
        self.assertEqual(result.agent_name, "unknown")
        self.assertEqual(result.agent_version, "unknown")

    def test_build_required_capabilities_defaults(self) -> None:
        """Verify build_required_capabilities() defaults to streaming=True, others False."""
        req = build_required_capabilities()
        self.assertTrue(req.streaming)
        self.assertFalse(req.elicitation)
        self.assertFalse(req.permissions)
        self.assertFalse(req.artifacts)
        self.assertFalse(req.citations)

    def test_capability_mismatch_error_message_includes_agent_name(self) -> None:
        """Verify error message includes agent name and all missing capability names."""
        err = CapabilityMismatchError(
            missing=["streaming", "elicitation"],
            agent_name="test-agent",
            details="test details",
        )
        msg = str(err)
        self.assertIn("test-agent", msg)
        self.assertIn("streaming", msg)
        self.assertIn("elicitation", msg)


if __name__ == "__main__":
    unittest.main()
