"""Unit tests for the Gateway auth middleware.

Tests GatewayAuth with static-token fallback, RBAC Bearer token,
session cookie fallback, role checks, and tenant checks.

CRITICAL: No method in GatewayAuth produces auto_approve, default_decision,
or allow_once fields (AGENTS.md: "Permission requests must never be
auto-approved server-side").
"""

from __future__ import annotations

import inspect
import time
import unittest

from gateway.auth import AuthContext, GatewayAuth, GatewayAuthError
from rbac.roles import Role
from rbac.session import SESSION_COOKIE_NAME, InMemorySessionStore, issue_session_cookie
from rbac.token import issue_token


class TestGatewayAuth(unittest.TestCase):

    def test_static_token_auth_success(self) -> None:
        auth = GatewayAuth(rbac_enabled=False, static_token="test")
        ctx = auth.authenticate({"Authorization": "Bearer test"})
        self.assertTrue(ctx.authenticated)
        self.assertEqual(ctx.tenant_id, "default")
        self.assertIsNotNone(ctx.identity)
        self.assertEqual(ctx.identity.role, Role.ADMIN)

    def test_static_token_auth_no_header(self) -> None:
        auth = GatewayAuth(rbac_enabled=False, static_token="test")
        ctx = auth.authenticate({})
        self.assertFalse(ctx.authenticated)

    def test_static_token_auth_wrong_token(self) -> None:
        auth = GatewayAuth(rbac_enabled=False, static_token="test")
        ctx = auth.authenticate({"Authorization": "Bearer wrong"})
        self.assertFalse(ctx.authenticated)

    def test_require_auth_raises_on_no_auth(self) -> None:
        auth = GatewayAuth(rbac_enabled=False, static_token="test")
        with self.assertRaises(GatewayAuthError) as cm:
            auth.require_auth({})
        self.assertEqual(cm.exception.status, 401)

    def test_require_role_success(self) -> None:
        auth = GatewayAuth(rbac_enabled=False, static_token="test")
        ctx = auth.require_role({"Authorization": "Bearer test"}, (Role.ADMIN,))
        self.assertTrue(ctx.authenticated)

    def test_require_role_wrong_role(self) -> None:
        secret = "test-secret-key"
        now = int(time.time())
        store = InMemorySessionStore()
        auth = GatewayAuth(
            rbac_enabled=True, rbac_secret=secret, session_store=store,
        )
        token = issue_token(secret, role=Role.LAWYER, tenant_id="tenant-1", now=now)
        with self.assertRaises(GatewayAuthError) as cm:
            auth.require_role({"Authorization": f"Bearer {token}"}, (Role.ADMIN,))
        self.assertEqual(cm.exception.status, 403)

    def test_check_tenant_match(self) -> None:
        auth = GatewayAuth(rbac_enabled=False, static_token="test")
        ctx = auth.require_auth({"Authorization": "Bearer test"})
        auth.check_tenant(ctx, "default")  # Should not raise

    def test_check_tenant_mismatch(self) -> None:
        auth = GatewayAuth(rbac_enabled=False, static_token="test")
        ctx = auth.require_auth({"Authorization": "Bearer test"})
        with self.assertRaises(GatewayAuthError) as cm:
            auth.check_tenant(ctx, "other")
        self.assertEqual(cm.exception.status, 403)

    def test_check_tenant_none_resource(self) -> None:
        auth = GatewayAuth(rbac_enabled=False, static_token="test")
        ctx = auth.require_auth({"Authorization": "Bearer test"})
        auth.check_tenant(ctx, None)  # Should not raise

    def test_rbac_bearer_token_auth(self) -> None:
        secret = "test-secret-key"
        now = int(time.time())
        store = InMemorySessionStore()
        auth = GatewayAuth(
            rbac_enabled=True, rbac_secret=secret, session_store=store,
        )
        token = issue_token(secret, role=Role.LAWYER, tenant_id="tenant-1", now=now)
        ctx = auth.authenticate({"Authorization": f"Bearer {token}"})
        self.assertTrue(ctx.authenticated)
        self.assertEqual(ctx.tenant_id, "tenant-1")

    def test_rbac_session_cookie_fallback(self) -> None:
        secret = "test-secret-key"
        now = int(time.time())
        store = InMemorySessionStore()
        auth = GatewayAuth(
            rbac_enabled=True, rbac_secret=secret, session_store=store,
        )
        sid = store.create(role=Role.LAWYER, tenant_id="tenant-cookie", ttl_seconds=3600, now=now)
        cookie_val = issue_session_cookie(
            secret, sid, role=Role.LAWYER, tenant_id="tenant-cookie", now=now,
        )
        ctx = auth.authenticate({"Cookie": f"{SESSION_COOKIE_NAME}={cookie_val}"})
        self.assertTrue(ctx.authenticated)
        self.assertEqual(ctx.tenant_id, "tenant-cookie")

    def test_no_auto_approve_fields(self) -> None:
        """No method in GatewayAuth produces auto_approve, default_decision, or allow_once."""
        src = inspect.getsource(GatewayAuth)
        for forbidden in ("auto_approve", "default_decision", "allow_once"):
            self.assertNotIn(forbidden, src, f"Found forbidden field '{forbidden}' in GatewayAuth source")

    def test_auth_context_tenant_id_from_identity(self) -> None:
        """When authenticated, tenant_id is always from the identity."""
        auth = GatewayAuth(rbac_enabled=False, static_token="test")
        ctx = auth.authenticate({"Authorization": "Bearer test"})
        self.assertEqual(ctx.tenant_id, ctx.identity.tenant_id)


if __name__ == "__main__":
    unittest.main()
