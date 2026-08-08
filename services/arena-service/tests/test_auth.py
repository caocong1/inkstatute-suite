"""Tests for ArenaServiceConfig and ArenaServiceAuth (SVC-01).

Covers config defaults, from_env, generate_token, token auth (constant-time
compare), and localhost-only binding enforcement.
"""

from __future__ import annotations

import unittest
from dataclasses import fields, is_dataclass

from arena_service.auth import ArenaServiceAuth, ArenaServiceAuthError, AuthContext
from arena_service.config import ArenaServiceConfig


class ArenaServiceConfigTests(unittest.TestCase):
    """Tests 1-4: ArenaServiceConfig frozen slotted dataclass + from_env + generate_token."""

    def test_config_is_frozen_slotted_dataclass_with_expected_fields(self):
        # Test 1: frozen slotted dataclass with the 7 required fields and defaults.
        self.assertTrue(is_dataclass(ArenaServiceConfig))
        cfg = ArenaServiceConfig()
        self.assertEqual(cfg.bind_host, "127.0.0.1")
        self.assertEqual(cfg.bind_port, 8001)
        self.assertEqual(cfg.base_path, "/v1")
        self.assertEqual(cfg.token, "")
        self.assertEqual(cfg.max_concurrent_initializations, 2)
        self.assertEqual(cfg.per_run_timeout_seconds, 300.0)
        self.assertTrue(cfg.enabled)
        # frozen: assignment must raise
        with self.assertRaises(Exception):
            cfg.token = "x"  # type: ignore[misc]
        # slotted: no __dict__
        self.assertFalse(hasattr(cfg, "__dict__"))
        # all 7 fields present
        field_names = {f.name for f in fields(ArenaServiceConfig)}
        self.assertEqual(
            field_names,
            {
                "bind_host",
                "bind_port",
                "base_path",
                "token",
                "max_concurrent_initializations",
                "per_run_timeout_seconds",
                "enabled",
            },
        )

    def test_from_env_with_token(self):
        # Test 2: from_env reads ARENA_SERVICE_TOKEN and defaults.
        cfg = ArenaServiceConfig.from_env({"ARENA_SERVICE_TOKEN": "abc123"})
        self.assertEqual(cfg.token, "abc123")
        self.assertEqual(cfg.bind_host, "127.0.0.1")
        self.assertEqual(cfg.bind_port, 8001)

    def test_from_env_empty_mapping_returns_empty_token(self):
        # Test 3: from_env({}) returns token="" (empty).
        cfg = ArenaServiceConfig.from_env({})
        self.assertEqual(cfg.token, "")

    def test_generate_token_returns_43_char_urlsafe_and_is_unique(self):
        # Test 4: generate_token() returns 43-char URL-safe string, unique per call.
        token_a = ArenaServiceConfig.generate_token()
        token_b = ArenaServiceConfig.generate_token()
        self.assertEqual(len(token_a), 43)
        self.assertEqual(len(token_b), 43)
        self.assertNotEqual(token_a, token_b)


class ArenaServiceAuthTests(unittest.TestCase):
    """Tests 5-10: ArenaServiceAuth token auth + localhost enforcement."""

    def _make_auth(self, token: str = "secret") -> ArenaServiceAuth:
        cfg = ArenaServiceConfig(token=token)
        return ArenaServiceAuth(config=cfg)

    def test_require_auth_valid_token_returns_authenticated_context(self):
        # Test 5: valid token returns AuthContext with authenticated=True.
        auth = self._make_auth(token="secret")
        ctx = auth.require_auth({"Authorization": "Bearer secret"})
        self.assertIsInstance(ctx, AuthContext)
        self.assertTrue(ctx.authenticated)

    def test_require_auth_missing_header_raises_401(self):
        # Test 6: no Authorization header raises ArenaServiceAuthError(401, unauthorized).
        auth = self._make_auth(token="secret")
        with self.assertRaises(ArenaServiceAuthError) as cm:
            auth.require_auth({})
        self.assertEqual(cm.exception.status, 401)
        self.assertEqual(cm.exception.code, "unauthorized")

    def test_require_auth_wrong_token_raises_401(self):
        # Test 7: wrong token raises ArenaServiceAuthError(401, unauthorized).
        auth = self._make_auth(token="secret")
        with self.assertRaises(ArenaServiceAuthError) as cm:
            auth.require_auth({"Authorization": "Bearer wrong"})
        self.assertEqual(cm.exception.status, 401)
        self.assertEqual(cm.exception.code, "unauthorized")

    def test_check_localhost_accepts_loopback_rejects_remote(self):
        # Test 8: check_localhost returns True for 127.* and ::1, False for remote.
        auth = self._make_auth()
        self.assertTrue(auth.check_localhost("127.0.0.1"))
        self.assertTrue(auth.check_localhost("::1"))
        self.assertFalse(auth.check_localhost("192.168.1.1"))
        self.assertFalse(auth.check_localhost("10.0.0.1"))

    def test_require_localhost_rejects_remote_with_403(self):
        # Test 9: require_localhost does not raise for loopback, raises 403 for remote.
        auth = self._make_auth()
        # loopback — no raise
        auth.require_localhost("127.0.0.1")
        auth.require_localhost("::1")
        # remote — 403 forbidden_remote
        with self.assertRaises(ArenaServiceAuthError) as cm:
            auth.require_localhost("192.168.1.1")
        self.assertEqual(cm.exception.status, 403)
        self.assertEqual(cm.exception.code, "forbidden_remote")

    def test_auth_context_is_frozen_slotted_dataclass(self):
        # Test 10: AuthContext is a frozen slotted dataclass with the 3 fields.
        self.assertTrue(is_dataclass(AuthContext))
        ctx = AuthContext(authenticated=True, token_valid=True, error=None)
        self.assertTrue(ctx.authenticated)
        self.assertTrue(ctx.token_valid)
        self.assertIsNone(ctx.error)
        # frozen
        with self.assertRaises(Exception):
            ctx.authenticated = False  # type: ignore[misc]
        # slotted
        self.assertFalse(hasattr(ctx, "__dict__"))
        field_names = {f.name for f in fields(AuthContext)}
        self.assertEqual(field_names, {"authenticated", "token_valid", "error"})


if __name__ == "__main__":
    unittest.main()
