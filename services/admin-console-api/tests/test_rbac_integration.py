"""Integration tests for RBAC enforcement in handle_admin_get."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from admin_console_api.api import handle_admin_get
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Role, issue_token
from rbac.token import _b64url_encode


def _expired_token(secret: str, role_str: str = "admin", tenant_id: str = "t1") -> str:
    """Build a token with exp in the past (exp=1060)."""
    import hashlib
    import hmac
    import json

    now = 1000
    payload = {
        "role": role_str,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + 60,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_b64 = _b64url_encode(payload_json.encode("utf-8"))
    sig = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{payload_b64}.{_b64url_encode(sig)}"


class FakeReadModel:
    """Minimal read model stub for RBAC integration tests."""

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


class RbacDisabledTests(unittest.TestCase):
    """When rbac_enabled=False, the v1.6 static-token path runs unchanged."""

    def setUp(self) -> None:
        self.flags = RuntimeFeatureFlags(admin_api_enabled=True)
        self.env = {"ADMIN_API_TOKEN": "tok"}
        self.read_model = FakeReadModel()
        self.feedback_queue: list[dict] = []

    def test_valid_static_token_returns_200(self) -> None:
        status, _ = handle_admin_get(
            "/sessions", "", {"Authorization": "Bearer tok"},
            self.read_model, self.feedback_queue, self.flags, self.env,
        )
        self.assertEqual(status, 200)

    def test_invalid_token_returns_401(self) -> None:
        status, body = handle_admin_get(
            "/sessions", "", {"Authorization": "Bearer wrong"},
            self.read_model, self.feedback_queue, self.flags, self.env,
        )
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_missing_token_returns_403(self) -> None:
        status, body = handle_admin_get(
            "/sessions", "", {"Authorization": "Bearer tok"},
            self.read_model, self.feedback_queue, self.flags, {},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_not_configured")


class RbacEnabledTests(unittest.TestCase):
    """When rbac_enabled=True, RBAC token + RbacGuard enforce role access."""

    def setUp(self) -> None:
        self.flags = RuntimeFeatureFlags(admin_api_enabled=True, rbac_enabled=True)
        self.rbac_secret = "test-secret"
        self.read_model = FakeReadModel()
        self.feedback_queue: list[dict] = []

    def _rbac_headers(self, role: Role, tenant_id: str = "t1") -> dict[str, str]:
        token = issue_token(self.rbac_secret, role=role, tenant_id=tenant_id)
        return {"Authorization": f"Bearer {token}"}

    def test_admin_token_sessions_returns_200(self) -> None:
        status, _ = handle_admin_get(
            "/sessions", "", self._rbac_headers(Role.ADMIN),
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 200)

    def test_viewer_gates_returns_403(self) -> None:
        status, body = handle_admin_get(
            "/gates", "", self._rbac_headers(Role.VIEWER),
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "forbidden")
        self.assertEqual(body["error"]["role"], "viewer")

    def test_viewer_sessions_returns_200(self) -> None:
        status, _ = handle_admin_get(
            "/sessions", "", self._rbac_headers(Role.VIEWER),
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 200)

    def test_operator_feedback_returns_200(self) -> None:
        status, _ = handle_admin_get(
            "/feedback", "", self._rbac_headers(Role.OPERATOR),
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 200)

    def test_viewer_feedback_returns_403(self) -> None:
        status, body = handle_admin_get(
            "/feedback", "", self._rbac_headers(Role.VIEWER),
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "forbidden")

    def test_lawyer_tasks_returns_200(self) -> None:
        status, _ = handle_admin_get(
            "/tasks", "", self._rbac_headers(Role.LAWYER),
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 200)

    @patch("rbac.token.time.time", return_value=2000.0)
    def test_expired_token_returns_401(self, _mock_time: Any) -> None:
        token = _expired_token(self.rbac_secret)
        status, body = handle_admin_get(
            "/sessions", "", {"Authorization": f"Bearer {token}"},
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_missing_auth_returns_401(self) -> None:
        status, body = handle_admin_get(
            "/sessions", "", None,
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_no_secret_returns_401(self) -> None:
        token = issue_token("other-secret", role=Role.ADMIN, tenant_id="t1")
        status, body = handle_admin_get(
            "/sessions", "", {"Authorization": f"Bearer {token}"},
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=None,
        )
        self.assertEqual(status, 401)

    def test_admin_health_returns_200(self) -> None:
        status, _ = handle_admin_get(
            "/health", "", self._rbac_headers(Role.ADMIN),
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 200)

    def test_operator_health_returns_200(self) -> None:
        status, _ = handle_admin_get(
            "/health", "", self._rbac_headers(Role.OPERATOR),
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 200)

    def test_lawyer_health_returns_403(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self._rbac_headers(Role.LAWYER),
            self.read_model, self.feedback_queue, self.flags,
            env={}, rbac_secret=self.rbac_secret,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "forbidden")


if __name__ == "__main__":
    unittest.main()
