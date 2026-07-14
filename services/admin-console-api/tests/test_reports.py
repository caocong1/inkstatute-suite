"""Tests for the /reports admin API route and RBAC wiring."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

from admin_console_api.api import handle_admin_get
from conversation_read_view.reports_aggregator import ReportsAggregator
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Role, issue_token


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
                "active_skill_name": None,
                "matched_registered_skill": True,
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


class ReportsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(timezone.utc)
        self.iso = self.now.isoformat().replace("+00:00", "Z")
        records = _turn_records("turn-1", "conv-1", "success", occurred_at=self.iso)
        self.contract_log = _make_jsonl(records)
        self.addCleanup(lambda: Path(self.contract_log).unlink(missing_ok=True))
        self.reports_aggregator = ReportsAggregator(self.contract_log)
        self.feature_flags = RuntimeFeatureFlags(admin_api_enabled=True)
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}
        self.feedback_queue: list[dict[str, Any]] = []

    def _get_reports(self, query: str = "") -> tuple[int, dict[str, Any]]:
        return handle_admin_get(
            "/reports",
            query,
            self.headers,
            read_model=None,
            feedback_queue=self.feedback_queue,
            feature_flags=self.feature_flags,
            env=self.env,
            reports_aggregator=self.reports_aggregator,
        )

    def test_reports_returns_200_with_expected_keys(self) -> None:
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [{"name": "g1", "exit_code": 0}],
        }):
            status, body = self._get_reports()
        self.assertEqual(status, 200)
        self.assertIn("sessions", body)
        self.assertIn("tasks", body)
        self.assertIn("feedback", body)
        self.assertIn("gates", body)
        self.assertIn("metadata", body)
        self.assertIn("count", body["sessions"])
        self.assertIn("completion_rate", body["tasks"])
        self.assertIn("long_task_success_rate", body["tasks"])
        self.assertIn("window", body["metadata"])

    def test_reports_window_today(self) -> None:
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body = self._get_reports("window=today")
        self.assertEqual(status, 200)
        self.assertEqual(body["metadata"]["window"], "today")

    def test_reports_window_invalid_returns_400(self) -> None:
        status, body = self._get_reports("window=invalid")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_window")

    def test_reports_default_window_is_7d(self) -> None:
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body = self._get_reports()
        self.assertEqual(status, 200)
        self.assertEqual(body["metadata"]["window"], "7d")

    def test_reports_aggregator_none_returns_500(self) -> None:
        status, body = handle_admin_get(
            "/reports",
            "",
            self.headers,
            read_model=None,
            feedback_queue=self.feedback_queue,
            feature_flags=self.feature_flags,
            env=self.env,
            reports_aggregator=None,
        )
        self.assertEqual(status, 500)
        self.assertEqual(body["error"]["code"], "reports_not_configured")

    def test_reports_admin_api_disabled_returns_403(self) -> None:
        flags = RuntimeFeatureFlags()
        status, body = handle_admin_get(
            "/reports",
            "",
            self.headers,
            read_model=None,
            feedback_queue=self.feedback_queue,
            feature_flags=flags,
            env=self.env,
            reports_aggregator=self.reports_aggregator,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_disabled")


class ReportsRbacTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rbac_secret = "test-secret"
        self.now = datetime.now(timezone.utc)
        self.iso = self.now.isoformat().replace("+00:00", "Z")
        records = _turn_records("turn-1", "conv-1", "success", occurred_at=self.iso)
        self.contract_log = _make_jsonl(records)
        self.addCleanup(lambda: Path(self.contract_log).unlink(missing_ok=True))
        self.reports_aggregator = ReportsAggregator(self.contract_log)

    def _rbac_headers(self, role: Role, tenant_id: str = "default") -> dict[str, str]:
        token = issue_token(self.rbac_secret, role=role, tenant_id=tenant_id)
        return {"Authorization": f"Bearer {token}"}

    def test_viewer_role_can_access_reports(self) -> None:
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True, rbac_enabled=True, multi_tenant_enabled=False,
        )
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, body = handle_admin_get(
                "/reports",
                "",
                self._rbac_headers(Role.VIEWER),
                read_model=None,
                feedback_queue=[],
                feature_flags=flags,
                env={},
                rbac_secret=self.rbac_secret,
                reports_aggregator=self.reports_aggregator,
            )
        self.assertEqual(status, 200)

    def test_lawyer_role_can_access_reports(self) -> None:
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True, rbac_enabled=True, multi_tenant_enabled=False,
        )
        with patch("admin_console_api.reports.run_gate_summary", return_value={
            "passed": True, "gates": [],
        }):
            status, _ = handle_admin_get(
                "/reports",
                "",
                self._rbac_headers(Role.LAWYER),
                read_model=None,
                feedback_queue=[],
                feature_flags=flags,
                env={},
                rbac_secret=self.rbac_secret,
                reports_aggregator=self.reports_aggregator,
            )
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
