"""Tests for AdminWebUiServer — feature flag gate, RBAC, CSP, routing."""

from __future__ import annotations

import unittest
from typing import Any, Mapping

from admin_web_ui.server import CSP_HEADER, handle_admin_web_ui_request
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Role, issue_token


def _make_fake_handle_admin_get(
    return_value: tuple[int, dict[str, Any]] = (200, {"items": [], "count": 0}),
) -> Any:
    """Create a fake handle_admin_get that returns a fixed value."""
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
        return return_value

    return handle_admin_get


class AdminWebUiServerTests(unittest.TestCase):
    SECRET = "test-secret-key"

    def setUp(self) -> None:
        self.handle_admin_get = _make_fake_handle_admin_get()
        self.read_model = None
        self.feedback_queue: list[dict[str, Any]] = []

    def test_disabled_feature_flag_returns_503(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=False)
        status, body, headers = handle_admin_web_ui_request(
            "/",
            {},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 503)
        self.assertIn("admin_web_ui_disabled", body)

    def test_enabled_flag_with_admin_token_returns_200(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True)
        token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="tenant-1")
        status, body, headers = handle_admin_web_ui_request(
            "/sessions",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 200)
        self.assertIn("Session Inspection", body)

    def test_enabled_flag_with_operator_token_returns_200(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True, rbac_enabled=True)
        token = issue_token(self.SECRET, role=Role.OPERATOR, tenant_id="tenant-1")
        status, body, headers = handle_admin_web_ui_request(
            "/feedback",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 200)

    def test_lawyer_role_forbidden_on_feedback(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True, rbac_enabled=True)
        token = issue_token(self.SECRET, role=Role.LAWYER, tenant_id="tenant-1")
        status, body, headers = handle_admin_web_ui_request(
            "/feedback",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 403)
        self.assertIn("forbidden", body)

    def test_lawyer_role_allowed_on_sessions(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True, rbac_enabled=True)
        token = issue_token(self.SECRET, role=Role.LAWYER, tenant_id="tenant-1")
        status, body, headers = handle_admin_web_ui_request(
            "/sessions",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 200)

    def test_invalid_token_returns_401(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True, rbac_enabled=True)
        status, body, headers = handle_admin_web_ui_request(
            "/sessions",
            {"Authorization": "Bearer invalid.token.here"},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 401)
        self.assertIn("unauthorized", body)

    def test_missing_token_returns_401(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True, rbac_enabled=True)
        status, body, headers = handle_admin_web_ui_request(
            "/sessions",
            {},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 401)

    def test_csp_header_present(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True)
        token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="tenant-1")
        status, body, headers = handle_admin_web_ui_request(
            "/",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertIn("Content-Security-Policy", headers)
        self.assertEqual(headers["Content-Security-Policy"], CSP_HEADER)

    def test_security_headers_present(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True)
        token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="tenant-1")
        status, body, headers = handle_admin_web_ui_request(
            "/sessions",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("text/html", headers["Content-Type"])

    def test_unknown_route_returns_404(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True)
        token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="tenant-1")
        status, body, headers = handle_admin_web_ui_request(
            "/unknown",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 404)

    def test_index_route_maps_to_sessions_api(self) -> None:
        captured_path: list[str] = []

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
            captured_path.append(path)
            return 200, {"items": [], "count": 0}

        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True)
        token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="tenant-1")
        handle_admin_web_ui_request(
            "/",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(captured_path, ["/sessions"])

    def test_output_boundary_filters_backend_noise(self) -> None:
        """Verify that backend noise in API response is filtered in rendered HTML."""
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
            return 200, {
                "items": [
                    {"id": "s1", "detail": "model: gpt-4 processing your request"},
                ],
                "count": 1,
            }

        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True)
        token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="tenant-1")
        status, body, headers = handle_admin_web_ui_request(
            "/sessions",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertNotIn("gpt-4", body)
        self.assertNotIn("model:", body.lower())


if __name__ == "__main__":
    unittest.main()
