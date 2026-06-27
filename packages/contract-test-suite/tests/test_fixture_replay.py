from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from contract_test_suite.fixture_replay import (
    FixtureReplayError,
    ReplayReport,
    assert_relationship_integrity,
    load_fixture_paths,
    load_fixtures_from_paths,
    replay_fixtures,
)
from contract_test_suite.paths import PLATFORM_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_contract_fixtures, load_schemas


class FixtureReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixtures = load_contract_fixtures()

    def test_load_fixture_paths_defaults_to_phase_one_fixtures(self) -> None:
        paths = load_fixture_paths()

        self.assertEqual(
            [path.name for path in paths],
            [
                "legal_wecom_contract_review.json",
                "non_legal_engineering_task.json",
            ],
        )
        self.assertTrue(all(path.parent == PLATFORM_FIXTURE_ROOT for path in paths))

    def test_load_fixtures_from_explicit_paths_preserves_path_context(self) -> None:
        paths = load_fixture_paths()

        loaded = load_fixtures_from_paths(paths)

        self.assertEqual(
            [item.fixture["fixture_id"] for item in loaded],
            ["legal-wecom-contract-review-001", "non-legal-engineering-task-001"],
        )
        self.assertEqual([item.path for item in loaded], paths)

    def test_successful_replay_returns_zero_breakage_report(self) -> None:
        report = replay_fixtures(schemas=self.schemas)

        self.assertIsInstance(report, ReplayReport)
        self.assertEqual(report.fixture_count, 2)
        self.assertGreater(report.relationship_check_count, 0)
        self.assertEqual(report.broken_relationship_count, 0)
        self.assertEqual(report.breakage_rate, 0.0)
        self.assertEqual(report.issues, [])

    def test_malformed_fixture_reports_path_and_schema_context(self) -> None:
        fixture = copy.deepcopy(self.fixtures[0])
        del fixture["events"]["agent_turn"]["turn_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "malformed.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")

            with self.assertRaisesRegex(
                FixtureReplayError,
                r"malformed\.json.*legal-wecom-contract-review-001.*agent_turn.*turn_id",
            ):
                replay_fixtures([path], schemas=self.schemas)

    def test_relationship_breaks_fail_with_fixture_name_expected_and_actual(self) -> None:
        cases = (
            (
                "turn_id",
                ("events", "agent_result", "turn_id"),
                "turn-broken",
                r"agent_result.turn_id.*expected='turn-lawfirm-001'.*actual='turn-broken'",
            ),
            (
                "feedback_result_id",
                ("events", "feedback_event", "result_id"),
                "result-broken",
                r"feedback_event.result_id.*expected='result-lawfirm-001'.*actual='result-broken'",
            ),
            (
                "feedback_target",
                ("events", "feedback_event", "feedback_target"),
                "feedback-target-broken",
                r"feedback_event.feedback_target.*expected='feedback-target-lawfirm-001'.*actual='feedback-target-broken'",
            ),
            (
                "route_decision",
                ("events", "feedback_event", "related_route_decision"),
                "route-broken",
                r"feedback_event.related_route_decision.*expected='route-lawfirm-001'.*actual='route-broken'",
            ),
            (
                "trace_id",
                ("events", "agent_result", "metadata", "trace_id"),
                "trace-broken",
                r"agent_result.metadata.trace_id.*expected='trace-lawfirm-001'.*actual='trace-broken'",
            ),
            (
                "artifact_id",
                ("events", "agent_result", "artifacts", 0, "artifact_id"),
                "artifact-broken",
                r"agent_result.artifacts\[0\].artifact_id.*expected=.*artifact-broken.*actual=.*artifact-lawfirm-trackchanges-001",
            ),
        )

        for relationship, path, replacement, expected_message in cases:
            with self.subTest(relationship=relationship):
                fixture = copy.deepcopy(self.fixtures[0])
                self._set_path(fixture, path, replacement)

                with self.assertRaisesRegex(
                    AssertionError,
                    rf"legal-wecom-contract-review-001.*{relationship}.*{expected_message}",
                ):
                    self._assert_single_fixture_integrity(fixture)

    def test_unreferenced_execution_trace_artifact_fails_relationship_integrity(self) -> None:
        fixture = copy.deepcopy(self.fixtures[0])
        fixture["events"]["execution_trace"]["artifacts_written"].append("artifact-unreferenced")

        with self.assertRaisesRegex(
            AssertionError,
            r"artifact_written.*execution_trace\.artifacts_written.*expected='artifact-unreferenced'.*actual=.*artifact-lawfirm-trackchanges-001",
        ):
            self._assert_single_fixture_integrity(fixture)

    def test_replay_calculates_breakage_rate_and_enforces_five_percent_tolerance(self) -> None:
        fixture = copy.deepcopy(self.fixtures[0])
        fixture["events"]["feedback_event"]["result_id"] = "result-broken"

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "broken.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")

            report = replay_fixtures([path], schemas=self.schemas)

            self.assertEqual(report.fixture_count, 1)
            self.assertGreater(report.relationship_check_count, 1)
            self.assertEqual(report.broken_relationship_count, 1)
            self.assertGreater(report.breakage_rate, 0.05)
            self.assertEqual(report.issues[0].relationship, "feedback_result_id")

            with self.assertRaisesRegex(AssertionError, r"breakage rate.*5\.00%"):
                assert_relationship_integrity([path], schemas=self.schemas)

            assert_relationship_integrity([path], max_breakage_rate=1.0, schemas=self.schemas)

    def _assert_single_fixture_integrity(self, fixture: dict) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "broken.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            assert_relationship_integrity([path], schemas=self.schemas)

    @staticmethod
    def _set_path(value: dict, path: tuple[str | int, ...], replacement: object) -> None:
        target = value
        for segment in path[:-1]:
            target = target[segment]
        target[path[-1]] = replacement


if __name__ == "__main__":
    unittest.main()
