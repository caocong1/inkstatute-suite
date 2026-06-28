from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any
import unittest

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from hermes_contract_layer.wecom_validation import validate_wecom_shadow_evidence


PHASE4_SUCCESS_STREAM = LOCAL_FIXTURE_ROOT / "phase4_success_event_stream.jsonl"


class WeComValidationTests(unittest.TestCase):
    def test_valid_wecom_stream_with_feedback_target_passes(self) -> None:
        report = validate_wecom_shadow_evidence(
            PHASE4_SUCCESS_STREAM,
            ack_started_at="2026-06-28T02:30:00Z",
            ack_completed_at="2026-06-28T02:30:03Z",
        )

        self.assertTrue(report.passed)
        self.assertEqual(report.event_count, 4)
        self.assertEqual(report.feedback_target, "phase4-msg-success-001")
        self.assertEqual(report.live_status, "fixture")
        self.assertEqual(report.issues, [])

    def test_missing_feedback_target_reports_issue_when_feedback_expected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "missing-feedback-target.jsonl"
            records = _load_raw_records(PHASE4_SUCCESS_STREAM)
            agent_result = records[3]["event"]
            agent_result.pop("feedback_target")
            agent_result["metadata"]["feedback_target_source"] = "unavailable"
            _write_raw_records(stream, records)

            report = validate_wecom_shadow_evidence(stream)

        self.assertFalse(report.passed)
        self.assertIn("missing_feedback_target", _issue_codes(report.issues))

    def test_non_wecom_channel_reports_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "qqbot-stream.jsonl"
            records = _load_raw_records(PHASE4_SUCCESS_STREAM)
            records[0]["event"]["channel"] = "qqbot"
            records[0]["event"]["metadata"]["raw_platform"] = "qqbot"
            _write_raw_records(stream, records)

            report = validate_wecom_shadow_evidence(stream)

        self.assertFalse(report.passed)
        self.assertIn("non_wecom_channel", _issue_codes(report.issues))

    def test_exact_raw_payload_key_reports_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "raw-payload.jsonl"
            records = _load_raw_records(PHASE4_SUCCESS_STREAM)
            records[0]["event"]["metadata"]["raw_payload"] = {"text": "do not store full payload"}
            _write_raw_records(stream, records)

            report = validate_wecom_shadow_evidence(stream)

        self.assertFalse(report.passed)
        raw_payload_issue = next(issue for issue in report.issues if issue.code == "raw_payload_forbidden")
        self.assertEqual(raw_payload_issue.path, "agent_turn.metadata.raw_payload")
        self.assertEqual(raw_payload_issue.event_key, "agent_turn")

    def test_ack_timeout_reports_issue(self) -> None:
        report = validate_wecom_shadow_evidence(
            PHASE4_SUCCESS_STREAM,
            ack_started_at="2026-06-28T02:30:00Z",
            ack_completed_at="2026-06-28T02:30:06Z",
        )

        self.assertFalse(report.passed)
        self.assertIn("ack_timeout", _issue_codes(report.issues))

    def test_stream_errors_are_structured_validation_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.jsonl"

            report = validate_wecom_shadow_evidence(missing, live_status="blocked")

        self.assertFalse(report.passed)
        self.assertEqual(report.event_count, 0)
        self.assertEqual(report.live_status, "blocked")
        self.assertEqual(report.issues[0].code, "stream_invalid")


def _issue_codes(issues: list[Any]) -> set[str]:
    return {issue.code for issue in issues}


def _load_raw_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_raw_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
