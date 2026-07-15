"""Tests for dashboard rendering — html.escape, CSP compliance, sections."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from admin_web_ui.boundary import AdminUiBoundary
from admin_web_ui.catalog import render_catalog_page
from admin_web_ui.channels import render_channels_page
from admin_web_ui.dashboard import (
    _page_template,
    _render_gate_honesty_banner,
    render_dashboard,
    render_error_page,
)
from admin_web_ui.providers import render_providers_page
from rbac import Identity, Role


_DASHBOARD_SRC = Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "dashboard.py"


class DashboardRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = AdminUiBoundary()
        self.identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")

    def test_render_index_contains_navigation(self) -> None:
        html_doc = render_dashboard("index", {}, identity=self.identity, boundary=self.boundary)
        self.assertIn("InkStatute Admin Dashboard", html_doc)
        self.assertIn("/sessions", html_doc)
        self.assertIn("/feedback", html_doc)
        self.assertIn("/health", html_doc)
        self.assertIn("/gates", html_doc)
        self.assertIn("/config/providers", html_doc)
        self.assertIn("/config/catalog", html_doc)
        self.assertIn("/config/vision", html_doc)

    def test_render_index_contains_config_cards(self) -> None:
        html_doc = render_dashboard("index", {}, identity=self.identity, boundary=self.boundary)
        self.assertIn("Channel Config", html_doc)
        self.assertIn("Provider Config", html_doc)
        self.assertIn("Model Catalog", html_doc)
        self.assertIn("Vision Config", html_doc)
        self.assertIn("/config/channels", html_doc)
        self.assertIn("/config/providers", html_doc)
        self.assertIn("/config/catalog", html_doc)
        self.assertIn("/config/vision", html_doc)

    def test_index_contains_gate_honesty_banner(self) -> None:
        html_doc = render_dashboard("index", {}, identity=self.identity, boundary=self.boundary)
        self.assertIn("This console does not close live acceptance gates", html_doc)
        self.assertIn("not_live_acceptance", html_doc)
        self.assertIn('role="note"', html_doc)
        self.assertIn('aria-label="Gate honesty notice"', html_doc)

    def test_gates_contains_carried_human_gates_card(self) -> None:
        data = {
            "gates": [
                {"name": "platform-contract", "status": "0"},
            ],
        }
        html_doc = render_dashboard("gates", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("Carried human gates", html_doc)
        self.assertIn("Phase 5 WeCom UAT", html_doc)
        self.assertIn("Phase 8 lawyer trial", html_doc)
        self.assertIn("QQ live acceptance", html_doc)
        self.assertIn("Automated gate results do not replace live acceptance.", html_doc)

    def test_gate_honesty_forbidden_phrases_absent(self) -> None:
        src = _DASHBOARD_SRC.read_text(encoding="utf-8").lower()
        self.assertNotIn("lawyer trial acceptance complete", src)
        self.assertNotIn("live wecom uat passed", src)
        self.assertNotIn("live qq openapi acceptance", src)
        self.assertNotIn("live provider reachability", src)

    def test_render_gate_honesty_banner_html_contract(self) -> None:
        html = _render_gate_honesty_banner()
        self.assertIn("This console does not close live acceptance gates", html)
        self.assertIn("not_live_acceptance", html)
        self.assertIn('role="note"', html)
        self.assertIn('aria-label="Gate honesty notice"', html)

    def test_render_sessions_with_items(self) -> None:
        data = {
            "items": [
                {"conversation_id": "conv-1", "user_id": "user-1", "channel": "wecom"},
                {"conversation_id": "conv-2", "user_id": "user-2", "channel": "web"},
            ],
            "count": 2,
            "has_more": False,
        }
        html_doc = render_dashboard("sessions", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("conv-1", html_doc)
        self.assertIn("conv-2", html_doc)
        self.assertIn("Session Inspection", html_doc)

    def test_render_tasks_with_items(self) -> None:
        data = {
            "items": [
                {"task_id": "task-1", "status": "succeeded"},
            ],
            "count": 1,
            "has_more": True,
            "next_cursor": "cursor-abc",
        }
        html_doc = render_dashboard("tasks", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("task-1", html_doc)
        self.assertIn("cursor-abc", html_doc)
        self.assertIn("Task Inspection", html_doc)

    def test_render_feedback_queue(self) -> None:
        data = {
            "items": [
                {"feedback_id": "fb-1", "status": "pending", "action": "needs_fix"},
            ],
            "count": 1,
        }
        html_doc = render_dashboard("feedback", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("fb-1", html_doc)
        self.assertIn("Feedback Review Queue", html_doc)

    def test_render_health(self) -> None:
        data = {"services": [{"name": "admin-console-api", "status": "ok", "ok": True, "host": None, "port": None}]}
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("Health Monitoring", html_doc)
        self.assertIn("Service Health", html_doc)
        self.assertIn("admin-console-api", html_doc)

    def test_render_gates(self) -> None:
        data = {
            "gates": [
                {"name": "platform-contract", "status": "0"},
                {"name": "wecom-service", "status": "0"},
            ],
        }
        html_doc = render_dashboard("gates", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("Gate Status", html_doc)
        self.assertIn("platform-contract", html_doc)
        self.assertIn("status-ok", html_doc)

    def test_render_error_response(self) -> None:
        data = {"error": {"code": "forbidden", "message": "Role not permitted"}}
        html_doc = render_dashboard("sessions", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("forbidden", html_doc)
        self.assertIn("Role not permitted", html_doc)
        self.assertIn("error", html_doc)

    def test_html_escape_in_items(self) -> None:
        data = {
            "items": [
                {"conversation_id": "<script>alert(1)</script>", "user_id": "x"},
            ],
            "count": 1,
        }
        html_doc = render_dashboard("sessions", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("&lt;script&gt;", html_doc)
        self.assertNotIn("<script>alert(1)</script>", html_doc)

    def test_identity_displayed(self) -> None:
        html_doc = render_dashboard("index", {}, identity=self.identity, boundary=self.boundary)
        self.assertIn("admin", html_doc)
        self.assertIn("tenant-1", html_doc)

    def test_render_empty_items(self) -> None:
        data = {"items": [], "count": 0}
        html_doc = render_dashboard("sessions", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("No items found", html_doc)

    def test_render_without_identity(self) -> None:
        html_doc = render_dashboard("index", {}, identity=None, boundary=self.boundary)
        self.assertIn("InkStatute Admin Dashboard", html_doc)

    def test_no_innerhtml_or_dangerous_attributes(self) -> None:
        """Ensure no innerHTML, onclick, or inline event handlers in output."""
        data = {"items": [{"id": "x"}], "count": 1}
        html_doc = render_dashboard("sessions", data, identity=self.identity, boundary=self.boundary)
        self.assertNotIn("innerHTML", html_doc)
        self.assertNotIn("onclick", html_doc)
        self.assertNotIn("onerror", html_doc)
        self.assertNotIn("onload", html_doc)
        self.assertNotIn("javascript:", html_doc)


class UnifiedHealthDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = AdminUiBoundary()
        self.identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")

    def test_render_health_unified_service_table(self) -> None:
        data = {
            "services": [
                {"name": "admin-console-api", "status": "ok", "ok": True, "host": None, "port": None},
                {"name": "wecom", "status": "running", "ok": True, "host": "127.0.0.1", "port": 8082},
            ]
        }
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("Service Health", html_doc)
        self.assertIn('<table class="health-services-table">', html_doc)
        self.assertIn("admin-console-api", html_doc)
        self.assertIn("wecom", html_doc)
        self.assertIn("running", html_doc)
        self.assertIn("yes", html_doc)

    def test_render_health_service_ok_false(self) -> None:
        data = {
            "services": [
                {"name": "qqbot", "status": "stopped", "ok": False, "host": None, "port": None},
            ]
        }
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("status-err", html_doc)
        self.assertIn("no", html_doc)

    def test_render_health_gate_pass_rate(self) -> None:
        data = {
            "gate_pass_rate": 0.75,
            "gate_count": 4,
            "gates_passed": 3,
            "gates_failed": 1,
        }
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("75%", html_doc)
        self.assertIn("3 passed", html_doc)
        self.assertIn("4 total", html_doc)
        self.assertIn("1 failed", html_doc)

    def test_render_health_gate_pass_rate_100(self) -> None:
        data = {"gate_pass_rate": 1.0, "gate_count": 2, "gates_passed": 2, "gates_failed": 0}
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("100%", html_doc)
        self.assertIn("gate-pass-rate-ok", html_doc)

    def test_render_health_gate_pass_rate_null(self) -> None:
        data = {"gate_pass_rate": None}
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("Not run", html_doc)
        self.assertIn("run-gates-link", html_doc)
        self.assertIn('href="/health?gates=true"', html_doc)

    def test_render_health_feature_flags_table(self) -> None:
        data = {
            "feature_flags": [
                {"name": "admin_api_enabled", "enabled": True},
                {"name": "wecom_channel_enabled", "enabled": False},
            ]
        }
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("Feature Flags", html_doc)
        self.assertIn('<table class="flags-table">', html_doc)
        self.assertIn("admin_api_enabled", html_doc)
        self.assertIn("wecom_channel_enabled", html_doc)
        self.assertIn("flag-on", html_doc)
        self.assertIn("flag-off", html_doc)

    def test_render_health_carried_human_gates(self) -> None:
        data = {
            "carried_human_gates": [
                {"name": "Phase 5 WeCom UAT", "status": "carried", "auto_closed": False},
            ]
        }
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("Carried Human Gates", html_doc)
        self.assertIn("Phase 5 WeCom UAT", html_doc)
        self.assertIn("HUMAN GATE — carried, not auto-closed", html_doc)
        self.assertIn("human-gate-carried", html_doc)

    def test_render_health_carried_human_gate_non_green(self) -> None:
        data = {
            "carried_human_gates": [
                {"name": "Phase 5 WeCom UAT", "status": "carried", "auto_closed": False},
            ]
        }
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("human-gate-carried", html_doc)
        # The human-gate row should NOT contain status-ok (green)
        # Find the human-gate-carried div and check it doesn't have status-ok
        self.assertIn("human-gate-carried", html_doc)
        # Verify the human-gate section does not use status-ok class
        idx = html_doc.find("human-gate-carried")
        # Check a window around the human-gate section
        section = html_doc[idx:idx + 500]
        self.assertNotIn("status-ok", section)

    def test_render_health_gate_honesty_banner_present(self) -> None:
        data = {"services": []}
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("This console does not close live acceptance gates", html_doc)
        self.assertIn("not_live_acceptance", html_doc)

    def test_render_health_no_mark_human_gate_control(self) -> None:
        src = _DASHBOARD_SRC.read_text(encoding="utf-8")
        self.assertNotIn("mark_human_gate", src)
        self.assertNotIn("pass_human_gate", src)
        self.assertNotIn("close_human_gate", src)

    def test_render_health_html_escaped(self) -> None:
        data = {
            "services": [
                {"name": "<script>alert(1)</script>", "status": "ok", "ok": True, "host": None, "port": None},
            ]
        }
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("&lt;script&gt;", html_doc)
        self.assertNotIn("<script>alert(1)</script>", html_doc)

    def test_render_health_empty_services(self) -> None:
        data = {"services": []}
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("No service health data available.", html_doc)

    def test_render_health_empty_feature_flags(self) -> None:
        data = {"feature_flags": []}
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("No feature flag data available.", html_doc)

    def test_render_health_no_innerhtml_or_dangerous_attributes(self) -> None:
        data = {
            "services": [{"name": "svc", "status": "ok", "ok": True, "host": None, "port": None}],
            "feature_flags": [{"name": "flag", "enabled": True}],
            "carried_human_gates": [{"name": "gate", "status": "carried", "auto_closed": False}],
        }
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertNotIn("innerHTML", html_doc)
        self.assertNotIn("onclick", html_doc)
        self.assertNotIn("onerror", html_doc)
        self.assertNotIn("onload", html_doc)
        self.assertNotIn("javascript:", html_doc)

    def test_render_health_run_gates_link(self) -> None:
        data = {"gate_pass_rate": None}
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn('href="/health?gates=true"', html_doc)
        self.assertIn("Run Gates", html_doc)

    def test_render_health_full_unified(self) -> None:
        data = {
            "services": [{"name": "admin-console-api", "status": "ok", "ok": True, "host": None, "port": None}],
            "gate_pass_rate": 0.5,
            "gate_count": 2,
            "gates_passed": 1,
            "gates_failed": 1,
            "feature_flags": [{"name": "admin_api_enabled", "enabled": True}],
            "carried_human_gates": [{"name": "Phase 5 WeCom UAT", "status": "carried", "auto_closed": False}],
        }
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("Service Health", html_doc)
        self.assertIn("Gate Pass Rate", html_doc)
        self.assertIn("Feature Flags", html_doc)
        self.assertIn("Carried Human Gates", html_doc)


class TestResponsive(unittest.TestCase):
    """Verify no fixed CSS width exceeds 1280px in dashboard.py style block."""

    def test_no_fixed_width_200px(self) -> None:
        """The fixed width: 200px rule must be removed (replaced with max-width)."""
        src = _DASHBOARD_SRC.read_text(encoding="utf-8")
        # Check that no standalone "width: 200px" exists (not preceded by "max-").
        matches = re.findall(r"(?<!max-)width:\s*200px", src)
        self.assertEqual(matches, [], "Fixed width: 200px should be replaced with max-width")

    def test_max_width_200px_present(self) -> None:
        """The max-width: 200px rule must be present (replacing the fixed width)."""
        src = _DASHBOARD_SRC.read_text(encoding="utf-8")
        self.assertIn("max-width: 200px", src)

    def test_no_fixed_width_exceeds_1280(self) -> None:
        """No CSS rule in the style block has a fixed width exceeding 1280px."""
        src = _DASHBOARD_SRC.read_text(encoding="utf-8")
        # Find all "width: NNNpx" occurrences (fixed widths, not max-width).
        matches = re.findall(r"(?<!max-)width:\s*(\d+)px", src)
        for value in matches:
            self.assertLessEqual(
                int(value),
                1280,
                f"Fixed CSS width {value}px exceeds 1280px limit",
            )


class TestErrorPage(unittest.TestCase):
    """Verify render_error_page produces escaped HTML with nav and back-to-dashboard link."""

    def test_404_error_page_contains_status_and_back_link(self) -> None:
        html_doc = render_error_page(404, "Not Found", "Unknown route: /test")
        self.assertIn("Error 404", html_doc)
        self.assertIn("Back to Dashboard", html_doc)

    def test_error_page_escapes_dynamic_content(self) -> None:
        html_doc = render_error_page(404, "Not Found", "<script>alert(1)</script>")
        self.assertNotIn("<script>", html_doc)
        self.assertIn("&lt;script&gt;", html_doc)

    def test_error_page_contains_nav(self) -> None:
        html_doc = render_error_page(500, "Internal Server Error", "An error occurred.")
        self.assertIn("InkStatute Admin Dashboard", html_doc)
        self.assertIn("/sessions", html_doc)

    def test_error_page_no_traceback(self) -> None:
        html_doc = render_error_page(500, "Internal Server Error", "An unexpected error occurred.")
        self.assertNotIn("Traceback", html_doc)
        self.assertNotIn("traceback", html_doc)


class TestNavActiveState(unittest.TestCase):
    """Verify nav active-state indication, auth-aware Login/Logout, and head_extras injection."""

    def test_active_link_has_aria_current(self) -> None:
        html_doc = _page_template("Test", "<p>body</p>", active_path="/")
        self.assertIn('class="nav-link active"', html_doc)
        self.assertIn('aria-current="page"', html_doc)
        # The active link should be on href="/"
        idx = html_doc.find('href="/"')
        self.assertGreater(idx, -1)
        active_fragment = html_doc[idx:idx + 120]
        self.assertIn("active", active_fragment)
        self.assertIn('aria-current="page"', active_fragment)
        # Other links should NOT have the active class
        sessions_idx = html_doc.find('href="/sessions"')
        sessions_fragment = html_doc[sessions_idx:sessions_idx + 120]
        self.assertNotIn("active", sessions_fragment)

    def test_nav_consistent_across_pages(self) -> None:
        html_root = _page_template("Test", "<p>body</p>", active_path="/")
        html_sessions = _page_template("Test", "<p>body</p>", active_path="/sessions")
        expected_labels = [
            "Dashboard",
            "Sessions",
            "Tasks",
            "Feedback Review",
            "Health",
            "Gates",
            "Reports",
            "Processes",
            "Logs",
            "Audit Trail",
            "Channel Config",
            "Provider Config",
            "Model Catalog",
            "Vision Config",
        ]
        for label in expected_labels:
            self.assertIn(label, html_root)
            self.assertIn(label, html_sessions)
        # Count nav links — should be the same (14 nav items + 1 Login/Logout = 15)
        root_count = html_root.count('class="nav-link')
        sessions_count = html_sessions.count('class="nav-link')
        self.assertEqual(root_count, sessions_count)

    def test_login_logout_auth_aware(self) -> None:
        # Anonymous — Login shown, Logout absent
        html_anon = _page_template("Test", "<p>body</p>", identity=None)
        self.assertIn("Login", html_anon)
        self.assertNotIn("Logout", html_anon)
        # Authenticated — Logout shown, Login absent
        identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")
        html_auth = _page_template("Test", "<p>body</p>", identity=identity)
        self.assertIn("Logout", html_auth)
        self.assertNotIn("Login", html_auth)

    def test_head_extras_injected(self) -> None:
        meta_tag = '<meta http-equiv="refresh" content="5">'
        html_with = _page_template("Test", "<p>body</p>", head_extras=meta_tag)
        self.assertIn(meta_tag, html_with)
        # Verify it's inside the <head> block
        head_end = html_with.find("</head>")
        meta_idx = html_with.find(meta_tag)
        self.assertLess(meta_idx, head_end)
        # Default head_extras="" should NOT inject the meta tag
        html_without = _page_template("Test", "<p>body</p>")
        self.assertNotIn('http-equiv="refresh"', html_without)

    def test_config_renderers_mark_active_nav_on_success_path(self) -> None:
        """Regression for WR-01: render_*_page must thread active_path on the
        success path, not only on the error path. Otherwise POLISH-02 nav
        active-state highlighting is silently lost on normal page views.
        """
        identity = Identity(role=Role.ADMIN, tenant_id="t1")
        channels_data = {
            "data": {
                "qqbot": {
                    "channel_id": "qqbot",
                    "enabled": False,
                    "app_id_ref": None,
                    "app_secret_ref": None,
                    "token_secret_ref": None,
                    "bot_secret_ref": None,
                    "metadata": {},
                },
                "wecom": {
                    "channel_id": "wecom",
                    "enabled": False,
                    "token_secret_ref": None,
                    "encoding_aes_key_secret_ref": None,
                    "corp_id_ref": None,
                    "metadata": {},
                },
            },
            "effective": {
                "qqbot": {
                    "platform_flag": False,
                    "host_enabled": False,
                    "effective_enabled": False,
                    "refs_configured": {},
                },
                "wecom": {
                    "platform_flag": False,
                    "host_enabled": False,
                    "effective_enabled": False,
                    "refs_configured": {},
                },
            },
            "metadata": {"operator_config_enabled": True},
        }
        providers_data = {"data": {}, "metadata": {"operator_config_enabled": True}}
        catalog_data = {"data": {}, "metadata": {"operator_config_enabled": True}}

        html_channels = render_channels_page(channels_data, identity=identity)
        html_providers = render_providers_page(providers_data, identity=identity)
        html_catalog = render_catalog_page(catalog_data, identity=identity)

        for html, active_href in (
            (html_channels, "/config/channels"),
            (html_providers, "/config/providers"),
            (html_catalog, "/config/catalog"),
        ):
            idx = html.find(f'href="{active_href}"')
            self.assertGreater(idx, -1, f"missing nav link {active_href}")
            fragment = html[idx : idx + 160]
            self.assertIn(
                "active",
                fragment,
                f"nav link {active_href} not marked active on success path",
            )
            self.assertIn(
                'aria-current="page"',
                fragment,
                f"nav link {active_href} missing aria-current on success path",
            )


if __name__ == "__main__":
    unittest.main()
