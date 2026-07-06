"""Tests for dashboard rendering — html.escape, CSP compliance, sections."""

from __future__ import annotations

import unittest

from admin_web_ui.boundary import AdminUiBoundary
from admin_web_ui.dashboard import render_dashboard
from rbac import Identity, Role


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
        data = {"ok": True, "components": [{"component_id": "api", "ok": True}]}
        html_doc = render_dashboard("health", data, identity=self.identity, boundary=self.boundary)
        self.assertIn("Health Monitoring", html_doc)
        self.assertIn("component_id", html_doc)

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


if __name__ == "__main__":
    unittest.main()
