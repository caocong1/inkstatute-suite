"""Tests for the bounded ReportsAggregator scanner."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from conversation_read_view.reports_aggregator import ReportsAggregator


class ReportsAggregatorTests(unittest.TestCase):
    def _make_jsonl(self, records: list[dict[str, object]]) -> str:
        path = Path(tempfile.mktemp(suffix=".jsonl"))
        lines = [json.dumps(rec, ensure_ascii=False, sort_keys=True) for rec in records]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.addCleanup(path.unlink)
        return str(path)

    def _turn_records(self, turn_id: str, conversation_id: str, status: str, *,
                      occurred_at: str, duration_seconds: float = 1.0,
                      tenant_id: str | None = None) -> list[dict[str, object]]:
        records = [
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
                    "started_at": (datetime.fromisoformat(occurred_at.replace("Z", "+00:00")) - timedelta(seconds=duration_seconds)).isoformat().replace("+00:00", "Z"),
                    "ended_at": occurred_at,
                    "active_skill_name": None,
                    "matched_registered_skill": True,
                    "occurred_at": occurred_at,
                    "ingested_at": occurred_at,
                    "seq": 1,
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
                    "occurred_at": occurred_at,
                    "ingested_at": occurred_at,
                    "seq": 2,
                },
            },
        ]
        if tenant_id is not None:
            for rec in records:
                rec["event"] = dict(rec["event"])
                rec["event"]["tenant_id"] = tenant_id
        return records

    def test_two_turns_one_success_one_failed_long_task(self) -> None:
        now = datetime.now(timezone.utc)
        iso = now.isoformat().replace("+00:00", "Z")
        records = []
        records.extend(self._turn_records("turn-1", "conv-1", "success", occurred_at=iso, duration_seconds=120.0))
        records.extend(self._turn_records("turn-2", "conv-2", "failed", occurred_at=iso, duration_seconds=120.0))
        path = self._make_jsonl(records)

        agg = ReportsAggregator(path)
        result = agg.build(now - timedelta(hours=1), now, feedback_queue=[])

        self.assertEqual(result["sessions"]["count"], 2)
        self.assertEqual(result["tasks"]["total"], 2)
        self.assertEqual(result["tasks"]["completed"], 1)
        self.assertEqual(result["tasks"]["failed"], 1)
        self.assertEqual(result["tasks"]["incomplete"], 0)
        self.assertEqual(result["tasks"]["completion_rate"], 0.5)
        self.assertEqual(result["tasks"]["long_task_total"], 2)
        self.assertEqual(result["tasks"]["long_task_success"], 1)
        self.assertEqual(result["tasks"]["long_task_success_rate"], 0.5)

    def test_empty_file_returns_zeros(self) -> None:
        path = self._make_jsonl([])
        agg = ReportsAggregator(path)
        now = datetime.now(timezone.utc)
        result = agg.build(now - timedelta(days=1), now, feedback_queue=[])

        self.assertEqual(result["sessions"]["count"], 0)
        self.assertEqual(result["tasks"]["total"], 0)
        self.assertEqual(result["tasks"]["completion_rate"], 0.0)
        self.assertEqual(result["tasks"]["long_task_success_rate"], 0.0)
        self.assertEqual(result["feedback"]["total"], 0)

    def test_feedback_distribution(self) -> None:
        now = datetime.now(timezone.utc)
        iso = now.isoformat().replace("+00:00", "Z")
        records = self._turn_records("turn-1", "conv-1", "success", occurred_at=iso)
        path = self._make_jsonl(records)

        feedback_queue = [
            {"feedback_id": "f1", "action": "up", "created_at": iso, "status": "pending"},
            {"feedback_id": "f2", "action": "down", "created_at": iso, "status": "pending"},
            {"feedback_id": "f3", "action": "needs_fix", "created_at": iso, "status": "pending"},
            {"feedback_id": "f4", "action": "route_wrong", "created_at": iso, "status": "pending"},
            {"feedback_id": "f5", "action": "other", "created_at": iso, "status": "pending"},
            {"feedback_id": "f6", "created_at": iso, "status": "pending"},
        ]

        agg = ReportsAggregator(path)
        result = agg.build(now - timedelta(hours=1), now, feedback_queue=feedback_queue)

        self.assertEqual(result["feedback"]["up"], 1)
        self.assertEqual(result["feedback"]["down"], 3)
        self.assertEqual(result["feedback"]["none"], 2)
        self.assertEqual(result["feedback"]["total"], 6)

    def test_long_running_turn_outside_window_result_inside_window(self) -> None:
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=25)
        end = now - timedelta(hours=1)
        start_iso = start.isoformat().replace("+00:00", "Z")
        end_iso = end.isoformat().replace("+00:00", "Z")
        records = []
        records.extend(self._turn_records("turn-1", "conv-1", "success", occurred_at=start_iso, duration_seconds=86400.0))
        # Move the result to inside the window while keeping the agent_turn outside the raw window
        records[2]["occurred_at"] = end_iso
        records[2]["ingested_at"] = end_iso
        records[2]["event"]["occurred_at"] = end_iso
        records[2]["event"]["ingested_at"] = end_iso
        path = self._make_jsonl(records)

        agg = ReportsAggregator(path, default_lookback_seconds=86400 * 2)
        result = agg.build(now - timedelta(hours=2), now, feedback_queue=[])

        self.assertEqual(result["sessions"]["count"], 1)
        self.assertEqual(result["tasks"]["total"], 1)
        self.assertEqual(result["tasks"]["completed"], 1)

    def test_tenant_filter(self) -> None:
        now = datetime.now(timezone.utc)
        iso = now.isoformat().replace("+00:00", "Z")
        records = []
        records.extend(self._turn_records("turn-1", "conv-1", "success", occurred_at=iso, tenant_id="t-a"))
        records.extend(self._turn_records("turn-2", "conv-2", "failed", occurred_at=iso, tenant_id="t-b"))
        path = self._make_jsonl(records)

        class FakeFilter:
            is_active = True
            tenant_id = "t-a"

        agg = ReportsAggregator(path)
        result = agg.build(now - timedelta(hours=1), now, feedback_queue=[], tenant_filter=FakeFilter())

        self.assertEqual(result["sessions"]["count"], 1)
        self.assertEqual(result["tasks"]["total"], 1)

    def test_forbidden_payload_fails_closed(self) -> None:
        now = datetime.now(timezone.utc)
        iso = now.isoformat().replace("+00:00", "Z")
        records = [
            {
                "event_key": "agent_turn",
                "occurred_at": iso,
                "ingested_at": iso,
                "seq": 0,
                "event": {
                    "turn_id": "turn-1",
                    "conversation_id": "conv-1",
                    "channel": "wecom",
                    "user_id": "user-1",
                    "message_type": "text",
                    "received_at": iso,
                    "raw_payload": "secret",
                },
            },
        ]
        path = self._make_jsonl(records)

        agg = ReportsAggregator(path)
        with self.assertRaises(ValueError):
            agg.build(now - timedelta(hours=1), now, feedback_queue=[])

    def test_display_tz_in_metadata(self) -> None:
        now = datetime.now(timezone.utc)
        path = self._make_jsonl([])
        agg = ReportsAggregator(path, display_tz="Asia/Shanghai", env={"INKSTATUTE_REPORT_DISPLAY_TZ": "UTC"})
        result = agg.build(now - timedelta(days=1), now, feedback_queue=[])
        self.assertEqual(result["metadata"]["display_tz"], "UTC")


if __name__ == "__main__":
    unittest.main()
