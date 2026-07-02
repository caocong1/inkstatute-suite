"""Tests for Phase 24: memory evaluation harness and privacy gates."""

from __future__ import annotations

import unittest

from platform_runtime import (
    MemoryEvalGateError,
    MemoryEvalReport,
    MemoryEvalResult,
    MemoryEvalRunner,
)
from platform_runtime.memory_eval import (
    FIXED_EVAL_TENANT_A,
    FIXED_EVAL_TENANT_B,
    FIXED_EVAL_WORKSPACE,
    FIXED_EVAL_USER,
    FIXED_EVAL_SESSION_A,
    _collect_hard_gate_failures,
    _synthetic_record,
)

FIXED_NOW = "2026-07-02T16:00:00+00:00"


def make_runner(**kwargs: object) -> MemoryEvalRunner:
    return MemoryEvalRunner(clock=lambda: FIXED_NOW, **kwargs)  # type: ignore[arg-type]


class MemoryEvalRunnerSmokeTests(unittest.TestCase):
    def test_run_returns_report_with_all_six_scenarios(self) -> None:
        """EVAL-01: run() returns exactly 6 scenario results."""
        runner = make_runner()
        report = runner.run()

        scenario_names = {r.scenario for r in report.results}
        self.assertEqual(len(report.results), 6)
        expected = {
            "multi_turn_recall",
            "cross_session_continuity",
            "deletion_and_export",
            "tenant_isolation",
            "feedback_learning_integration",
            "false_recall_rejection",
        }
        self.assertEqual(scenario_names, expected)

    def test_run_is_deterministic(self) -> None:
        """EVAL-04: two runs with the same clock produce the same baseline_score."""
        runner1 = make_runner()
        runner2 = make_runner()

        report1 = runner1.run()
        report2 = runner2.run()

        self.assertAlmostEqual(report1.baseline_score, report2.baseline_score)
        for r1, r2 in zip(report1.results, report2.results):
            self.assertEqual(r1.scenario, r2.scenario)
            self.assertEqual(r1.passed, r2.passed)


class MemoryEvalScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = make_runner()
        self.report = self.runner.run()

    def _result(self, scenario: str) -> MemoryEvalResult:
        for r in self.report.results:
            if r.scenario == scenario:
                return r
        self.fail(f"Scenario '{scenario}' not found in report")

    def test_multi_turn_recall_passes(self) -> None:
        """EVAL-01: multi_turn_recall correctly recalls all 3 records."""
        r = self._result("multi_turn_recall")
        self.assertTrue(r.passed, msg=f"multi_turn_recall: {r.notes}")

    def test_cross_session_continuity_passes(self) -> None:
        """EVAL-01: user-scoped records are recalled across sessions."""
        r = self._result("cross_session_continuity")
        self.assertTrue(r.passed, msg=f"cross_session_continuity: {r.notes}")

    def test_deletion_correctness_passes(self) -> None:
        """EVAL-01: deleted records are not recalled."""
        r = self._result("deletion_and_export")
        self.assertTrue(r.passed, msg=f"deletion_and_export: {r.notes}")
        self.assertTrue(r.deletion_correctness)

    def test_tenant_isolation_passes(self) -> None:
        """EVAL-01: cross-tenant queries return no results."""
        r = self._result("tenant_isolation")
        self.assertTrue(r.passed, msg=f"tenant_isolation: {r.notes}")
        self.assertFalse(r.cross_tenant_leaked)

    def test_feedback_learning_integration_passes(self) -> None:
        """EVAL-01: feedback-promoted candidates are recalled after approval."""
        r = self._result("feedback_learning_integration")
        self.assertTrue(r.passed, msg=f"feedback_learning_integration: {r.notes}")

    def test_false_recall_rejection_passes(self) -> None:
        """EVAL-01: session-scoped records are not recalled for the wrong session."""
        r = self._result("false_recall_rejection")
        self.assertTrue(r.passed, msg=f"false_recall_rejection: {r.notes}")


class MemoryEvalReportTests(unittest.TestCase):
    def test_all_results_have_source_traceability(self) -> None:
        """EVAL-02: all scenarios report source_traceability=True."""
        runner = make_runner()
        report = runner.run()

        for r in report.results:
            with self.subTest(scenario=r.scenario):
                self.assertTrue(r.source_traceability, f"{r.scenario}: source_traceability=False")

    def test_privacy_passed_for_all_scenarios(self) -> None:
        """EVAL-02: all scenarios report privacy_passed=True."""
        runner = make_runner()
        report = runner.run()

        for r in report.results:
            with self.subTest(scenario=r.scenario):
                self.assertTrue(r.privacy_passed, f"{r.scenario}: privacy_passed=False")

    def test_assert_gates_passes_when_all_green(self) -> None:
        """EVAL-03: assert_gates() does not raise when all scenarios pass."""
        runner = make_runner()
        report = runner.run()

        # Should not raise
        report.assert_gates()

    def test_assert_gates_raises_on_cross_tenant_leak(self) -> None:
        """EVAL-03: assert_gates() raises MemoryEvalGateError on cross-tenant leak."""
        bad_result = MemoryEvalResult(
            scenario="tenant_isolation",
            passed=False,
            relevance_score=0.0,
            source_traceability=True,
            deletion_correctness=True,
            privacy_passed=True,
            cross_tenant_leaked=True,
            notes="forced cross-tenant leak for gate test",
        )
        report = MemoryEvalReport(
            results=(bad_result,),
            baseline_score=0.0,
            hard_gate_failures=tuple(_collect_hard_gate_failures([bad_result])),
        )
        with self.assertRaisesRegex(MemoryEvalGateError, "cross-tenant leak"):
            report.assert_gates()

    def test_assert_gates_raises_on_privacy_failure(self) -> None:
        """EVAL-03: assert_gates() raises MemoryEvalGateError when privacy gate fails."""
        bad_result = MemoryEvalResult(
            scenario="multi_turn_recall",
            passed=True,
            relevance_score=1.0,
            source_traceability=True,
            deletion_correctness=True,
            privacy_passed=False,
            cross_tenant_leaked=False,
            notes="forced privacy fail for gate test",
        )
        report = MemoryEvalReport(
            results=(bad_result,),
            baseline_score=1.0,
            hard_gate_failures=tuple(_collect_hard_gate_failures([bad_result])),
        )
        with self.assertRaisesRegex(MemoryEvalGateError, "privacy gate failure"):
            report.assert_gates()

    def test_baseline_score_is_perfect_on_clean_run(self) -> None:
        """EVAL-04: baseline_score is 1.0 when all scenarios pass."""
        runner = make_runner()
        report = runner.run()

        self.assertAlmostEqual(report.baseline_score, 1.0)

    def test_baseline_score_computes_pass_rate(self) -> None:
        """MemoryEvalReport.compute_baseline returns correct pass rate."""
        results = [
            MemoryEvalResult("a", True, 1.0, True, True, True, False),
            MemoryEvalResult("b", True, 1.0, True, True, True, False),
            MemoryEvalResult("c", False, 0.0, True, True, True, False),
        ]
        score = MemoryEvalReport.compute_baseline(results)
        self.assertAlmostEqual(score, 2 / 3)


if __name__ == "__main__":
    unittest.main()
