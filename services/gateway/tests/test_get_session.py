"""Tests for the Gateway GET /v1/sessions/{id} endpoint.

Verifies:
- get_session returns session info with all fields (200)
- get_session returns 404 for nonexistent session
- get_session denies cross-tenant access (403)
- get_session requires auth (401)
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


class TestGetSession(unittest.TestCase):
    """Tests for GET /v1/sessions/{session_id}."""

    def test_get_session_returns_session_info(self) -> None:
        """Create a session via create_session, then GET it → 200 with session fields."""
        app = _make_app()
        # Create a session first
        create_result = asyncio.run(app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "default", "user_id": "lawyer1", "conversation_id": "conv-1"},
        ))
        session_id = create_result["session_id"]

        # Now GET the session
        result = asyncio.run(app.dispatch("GET", f"/v1/sessions/{session_id}", AUTH_HEADERS, None))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["session_id"], session_id)
        self.assertEqual(result["tenant_id"], "default")
        self.assertEqual(result["user_id"], "lawyer1")
        self.assertEqual(result["conversation_id"], "conv-1")
        self.assertIn("created_at", result)
        self.assertIn("expires_at", result)
        self.assertIn("devices", result)

    def test_get_session_not_found(self) -> None:
        """GET /v1/sessions/nonexistent → 404."""
        app = _make_app()
        result = asyncio.run(app.dispatch("GET", "/v1/sessions/nonexistent", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 404)
        self.assertEqual(result["error"]["code"], "not_found")

    def test_get_session_cross_tenant_denied(self) -> None:
        """Create session with tenant A, request with tenant B auth → 403."""
        app = _make_app()
        # Create a session with tenant "firm-a"
        create_result = asyncio.run(app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "firm-a", "user_id": "lawyer1", "conversation_id": "conv-a"},
        ))
        session_id = create_result["session_id"]

        # Request with a different tenant's auth.
        # The static token resolves to tenant_id="default" in dev mode.
        # We need to create a session for "firm-a" and then access with "default" tenant.
        # Since the static token always resolves to "default" tenant, the session
        # created with tenant_id="firm-a" will be cross-tenant.
        result = asyncio.run(app.dispatch("GET", f"/v1/sessions/{session_id}", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 403)
        self.assertEqual(result["error"]["code"], "tenant_mismatch")

    def test_get_session_requires_auth(self) -> None:
        """GET /v1/sessions/{id} without auth → 401."""
        app = _make_app()
        result = asyncio.run(app.dispatch("GET", "/v1/sessions/some-id", {}, None))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")


if __name__ == "__main__":
    unittest.main()
