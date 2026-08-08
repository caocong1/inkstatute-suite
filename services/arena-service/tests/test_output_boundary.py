"""Unit tests for Arena Service output boundary enforcement (SVC-04).

Tests :class:`ArenaOutputBoundary` — the arena service's second
enforcement point of the "output boundary enforced twice" requirement.

Covers:
- All 8 blocked content categories (meta, gateway, system, update,
  command, help, available_commands_update, terminal)
- Default-deny for unknown event types
- Two-layer enforcement (ACP pre-filter + DefaultAssistantOutputBoundary)
- SSE event integration via ``apply_to_sse_event``
- ArenaSseStream integration (blocked → None, allowed → valid frame)
"""

from __future__ import annotations

import unittest

from arena_service.output_boundary import ArenaOutputBoundary
from arena_service.sse import ArenaSseStream
from inkstatute_acp_event_bridge.output_filter import FilterDecision


class OutputBoundaryTests(unittest.TestCase):
    """SVC-04: Arena output boundary enforcement tests."""

    def setUp(self) -> None:
        self.boundary = ArenaOutputBoundary()

    # -- Test 1: normal content is allowed --
    def test_normal_content_allowed(self) -> None:
        """Test 1: ``filter_event("message.delta", "hello world", {})`` returns ALLOW."""
        decision = self.boundary.filter_event("message.delta", "hello world", {})
        self.assertIsInstance(decision, FilterDecision)
        self.assertEqual(decision.action, "allow")

    # -- Test 2: meta: prefix is blocked --
    def test_meta_prefix_blocked(self) -> None:
        """Test 2: ``meta:`` prefix is blocked."""
        decision = self.boundary.filter_event("message.delta", "meta: some internal info", {})
        self.assertEqual(decision.action, "block")

    # -- Test 3: gateway: prefix is blocked --
    def test_gateway_prefix_blocked(self) -> None:
        """Test 3: ``gateway:`` prefix is blocked."""
        decision = self.boundary.filter_event("message.delta", "gateway: connection lost", {})
        self.assertEqual(decision.action, "block")

    # -- Test 4: system: prefix is blocked --
    def test_system_prefix_blocked(self) -> None:
        """Test 4: ``system:`` prefix is blocked."""
        decision = self.boundary.filter_event("message.delta", "system: restarting", {})
        self.assertEqual(decision.action, "block")

    # -- Test 5: update: prefix is blocked --
    def test_update_prefix_blocked(self) -> None:
        """Test 5: ``update:`` prefix is blocked."""
        decision = self.boundary.filter_event("message.delta", "update: new version available", {})
        self.assertEqual(decision.action, "block")

    # -- Test 6: command: prefix is blocked --
    def test_command_prefix_blocked(self) -> None:
        """Test 6: ``command:`` prefix is blocked."""
        decision = self.boundary.filter_event("message.delta", "command: run ls", {})
        self.assertEqual(decision.action, "block")

    # -- Test 7: terminal: prefix is blocked --
    def test_terminal_prefix_blocked(self) -> None:
        """Test 7: ``terminal:`` prefix is blocked."""
        decision = self.boundary.filter_event("message.delta", "terminal: execute rm -rf", {})
        self.assertEqual(decision.action, "block")

    # -- Additional: help: prefix is blocked (8th category) --
    def test_help_prefix_blocked(self) -> None:
        """All 8 categories: ``help:`` prefix is blocked."""
        decision = self.boundary.filter_event("message.delta", "help: show commands", {})
        self.assertEqual(decision.action, "block")

    # -- Additional: available_commands_update is blocked (8th category) --
    def test_available_commands_update_blocked(self) -> None:
        """All 8 categories: ``available_commands_update`` is blocked."""
        decision = self.boundary.filter_event(
            "message.delta", "available_commands_update triggered", {}
        )
        self.assertEqual(decision.action, "block")

    # -- Test 8: unknown event type is default-denied --
    def test_unknown_event_type_blocked(self) -> None:
        """Test 8: unknown event type returns BLOCK (default-deny)."""
        decision = self.boundary.filter_event("unknown_event_type", "hello", {})
        self.assertEqual(decision.action, "block")

    # -- Test 9: None content passes through --
    def test_none_content_allowed(self) -> None:
        """Test 9: ``filter_event("message.delta", None, {})`` returns ALLOW."""
        decision = self.boundary.filter_event("message.delta", None, {})
        self.assertEqual(decision.action, "allow")

    # -- Test 10: apply_to_sse_event --
    def test_apply_to_sse_event_allowed(self) -> None:
        """Test 10a: ``apply_to_sse_event`` on allowed content returns (True, event)."""
        event = {
            "event_id": "evt-1",
            "event_type": "message.delta",
            "payload": {"text": "hello world"},
            "metadata": {"agent_slot": "slot-0"},
        }
        should_send, result = self.boundary.apply_to_sse_event(event)
        self.assertTrue(should_send)
        self.assertEqual(result["payload"]["text"], "hello world")

    def test_apply_to_sse_event_blocked(self) -> None:
        """Test 10b: ``apply_to_sse_event`` on blocked content returns (False, event)."""
        event = {
            "event_id": "evt-2",
            "event_type": "message.delta",
            "payload": {"text": "meta: secret info"},
            "metadata": {"agent_slot": "slot-0"},
        }
        should_send, result = self.boundary.apply_to_sse_event(event)
        self.assertFalse(should_send)
        self.assertEqual(result["payload"]["text"], "meta: secret info")

    def test_apply_to_sse_event_rewritten(self) -> None:
        """Test 10c: ``apply_to_sse_event`` on rewritten content returns (True, replaced)."""
        event = {
            "event_id": "evt-3",
            "event_type": "message.delta",
            "payload": {"text": "reconnecting to backend"},
            "metadata": {"agent_slot": "slot-0"},
        }
        should_send, result = self.boundary.apply_to_sse_event(event)
        self.assertTrue(should_send)
        self.assertNotEqual(result["payload"]["text"], "reconnecting to backend")
        self.assertIsNotNone(result["payload"]["text"])

    def test_apply_to_sse_event_content_from_message_delta(self) -> None:
        """Test 10d: ``apply_to_sse_event`` extracts content from ``payload.message_delta``."""
        event = {
            "event_id": "evt-4",
            "event_type": "message.delta",
            "payload": {"message_delta": "meta: leak"},
            "metadata": {"agent_slot": "slot-0"},
        }
        should_send, result = self.boundary.apply_to_sse_event(event)
        self.assertFalse(should_send)

    # -- Test 11: ArenaSseStream with ArenaOutputBoundary — blocked → None --
    def test_sse_stream_blocked_event_returns_none(self) -> None:
        """Test 11: ``ArenaSseStream`` with boundary drops blocked events (None)."""
        stream = ArenaSseStream(output_filter=self.boundary)
        event = {
            "event_id": "evt-blocked",
            "event_type": "message.delta",
            "payload": {"text": "meta: internal system info"},
            "metadata": {"agent_slot": "slot-0"},
        }
        frame = stream.encode_event(event)
        self.assertIsNone(frame)

    # -- Test 12: ArenaSseStream with ArenaOutputBoundary — normal → valid frame --
    def test_sse_stream_normal_event_encodes(self) -> None:
        """Test 12: ``ArenaSseStream`` with boundary encodes normal events."""
        stream = ArenaSseStream(output_filter=self.boundary)
        event = {
            "event_id": "evt-normal",
            "event_type": "message.delta",
            "payload": {"text": "hello world"},
            "metadata": {"agent_slot": "slot-0"},
        }
        frame = stream.encode_event(event)
        self.assertIsNotNone(frame)
        self.assertIsInstance(frame, str)
        self.assertIn("event: message.delta", frame)
        self.assertIn("hello world", frame)

    # -- should_send helper --
    def test_should_send_allow(self) -> None:
        """``should_send`` returns True for ALLOW decisions."""
        decision = self.boundary.filter_event("message.delta", "hello", {})
        self.assertTrue(self.boundary.should_send(decision))

    def test_should_send_block(self) -> None:
        """``should_send`` returns False for BLOCK decisions."""
        decision = self.boundary.filter_event("message.delta", "meta: leak", {})
        self.assertFalse(self.boundary.should_send(decision))


if __name__ == "__main__":
    unittest.main()
