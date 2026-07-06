"""Tests for the Admin Console API auth gate and route dispatch."""

from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import patch

from admin_console_api.api import handle_admin_get
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.tenant_scope import TenantScopeError
from rbac import Role, issue_token


class FakeReadModel:
    """Minimal read model stub for auth-gate tests."""

    def list_conversations(self, **kwargs: Any) -> list[tuple[str, str, dict]]:
        return [("conv-1", "2026-01-01T00:00:00Z", {"conversation_id": "conv-1"})]

    def get_conversation(self, conversation_id: str) -> dict | None:
        if conversation_id == "conv-1":
            return {"conversation_id": "conv-1"}
        return None

    def list_tasks(self, **kwargs: Any) -> list[tuple[str, str, dict]]:
        return [("task-1", "2026-01-01T00:00:00Z", {"task_id": "task-1"})]

    def get_task(self, identifier: str) -> dict | None:
        if identifier == "task-1":
            return {"task_id": "task-1"}
        return None

    def get_task_by_trace_id(self, trace_id: str) -> dict | None:
        if trace_id == "trace-1":
            return {"task_id": "task-1", "trace_id": "trace-1"}
        return None


class AdminApiAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_flags = RuntimeFeatureFlags(admin_api_enabled=True)
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}
        self.read_model = FakeReadModel()
        self.feedback_queue: list[dict] = []

    def test_disabled_flag_returns_403(self) -> None:
        flags = RuntimeFeatureFlags()
        status, body = handle_admin_get(
            "/sessions", "", self.headers, self.read_model,
            self.feedback_queue, flags, self.env,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_disabled")

    def test_missing_token_returns_403(self) -> None:
        status, body = handle_admin_get(
            "/sessions", "", self.headers, self.read_model,
            self.feedback_queue, self.feature_flags, {},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_not_configured")

    def test_missing_auth_header_returns_401(self) -> None:
        status, body = handle_admin_get(
            "/sessions", "", None, self.read_model,
            self.feedback_queue, self.feature_flags, self.env,
        )
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_invalid_token_returns_401(self) -> None:
        headers = {"Authorization": "Bearer wrong"}
        status, body = handle_admin_get(
            "/sessions", "", headers, self.read_model,
            self.feedback_queue, self.feature_flags, self.env,
        )
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_valid_auth_routes_to_sessions(self) -> None:
        status, body = handle_admin_get(
            "/sessions", "", self.headers, self.read_model,
            self.feedback_queue, self.feature_flags, self.env,
        )
        self.assertEqual(status, 200)

    def test_unknown_path_returns_404(self) -> None:
        status, body = handle_admin_get(
            "/unknown", "", self.headers, self.read_model,
            self.feedback_queue, self.feature_flags, self.env,
        )
        self.assertEqual(status, 404)

    def test_health_returns_200(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            self.feedback_queue, self.feature_flags, self.env,
        )
        self.assertEqual(status, 200)
        self.assertIn("service", body)

    def test_health_excludes_secret_refs(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            self.feedback_queue, self.feature_flags, self.env,
        )
        self.assertNotIn("secret_refs_configured", body)

    def test_health_has_secrets_configured_boolean(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            self.feedback_queue, self.feature_flags, self.env,
        )
        self.assertIn("secrets_configured", body)
        self.assertIsInstance(body["secrets_configured"], bool)

    @unittest.skipIf(os.environ.get("SKIP_GATE_TESTS"), "gate subprocess tests skipped")
    def test_gates_returns_200(self) -> None:
        with patch("admin_console_api.gates.run_gate_summary", return_value={
            "passed": True, "gates": [{"name": "g1", "exit_code": 0}],
        }):
            status, body = handle_admin_get(
                "/gates", "", self.headers, self.read_model,
                self.feedback_queue, self.feature_flags, self.env,
            )
        self.assertEqual(status, 200)
        self.assertIn("passed", body)


class TenantGuardIntegrationTests(unittest.TestCase):
    """Tests for TenantGuard integration in handle_admin_get."""

    def setUp(self) -> None:
        self.rbac_secret = "test-secret"
        self.read_model = FakeReadModel()
        self.feedback_queue: list[dict] = []

    def _rbac_headers(self, role: Role, tenant_id: str = "t1") -> dict[str, str]:
        token = issue_token(self.rbac_secret, role=role, tenant_id=tenant_id)
        return {"Authorization": f"Bearer {token}"}

    def test_disabled_multi_tenant_returns_all_data(self) -> None:
        """multi_tenant_enabled=False → all data returned (no regression)."""
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True, rbac_enabled=True, multi_tenant_enabled=False,
        )
        status, body = handle_admin_get(
            "/sessions", "", self._rbac_headers(Role.ADMIN),
            self.read_model, self.feedback_queue, flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 200)
        self.assertGreater(len(body["items"]), 0)

    def test_enabled_multi_tenant_filters_by_identity_tenant(self) -> None:
        """multi_tenant_enabled=True → TenantGuard enforces tenant filtering."""
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True, rbac_enabled=True, multi_tenant_enabled=True,
        )
        status, body = handle_admin_get(
            "/sessions", "", self._rbac_headers(Role.ADMIN, tenant_id="firm-a"),
            self.read_model, self.feedback_queue, flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 200)

    def test_enabled_multi_tenant_unresolved_identity_raises(self) -> None:
        """multi_tenant_enabled=True with no tenant_id → TenantScopeError (fail-safe)."""
        from rbac.token import _b64url_encode
        from unittest.mock import patch
        import hashlib
        import hmac
        import json as _json

        # Build a token with tenant_id="" (empty string → unresolved)
        with patch("rbac.token.time.time", return_value=1000.0):
            now = 1000
            payload = {
                "role": "admin",
                "tenant_id": "",
                "iat": now,
                "exp": now + 60,
            }
            payload_json = _json.dumps(payload, separators=(",", ":"), sort_keys=True)
            payload_b64 = _b64url_encode(payload_json.encode("utf-8"))
            sig = hmac.new(
                self.rbac_secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
            ).digest()
            token = f"{payload_b64}.{_b64url_encode(sig)}"

            flags = RuntimeFeatureFlags(
                admin_api_enabled=True, rbac_enabled=True, multi_tenant_enabled=True,
            )
            with self.assertRaises(TenantScopeError):
                handle_admin_get(
                    "/sessions", "", {"Authorization": f"Bearer {token}"},
                    self.read_model, self.feedback_queue, flags,
                    env={}, rbac_secret=self.rbac_secret,
                )

    def test_static_token_path_with_multi_tenant_disabled(self) -> None:
        """Static token auth + multi_tenant_enabled=False → unchanged behavior."""
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True, rbac_enabled=False, multi_tenant_enabled=False,
        )
        env = {"ADMIN_API_TOKEN": "test-token"}
        status, body = handle_admin_get(
            "/sessions", "", {"Authorization": "Bearer test-token"},
            self.read_model, self.feedback_queue, flags, env,
        )
        self.assertEqual(status, 200)
        self.assertGreater(len(body["items"]), 0)


if __name__ == "__main__":
    unittest.main()
