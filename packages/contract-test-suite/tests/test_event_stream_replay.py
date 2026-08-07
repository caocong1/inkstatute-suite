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
    resume_from_seq,
    sort_events_by_seq,
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

    def test_out_of_order_sequence_reports_envelope_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "out-of-order.jsonl"
            records = _load_raw_records(PHASE4_STREAMS[0])
            _write_raw_records(broken, [records[0], records[2], records[1], records[3]])

            report = replay_event_streams([broken])
            with self.assertRaises(AssertionError):
                assert_event_stream_integrity([broken])

        issue = next(issue for issue in report.issues if issue.relationship == "seq_monotonic")
        self.assertEqual(issue.field_path, "envelope.seq")
        self.assertEqual(issue.expected, [0, 1, 2, 3])
        self.assertEqual(issue.actual, [0, 2, 1, 3])

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

    def test_out_of_order_events_replay_correctly_by_seq(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out-of-order-run-events.jsonl"
            seq_order = [0, 2, 1, 4, 3]
            records = [_make_run_event_record(seq=s) for s in seq_order]
            _write_raw_records(path, records)

            loaded = _load_raw_records(path)
            sorted_events = sort_events_by_seq(loaded)

            self.assertEqual([e["seq"] for e in sorted_events], [0, 1, 2, 3, 4])
            self.assertEqual(len(sorted_events), 5)
            self.assertEqual(len({e["event_id"] for e in sorted_events}), 5)

    def test_resume_from_seq_no_duplicates_no_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ten-run-events.jsonl"
            records = [_make_run_event_record(seq=s) for s in range(10)]
            _write_raw_records(path, records)

            events = _load_raw_records(path)

            resumed = resume_from_seq(events, 4)
            self.assertEqual([e["seq"] for e in resumed], [5, 6, 7, 8, 9])
            self.assertEqual(len(resumed), 5)

            resumed_all = resume_from_seq(events, -1)
            self.assertEqual(len(resumed_all), 10)

            resumed_none = resume_from_seq(events, 9)
            self.assertEqual(len(resumed_none), 0)

    def test_resume_from_arbitrary_breakpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "breakpoint-run-events.jsonl"
            records = [_make_run_event_record(seq=s) for s in range(10)]
            _write_raw_records(path, records)

            events = _load_raw_records(path)

            for bp in range(-1, 10):
                resumed = resume_from_seq(events, bp)
                if bp == -1:
                    self.assertEqual(len(resumed), 10)
                else:
                    self.assertEqual(len(resumed), 10 - (bp + 1))
                    for e in resumed:
                        self.assertGreater(e["seq"], bp)

    def test_ingested_at_preserved_through_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ingested-at-events.jsonl"
            records = [
                _make_run_event_record(seq=s, occurred_at=f"2026-08-07T10:00:0{s}Z", ingested_at=f"2026-08-07T10:00:0{s}Z")
                for s in [0, 2, 1, 4, 3]
            ]
            _write_raw_records(path, records)

            loaded = _load_raw_records(path)
            sorted_events = sort_events_by_seq(loaded)
            resumed = resume_from_seq(sorted_events, 1)

            for e in resumed:
                self.assertIn("occurred_at", e)
                self.assertIn("ingested_at", e)
                self.assertIsNotNone(e["occurred_at"])
                self.assertIsNotNone(e["ingested_at"])

            self.assertEqual(
                [(e["seq"], e["occurred_at"], e["ingested_at"]) for e in resumed],
                [
                    (2, "2026-08-07T10:00:02Z", "2026-08-07T10:00:02Z"),
                    (3, "2026-08-07T10:00:03Z", "2026-08-07T10:00:03Z"),
                    (4, "2026-08-07T10:00:04Z", "2026-08-07T10:00:04Z"),
                ],
            )

    def test_occurred_at_and_ingested_at_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "semantics-events.jsonl"
            records = [
                _make_run_event_record(seq=0, occurred_at="2026-08-07T10:00:00Z", ingested_at="2026-08-07T10:00:05Z"),
                _make_run_event_record(seq=1, occurred_at="2026-08-07T10:00:10Z", ingested_at="2026-08-07T10:00:15Z"),
            ]
            _write_raw_records(path, records)

            loaded = _load_raw_records(path)
            sorted_events = sort_events_by_seq(loaded)
            resumed = resume_from_seq(sorted_events, -1)

            self.assertEqual(len(resumed), 2)
            for e in resumed:
                self.assertIn("occurred_at", e)
                self.assertIn("ingested_at", e)
                self.assertNotEqual(e["occurred_at"], e["ingested_at"])

            self.assertEqual(resumed[0]["occurred_at"], "2026-08-07T10:00:00Z")
            self.assertEqual(resumed[0]["ingested_at"], "2026-08-07T10:00:05Z")
            self.assertEqual(resumed[1]["occurred_at"], "2026-08-07T10:00:10Z")
            self.assertEqual(resumed[1]["ingested_at"], "2026-08-07T10:00:15Z")

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


def _make_run_event_record(
    seq: int,
    *,
    occurred_at: str = "2026-08-07T00:00:00Z",
    ingested_at: str = "2026-08-07T00:00:01Z",
    event_type: str = "session.started",
) -> dict[str, Any]:
    """Build a minimal RunEvent dict for replay/resume tests."""
    return {
        "event_id": f"evt-{seq}",
        "run_id": "run-test",
        "event_type": event_type,
        "occurred_at": occurred_at,
        "ingested_at": ingested_at,
        "seq": seq,
    }


if __name__ == "__main__":
    unittest.main()
