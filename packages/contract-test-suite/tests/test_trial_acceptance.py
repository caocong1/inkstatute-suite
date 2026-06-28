from __future__ import annotations

import unittest

from contract_test_suite.trial_acceptance import TrialTaskEvidence


class TrialAcceptanceTests(unittest.TestCase):
    def test_raw_payload_key_is_rejected(self) -> None:
        row = _trial_row()
        row["metadata"] = {"raw" + "_payload": "forbidden"}

        with self.assertRaisesRegex(ValueError, "references"):
            TrialTaskEvidence.from_mapping(row)


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


if __name__ == "__main__":
    unittest.main()
