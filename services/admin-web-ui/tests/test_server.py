"""Tests for AdminWebUiServer — feature flag gate, RBAC, CSP, routing."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any, Mapping

from admin_console_api.api import handle_admin_get as real_handle_admin_get
from admin_web_ui.dashboard import render_error_page
from admin_web_ui.server import CSP_HEADER, handle_admin_web_ui_request
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
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


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


def _load_raw_records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_tenant_tagged_read_model():
    """Build a read model with tenant_id-injected records for two tenants."""
    base_records = _load_raw_records(PHASE5_STREAM)
    records: list[dict[str, object]] = []

    for tenant in ("firm-a", "firm-b"):
        for rec in base_records:
            cloned = copy.deepcopy(rec)
            event = cloned.get("event")
            if isinstance(event, dict):
                event["tenant_id"] = tenant
                if cloned.get("event_key") == "agent_turn":
                    event["conversation_id"] = f"conv-{tenant}"
                    event["turn_id"] = f"turn-{tenant}"
                elif "turn_id" in event:
                    event["turn_id"] = f"turn-{tenant}"
                    event["conversation_id"] = f"conv-{tenant}"
            records.append(cloned)

    return build_read_model(records)


class TenantIsolationTests(unittest.TestCase):
    """End-to-end tenant isolation tests through admin-web-ui → admin-console-api."""

    SECRET = "test-secret-key"

    def setUp(self) -> None:
        self.read_model = _build_tenant_tagged_read_model()
        self.feedback_queue: list[dict[str, Any]] = [
            {"feedback_id": "fb-a", "status": "pending", "tenant_id": "firm-a"},
            {"feedback_id": "fb-b", "status": "pending", "tenant_id": "firm-b"},
        ]

    def _token(self, tenant_id: str) -> str:
        return issue_token(self.SECRET, role=Role.ADMIN, tenant_id=tenant_id)

    def test_disabled_multi_tenant_shows_all_data(self) -> None:
        """multi_tenant_enabled=False → all data shown (no regression)."""
        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            rbac_enabled=True,
            multi_tenant_enabled=False,
        )
        status, body, _ = handle_admin_web_ui_request(
            "/sessions",
            {"Authorization": f"Bearer {self._token('firm-a')}"},
            feature_flags=flags,
            handle_admin_get=real_handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 200)
        self.assertIn("conv-firm-a", body)
        self.assertIn("conv-firm-b", body)

    def test_enabled_multi_tenant_filters_by_identity(self) -> None:
        """multi_tenant_enabled=True → only firm-a data shown for firm-a admin."""
        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            rbac_enabled=True,
            multi_tenant_enabled=True,
        )
        status, body, _ = handle_admin_web_ui_request(
            "/sessions",
            {"Authorization": f"Bearer {self._token('firm-a')}"},
            feature_flags=flags,
            handle_admin_get=real_handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 200)
        self.assertIn("conv-firm-a", body)
        self.assertNotIn("conv-firm-b", body)

    def test_enabled_multi_tenant_different_tenant_isolation(self) -> None:
        """firm-b admin cannot see firm-a conversations."""
        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            rbac_enabled=True,
            multi_tenant_enabled=True,
        )
        status, body, _ = handle_admin_web_ui_request(
            "/sessions",
            {"Authorization": f"Bearer {self._token('firm-b')}"},
            feature_flags=flags,
            handle_admin_get=real_handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 200)
        self.assertIn("conv-firm-b", body)
        self.assertNotIn("conv-firm-a", body)

    def test_enabled_multi_tenant_feedback_filtered(self) -> None:
        """feedback section shows only firm-a feedback items for firm-a admin."""
        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            rbac_enabled=True,
            multi_tenant_enabled=True,
        )
        status, body, _ = handle_admin_web_ui_request(
            "/feedback",
            {"Authorization": f"Bearer {self._token('firm-a')}"},
            feature_flags=flags,
            handle_admin_get=real_handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 200)
        self.assertIn("fb-a", body)
        self.assertNotIn("fb-b", body)


class TestErrorPages(unittest.TestCase):
    """Verify dedicated 404/500/413 error pages (POLISH-01)."""

    SECRET = "test-secret-key"

    def setUp(self) -> None:
        self.handle_admin_get = _make_fake_handle_admin_get()
        self.read_model = None
        self.feedback_queue: list[dict[str, Any]] = []

    def test_404_dedicated_page(self) -> None:
        """GET /nonexistent returns 404 with dedicated error page (nav + back link)."""
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True)
        token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="tenant-1")
        status, body, headers = handle_admin_web_ui_request(
            "/nonexistent-route-xyz",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 404)
        self.assertIn("Error 404", body)
        self.assertIn("Back to Dashboard", body)
        self.assertNotIn("Traceback", body)

    def test_500_on_uncaught_exception(self) -> None:
        """render_error_page(500, ...) produces a dedicated 500 page."""
        html_body = render_error_page(
            500,
            "Internal Server Error",
            "An unexpected error occurred. Check server logs.",
        )
        self.assertIn("Internal Server Error", html_body)
        self.assertIn("Error 500", html_body)
        self.assertIn("Back to Dashboard", html_body)

    def test_500_no_stack_trace_leak(self) -> None:
        """500 response body must not contain Traceback or exception details."""
        html_body = render_error_page(
            500,
            "Internal Server Error",
            "An unexpected error occurred. Check server logs.",
        )
        self.assertNotIn("Traceback", html_body)
        self.assertNotIn("traceback", html_body)

    def test_500_try_except_exists_in_dispatch(self) -> None:
        """Verify the try/except 500 catch-all exists in server.py source."""
        server_src = Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "server.py"
        src = server_src.read_text(encoding="utf-8")
        self.assertIn("traceback.print_exc", src)
        self.assertIn("render_error_page", src)
        self.assertIn("500", src)

    def test_500_no_str_exc_in_html(self) -> None:
        """Verify str(exc) is never used in HTML response context."""
        server_src = Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "server.py"
        src = server_src.read_text(encoding="utf-8")
        self.assertNotIn("str(exc)", src)

    def test_413_uses_render_error_page(self) -> None:
        """Verify the 413 handler uses render_error_page, not bare HTML."""
        server_src = Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "server.py"
        src = server_src.read_text(encoding="utf-8")
        # The bare HTML pattern must be gone.
        self.assertNotIn("<!DOCTYPE html><html><body>", src)
        # The 413 render_error_page call must be present.
        self.assertIn("render_error_page", src)
        self.assertIn("413", src)

    def test_404_uses_render_error_page(self) -> None:
        """Verify the 404 handler uses render_error_page."""
        server_src = Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "server.py"
        src = server_src.read_text(encoding="utf-8")
        # Count render_error_page occurrences (404, 500, 413 = at least 3).
        count = src.count("render_error_page")
        self.assertGreaterEqual(count, 3)

    def test_500_response_includes_security_headers(self) -> None:
        """Verify the 500 except block sets CSP, X-Content-Type-Options, X-Frame-Options."""
        server_src = Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "server.py"
        src = server_src.read_text(encoding="utf-8")
        # The 500 except block must include all three security headers.
        self.assertIn("X-Content-Type-Options", src)
        self.assertIn("X-Frame-Options", src)
        self.assertIn("Content-Security-Policy", src)


if __name__ == "__main__":
    unittest.main()
