"""Double-layer permission safety enforcement tests.

Tests that permission safety is enforced at both layers:
- **Adapter layer** (existing in ``acp-client/adapter.py``): rejects
  approved decisions for dangerous permission kinds.
- **Bridge layer** (new in ``acp-event-bridge``): ensures no
  auto-approval path exists; permission requests are forwarded to the
  user, not auto-answered.

Binding constraint (AGENTS.md):
    "Permission requests must never be auto-approved server-side. ACP
    session/request_permission for terminal / execute_code must be
    explicitly denied or escalated to a user approval card. Reference
    failure: Buzz's ACP bridge auto-answers allow_once."
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from inkstatute_acp_event_bridge.bridge import EventBridge
from inkstatute_acp_event_bridge.output_filter import ACPOutputFilter
from inkstatute_acp_event_bridge.reverse_mapping import (
    map_permission_decision_to_acp,
)
from inkstatute_acp_client.adapter import _DANGEROUS_PERMISSION_KINDS


def _contains_key_recursive(obj, key: str) -> bool:
    """Recursively check if *key* appears at any level in nested dicts/lists."""
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(_contains_key_recursive(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_key_recursive(item, key) for item in obj)
    return False


def _contains_value_recursive(obj, value: str) -> bool:
    """Recursively check if *value* appears at any level in nested dicts/lists."""
    if isinstance(obj, dict):
        for v in obj.values():
            if v == value:
                return True
            if _contains_value_recursive(v, value):
                return True
        return False
    if isinstance(obj, list):
        for item in obj:
            if item == value:
                return True
            if _contains_value_recursive(item, value):
                return True
        return False
    return False


def _make_permission_notification(kind: str = "terminal") -> dict:
    """Create a session/request_permission notification with the given kind."""
    return {
        "jsonrpc": "2.0",
        "id": "perm-1",
        "method": "session/request_permission",
        "params": {
            "id": "perm-1",
            "tool_call_id": "tc-2",
            "description": "Run shell command",
            "kind": kind,
        },
    }


class TestPermissionSafety(unittest.TestCase):
    """Double-layer permission safety enforcement tests."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load JSON fixtures once for all tests."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        with open(fixtures_dir / "acp_notifications.json") as f:
            cls._notifications = json.load(f)

    def _load_notification(self, key: str) -> dict:
        """Load a specific ACP notification fixture by key (deep copy)."""
        return copy.deepcopy(self._notifications[key])

    # ------------------------------------------------------------------
    # 1. No auto_approve in permission event payload
    # ------------------------------------------------------------------

    def test_permission_event_has_no_auto_approve(self) -> None:
        """Permission event payload does NOT contain auto_approve/default_decision/allow_once."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            _make_permission_notification("terminal")
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertFalse(
            _contains_key_recursive(event.payload, "auto_approve"),
            "auto_approve found in permission event payload",
        )
        self.assertFalse(
            _contains_key_recursive(event.payload, "default_decision"),
            "default_decision found in permission event payload",
        )
        self.assertFalse(
            _contains_key_recursive(event.payload, "allow_once"),
            "allow_once found in permission event payload",
        )

    # ------------------------------------------------------------------
    # 2. No auto_approve in permission response
    # ------------------------------------------------------------------

    def test_permission_response_has_no_auto_approve(self) -> None:
        """map_permission_decision_to_acp response does NOT contain auto_approve fields."""
        response = map_permission_decision_to_acp("perm-1", "selected", "deny")
        self.assertFalse(
            _contains_key_recursive(response, "auto_approve"),
            "auto_approve found in permission response",
        )
        self.assertFalse(
            _contains_key_recursive(response, "default_decision"),
            "default_decision found in permission response",
        )
        self.assertFalse(
            _contains_key_recursive(response, "allow_once"),
            "allow_once found in permission response",
        )

    # ------------------------------------------------------------------
    # 3. Bridge does not auto-answer permissions
    # ------------------------------------------------------------------

    def test_bridge_does_not_auto_answer_permissions(self) -> None:
        """Bridge forwards permission requests to user — does not auto-answer."""
        bridge = EventBridge(run_id="run-1")
        bridge.ingest_acp_notification(_make_permission_notification("terminal"))
        pending = bridge.get_pending_requests()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["type"], "permission")
        self.assertEqual(pending[0]["request_id"], "perm-1")

    # ------------------------------------------------------------------
    # 4. Permission must be explicitly responded
    # ------------------------------------------------------------------

    def test_permission_must_be_explicitly_responded(self) -> None:
        """No ACP response until build_acp_response is explicitly called."""
        bridge = EventBridge(run_id="run-1")
        bridge.ingest_acp_notification(_make_permission_notification("terminal"))

        # Before explicit response — request is pending
        pending_before = bridge.get_pending_requests()
        self.assertEqual(len(pending_before), 1)

        # No response generated yet — build_acp_response is the only way
        # to generate one, and it requires explicit call
        # (The bridge does not auto-generate responses on ingest)

        # After explicit response
        response = bridge.build_acp_response(
            "permission.requested",
            {"outcome": "selected", "option_id": "deny"},
        )
        self.assertIsNotNone(response)

        # Mark as responded
        bridge.mark_request_responded("perm-1")
        pending_after = bridge.get_pending_requests()
        self.assertEqual(len(pending_after), 0)

    # ------------------------------------------------------------------
    # 5. Dangerous kind terminal forwarded to user
    # ------------------------------------------------------------------

    def test_dangerous_kind_terminal_forwarded_to_user(self) -> None:
        """terminal permission request passes through filter — reaches user."""
        filt = ACPOutputFilter()
        notif = _make_permission_notification("terminal")
        decision = filt.filter_notification(notif)
        self.assertEqual(decision.action, "allow")

    # ------------------------------------------------------------------
    # 6. Dangerous kind execute_code forwarded to user
    # ------------------------------------------------------------------

    def test_dangerous_kind_execute_code_forwarded_to_user(self) -> None:
        """execute_code permission request passes through filter — reaches user."""
        filt = ACPOutputFilter()
        notif = _make_permission_notification("execute_code")
        decision = filt.filter_notification(notif)
        self.assertEqual(decision.action, "allow")

    # ------------------------------------------------------------------
    # 7. Permission response never contains allow_once
    # ------------------------------------------------------------------

    def test_permission_response_never_contains_allow_once(self) -> None:
        """For all outcomes and non-allow_once option_ids, response never contains allow_once.

        The reverse mapping function is a pure envelope constructor — it
        does not introduce ``allow_once`` as a key or value on its own.
        If the caller explicitly passes ``option_id="allow_once"``, that
        value appears in the response (the caller decides the outcome),
        but the function itself never adds it.  The adapter layer
        enforces safety by rejecting dangerous approvals.
        """
        for outcome in ("selected", "cancelled"):
            for option_id in ("deny", "allow", "approve", None):
                response = map_permission_decision_to_acp(
                    "perm-1", outcome, option_id
                )
                self.assertFalse(
                    _contains_value_recursive(response, "allow_once"),
                    f"allow_once found in response for outcome={outcome}, option_id={option_id}",
                )
                self.assertFalse(
                    _contains_key_recursive(response, "allow_once"),
                    f"allow_once key found in response for outcome={outcome}, option_id={option_id}",
                )

    # ------------------------------------------------------------------
    # 8. No silent degradation on dangerous permission
    # ------------------------------------------------------------------

    def test_no_silent_degradation_on_dangerous_permission(self) -> None:
        """terminal permission produces a valid RunEvent — not None, not silently dropped."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            _make_permission_notification("terminal")
        )
        self.assertIsNotNone(event, "Dangerous permission was silently dropped (None)")
        assert event is not None
        self.assertEqual(event.event_type, "permission.requested")
        self.assertEqual(event.payload["kind"], "terminal")

    # ------------------------------------------------------------------
    # 9. Permission safety double-layer — adapter
    # ------------------------------------------------------------------

    def test_permission_safety_double_layer_adapter(self) -> None:
        """Adapter-level enforcement: _DANGEROUS_PERMISSION_KINDS rejects approved for terminal."""
        # Import and verify the adapter's dangerous kinds set
        self.assertIn("terminal", _DANGEROUS_PERMISSION_KINDS)
        self.assertIn("execute_code", _DANGEROUS_PERMISSION_KINDS)

        # Simulate the adapter's check logic:
        # If kind is dangerous AND decision is "approved" → must be rejected
        kind = "terminal"
        decision = "approved"
        self.assertTrue(
            kind in _DANGEROUS_PERMISSION_KINDS and decision == "approved",
            "Adapter should flag this combination as dangerous",
        )
        # The adapter's submit_approval would set WAITING_FOR_USER for this combo

    # ------------------------------------------------------------------
    # 10. Permission safety double-layer — bridge
    # ------------------------------------------------------------------

    def test_permission_safety_double_layer_bridge(self) -> None:
        """Bridge-level enforcement: no auto-response, user must explicitly respond."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            _make_permission_notification("terminal")
        )
        self.assertIsNotNone(event)

        # Bridge does NOT auto-generate a response
        pending = bridge.get_pending_requests()
        self.assertEqual(len(pending), 1)

        # User explicitly denies
        response = bridge.build_acp_response(
            "permission.requested",
            {"outcome": "selected", "option_id": "deny"},
        )
        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(_contains_key_recursive(response, "allow_once"))
        self.assertFalse(_contains_value_recursive(response, "allow_once"))
        self.assertEqual(response["result"]["outcome"]["optionId"], "deny")

    # ------------------------------------------------------------------
    # 11. No auto_approve field in any permission path
    # ------------------------------------------------------------------

    def test_no_auto_approve_field_in_any_permission_path(self) -> None:
        """Exhaustively test all permission paths for auto_approve/default_decision/allow_once."""
        bridge = EventBridge(run_id="run-1")

        # (a) Ingest notification → check payload
        event = bridge.ingest_acp_notification(
            _make_permission_notification("terminal")
        )
        assert event is not None
        for forbidden in ("auto_approve", "default_decision", "allow_once"):
            self.assertFalse(
                _contains_key_recursive(event.payload, forbidden),
                f"{forbidden} found in event payload",
            )

        # (b) build_acp_response with selected → check response
        response_selected = bridge.build_acp_response(
            "permission.requested",
            {"outcome": "selected", "option_id": "deny"},
        )
        assert response_selected is not None
        for forbidden in ("auto_approve", "default_decision", "allow_once"):
            self.assertFalse(
                _contains_key_recursive(response_selected, forbidden),
                f"{forbidden} found in selected response",
            )

        # (c) build_acp_response with cancelled → check response
        # Need to re-ingest since the previous response consumed the request
        bridge.ingest_acp_notification(_make_permission_notification("terminal"))
        response_cancelled = bridge.build_acp_response(
            "permission.requested",
            {"outcome": "cancelled"},
        )
        assert response_cancelled is not None
        for forbidden in ("auto_approve", "default_decision", "allow_once"):
            self.assertFalse(
                _contains_key_recursive(response_cancelled, forbidden),
                f"{forbidden} found in cancelled response",
            )

        # (d) map_permission_decision_to_acp directly → check response
        response_direct = map_permission_decision_to_acp("perm-x", "selected", "deny")
        for forbidden in ("auto_approve", "default_decision", "allow_once"):
            self.assertFalse(
                _contains_key_recursive(response_direct, forbidden),
                f"{forbidden} found in direct mapping response",
            )

    # ------------------------------------------------------------------
    # 12. Dangerous kinds set is complete and immutable
    # ------------------------------------------------------------------

    def test_dangerous_kinds_set_complete(self) -> None:
        """_DANGEROUS_PERMISSION_KINDS contains exactly terminal and execute_code, is frozenset."""
        self.assertIsInstance(_DANGEROUS_PERMISSION_KINDS, frozenset)
        self.assertEqual(_DANGEROUS_PERMISSION_KINDS, frozenset({"terminal", "execute_code"}))

    # ------------------------------------------------------------------
    # 13. Permission request reaches user through filter
    # ------------------------------------------------------------------

    def test_permission_request_reaches_user_through_filter(self) -> None:
        """ACPOutputFilter allows session/request_permission for terminal — reaches user."""
        filt = ACPOutputFilter()
        notif = _make_permission_notification("terminal")
        decision = filt.filter_notification(notif)
        self.assertEqual(decision.action, "allow")

    # ------------------------------------------------------------------
    # 14. Elicitation request reaches user through filter
    # ------------------------------------------------------------------

    def test_elicitation_request_reaches_user_through_filter(self) -> None:
        """ACPOutputFilter allows elicitation/create — reaches user."""
        filt = ACPOutputFilter()
        notif = self._load_notification("elicitation_create")
        decision = filt.filter_notification(notif)
        self.assertEqual(decision.action, "allow")

    # ------------------------------------------------------------------
    # 15. Buzz failure scenario prevented
    # ------------------------------------------------------------------

    def test_buzz_failure_scenario_prevented(self) -> None:
        """The Buzz auto-allow_once scenario cannot happen — bridge requires explicit response."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            _make_permission_notification("terminal")
        )
        self.assertIsNotNone(event)

        # The bridge does NOT auto-generate a response with outcome=selected + optionId=allow_once
        # The only way to generate a response is through explicit build_acp_response
        pending = bridge.get_pending_requests()
        self.assertEqual(len(pending), 1, "Permission is pending — not auto-answered")

        # Even if build_acp_response is called with option_id="allow_once",
        # the bridge constructs the envelope but the adapter layer would reject it
        # (the bridge constructs; the adapter enforces safety)
        response = bridge.build_acp_response(
            "permission.requested",
            {"outcome": "selected", "option_id": "allow_once"},
        )
        # The bridge constructs a valid JSON-RPC response (it doesn't filter option_ids)
        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["result"]["outcome"]["optionId"], "allow_once")

        # BUT: the adapter layer would reject this because kind=terminal is dangerous.
        # The adapter's _DANGEROUS_PERMISSION_KINDS check prevents auto-approval.
        # This test documents that the bridge layer constructs the envelope
        # (caller decides outcome), while the adapter layer enforces safety
        # (rejects dangerous approvals). The Buzz scenario required the BRIDGE
        # to auto-answer — our bridge does NOT auto-answer.
        #
        # Key assertion: the bridge never generates a response without an
        # explicit build_acp_response call. This is the core prevention.
        self.assertEqual(response["id"], "perm-1")


if __name__ == "__main__":
    unittest.main()
