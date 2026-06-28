from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
from typing import Any
import unittest

from contract_test_suite.event_stream_replay import (
    assert_event_stream_integrity,
    load_event_stream,
    replay_event_streams,
)
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT


PHASE4_STREAMS = [
    LOCAL_FIXTURE_ROOT / "phase4_success_event_stream.jsonl",
    LOCAL_FIXTURE_ROOT / "phase4_simple_qa_event_stream.jsonl",
    LOCAL_FIXTURE_ROOT / "phase4_failed_long_task_event_stream.jsonl",
]


class EventStreamReplayTests(unittest.TestCase):
    def test_load_event_stream_validates_envelope_and_nested_payloads(self) -> None:
        records = load_event_stream(PHASE4_STREAMS[0])

        self.assertEqual([record.event_key for record in records], ["agent_turn", "route_decision", "execution_trace", "agent_result"])
        self.assertEqual([record.seq for record in records], [0, 1, 2, 3])
        self.assertTrue(all(record.occurred_at == "2026-06-28T02:30:00Z" for record in records))

    def test_phase4_stream_fixtures_replay_with_zero_relationship_breakage(self) -> None:
        report = assert_event_stream_integrity(PHASE4_STREAMS)

        self.assertEqual(report.stream_count, 3)
        self.assertEqual(report.record_count, 12)
        self.assertEqual(report.broken_relationship_count, 0)
        self.assertGreater(report.relationship_check_count, 20)

    def test_missing_feedback_event_is_allowed_for_phase4_streams(self) -> None:
        for stream_path in PHASE4_STREAMS:
            event_keys = [record.event_key for record in load_event_stream(stream_path)]
            self.assertNotIn("feedback_event", event_keys)

        report = replay_event_streams(PHASE4_STREAMS)
        self.assertEqual(report.broken_relationship_count, 0)

    def test_broken_turn_relationship_reports_expected_and_actual(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken-turn.jsonl"
            records = _load_raw_records(PHASE4_STREAMS[0])
            records[1]["event"]["turn_id"] = "turn-broken"
            _write_raw_records(broken, records)

            report = replay_event_streams([broken])
            with self.assertRaises(AssertionError):
                assert_event_stream_integrity([broken])

        self.assertGreater(report.broken_relationship_count, 0)
        issue = next(issue for issue in report.issues if issue.relationship == "turn_id")
        self.assertEqual(issue.field_path, "route_decision.turn_id")
        self.assertEqual(issue.expected, "turn-1b3f9e23ad339a1f")
        self.assertEqual(issue.actual, "turn-broken")

    def test_broken_artifact_relationship_reports_fixture_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken-artifact.jsonl"
            records = _load_raw_records(PHASE4_STREAMS[0])
            records[3]["event"]["artifacts"][0]["artifact_id"] = "artifact-mismatch"
            _write_raw_records(broken, records)

            report = replay_event_streams([broken])

        artifact_issues = [issue for issue in report.issues if issue.relationship in {"artifact_id", "artifact_written"}]
        self.assertEqual(len(artifact_issues), 2)
        self.assertTrue(all(issue.stream_path.name == "broken-artifact.jsonl" for issue in artifact_issues))

    def test_phase4_stream_fixtures_are_reference_first_and_no_feedback_fabrication(self) -> None:
        secret_like = re.compile(r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN|password\\s*[:=]|secret\\s*[:=]|token\\s*[:=])")
        for stream_path in PHASE4_STREAMS:
            raw_text = stream_path.read_text(encoding="utf-8")
            self.assertIsNone(secret_like.search(raw_text))
            for record in _load_raw_records(stream_path):
                self.assertNotEqual(record["event_key"], "feedback_event")
                self.assert_no_exact_raw_payload_key(record)

    def test_failed_long_task_fixture_records_exact_async_states_and_runtime_error(self) -> None:
        records = {record.event_key: record.event for record in load_event_stream(PHASE4_STREAMS[2])}
        trace = records["execution_trace"]
        result = records["agent_result"]

        state_values = [step["state"] for step in trace["steps"] if "state" in step]
        self.assertEqual(state_values, ["queued", "running", "failed"])
        self.assertEqual(trace["errors"][0]["category"], "runtime_error")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reply_type"], "status_update")

    def assert_no_exact_raw_payload_key(self, value: Any) -> None:
        if isinstance(value, dict):
            self.assertNotIn("raw_payload", value)
            for child in value.values():
                self.assert_no_exact_raw_payload_key(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_exact_raw_payload_key(child)


def _load_raw_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_raw_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
