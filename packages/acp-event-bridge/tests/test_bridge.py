"""End-to-end tracer tests for EventBridge bidirectional flow.

Tests the full bidirectional flow:
ACP notification → EventBridge.ingest_acp_notification → unified RunEvent
→ user response → EventBridge.build_acp_response → ACP JSON-RPC response.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from inkstatute_acp_event_bridge.bridge import EventBridge
from platform_runtime.protocols import RunEvent


def _contains_key_recursive(obj, key: str) -> bool:
    """Recursively check if *key* appears at any level in nested dicts/lists."""
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(_contains_key_recursive(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_key_recursive(item, key) for item in obj)
    return False


class TestEventBridgeTracer(unittest.TestCase):
    """End-to-end tracer tests for EventBridge — bidirectional event flow."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load JSON fixtures once for all tests."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        with open(fixtures_dir / "acp_notifications.json") as f:
            cls._notifications = json.load(f)
        with open(fixtures_dir / "user_responses.json") as f:
            cls._user_responses = json.load(f)

    def _load_notification(self, key: str) -> dict:
        """Load a specific ACP notification fixture by key."""
        return self._notifications[key]

    def _load_user_response(self, key: str) -> dict:
        """Load a specific user response fixture by key."""
        return self._user_responses[key]

    # ------------------------------------------------------------------
    # Forward mapping tests (ACP → unified)
    # ------------------------------------------------------------------

    def test_forward_mapping_agent_message_chunk(self) -> None:
        """agent_message_chunk → message.delta with correct delta and seq."""
        bridge = EventBridge("run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("agent_message_chunk")
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "message.delta")
        self.assertEqual(event.payload["delta"], "Hello, ")
        self.assertEqual(event.seq, 1)

    def test_forward_mapping_agent_message(self) -> None:
        """agent_message → message.completed with correct content."""
        bridge = EventBridge("run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("agent_message")
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "message.completed")
        self.assertEqual(event.payload["content"], "Hello, world!")

    def test_forward_mapping_thought_chunk(self) -> None:
        """agent_thought_chunk → thought.delta."""
        bridge = EventBridge("run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("agent_thought_chunk")
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "thought.delta")

    def test_forward_mapping_tool_call_lifecycle(self) -> None:
        """Three tool_call_update events produce started, delta, completed with seq 1, 2, 3."""
        bridge = EventBridge("run-1")
        e1 = bridge.ingest_acp_notification(
            self._load_notification("tool_call_update_pending")
        )
        e2 = bridge.ingest_acp_notification(
            self._load_notification("tool_call_update_in_progress")
        )
        e3 = bridge.ingest_acp_notification(
            self._load_notification("tool_call_update_completed")
        )
        self.assertIsNotNone(e1)
        self.assertIsNotNone(e2)
        self.assertIsNotNone(e3)
        self.assertEqual(e1.event_type, "tool_call.started")
        self.assertEqual(e2.event_type, "tool_call.delta")
        self.assertEqual(e3.event_type, "tool_call.completed")
        self.assertEqual((e1.seq, e2.seq, e3.seq), (1, 2, 3))

    def test_forward_mapping_plan(self) -> None:
        """plan → plan.updated."""
        bridge = EventBridge("run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("plan")
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "plan.updated")

    def test_forward_mapping_elicitation(self) -> None:
        """elicitation/create → elicitation.requested with pending request recorded."""
        bridge = EventBridge("run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("elicitation_create")
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "elicitation.requested")
        self.assertEqual(event.payload["interrupt_id"], "elic-1")
        self.assertTrue(event.payload["intro"])
        self.assertIsInstance(event.payload["questions"], list)
        self.assertTrue(len(event.payload["questions"]) > 0)

        pending = bridge.get_pending_requests()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["type"], "elicitation")

    def test_forward_mapping_permission(self) -> None:
        """session/request_permission → permission.requested with kind=terminal, no auto-approve."""
        bridge = EventBridge("run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("request_permission")
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "permission.requested")
        self.assertEqual(event.payload["kind"], "terminal")

        # Must NOT contain auto_approve or default_decision
        self.assertNotIn("auto_approve", event.payload)
        self.assertNotIn("default_decision", event.payload)

        pending = bridge.get_pending_requests()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["type"], "permission")

    # ------------------------------------------------------------------
    # Reverse mapping roundtrip tests (unified → ACP)
    # ------------------------------------------------------------------

    def test_reverse_mapping_elicitation_roundtrip(self) -> None:
        """Full elicitation roundtrip: ingest → build response → mark responded."""
        bridge = EventBridge("run-1")
        bridge.ingest_acp_notification(
            self._load_notification("elicitation_create")
        )

        resp = bridge.build_acp_response(
            "elicitation.requested",
            {"action": "accept", "content": {"user_provided_data": "case-2026-001"}},
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], "elic-1")
        self.assertEqual(resp["result"]["action"], "accept")
        self.assertEqual(
            resp["result"]["content"]["user_provided_data"], "case-2026-001"
        )

        bridge.mark_request_responded("elic-1")
        self.assertEqual(len(bridge.get_pending_requests()), 0)

    def test_reverse_mapping_permission_roundtrip(self) -> None:
        """Full permission roundtrip with no auto-approve fields."""
        bridge = EventBridge("run-1")
        bridge.ingest_acp_notification(
            self._load_notification("request_permission")
        )

        resp = bridge.build_acp_response(
            "permission.requested",
            {"outcome": "selected", "option_id": "deny"},
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], "perm-1")
        self.assertEqual(resp["result"]["outcome"]["outcome"], "selected")
        self.assertEqual(resp["result"]["outcome"]["optionId"], "deny")

        # Must NOT contain auto_approve or allow_once at any level
        for forbidden in ("auto_approve", "allow_once", "default_decision"):
            self.assertFalse(
                _contains_key_recursive(resp, forbidden),
                f"Response contains forbidden key: {forbidden}",
            )

    def test_reverse_mapping_no_matching_request(self) -> None:
        """build_acp_response with no prior notification returns None."""
        bridge = EventBridge("run-2")
        resp = bridge.build_acp_response(
            "elicitation.requested",
            {"action": "accept"},
        )
        self.assertIsNone(resp)

    # ------------------------------------------------------------------
    # Cancel request
    # ------------------------------------------------------------------

    def test_cancel_request(self) -> None:
        """build_cancel_request produces a valid session/cancel request."""
        bridge = EventBridge("run-1")
        cancel = bridge.build_cancel_request("session-1")
        self.assertEqual(cancel["method"], "session/cancel")
        self.assertEqual(cancel["params"]["sessionId"], "session-1")

    # ------------------------------------------------------------------
    # Sequence counter
    # ------------------------------------------------------------------

    def test_seq_increments(self) -> None:
        """seq increments by 1 for each successfully mapped event."""
        bridge = EventBridge("run-1")
        e1 = bridge.ingest_acp_notification(
            self._load_notification("agent_message_chunk")
        )
        e2 = bridge.ingest_acp_notification(
            self._load_notification("agent_message")
        )
        e3 = bridge.ingest_acp_notification(
            self._load_notification("agent_thought_chunk")
        )
        self.assertEqual((e1.seq, e2.seq, e3.seq), (1, 2, 3))

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_unrecognized_notification_returns_none(self) -> None:
        """Unrecognized notification type returns None and seq stays 0."""
        bridge = EventBridge("run-1")
        event = bridge.ingest_acp_notification(
            {"method": "session/update", "params": {"update": {"type": "unknown_type"}}}
        )
        self.assertIsNone(event)
        self.assertEqual(bridge.seq, 0)

    # ------------------------------------------------------------------
    # End-to-end tracer slice
    # ------------------------------------------------------------------

    def test_end_to_end_tracer_slice(self) -> None:
        """Full bidirectional flow: ACP notification → bridge → unified event → user response → bridge → ACP response."""
        bridge = EventBridge("run-tracer")

        # 1. Ingest agent_message_chunk → message.delta
        e1 = bridge.ingest_acp_notification(
            self._load_notification("agent_message_chunk")
        )
        self.assertIsNotNone(e1)
        self.assertEqual(e1.event_type, "message.delta")

        # 2. Ingest elicitation_create → elicitation.requested
        e2 = bridge.ingest_acp_notification(
            self._load_notification("elicitation_create")
        )
        self.assertIsNotNone(e2)
        self.assertEqual(e2.event_type, "elicitation.requested")

        # 3. Verify pending request exists
        pending = bridge.get_pending_requests()
        self.assertEqual(len(pending), 1)

        # 4. Build ACP response with accept
        resp = bridge.build_acp_response(
            "elicitation.requested",
            {"action": "accept", "content": {"user_provided_data": "case-2026-001"}},
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], "elic-1")
        self.assertEqual(resp["result"]["action"], "accept")

        # 5. Mark request responded → no pending requests
        bridge.mark_request_responded("elic-1")
        self.assertEqual(len(bridge.get_pending_requests()), 0)

        # 6. Ingest agent_message → message.completed
        e3 = bridge.ingest_acp_notification(
            self._load_notification("agent_message")
        )
        self.assertIsNotNone(e3)
        self.assertEqual(e3.event_type, "message.completed")


if __name__ == "__main__":
    unittest.main()
