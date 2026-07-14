"""Tests for dashboard rendering — html.escape, CSP compliance, sections."""

from __future__ import annotations

import unittest
from pathlib import Path

from admin_web_ui.boundary import AdminUiBoundary
from admin_web_ui.dashboard import _render_gate_honesty_banner, render_dashboard
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


if __name__ == "__main__":
    unittest.main()
