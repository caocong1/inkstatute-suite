from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

from inkstatute_backends_hermes.parity import (
    DIMENSION_FIELDS,
    ParityCase,
    evaluate_parity_cases,
    iter_case_observations,
    load_parity_cases,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "packages" / "contract-test-suite" / "src"))

from contract_test_suite.privacy_scan import assert_privacy_clean

FIXTURE_PATH = REPO_ROOT / "packages/backends/hermes/fixtures/parity_cases.json"
REQUIRED_CASES = {"legal_qa", "drafting_artifact", "follow_up", "route_mismatch", "mcp_tool_task", "non_legal"}


class HermesParityReportTests(unittest.TestCase):
    def test_loads_exact_six_sanitized_cases(self) -> None:
        cases = load_parity_cases(FIXTURE_PATH)

        self.assertEqual({case.case_id for case in cases}, REQUIRED_CASES)
        self.assertEqual(len(cases), 6)
        for case in cases:
            self.assertTrue(case.metadata["not_live_acceptance"])
            self.assertEqual(set(case.required_dimensions), set(DIMENSION_FIELDS))

    def test_fixture_observations_use_hashes_not_visible_text(self) -> None:
        cases = load_parity_cases(FIXTURE_PATH)

        for observation in iter_case_observations(cases):
            self.assertIn("visible_text_hash", observation)
            self.assertNotIn("visible_text", observation)

    def test_failed_fixture_parity_keeps_oneshot_default(self) -> None:
        report = evaluate_parity_cases(load_parity_cases(FIXTURE_PATH))

        self.assertFalse(report.promote_api_runs)
        self.assertEqual(report.default_lane, "oneshot")
        self.assertTrue(
            any(
                result.case_id == "route_mismatch"
                and result.dimension in {"route", "skills_gates", "state_transitions"}
                and not result.passed
                for result in report.dimension_results
            )
        )

    def test_passing_synthetic_parity_is_representable_without_mutating_defaults(self) -> None:
        case = ParityCase(
            case_id="synthetic_pass",
            input_ref="fixture://phase11/inputs/synthetic_pass",
            required_dimensions=list(DIMENSION_FIELDS),
            one_shot_observation=_matching_observation(),
            api_runs_observation=_matching_observation(),
            metadata={"not_live_acceptance": True},
        )

        report = evaluate_parity_cases([case])

        self.assertTrue(report.promote_api_runs)
        self.assertEqual(report.default_lane, "oneshot")

    def test_mismatch_or_missing_dimension_blocks_promotion(self) -> None:
        case = ParityCase(
            case_id="synthetic_mismatch",
            input_ref="fixture://phase11/inputs/synthetic_mismatch",
            required_dimensions=list(DIMENSION_FIELDS),
            one_shot_observation=_matching_observation(),
            api_runs_observation={**_matching_observation(), "route_id": "route://other"},
            metadata={"not_live_acceptance": True},
        )
        missing = copy.deepcopy(case.api_runs_observation)
        del missing["visible_text_hash"]
        missing_case = ParityCase(
            case_id="synthetic_missing",
            input_ref="fixture://phase11/inputs/synthetic_missing",
            required_dimensions=list(DIMENSION_FIELDS),
            one_shot_observation=_matching_observation(),
            api_runs_observation=missing,
            metadata={"not_live_acceptance": True},
        )

        mismatch_report = evaluate_parity_cases([case])
        missing_report = evaluate_parity_cases([missing_case])

        self.assertFalse(mismatch_report.promote_api_runs)
        self.assertFalse(missing_report.promote_api_runs)

    def test_fixture_privacy_scan_and_forbidden_markers(self) -> None:
        text = FIXTURE_PATH.read_text(encoding="utf-8")
        fixture = json.loads(text)

        assert_privacy_clean([FIXTURE_PATH], mode="data")
        for marker in ("transcript", "token=", "access_token", "customer", "/.hermes/", "feedback.jsonl", "logs"):
            self.assertNotIn(marker, text)
        self.assertEqual(fixture["metadata"]["raw_payload_policy"], "refs_and_hashes_only")
        self.assertTrue(fixture["metadata"]["not_live_acceptance"])


def _matching_observation() -> dict[str, object]:
    return {
        "route_id": "route://synthetic/match",
        "skill_refs": ["skill://synthetic/match"],
        "gate_refs": ["gate://policy/output-boundary"],
        "tool_trace_refs": ["trace://tool/match"],
        "artifact_refs": ["artifact://synthetic/match"],
        "state_sequence": ["queued", "running", "succeeded"],
        "output_policy_action": "allow",
        "visible_text_hash": "0" * 64,
        "feedback_target_ref": "feedback://synthetic/match",
        "summary_ref": "summary://synthetic/match",
    }


if __name__ == "__main__":
    unittest.main()
