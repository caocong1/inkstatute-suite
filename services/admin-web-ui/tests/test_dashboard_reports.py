"""Integration tests for the /reports admin web UI page."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

from admin_console_api.api import handle_admin_get
from admin_web_ui.server import handle_admin_web_ui_request
from conversation_read_view.reports_aggregator import ReportsAggregator
from platform_runtime.feature_flags import RuntimeFeatureFlags


def _make_jsonl(records: list[dict[str, object]]) -> str:
    path = Path(tempfile.mktemp(suffix=".jsonl"))
    lines = [json.dumps(rec, ensure_ascii=False, sort_keys=True) for rec in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _turn_records(turn_id: str, conversation_id: str, status: str, *, occurred_at: str) -> list[dict[str, object]]:
    return [
        {
            "event_key": "agent_turn",
            "occurred_at": occurred_at,
            "ingested_at": occurred_at,
            "seq": 0,
            "event": {
                "turn_id": turn_id,
                "conversation_id": conversation_id,
                "channel": "wecom",
                "user_id": "user-1",
                "message_type": "text",
                "received_at": occurred_at,
            },
        },
        {
            "event_key": "execution_trace",
            "occurred_at": occurred_at,
            "ingested_at": occurred_at,
            "seq": 1,
            "event": {
                "trace_id": f"trace-{turn_id}",
                "turn_id": turn_id,
                "started_at": occurred_at,
                "ended_at": occurred_at,
            },
        },
        {
            "event_key": "agent_result",
            "occurred_at": occurred_at,
            "ingested_at": occurred_at,
            "seq": 2,
            "event": {
                "result_id": f"result-{turn_id}",
                "turn_id": turn_id,
                "status": status,
                "reply_type": "text",
            },
        },
    ]


class ReportsDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(timezone.utc)
        self.iso = self.now.isoformat().replace("+00:00", "Z")
        records = _turn_records("turn-1", "conv-1", "success", occurred_at=self.iso)
        self.contract_log = _make_jsonl(records)
        self.addCleanup(lambda: Path(self.contract_log).unlink(missing_ok=True))
        self.reports_aggregator = ReportsAggregator(self.contract_log)
        self.feature_flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
        )
        self.env = {"ADMIN_API_TOKEN": "test-token"}

    def _request(self, path: str = "/reports") -> tuple[int, str, dict[str, str]]:
        return handle_admin_web_ui_request(
            path,
            {"Authorization": "Bearer test-token"},
            feature_flags=self.feature_flags,
            handle_admin_get=handle_admin_get,
            read_model=None,
            feedback_queue=[],
            env=self.env,
            rbac_secret=None,
            reports_aggregator=self.reports_aggregator,
        )

    def test_reports_page_returns_200_with_title(self) -> None:
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body, _ = self._request()
        self.assertEqual(status, 200)
        self.assertIn("Reports Dashboard", body)

    def test_reports_page_has_metric_cards(self) -> None:
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body, _ = self._request()
        self.assertEqual(status, 200)
        self.assertIn("Sessions", body)
        self.assertIn("Completion Rate", body)
        self.assertIn("Long Task Success Rate", body)
        self.assertIn("Feedback Up", body)

    def test_reports_page_window_today_selected(self) -> None:
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body, _ = self._request("/reports?window=today")
        self.assertEqual(status, 200)
        self.assertIn('value="today" selected', body)

    def test_reports_page_has_refresh_button(self) -> None:
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body, _ = self._request()
        self.assertEqual(status, 200)
        self.assertIn("Refresh", body)

    def test_reports_page_gate_pass_rate_with_gates(self) -> None:
        """Gate Pass Rate metric should reflect gates_passed/gate_count (MEDIUM-1 fix)."""
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True,
            "gates": [
                {"name": "g1", "exit_code": 0},
                {"name": "g2", "exit_code": 0},
                {"name": "g3", "exit_code": 1},
            ],
        }):
            status, body, _ = self._request()
        self.assertEqual(status, 200)
        # 2/3 = 66.7%
        self.assertIn("66.7%", body)

    def test_reports_page_has_time_range_selector(self) -> None:
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body, _ = self._request()
        self.assertEqual(status, 200)
        self.assertIn('name="window"', body)
        self.assertIn("today", body)
        self.assertIn("7d", body)
        self.assertIn("30d", body)
        self.assertIn("custom", body)

    def test_reports_page_escapes_script_injection(self) -> None:
        """Raw <script> in API response must be escaped in the HTML output."""
        fake_aggregator = type("FakeAggregator", (), {})()
        fake_aggregator.build = lambda *a, **kw: {
            "sessions": {"count": 1},
            "tasks": {"total": 1, "completed": 1, "completion_rate": 1.0,
                      "long_task_total": 0, "long_task_success": 0,
                      "long_task_success_rate": 0.0},
            "feedback": {"up": 0, "down": 0, "none": 0, "total": 0},
            "gates": {"passed": True, "gate_count": 0},
            "metadata": {
                "window": "7d",
                "time_from": "2026-01-01T00:00:00Z",
                "time_to": "2026-01-08T00:00:00Z",
                "aggregated_at": "<script>alert(1)</script>",
                "scan_lines": 0,
                "max_scan_lines": 10000,
                "lookback_seconds": 86400,
                "display_tz": "UTC",
            },
        }
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body, _ = handle_admin_web_ui_request(
                "/reports",
                {"Authorization": "Bearer test-token"},
                feature_flags=self.feature_flags,
                handle_admin_get=handle_admin_get,
                read_model=None,
                feedback_queue=[],
                env=self.env,
                rbac_secret=None,
                reports_aggregator=fake_aggregator,
            )
        self.assertEqual(status, 200)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_reports_nav_link_present_on_index(self) -> None:
        class _FakeReadModel:
            def list_conversations(self, **kw: Any) -> list[tuple[str, str, dict]]:
                return [("conv-1", "2026-01-01T00:00:00Z", {"conversation_id": "conv-1"})]

            def get_conversation(self, cid: str) -> dict | None:
                return {"conversation_id": cid} if cid == "conv-1" else None

            def list_tasks(self, **kw: Any) -> list[tuple[str, str, dict]]:
                return []

            def get_task(self, tid: str) -> dict | None:
                return None

            def get_task_by_trace_id(self, tid: str) -> dict | None:
                return None

        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body, _ = handle_admin_web_ui_request(
                "/",
                {"Authorization": "Bearer test-token"},
                feature_flags=self.feature_flags,
                handle_admin_get=handle_admin_get,
                read_model=_FakeReadModel(),
                feedback_queue=[],
                env=self.env,
                rbac_secret=None,
                reports_aggregator=self.reports_aggregator,
            )
        self.assertEqual(status, 200)
        self.assertIn('href="/reports"', body)
        self.assertIn("Reports", body)


if __name__ == "__main__":
    unittest.main()
