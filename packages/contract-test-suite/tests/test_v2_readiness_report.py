"""Tests for the V2 acceptance readiness report generator.

Tests cover (DOC-02, DOC-05, DOC-07):
  1. Script runs and produces Markdown
  2. All §10.1–10.4 section headers exist
  3. Two-tier status model is present
  4. §13 residual risk classification has all 17 risks
  5. Phase 5 UAT documentation has checklist + criteria
  6. Phase 8 trial documentation has thresholds + template
  7. Human-gate requirements are identified
  8. Determinism (two runs → identical output)
  9. --check flag exits 0 when report is valid
 10-14. Additional structural and content checks
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_v2_readiness_report.py"
REPORT_PATH = REPO_ROOT / ".planning" / "milestones" / "v1.5-V2-ACCEPTANCE-READINESS.md"


def _load_report_module():
    """Load the report generator script as a module via importlib."""
    spec = importlib.util.spec_from_file_location(
        "generate_v2_readiness_report", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load report generator module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_v2_readiness_report"] = module
    spec.loader.exec_module(module)
    return module


class V2ReadinessReportTests(unittest.TestCase):
    """Tests for the V2 acceptance readiness report generator."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the module and generate the report once for all tests."""
        cls.module = _load_report_module()
        # Generate the report to ensure it's fresh
        cls.module.write_report(REPO_ROOT)
        cls.report_text = REPORT_PATH.read_text(encoding="utf-8")

    # --- Test 1: Script runs and produces Markdown ---

    def test_script_runs(self) -> None:
        """main() returns 0 and writes report file."""
        result = self.module.main([])
        self.assertEqual(result, 0)
        self.assertTrue(REPORT_PATH.exists())

    # --- Test 2: Report is Markdown ---

    def test_report_is_markdown(self) -> None:
        """Output starts with '#' and contains markdown headers."""
        self.assertTrue(self.report_text.startswith("#"))
        self.assertIn("## ", self.report_text)
        # Should have multiple section headers
        headers = [line for line in self.report_text.splitlines() if line.startswith("## ")]
        self.assertGreaterEqual(len(headers), 8)

    # --- Test 3-6: Section headers exist ---

    def test_section_10_1_exists(self) -> None:
        """Report contains §10.1 section header."""
        self.assertIn("## §10.1", self.report_text)

    def test_section_10_2_exists(self) -> None:
        """Report contains §10.2 section header."""
        self.assertIn("## §10.2", self.report_text)

    def test_section_10_3_exists(self) -> None:
        """Report contains §10.3 section header."""
        self.assertIn("## §10.3", self.report_text)

    def test_section_10_4_exists(self) -> None:
        """Report contains §10.4 section header."""
        self.assertIn("## §10.4", self.report_text)

    # --- Test 7: §13 residual risk section exists ---

    def test_section_13_exists(self) -> None:
        """Report contains §13 residual risk section."""
        self.assertIn("## §13", self.report_text)

    # --- Test 8: Two-tier status model ---

    def test_two_tier_status(self) -> None:
        """Report contains both 'READY' and 'BLOCKED ON HUMAN GATES'."""
        self.assertIn("READY", self.report_text)
        self.assertIn("BLOCKED ON HUMAN GATES", self.report_text)
        # Verify they are in the executive summary
        exec_section = self.report_text.split("## Executive Summary")[1].split("## §10.1")[0]
        self.assertIn("READY", exec_section)
        self.assertIn("BLOCKED ON HUMAN GATES", exec_section)
        # Verify autonomous closure and V2 acceptance are separate
        self.assertIn("Autonomous Code Closure", exec_section)
        self.assertIn("V2 Acceptance", exec_section)

    # --- Test 9: All 17 §13 residual risks ---

    def test_residual_risks_count(self) -> None:
        """Report contains all 17 §13 risks."""
        # Check that risk numbers 1-17 appear in the §13 section
        section_13 = self.report_text.split("## §13")[1].split("## Phase 5")[0]
        for i in range(1, 18):
            with self.subTest(risk_number=i):
                # Each risk should appear as a table row starting with | i |
                self.assertIn(f"| {i} |", section_13)

    # --- Test 10: Phase 5 UAT section ---

    def test_phase5_uat_section(self) -> None:
        """Report contains Phase 5 UAT checklist + pass/fail criteria."""
        self.assertIn("## Phase 5 Live WeCom UAT Documentation", self.report_text)
        # Operator checklist
        self.assertIn("Operator Checklist", self.report_text)
        self.assertIn("- [ ]", self.report_text)
        # Pass/Fail criteria
        self.assertIn("Pass/Fail Criteria", self.report_text)
        self.assertIn("PASS:", self.report_text)
        self.assertIn("FAIL:", self.report_text)

    # --- Test 11: Phase 8 trial section ---

    def test_phase8_trial_section(self) -> None:
        """Report contains Phase 8 trial thresholds + template reference."""
        self.assertIn("## Phase 8 Five-Workday Lawyer Trial Documentation", self.report_text)
        # Trial protocol
        self.assertIn("Trial Protocol", self.report_text)
        # Thresholds table
        self.assertIn("§10.4 Thresholds Table", self.report_text)
        self.assertIn("≥ 5", self.report_text)
        self.assertIn("≥ 15", self.report_text)
        self.assertIn("≥ 12", self.report_text)
        # Trial-log template reference
        self.assertIn("Trial-Log Template", self.report_text)
        self.assertIn("08-TRIAL-EVIDENCE-TEMPLATE.json", self.report_text)

    # --- Test 12: Determinism ---

    def test_determinism(self) -> None:
        """Two runs produce byte-identical output."""
        # Generate first copy
        text1 = self.module.generate_report(REPO_ROOT)
        # Generate second copy
        text2 = self.module.generate_report(REPO_ROOT)
        self.assertEqual(text1, text2)

    # --- Test 13: --check flag ---

    def test_check_flag(self) -> None:
        """--check exits 0 when report exists and is valid."""
        # First ensure report exists
        self.module.write_report(REPO_ROOT)
        # Run --check via subprocess to verify exit code
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"--check failed: {result.stderr}")
        self.assertIn("OK", result.stdout)

    # --- Test 14: Human-gate identified ---

    def test_human_gate_identified(self) -> None:
        """Report identifies TRIAL-01 as human gate."""
        self.assertIn("TRIAL-01", self.report_text)
        self.assertIn("human gate", self.report_text.lower())
        # Verify TRIAL-01 is mentioned in the §10.4 section
        section_10_4 = self.report_text.split("## §10.4")[1].split("## §13")[0]
        self.assertIn("TRIAL-01", section_10_4)


if __name__ == "__main__":
    unittest.main()
