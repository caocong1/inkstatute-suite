"""Tests for AdminApiClient — proxy to admin-console-api."""

from __future__ import annotations

import unittest
from typing import Any, Mapping

from admin_web_ui.api_client import AdminApiClient
from rbac import Identity, Role


class AdminApiClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = AdminApiClient()
        self.identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")

    def _make_handle(
        self,
        expected_path: str = "/sessions",
        return_value: tuple[int, dict[str, Any]] = (200, {"items": [], "count": 0}),
    ) -> Any:
        """Create a fake handle_admin_get callable."""
        def handle_admin_get(
            path: str,
            query: str | Mapping[str, str] | None,
            headers: Mapping[str, str] | None,
            read_model: Any,
            feedback_queue: list[dict[str, Any]] | None,
            feature_flags: Any,
            env: Mapping[str, str] | None = None,
            rbac_secret: str | None = None,
        ) -> tuple[int, dict[str, Any]]:
            assert path == expected_path, f"expected {expected_path}, got {path}"
            return return_value

        return handle_admin_get

    def test_proxy_passes_path_and_returns_response(self) -> None:
        handle = self._make_handle("/sessions", (200, {"items": [{"id": "s1"}], "count": 1}))
        status, data = self.client.proxy(
            handle,
            "/sessions",
            self.identity,
            read_model=None,
            feature_flags=None,
            auth_header="Bearer token123",
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 1)

    def test_proxy_passes_auth_header(self) -> None:
        captured_headers: dict[str, str] = {}

        def handle_admin_get(
            path: str,
            query: str | Mapping[str, str] | None,
            headers: Mapping[str, str] | None,
            read_model: Any,
            feedback_queue: list[dict[str, Any]] | None,
            feature_flags: Any,
            env: Mapping[str, str] | None = None,
            rbac_secret: str | None = None,
        ) -> tuple[int, dict[str, Any]]:
            if headers:
                captured_headers.update(headers)
            return 200, {"ok": True}

        self.client.proxy(
            handle_admin_get,
            "/tasks",
            self.identity,
            read_model=None,
            feature_flags=None,
            auth_header="Bearer abc.def",
        )
        self.assertEqual(captured_headers.get("Authorization"), "Bearer abc.def")

    def test_proxy_works_without_auth_header(self) -> None:
        handle = self._make_handle("/health", (200, {"ok": True}))
        status, data = self.client.proxy(
            handle,
            "/health",
            self.identity,
            read_model=None,
            feature_flags=None,
        )
        self.assertEqual(status, 200)

    def test_proxy_passes_feedback_queue(self) -> None:
        captured: dict[str, Any] = {}

        def handle_admin_get(
            path: str,
            query: str | Mapping[str, str] | None,
            headers: Mapping[str, str] | None,
            read_model: Any,
            feedback_queue: list[dict[str, Any]] | None,
            feature_flags: Any,
            env: Mapping[str, str] | None = None,
            rbac_secret: str | None = None,
        ) -> tuple[int, dict[str, Any]]:
            captured["feedback_queue"] = feedback_queue
            return 200, {"items": []}

        queue = [{"id": "f1", "status": "pending"}]
        self.client.proxy(
            handle_admin_get,
            "/feedback",
            self.identity,
            read_model=None,
            feedback_queue=queue,
            feature_flags=None,
        )
        self.assertEqual(captured["feedback_queue"], queue)


if __name__ == "__main__":
    unittest.main()
