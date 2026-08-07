"""Tests for the Gateway POST /v1/auth/login endpoint.

Verifies:
- Dev mode (rbac_enabled=False) accepts any credentials
- Dev mode cookie has no Secure flag, uses SameSite=Lax
- Tenant_id and user_id from body are respected
- RBAC mode rejects missing/invalid token with 401
- RBAC mode accepts valid static token
- All other routes still require auth (login bypass is scoped)
- Route parsing for /v1/auth/login
"""

from __future__ import annotations

import asyncio
import unittest

from gateway.app import GatewayApp, OPERATION_LOGIN, _parse_route
from gateway.auth import GatewayAuth
from gateway.config import GatewayConfig
from gateway.login import GatewayLoginHandler
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from rbac.session import InMemorySessionStore


def _make_app(rbac_enabled: bool = False, static_token: str | None = "test-token") -> GatewayApp:
    config = GatewayConfig(enabled=True, rbac_enabled=rbac_enabled)
    auth = GatewayAuth(rbac_enabled=rbac_enabled, static_token=static_token)
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()
    login_handler = GatewayLoginHandler(session_mgr, auth, config)
    return GatewayApp(
        config,
        runtime=object(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
        login_handler=login_handler,
    )


class TestLoginEndpoint(unittest.TestCase):
    """Tests for POST /v1/auth/login."""

    def test_login_dev_mode_accepts_any_credentials(self) -> None:
        app = _make_app(rbac_enabled=False)
        result = asyncio.run(app.dispatch("POST", "/v1/auth/login", {}, {}))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["status"], "ok")
        self.assertIn("session_id", result)
        self.assertIn("tenant_id", result)
        self.assertIn("set_cookie", result)

    def test_login_dev_mode_set_cookie_has_no_secure_flag(self) -> None:
        app = _make_app(rbac_enabled=False)
        result = asyncio.run(app.dispatch("POST", "/v1/auth/login", {}, {}))
        set_cookie = result["set_cookie"]
        self.assertNotIn("Secure", set_cookie, f"Dev cookie must not have Secure flag: {set_cookie}")

    def test_login_dev_mode_set_cookie_has_same_site_lax(self) -> None:
        app = _make_app(rbac_enabled=False)
        result = asyncio.run(app.dispatch("POST", "/v1/auth/login", {}, {}))
        set_cookie = result["set_cookie"]
        self.assertIn("SameSite=Lax", set_cookie, f"Dev cookie must have SameSite=Lax: {set_cookie}")

    def test_login_with_tenant_id(self) -> None:
        app = _make_app(rbac_enabled=False)
        result = asyncio.run(app.dispatch(
            "POST", "/v1/auth/login", {},
            {"tenant_id": "firm-a", "user_id": "lawyer1"},
        ))
        self.assertEqual(result["tenant_id"], "firm-a")

    def test_login_rbac_enabled_rejects_missing_token(self) -> None:
        app = _make_app(rbac_enabled=True, static_token="secret-token")
        result = asyncio.run(app.dispatch("POST", "/v1/auth/login", {}, {}))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "invalid_credentials")

    def test_login_rbac_enabled_accepts_valid_static_token(self) -> None:
        app = _make_app(rbac_enabled=True, static_token="secret-token")
        result = asyncio.run(app.dispatch(
            "POST", "/v1/auth/login", {},
            {"token": "secret-token"},
        ))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["status"], "ok")
        self.assertIn("session_id", result)

    def test_other_routes_still_require_auth(self) -> None:
        """The login bypass is scoped to exactly one route — other routes still require auth."""
        app = _make_app(rbac_enabled=False)
        # GET /v1/sessions/{id} without auth should return 401
        result = asyncio.run(app.dispatch("GET", "/v1/sessions/sess-1", {}, None))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")

    def test_login_route_parsed(self) -> None:
        operation, path_params = _parse_route("POST", "/v1/auth/login", "/v1")
        self.assertEqual(operation, OPERATION_LOGIN)
        self.assertEqual(path_params, {})


if __name__ == "__main__":
    unittest.main()
