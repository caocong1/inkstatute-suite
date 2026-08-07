"""Tests for the Gateway POST /v1/runs/{id}/approvals endpoint.

Verifies:
- submit_approval with "allow" → 200
- submit_approval with "deny" → 200
- submit_approval with invalid decision → 400
- submit_approval with missing permission_id → 400
- submit_approval requires auth (401)
- submit_approval does not auto-approve — the handler records the user's decision exactly
"""

from __future__ import annotations

import asyncio
import unittest

from gateway.app import GatewayApp
from gateway.approvals import GatewayApprovalHandler
from gateway.auth import GatewayAuth
from gateway.config import GatewayConfig
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from rbac.session import InMemorySessionStore

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def _make_app(handler: GatewayApprovalHandler | None = None) -> GatewayApp:
    config = GatewayConfig(enabled=True)
    auth = GatewayAuth(rbac_enabled=False, static_token="test-token")
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()
    return GatewayApp(
        config,
        runtime=object(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
        approval_handler=handler or GatewayApprovalHandler(),
    )


class TestApprovals(unittest.TestCase):
    """Tests for POST /v1/runs/{run_id}/approvals."""

    def test_submit_approval_allow(self) -> None:
        """POST with permission_id and decision: 'allow' → 200."""
        app = _make_app()
        body = {"permission_id": "p1", "decision": "allow"}
        result = asyncio.run(app.dispatch("POST", "/v1/runs/run-1/approvals", AUTH_HEADERS, body))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["run_id"], "run-1")
        self.assertEqual(result["permission_id"], "p1")
        self.assertEqual(result["decision"], "allow")

    def test_submit_approval_deny(self) -> None:
        """POST with permission_id and decision: 'deny' → 200."""
        app = _make_app()
        body = {"permission_id": "p1", "decision": "deny"}
        result = asyncio.run(app.dispatch("POST", "/v1/runs/run-1/approvals", AUTH_HEADERS, body))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["decision"], "deny")

    def test_submit_approval_invalid_decision(self) -> None:
        """POST with decision: 'maybe' → 400."""
        app = _make_app()
        body = {"permission_id": "p1", "decision": "maybe"}
        result = asyncio.run(app.dispatch("POST", "/v1/runs/run-1/approvals", AUTH_HEADERS, body))
        self.assertEqual(result["status"], 400)
        self.assertEqual(result["error"]["code"], "invalid_request")

    def test_submit_approval_missing_permission_id(self) -> None:
        """POST without permission_id → 400."""
        app = _make_app()
        body = {"decision": "allow"}
        result = asyncio.run(app.dispatch("POST", "/v1/runs/run-1/approvals", AUTH_HEADERS, body))
        self.assertEqual(result["status"], 400)
        self.assertEqual(result["error"]["code"], "invalid_request")

    def test_submit_approval_requires_auth(self) -> None:
        """No auth → 401."""
        app = _make_app()
        body = {"permission_id": "p1", "decision": "allow"}
        result = asyncio.run(app.dispatch("POST", "/v1/runs/run-1/approvals", {}, body))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")

    def test_submit_approval_does_not_auto_approve(self) -> None:
        """Verify the handler records the user's decision exactly — no server-side auto-allow path exists."""
        handler = GatewayApprovalHandler()
        app = _make_app(handler=handler)

        # Submit a "deny" decision
        body_deny = {"permission_id": "p1", "decision": "deny"}
        asyncio.run(app.dispatch("POST", "/v1/runs/run-1/approvals", AUTH_HEADERS, body_deny))

        # Verify the stored decision is exactly "deny" — not auto-changed to "allow"
        stored = handler.get_submission("run-1", "p1")
        self.assertIsNotNone(stored, "Submission should be stored")
        self.assertEqual(stored["decision"], "deny", "Handler must record the user's decision exactly")

        # Submit a "allow" decision for a different permission
        body_allow = {"permission_id": "p2", "decision": "allow"}
        asyncio.run(app.dispatch("POST", "/v1/runs/run-1/approvals", AUTH_HEADERS, body_allow))

        stored_allow = handler.get_submission("run-1", "p2")
        self.assertIsNotNone(stored_allow)
        self.assertEqual(stored_allow["decision"], "allow")

        # Verify there is no auto-approve path: the handler only has
        # handle_submit_approval and get_submission — no method that
        # produces an automatic "allow" decision.
        # Check that the handler class has no method with "auto" in its name.
        handler_methods = [m for m in dir(handler) if not m.startswith("_")]
        for method_name in handler_methods:
            self.assertNotIn(
                "auto", method_name.lower(),
                f"No auto-approve method should exist, found: {method_name}",
            )


if __name__ == "__main__":
    unittest.main()
