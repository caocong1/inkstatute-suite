from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contract_test_suite.coverage_report import (
    assert_coverage_thresholds,
    format_coverage_summary,
    summarize_event_stream_coverage,
    summarize_fixture_bundle_coverage,
)
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT


PHASE5_STREAM = LOCAL_FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"
PHASE6_BUNDLE = LOCAL_FIXTURE_ROOT / "phase6_read_feedback_bundle.json"


class CoverageReportTests(unittest.TestCase):
    def test_event_stream_report_counts_paired_turn_and_result(self) -> None:
        report = summarize_event_stream_coverage([PHASE5_STREAM])

        self.assertEqual(report.turn_count, 1)
        self.assertEqual(report.paired_turn_result_count, 1)
        self.assertEqual(report.paired_turn_result_coverage, 1.0)
        self.assertEqual(report.breakage_rate, 0.0)
        self.assertEqual(report.runtime_input_status, "not_provided")

    def test_fixture_bundle_report_counts_paired_turn_and_result(self) -> None:
        report = summarize_fixture_bundle_coverage([PHASE6_BUNDLE])

        self.assertEqual(report.turn_count, 1)
        self.assertEqual(report.paired_turn_result_count, 1)
        self.assertEqual(report.paired_turn_result_coverage, 1.0)
        self.assertEqual(report.breakage_rate, 0.0)

    def test_missing_runtime_input_is_not_reported_as_live_acceptance(self) -> None:
        report = summarize_event_stream_coverage([PHASE5_STREAM], evidence_kind="fixture")

        self.assertEqual(report.runtime_input_status, "not_provided")
        with self.assertRaisesRegex(AssertionError, "runtime coverage input not provided"):
            assert_coverage_thresholds(report, require_runtime_input=True)

    def test_runtime_input_can_be_reported_as_provided_for_sanitized_streams(self) -> None:
        report = summarize_event_stream_coverage([PHASE5_STREAM], evidence_kind="sanitized_runtime")

        self.assertEqual(report.runtime_input_status, "provided")
        assert_coverage_thresholds(report, require_runtime_input=True)

    def test_threshold_failure_reports_sanitized_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            broken_stream = Path(tmpdir) / "missing_result.jsonl"
            records = [
                json.loads(line)
                for line in PHASE5_STREAM.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            broken_stream.write_text(
                "\n".join(json.dumps(record, sort_keys=True) for record in records if record["event_key"] != "agent_result"),
                encoding="utf-8",
            )

            report = summarize_event_stream_coverage([broken_stream], max_breakage_rate=1.0)
            with self.assertRaisesRegex(AssertionError, "paired AgentTurn/AgentResult coverage"):
                assert_coverage_thresholds(report)

            summary = format_coverage_summary(report, as_json=True)
            self.assertIn('"paired_turn_result_coverage": 0.0', summary)
            self.assertNotIn("Synthetic legal retrieval request", summary)


if __name__ == "__main__":
    unittest.main()

