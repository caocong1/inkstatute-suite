"""Tests for RBAC token signing and verification."""

from __future__ import annotations

import unittest

from rbac.roles import Role
from rbac.token import (
    DEFAULT_TOKEN_TTL_SECONDS,
    RbacTokenClaims,
    RbacTokenError,
    issue_token,
    verify_token,
)


class TokenIssueVerifyTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        token = issue_token("secret", role=Role.ADMIN, tenant_id="t1", now=1000)
        claims = verify_token(token, "secret", now=1500)
        self.assertEqual(claims.role, "admin")
        self.assertEqual(claims.tenant_id, "t1")
        self.assertEqual(claims.iat, 1000)
        self.assertEqual(claims.exp, 1900)

    def test_expired_token_rejected(self) -> None:
        token = issue_token("secret", role=Role.ADMIN, tenant_id="t1", now=1000, ttl_seconds=60)
        with self.assertRaises(RbacTokenError):
            verify_token(token, "secret", now=2000)

    def test_wrong_secret_rejected(self) -> None:
        token = issue_token("secret-a", role=Role.ADMIN, tenant_id="t1", now=1000)
        with self.assertRaises(RbacTokenError):
            verify_token(token, "secret-b", now=1500)

    def test_tampered_payload_rejected(self) -> None:
        token = issue_token("secret", role=Role.ADMIN, tenant_id="t1", now=1000)
        payload_b64, sig_b64 = token.split(".")
        # Flip the first character of the payload.
        tampered = ("A" + payload_b64[1:]) + "." + sig_b64
        with self.assertRaises(RbacTokenError):
            verify_token(tampered, "secret", now=1500)

    def test_custom_ttl(self) -> None:
        token = issue_token("secret", role=Role.ADMIN, tenant_id="t1", now=1000, ttl_seconds=60)
        claims = verify_token(token, "secret", now=1050)
        self.assertEqual(claims.exp, 1060)

    def test_default_ttl_is_900(self) -> None:
        self.assertEqual(DEFAULT_TOKEN_TTL_SECONDS, 900)
        token = issue_token("secret", role=Role.ADMIN, tenant_id="t1", now=1000)
        claims = verify_token(token, "secret", now=1500)
        self.assertEqual(claims.exp, 1900)

    def test_invalid_format_rejected(self) -> None:
        with self.assertRaises(RbacTokenError):
            verify_token("not-a-token", "secret", now=1500)

    def test_no_dot_rejected(self) -> None:
        with self.assertRaises(RbacTokenError):
            verify_token("nodot", "secret", now=1500)

    def test_claims_fields(self) -> None:
        token = issue_token("secret", role=Role.LAWYER, tenant_id="firm-1", now=1000)
        claims = verify_token(token, "secret", now=1500)
        self.assertIsInstance(claims, RbacTokenClaims)
        self.assertEqual(claims.role, "lawyer")
        self.assertEqual(claims.tenant_id, "firm-1")

    def test_string_role_accepted(self) -> None:
        token = issue_token("secret", role="operator", tenant_id="t1", now=1000)
        claims = verify_token(token, "secret", now=1500)
        self.assertEqual(claims.role, "operator")

    def test_boundary_expiry_rejected(self) -> None:
        # exp == now should be rejected (exp must be > now).
        token = issue_token("secret", role=Role.ADMIN, tenant_id="t1", now=1000, ttl_seconds=500)
        with self.assertRaises(RbacTokenError):
            verify_token(token, "secret", now=1500)


if __name__ == "__main__":
    unittest.main()
