"""Tests for resolve_identity() with RBAC token and static-token fallback."""

from __future__ import annotations

import hashlib
import hmac
import json
import unittest

from rbac.identity import Identity, resolve_identity
from rbac.roles import Role
from rbac.token import _b64url_encode, issue_token


def _make_token_with_role(
    secret: str,
    role_str: str,
    tenant_id: str = "t1",
    now: int = 1000,
    ttl: int = 900,
) -> str:
    """Build a token with an arbitrary role string (for unknown-role tests)."""
    payload = {
        "role": role_str,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + ttl,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_b64 = _b64url_encode(payload_json.encode("utf-8"))
    sig = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{payload_b64}.{_b64url_encode(sig)}"


class ResolveIdentityRbacTests(unittest.TestCase):
    def test_rbac_token_resolves_identity(self) -> None:
        token = issue_token("s", role=Role.ADMIN, tenant_id="t1", now=1000)
        identity = resolve_identity(
            f"Bearer {token}",
            rbac_secret="s",
            rbac_enabled=True,
            now=1500,
        )
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity.role, Role.ADMIN)
        self.assertEqual(identity.tenant_id, "t1")

    def test_rbac_token_lawyer_role(self) -> None:
        token = issue_token("s", role=Role.LAWYER, tenant_id="firm-1", now=1000)
        identity = resolve_identity(
            f"Bearer {token}",
            rbac_secret="s",
            rbac_enabled=True,
            now=1500,
        )
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity.role, Role.LAWYER)
        self.assertEqual(identity.tenant_id, "firm-1")

    def test_expired_rbac_token_returns_none(self) -> None:
        token = issue_token("s", role=Role.ADMIN, tenant_id="t1", now=1000, ttl_seconds=60)
        identity = resolve_identity(
            f"Bearer {token}",
            rbac_secret="s",
            rbac_enabled=True,
            now=2000,
        )
        self.assertIsNone(identity)

    def test_wrong_secret_returns_none(self) -> None:
        token = issue_token("s-a", role=Role.ADMIN, tenant_id="t1", now=1000)
        identity = resolve_identity(
            f"Bearer {token}",
            rbac_secret="s-b",
            rbac_enabled=True,
            now=1500,
        )
        self.assertIsNone(identity)

    def test_unknown_role_string_returns_none(self) -> None:
        token = _make_token_with_role("s", "superuser", now=1000)
        identity = resolve_identity(
            f"Bearer {token}",
            rbac_secret="s",
            rbac_enabled=True,
            now=1500,
        )
        self.assertIsNone(identity)

    def test_missing_auth_header_rbac_returns_none(self) -> None:
        identity = resolve_identity(
            None,
            rbac_secret="s",
            rbac_enabled=True,
            now=1500,
        )
        self.assertIsNone(identity)

    def test_rbac_secret_none_with_rbac_enabled_returns_none(self) -> None:
        identity = resolve_identity(
            "Bearer some-token",
            rbac_secret=None,
            rbac_enabled=True,
            now=1500,
        )
        self.assertIsNone(identity)

    def test_non_bearer_header_rbac_returns_none(self) -> None:
        identity = resolve_identity(
            "some-token",
            rbac_secret="s",
            rbac_enabled=True,
            now=1500,
        )
        self.assertIsNone(identity)

    def test_identity_is_frozen(self) -> None:
        token = issue_token("s", role=Role.ADMIN, tenant_id="t1", now=1000)
        identity = resolve_identity(
            f"Bearer {token}",
            rbac_secret="s",
            rbac_enabled=True,
            now=1500,
        )
        assert identity is not None
        with self.assertRaises(Exception):
            identity.role = Role.VIEWER  # type: ignore[misc]


class ResolveIdentityStaticFallbackTests(unittest.TestCase):
    def test_static_token_fallback_returns_admin(self) -> None:
        identity = resolve_identity(
            "Bearer tok",
            static_token="tok",
            rbac_enabled=False,
        )
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity.role, Role.ADMIN)
        self.assertEqual(identity.tenant_id, "default")

    def test_static_token_fallback_invalid_returns_none(self) -> None:
        identity = resolve_identity(
            "Bearer wrong",
            static_token="tok",
            rbac_enabled=False,
        )
        self.assertIsNone(identity)

    def test_static_token_fallback_missing_returns_none(self) -> None:
        identity = resolve_identity(
            None,
            static_token="tok",
            rbac_enabled=False,
        )
        self.assertIsNone(identity)

    def test_static_token_fallback_no_bearer_returns_none(self) -> None:
        identity = resolve_identity(
            "tok",
            static_token="tok",
            rbac_enabled=False,
        )
        self.assertIsNone(identity)

    def test_static_token_fallback_token_none_returns_none(self) -> None:
        identity = resolve_identity(
            "Bearer tok",
            static_token=None,
            rbac_enabled=False,
        )
        self.assertIsNone(identity)


if __name__ == "__main__":
    unittest.main()
