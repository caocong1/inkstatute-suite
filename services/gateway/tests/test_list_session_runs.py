"""Tests for the Gateway GET /v1/sessions/{id}/runs endpoint.

Verifies:
- list_session_runs returns run list (200)
- list_session_runs returns empty array for new session (200)
- list_session_runs returns 404 for nonexistent session
- list_session_runs requires auth (401)
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


class TestListSessionRuns(unittest.TestCase):
    """Tests for GET /v1/sessions/{session_id}/runs."""

    def test_list_session_runs_returns_run_list(self) -> None:
        """Create session, then GET runs → 200 with runs array (runtime has no list_runs → empty)."""
        app = _make_app()
        create_result = asyncio.run(app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "default", "user_id": "lawyer1", "conversation_id": "conv-1"},
        ))
        session_id = create_result["session_id"]

        result = asyncio.run(app.dispatch(
            "GET", f"/v1/sessions/{session_id}/runs", AUTH_HEADERS, None,
        ))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertIn("runs", result)
        self.assertIsInstance(result["runs"], list)
        self.assertEqual(result["session_id"], session_id)

    def test_list_session_runs_empty(self) -> None:
        """New session with no runs → 200 with empty runs array."""
        app = _make_app()
        create_result = asyncio.run(app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "default", "user_id": "lawyer1", "conversation_id": "conv-1"},
        ))
        session_id = create_result["session_id"]

        result = asyncio.run(app.dispatch(
            "GET", f"/v1/sessions/{session_id}/runs", AUTH_HEADERS, None,
        ))
        self.assertEqual(result["runs"], [])
        self.assertEqual(result["count"], 0)

    def test_list_session_runs_not_found(self) -> None:
        """Nonexistent session → 404."""
        app = _make_app()
        result = asyncio.run(app.dispatch(
            "GET", "/v1/sessions/nonexistent/runs", AUTH_HEADERS, None,
        ))
        self.assertEqual(result["status"], 404)
        self.assertEqual(result["error"]["code"], "not_found")

    def test_list_session_runs_requires_auth(self) -> None:
        """No auth → 401."""
        app = _make_app()
        result = asyncio.run(app.dispatch(
            "GET", "/v1/sessions/some-id/runs", {}, None,
        ))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")


if __name__ == "__main__":
    unittest.main()
