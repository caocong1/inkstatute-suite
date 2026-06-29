from __future__ import annotations

import json
import unittest
from pathlib import Path

from contract_test_suite.privacy_scan import assert_privacy_clean
from inkstatute_backends_hermes.parity import evaluate_parity_cases, iter_case_observations, load_parity_cases


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "packages/backends/hermes/fixtures/parity_cases.json"
REQUIRED_CASES = {"legal_qa", "drafting_artifact", "follow_up", "route_mismatch", "mcp_tool_task", "non_legal"}


class Phase11HermesParityContractTests(unittest.TestCase):
    def test_fixture_has_required_case_coverage_and_not_live_metadata(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cases = load_parity_cases(FIXTURE_PATH)

        self.assertEqual({case.case_id for case in cases}, REQUIRED_CASES)
        self.assertTrue(fixture["metadata"]["not_live_acceptance"])
        for case in fixture["cases"]:
            self.assertTrue(case["metadata"]["not_live_acceptance"])

    def test_fixture_policy_is_sanitized_and_hash_only(self) -> None:
        cases = load_parity_cases(FIXTURE_PATH)

        assert_privacy_clean([FIXTURE_PATH], mode="data")
        for observation in iter_case_observations(cases):
            self.assertIn("visible_text_hash", observation)
            self.assertNotIn("visible_text", observation)

    def test_report_blocks_promotion_when_required_parity_fails(self) -> None:
        report = evaluate_parity_cases(load_parity_cases(FIXTURE_PATH))

        self.assertFalse(report.promote_api_runs)
        self.assertEqual(report.default_lane, "oneshot")
        self.assertTrue(any(not result.passed for result in report.dimension_results))
        self.assertTrue(report.metadata["not_live_acceptance"])


if __name__ == "__main__":
    unittest.main()
