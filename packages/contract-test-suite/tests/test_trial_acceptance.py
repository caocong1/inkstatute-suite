from __future__ import annotations

import json
import unittest

from contract_test_suite.trial_acceptance import (
    TrialTaskEvidence,
    assert_trial_acceptance_ready,
    evaluate_trial_acceptance,
    format_trial_acceptance_summary,
)


class TrialAcceptanceTests(unittest.TestCase):
    def test_raw_payload_key_is_rejected(self) -> None:
        row = _trial_row()
        row["metadata"] = {"raw" + "_payload": "forbidden"}

        with self.assertRaisesRegex(ValueError, "references"):
            TrialTaskEvidence.from_mapping(row)

    def test_fixture_evidence_cannot_pass_live_trial(self) -> None:
        rows = _passing_trial_rows()
        for row in rows:
            row["evidence_kind"] = "fixture"

        report = evaluate_trial_acceptance(rows, readiness_gates_passed=True)

        self.assertEqual(report.status, "blocked")
        self.assertEqual(report.live_task_count, 0)
        self.assertIn("no_live_trial_evidence", _issue_codes(report))

    def test_missing_readiness_gates_returns_blocked(self) -> None:
        report = evaluate_trial_acceptance(_passing_trial_rows(), readiness_gates_passed=False)

        self.assertEqual(report.status, "blocked")
        self.assertIn("readiness_gates_missing", _issue_codes(report))

    def test_full_trial_thresholds_can_pass(self) -> None:
        report = evaluate_trial_acceptance(_passing_trial_rows(), readiness_gates_passed=True)

        self.assertEqual(report.status, "passed")
        self.assertEqual(report.live_task_count, 15)
        self.assertEqual(report.workday_count, 5)
        self.assertEqual(report.category_count, 3)
        self.assertEqual(report.clear_business_output_count, 15)
        self.assertGreaterEqual(report.long_task_success_rate, 0.80)
        self.assertGreaterEqual(report.ordinary_task_success_rate, 0.85)
        self.assertGreaterEqual(report.feedback_capture_rate, 0.60)
        self.assertGreaterEqual(report.positive_feedback_share, 0.60)

    def test_positive_feedback_below_threshold_needs_repair_plan(self) -> None:
        rows = _passing_trial_rows()
        for index, row in enumerate(rows):
            if row["feedback_captured"]:
                row["positive_feedback"] = index < 5

        failed_report = evaluate_trial_acceptance(rows, readiness_gates_passed=True)
        repair_report = evaluate_trial_acceptance(
            rows,
            readiness_gates_passed=True,
            repair_plan_ref="external://trial-repair/planned-positive-feedback",
        )

        self.assertEqual(failed_report.status, "failed")
        self.assertIn("positive_feedback_below_threshold", _issue_codes(failed_report))
        self.assertEqual(repair_report.status, "passed_with_repair_plan")
        self.assertIn("positive_feedback_repair_plan", _issue_codes(repair_report))

    def test_negative_feedback_requires_response_action_within_48_hours(self) -> None:
        rows = _passing_trial_rows()
        rows[0]["positive_feedback"] = False
        rows[0]["negative_feedback"] = True
        rows[0]["response_action_ref"] = None
        rows[0]["response_action_at"] = None
        rows[6]["positive_feedback"] = True

        report = evaluate_trial_acceptance(rows, readiness_gates_passed=True)

        self.assertEqual(report.status, "failed")
        self.assertIn("negative_feedback_response_missing", _issue_codes(report))

    def test_route_mismatch_requires_candidate_evidence(self) -> None:
        rows = _passing_trial_rows()
        rows[2]["route_mismatch"] = True
        rows[2]["skill_candidate_ref"] = None
        rows[2]["routing_rule_candidate_ref"] = None

        report = evaluate_trial_acceptance(rows, readiness_gates_passed=True)

        self.assertEqual(report.status, "failed")
        self.assertIn("route_mismatch_missing_candidate", _issue_codes(report))

    def test_sanitized_summary_formatting_exposes_status_without_rows(self) -> None:
        report = evaluate_trial_acceptance(_passing_trial_rows(), readiness_gates_passed=True)

        assert_trial_acceptance_ready(report)
        json_summary = format_trial_acceptance_summary(report, as_json=True)
        text_summary = format_trial_acceptance_summary(report)
        parsed = json.loads(json_summary)

        self.assertEqual(parsed["status"], "passed")
        self.assertIn('"status"', json_summary)
        self.assertIn("trial_acceptance=passed", text_summary)
        self.assertNotIn("Synthetic legal retrieval request", json_summary)
        self.assertNotIn("trial-task-001", json_summary)

    def test_assert_trial_acceptance_ready_rejects_failed_report(self) -> None:
        rows = _passing_trial_rows()
        rows[0]["success"] = False
        rows[5]["success"] = False

        report = evaluate_trial_acceptance(rows, readiness_gates_passed=True)

        with self.assertRaisesRegex(AssertionError, "trial_acceptance=failed"):
            assert_trial_acceptance_ready(report)


def _trial_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "task_ref": "trial-task-001",
        "evidence_kind": "sanitized_runtime",
        "workday": "2026-06-29",
        "participant_alias": "lawyer-a",
        "category": "contract_review",
        "started_at": "2026-06-29T09:00:00Z",
        "completed_at": "2026-06-29T09:02:00Z",
        "duration_seconds": 120,
        "success": True,
        "clear_business_output": True,
        "feedback_captured": True,
        "positive_feedback": True,
        "negative_feedback": False,
        "route_mismatch": False,
        "response_action_ref": None,
        "response_action_at": None,
        "skill_candidate_ref": None,
        "routing_rule_candidate_ref": None,
        "output_boundary_checked": True,
        "hermes_meta_leak_detected": False,
        "turn_id": "turn-ref-001",
        "conversation_id": "conversation-ref-001",
        "trace_id": "trace-ref-001",
        "result_id": "result-ref-001",
        "feedback_id": "feedback-ref-001",
        "raw_payload_ref": "external://trial-evidence/raw-ref-001",
    }
    row.update(overrides)
    return row


def _passing_trial_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    categories = ("contract_review", "legal_retrieval_qa", "document_drafting")
    workdays = ("2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02", "2026-07-03")
    for index in range(15):
        workday = workdays[index // 3]
        minute = index % 3
        duration_seconds = 120 if index in {0, 5, 10} else 45
        feedback_captured = index < 10
        positive_feedback = index < 6
        rows.append(
            _trial_row(
                task_ref=f"trial-task-{index + 1:03d}",
                workday=workday,
                category=categories[index % len(categories)],
                started_at=f"{workday}T09:{minute * 10:02d}:00Z",
                completed_at=f"{workday}T09:{minute * 10 + 2:02d}:00Z",
                duration_seconds=duration_seconds,
                feedback_captured=feedback_captured,
                positive_feedback=positive_feedback,
                feedback_id=f"feedback-ref-{index + 1:03d}" if feedback_captured else None,
                raw_payload_ref=f"external://trial-evidence/raw-ref-{index + 1:03d}",
            )
        )
    return rows


def _issue_codes(report: object) -> set[str]:
    return {issue.code for issue in getattr(report, "issues")}


if __name__ == "__main__":
    unittest.main()
