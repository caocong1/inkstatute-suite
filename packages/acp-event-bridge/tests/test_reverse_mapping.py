"""Unit tests for reverse mapping functions (unified → ACP JSON-RPC responses)."""

from __future__ import annotations

import json
import unittest

from inkstatute_acp_event_bridge.reverse_mapping import (
    map_elicitation_response_to_acp,
    map_permission_decision_to_acp,
    map_run_cancel_to_acp,
    map_unified_event_to_acp_response,
)


def _contains_key_recursive(obj, key: str) -> bool:
    """Recursively check if *key* appears at any level in nested dicts/lists."""
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(_contains_key_recursive(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_key_recursive(item, key) for item in obj)
    return False


class TestReverseMapping(unittest.TestCase):
    """Tests for reverse mapping functions — ACP v1 JSON-RPC response formats."""

    # ------------------------------------------------------------------
    # Elicitation responses
    # ------------------------------------------------------------------

    def test_elicitation_accept_response(self) -> None:
        """accept action with content produces a valid JSON-RPC response."""
        resp = map_elicitation_response_to_acp(
            "elic-1", "accept", {"user_provided_data": "case-001"}
        )
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["id"], "elic-1")
        self.assertEqual(resp["result"]["action"], "accept")
        self.assertEqual(
            resp["result"]["content"], {"user_provided_data": "case-001"}
        )

    def test_elicitation_decline_response(self) -> None:
        """decline action omits content."""
        resp = map_elicitation_response_to_acp("elic-1", "decline")
        self.assertEqual(resp["result"]["action"], "decline")
        self.assertNotIn("content", resp["result"])

    def test_elicitation_cancel_response(self) -> None:
        """cancel action produces a valid response."""
        resp = map_elicitation_response_to_acp("elic-1", "cancel")
        self.assertEqual(resp["result"]["action"], "cancel")

    def test_elicitation_invalid_action_raises(self) -> None:
        """Invalid action raises ValueError."""
        with self.assertRaises(ValueError):
            map_elicitation_response_to_acp("elic-1", "maybe")

    def test_elicitation_empty_request_id_raises(self) -> None:
        """Empty request_id raises ValueError."""
        with self.assertRaises(ValueError):
            map_elicitation_response_to_acp("", "accept")

    # ------------------------------------------------------------------
    # Permission responses
    # ------------------------------------------------------------------

    def test_permission_selected_response(self) -> None:
        """selected outcome with option_id produces a valid JSON-RPC response."""
        resp = map_permission_decision_to_acp("perm-1", "selected", "allow-once")
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["id"], "perm-1")
        self.assertEqual(resp["result"]["outcome"]["outcome"], "selected")
        self.assertEqual(resp["result"]["outcome"]["optionId"], "allow-once")

    def test_permission_cancelled_response(self) -> None:
        """cancelled outcome omits optionId."""
        resp = map_permission_decision_to_acp("perm-1", "cancelled")
        self.assertEqual(resp["result"]["outcome"]["outcome"], "cancelled")
        self.assertNotIn("optionId", resp["result"]["outcome"])

    def test_permission_invalid_outcome_raises(self) -> None:
        """Invalid outcome raises ValueError."""
        with self.assertRaises(ValueError):
            map_permission_decision_to_acp("perm-1", "approved")

    def test_permission_empty_request_id_raises(self) -> None:
        """Empty request_id raises ValueError."""
        with self.assertRaises(ValueError):
            map_permission_decision_to_acp("", "selected")

    def test_no_auto_approve_in_permission_response(self) -> None:
        """No auto-approval fields at any level in the response."""
        resp = map_permission_decision_to_acp("perm-1", "selected", "allow-once")
        for forbidden_key in ("auto_approve", "default_decision", "allow_once"):
            self.assertFalse(
                _contains_key_recursive(resp, forbidden_key),
                f"Response contains forbidden key: {forbidden_key}",
            )

    # ------------------------------------------------------------------
    # Run cancellation
    # ------------------------------------------------------------------

    def test_run_cancel_request(self) -> None:
        """session/cancel request has correct method and params."""
        resp = map_run_cancel_to_acp("session-1")
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["method"], "session/cancel")
        self.assertEqual(resp["params"]["sessionId"], "session-1")

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def test_dispatcher_elicitation(self) -> None:
        """Dispatcher routes elicitation.requested to elicitation mapping."""
        resp = map_unified_event_to_acp_response(
            "elicitation.requested",
            {"action": "accept", "content": {"data": "x"}},
            "elic-1",
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], "elic-1")
        self.assertEqual(resp["result"]["action"], "accept")

    def test_dispatcher_permission(self) -> None:
        """Dispatcher routes permission.requested to permission mapping."""
        resp = map_unified_event_to_acp_response(
            "permission.requested",
            {"outcome": "selected", "option_id": "opt-1"},
            "perm-1",
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], "perm-1")
        self.assertEqual(resp["result"]["outcome"]["optionId"], "opt-1")

    def test_dispatcher_unknown_type_returns_none(self) -> None:
        """Unknown event type returns None."""
        resp = map_unified_event_to_acp_response("unknown.type", {}, "req-1")
        self.assertIsNone(resp)

    # ------------------------------------------------------------------
    # JSON-RPC structure validation
    # ------------------------------------------------------------------

    def test_all_responses_are_valid_jsonrpc(self) -> None:
        """All responses produced by mapping functions have valid JSON-RPC 2.0 structure."""
        responses = [
            map_elicitation_response_to_acp("r1", "accept", {"data": "x"}),
            map_elicitation_response_to_acp("r2", "decline"),
            map_elicitation_response_to_acp("r3", "cancel"),
            map_permission_decision_to_acp("r4", "selected", "opt-1"),
            map_permission_decision_to_acp("r5", "cancelled"),
        ]
        for resp in responses:
            self.assertIn("jsonrpc", resp)
            self.assertEqual(resp["jsonrpc"], "2.0")
            self.assertIn("id", resp)
            self.assertIn("result", resp)

        # Also verify the cancel request has valid JSON-RPC structure
        cancel = map_run_cancel_to_acp("session-1")
        self.assertEqual(cancel["jsonrpc"], "2.0")
        self.assertIn("method", cancel)


if __name__ == "__main__":
    unittest.main()
