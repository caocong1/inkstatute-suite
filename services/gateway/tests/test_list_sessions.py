"""Tests for the Gateway GET /v1/sessions (list sessions) endpoint.

Verifies:
- list_sessions returns all sessions for the authenticated tenant (200)
- list_sessions enforces cross-tenant isolation (tenant B only sees own sessions)
- list_sessions requires auth (401)
"""

from __future__ import annotations

import asyncio
import unittest

from gateway.app import GatewayApp
from gateway.auth import GatewayAuth
from gateway.config import GatewayConfig
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from rbac.session import InMemorySessionStore

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def _make_app() -> GatewayApp:
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
    )


class TestListSessions(unittest.TestCase):
    """Tests for GET /v1/sessions — list all sessions for the authenticated tenant."""

    def test_list_sessions_returns_tenant_sessions(self) -> None:
        """Create 2 sessions for tenant 'default', GET /v1/sessions → 200 with 2 sessions."""
        app = _make_app()
        # Create 2 sessions for the default tenant (static token resolves to "default")
        asyncio.run(app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "default", "user_id": "u1", "conversation_id": "c1"},
        ))
        asyncio.run(app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "default", "user_id": "u2", "conversation_id": "c2"},
        ))

        result = asyncio.run(app.dispatch("GET", "/v1/sessions", AUTH_HEADERS, None))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertIn("sessions", result)
        self.assertIsInstance(result["sessions"], list)
        self.assertEqual(len(result["sessions"]), 2)
        self.assertEqual(result["count"], 2)
        # Each session should have the expected fields
        for s in result["sessions"]:
            self.assertIn("session_id", s)
            self.assertIn("tenant_id", s)
            self.assertIn("conversation_id", s)

    def test_list_sessions_cross_tenant_isolation(self) -> None:
        """Create sessions for different tenants, verify tenant isolation.

        The static token resolves to tenant_id="default", so sessions
        created with a different tenant_id should not appear in the list.
        """
        app = _make_app()
        # Create 1 session for "default" tenant
        asyncio.run(app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "default", "user_id": "u1", "conversation_id": "c1"},
        ))
        # Create 1 session for "firm-a" tenant (different from auth context)
        asyncio.run(app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "firm-a", "user_id": "u2", "conversation_id": "c2"},
        ))

        # GET /v1/sessions with "default" tenant auth → only see "default" sessions
        result = asyncio.run(app.dispatch("GET", "/v1/sessions", AUTH_HEADERS, None))
        self.assertEqual(result["count"], 1)
        for s in result["sessions"]:
            self.assertEqual(s["tenant_id"], "default", "Should only see own tenant sessions")

    def test_list_sessions_requires_auth(self) -> None:
        """No auth → 401."""
        app = _make_app()
        result = asyncio.run(app.dispatch("GET", "/v1/sessions", {}, None))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")


if __name__ == "__main__":
    unittest.main()
