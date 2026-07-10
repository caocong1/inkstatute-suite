"""Signed CSRF issue/validate RED contract (Plan 76-02).

Wave 0 scaffold: process-local HMAC-SHA256 signing key, random nonce,
role/tenant/route binding, and ``hmac.compare_digest`` verification. Valid
tokens pass only for the issuing Identity and route; missing, malformed,
tampered, cross-role, cross-tenant, and cross-route tokens fail.

These contracts are intentionally RED until Plan 76-04 implements
``admin_web_ui.csrf``. No live provider, WeCom, QQ, or lawyer-trial acceptance
is claimed.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from rbac import Identity, Role


_CSRF_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "csrf.py"
)

_SIGNING_KEY = "process-local-csrf-signing-key-NEVER-COMMITTED"
_ROUTE_PROVIDERS = "/config/providers"
_ROUTE_CATALOG = "/config/catalog"
_ROUTE_PROBE = "/config/providers/probe"


def _try_import_csrf() -> Any:
    """Import the csrf module; return None if it does not exist yet."""
    try:
        from admin_web_ui import csrf
    except ImportError:
        return None
    return csrf


class CsrfScaffoldTests(unittest.TestCase):
    """Signed CSRF token issue/validate RED contract (Plan 76-04)."""

    def test_csrf_module_exists_with_issue_and_validate(self) -> None:
        if not _CSRF_SRC.is_file():
            self.fail(
                "PROV-01..04: admin_web_ui/csrf.py not implemented (Plan 76-04) — "
                "expected issue_csrf_token / validate_csrf_token with HMAC-SHA256"
            )
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail(
                "PROV-01..04: admin_web_ui.csrf import failed (Plan 76-04)"
            )
        if not hasattr(csrf, "issue_csrf_token") or not hasattr(
            csrf, "validate_csrf_token"
        ):
            self.fail(
                "PROV-01..04: csrf module missing issue_csrf_token / "
                "validate_csrf_token (Plan 76-04)"
            )

    def test_csrf_uses_hmac_compare_digest(self) -> None:
        """Validation must use hmac.compare_digest (constant-time)."""
        if not _CSRF_SRC.is_file():
            self.fail("csrf.py not implemented (Plan 76-04)")
        src = _CSRF_SRC.read_text(encoding="utf-8")
        self.assertIn("compare_digest", src)
        self.assertIn("hmac", src)

    def test_valid_token_passes_for_issuing_identity_and_route(self) -> None:
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = csrf.issue_csrf_token(
            identity=identity,
            route=_ROUTE_PROVIDERS,
            signing_key=_SIGNING_KEY,
        )
        self.assertIsInstance(token, str)
        self.assertTrue(token)
        self.assertTrue(
            csrf.validate_csrf_token(
                token=token,
                identity=identity,
                route=_ROUTE_PROVIDERS,
                signing_key=_SIGNING_KEY,
            )
        )

    def test_token_contains_random_nonce(self) -> None:
        """Two tokens for the same identity/route must differ (random nonce)."""
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        t1 = csrf.issue_csrf_token(
            identity=identity, route=_ROUTE_PROVIDERS, signing_key=_SIGNING_KEY
        )
        t2 = csrf.issue_csrf_token(
            identity=identity, route=_ROUTE_PROVIDERS, signing_key=_SIGNING_KEY
        )
        self.assertNotEqual(t1, t2)

    def test_missing_token_fails(self) -> None:
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        self.assertFalse(
            csrf.validate_csrf_token(
                token=None,
                identity=identity,
                route=_ROUTE_PROVIDERS,
                signing_key=_SIGNING_KEY,
            )
        )
        self.assertFalse(
            csrf.validate_csrf_token(
                token="",
                identity=identity,
                route=_ROUTE_PROVIDERS,
                signing_key=_SIGNING_KEY,
            )
        )

    def test_malformed_token_fails(self) -> None:
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        for bad in ("not-a-token", "only-one-part", "a.b.c", "   ", "x.y.z.w"):
            with self.subTest(token=bad):
                self.assertFalse(
                    csrf.validate_csrf_token(
                        token=bad,
                        identity=identity,
                        route=_ROUTE_PROVIDERS,
                        signing_key=_SIGNING_KEY,
                    )
                )

    def test_tampered_token_fails(self) -> None:
        """A token with a modified payload or signature must fail."""
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = csrf.issue_csrf_token(
            identity=identity, route=_ROUTE_PROVIDERS, signing_key=_SIGNING_KEY
        )
        # Flip the last character of the signature portion.
        parts = token.split(".")
        tampered_sig = parts[-1][:-1] + ("a" if parts[-1][-1] != "a" else "b")
        tampered = ".".join(parts[:-1] + [tampered_sig])
        self.assertFalse(
            csrf.validate_csrf_token(
                token=tampered,
                identity=identity,
                route=_ROUTE_PROVIDERS,
                signing_key=_SIGNING_KEY,
            )
        )

    def test_cross_role_token_fails(self) -> None:
        """A token issued for ADMIN must not validate for OPERATOR."""
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        admin = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        operator = Identity(role=Role.OPERATOR, tenant_id="tenant-1")
        token = csrf.issue_csrf_token(
            identity=admin, route=_ROUTE_PROVIDERS, signing_key=_SIGNING_KEY
        )
        self.assertFalse(
            csrf.validate_csrf_token(
                token=token,
                identity=operator,
                route=_ROUTE_PROVIDERS,
                signing_key=_SIGNING_KEY,
            )
        )

    def test_cross_tenant_token_fails(self) -> None:
        """A token issued for tenant-1 must not validate for tenant-2."""
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        t1 = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        t2 = Identity(role=Role.ADMIN, tenant_id="tenant-2")
        token = csrf.issue_csrf_token(
            identity=t1, route=_ROUTE_PROVIDERS, signing_key=_SIGNING_KEY
        )
        self.assertFalse(
            csrf.validate_csrf_token(
                token=token,
                identity=t2,
                route=_ROUTE_PROVIDERS,
                signing_key=_SIGNING_KEY,
            )
        )

    def test_cross_route_token_fails(self) -> None:
        """A token issued for /config/providers must not validate for /config/catalog."""
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = csrf.issue_csrf_token(
            identity=identity, route=_ROUTE_PROVIDERS, signing_key=_SIGNING_KEY
        )
        self.assertFalse(
            csrf.validate_csrf_token(
                token=token,
                identity=identity,
                route=_ROUTE_CATALOG,
                signing_key=_SIGNING_KEY,
            )
        )
        self.assertFalse(
            csrf.validate_csrf_token(
                token=token,
                identity=identity,
                route=_ROUTE_PROBE,
                signing_key=_SIGNING_KEY,
            )
        )

    def test_wrong_signing_key_fails(self) -> None:
        """A token signed with one key must not validate with another."""
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        token = csrf.issue_csrf_token(
            identity=identity, route=_ROUTE_PROVIDERS, signing_key=_SIGNING_KEY
        )
        self.assertFalse(
            csrf.validate_csrf_token(
                token=token,
                identity=identity,
                route=_ROUTE_PROVIDERS,
                signing_key="wrong-key",
            )
        )

    def test_probe_route_bound_token_validates_for_probe_route(self) -> None:
        """A token issued for the probe route validates only for that route."""
        csrf = _try_import_csrf()
        if csrf is None:
            self.fail("csrf module not implemented (Plan 76-04)")
        identity = Identity(role=Role.OPERATOR, tenant_id="tenant-1")
        token = csrf.issue_csrf_token(
            identity=identity, route=_ROUTE_PROBE, signing_key=_SIGNING_KEY
        )
        self.assertTrue(
            csrf.validate_csrf_token(
                token=token,
                identity=identity,
                route=_ROUTE_PROBE,
                signing_key=_SIGNING_KEY,
            )
        )
        self.assertFalse(
            csrf.validate_csrf_token(
                token=token,
                identity=identity,
                route=_ROUTE_PROVIDERS,
                signing_key=_SIGNING_KEY,
            )
        )


if __name__ == "__main__":
    unittest.main()
