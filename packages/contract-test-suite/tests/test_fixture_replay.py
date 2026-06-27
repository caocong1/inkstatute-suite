from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from contract_test_suite.fixture_replay import (
    FixtureReplayError,
    RelationshipIssue,
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
            path.write_text(f"{fixture!r}".replace("'", '"'), encoding="utf-8")

            with self.assertRaisesRegex(
                FixtureReplayError,
                r"malformed\.json.*legal-wecom-contract-review-001.*agent_turn.*turn_id",
            ):
                replay_fixtures([path], schemas=self.schemas)


if __name__ == "__main__":
    unittest.main()
