"""Tests for the Admin Console API auth gate and route dispatch."""

from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import patch

from admin_console_api.api import handle_admin_get
from platform_runtime.feature_flags import RuntimeFeatureFlags


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


if __name__ == "__main__":
    unittest.main()
