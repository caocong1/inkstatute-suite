"""Tests for GAP-08 composability coverage report and GAP-09 output boundary evidence summary."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contract_test_suite.boundary_checks import (
    OUTPUT_BOUNDARY_CATEGORIES,
    build_output_boundary_evidence_summary,
)
from contract_test_suite.coverage_report import (
    SYNTHETIC_TASK_TYPES,
    build_composability_coverage_report,
)
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT, REPO_ROOT


class ComposabilityCoverageReportTests(unittest.TestCase):
    """Tests for GAP-08: build_composability_coverage_report()."""

    def test_composability_coverage_all_7_task_types(self) -> None:
        """Report has exactly 7 entries — one per §10.3 synthetic task type."""
        report = build_composability_coverage_report(repo_root=REPO_ROOT)

        self.assertEqual(len(report.entries), 7)

    def test_composability_coverage_all_covered(self) -> None:
        """All 7 task types are covered — all_covered=True, missing_count=0."""
        report = build_composability_coverage_report(repo_root=REPO_ROOT)

        self.assertTrue(report.all_covered)
        self.assertEqual(report.missing_count, 0)
        self.assertEqual(report.covered_count, 7)

    def test_composability_coverage_fixtures_exist(self) -> None:
        """Every listed fixture path exists on disk and is non-empty."""
        report = build_composability_coverage_report(repo_root=REPO_ROOT)

        for entry in report.entries:
            with self.subTest(task_type=entry.task_type):
                self.assertTrue(entry.covered, f"{entry.task_type} is not covered")
                self.assertGreater(len(entry.fixtures), 0)
                for fixture_path in entry.fixtures:
                    abs_path = REPO_ROOT / fixture_path
                    self.assertTrue(abs_path.exists(), f"Missing fixture: {fixture_path}")
                    self.assertGreater(abs_path.stat().st_size, 0, f"Empty fixture: {fixture_path}")

    def test_composability_coverage_non_legal_has_3_domains(self) -> None:
        """non_legal_synthetic entry lists finance_tax, engineering, and education fixtures."""
        report = build_composability_coverage_report(repo_root=REPO_ROOT)

        non_legal = next(
            e for e in report.entries if e.task_type == "non_legal_synthetic"
        )
        fixture_str = " ".join(non_legal.fixtures)
        self.assertIn("finance_tax", fixture_str)
        self.assertIn("engineering", fixture_str)
        self.assertIn("education", fixture_str)
        self.assertGreaterEqual(len(non_legal.fixtures), 3)

    def test_composability_coverage_report_serializes_to_json(self) -> None:
        """to_dict() produces valid JSON with expected structure."""
        report = build_composability_coverage_report(repo_root=REPO_ROOT)

        data = report.to_dict()
        serialized = json.dumps(data, indent=2, sort_keys=True)
        parsed = json.loads(serialized)

        self.assertIn("entries", parsed)
        self.assertIn("covered_count", parsed)
        self.assertIn("missing_count", parsed)
        self.assertIn("all_covered", parsed)
        self.assertEqual(len(parsed["entries"]), 7)
        for entry in parsed["entries"]:
            self.assertIn("task_type", entry)
            self.assertIn("prd_label", entry)
            self.assertIn("covered", entry)
            self.assertIn("fixtures", entry)
            self.assertIn("evidence", entry)

    def test_composability_coverage_synthetic_task_types_match_registry(self) -> None:
        """SYNTHETIC_TASK_TYPES registry has 7 entries with non-empty fixture paths."""
        self.assertEqual(len(SYNTHETIC_TASK_TYPES), 7)
        for task_type, prd_label, fixture_paths, evidence in SYNTHETIC_TASK_TYPES:
            with self.subTest(task_type=task_type):
                self.assertTrue(task_type)
                self.assertTrue(prd_label)
                self.assertGreater(len(fixture_paths), 0)
                self.assertTrue(evidence)


class OutputBoundaryEvidenceReportTests(unittest.TestCase):
    """Tests for GAP-09: build_output_boundary_evidence_summary()."""

    def test_output_boundary_all_4_categories_covered(self) -> None:
        """Report has entries for gateway, update, command, and meta."""
        report = build_output_boundary_evidence_summary(repo_root=REPO_ROOT)

        categories = {entry.category for entry in report.entries}
        self.assertEqual(categories, {"gateway", "update", "command", "meta"})
        self.assertTrue(report.all_categories_covered)
        self.assertEqual(len(report.entries), 4)

    def test_output_boundary_all_categories_block_or_rewrite(self) -> None:
        """Every entry action is 'block' or 'rewrite'."""
        report = build_output_boundary_evidence_summary(repo_root=REPO_ROOT)

        for entry in report.entries:
            with self.subTest(category=entry.category):
                self.assertIn(entry.action, {"block", "rewrite"})

    def test_output_boundary_no_visible_backend_terms(self) -> None:
        """No backend terms in visible text — no_visible_backend_terms=True."""
        report = build_output_boundary_evidence_summary(repo_root=REPO_ROOT)

        self.assertTrue(report.no_visible_backend_terms)

    def test_output_boundary_missing_category_detected(self) -> None:
        """Removing meta and command cases causes all_categories_covered=False."""
        fixture_path = LOCAL_FIXTURE_ROOT / "phase55_output_policy_cases.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as tmpdir:
            # Remove both meta-matching cases to ensure the meta category is
            # truly uncovered. block-command-debug-stack matches both command
            # and meta keywords, so both must be removed to make meta missing.
            modified_cases = [
                c for c in fixture["cases"]
                if c["id"] not in ("block-meta-tool-progress", "block-command-debug-stack")
            ]
            modified_fixture = {
                "fixture_id": fixture["fixture_id"],
                "cases": modified_cases,
            }
            modified_path = Path(tmpdir) / "modified_cases.json"
            modified_path.write_text(
                json.dumps(modified_fixture, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            report = build_output_boundary_evidence_summary(
                fixture_path=modified_path, repo_root=REPO_ROOT
            )

            self.assertFalse(report.all_categories_covered)
            self.assertIn("meta", report.missing_categories)
            self.assertIn("command", report.missing_categories)

    def test_output_boundary_report_serializes_to_json(self) -> None:
        """to_dict() produces valid JSON with expected structure."""
        report = build_output_boundary_evidence_summary(repo_root=REPO_ROOT)

        data = report.to_dict()
        serialized = json.dumps(data, indent=2, sort_keys=True)
        parsed = json.loads(serialized)

        self.assertIn("entries", parsed)
        self.assertIn("all_categories_covered", parsed)
        self.assertIn("missing_categories", parsed)
        self.assertIn("no_visible_backend_terms", parsed)
        for entry in parsed["entries"]:
            self.assertIn("category", entry)
            self.assertIn("action", entry)
            self.assertIn("fixture_case_id", entry)
            self.assertIn("proof", entry)

    def test_output_boundary_fixture_has_5_cases(self) -> None:
        """Fixture has exactly 5 cases after gap closure."""
        fixture_path = LOCAL_FIXTURE_ROOT / "phase55_output_policy_cases.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertEqual(len(fixture["cases"]), 5)

    def test_output_boundary_fixture_covers_all_4_categories(self) -> None:
        """Fixture cases map to all 4 §10.2 categories via keyword classification."""
        fixture_path = LOCAL_FIXTURE_ROOT / "phase55_output_policy_cases.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        covered_categories: set[str] = set()
        for case in fixture["cases"]:
            input_text = str(case.get("input", "")).lower()
            expected_action = str(case.get("expected_action", ""))
            if expected_action not in ("block", "rewrite"):
                continue
            for category, keywords in OUTPUT_BOUNDARY_CATEGORIES:
                if any(kw in input_text for kw in keywords):
                    covered_categories.add(category)

        self.assertEqual(covered_categories, {"gateway", "update", "command", "meta"})

    def test_output_boundary_categories_registry_has_4(self) -> None:
        """OUTPUT_BOUNDARY_CATEGORIES registry has exactly 4 categories."""
        self.assertEqual(len(OUTPUT_BOUNDARY_CATEGORIES), 4)
        categories = {cat for cat, _ in OUTPUT_BOUNDARY_CATEGORIES}
        self.assertEqual(categories, {"gateway", "update", "command", "meta"})

    def test_output_boundary_gateway_is_rewrite(self) -> None:
        """Gateway category uses 'rewrite' action (backend lifecycle notice)."""
        report = build_output_boundary_evidence_summary(repo_root=REPO_ROOT)

        gateway_entry = next(e for e in report.entries if e.category == "gateway")
        self.assertEqual(gateway_entry.action, "rewrite")
        self.assertEqual(gateway_entry.fixture_case_id, "rewrite-gateway-lifecycle")

    def test_output_boundary_update_is_block(self) -> None:
        """Update category uses 'block' action (self-update notice)."""
        report = build_output_boundary_evidence_summary(repo_root=REPO_ROOT)

        update_entry = next(e for e in report.entries if e.category == "update")
        self.assertEqual(update_entry.action, "block")
        self.assertEqual(update_entry.fixture_case_id, "block-self-update-notice")

    def test_output_boundary_meta_uses_dedicated_case(self) -> None:
        """Meta category is assigned to the dedicated block-meta-tool-progress case."""
        report = build_output_boundary_evidence_summary(repo_root=REPO_ROOT)

        meta_entry = next(e for e in report.entries if e.category == "meta")
        self.assertEqual(meta_entry.action, "block")
        self.assertEqual(meta_entry.fixture_case_id, "block-meta-tool-progress")


if __name__ == "__main__":
    unittest.main()
