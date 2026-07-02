"""Contract tests for Phase 24 memory evaluation harness and privacy gates fixture."""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE24_FIXTURE = LOCAL_FIXTURE_ROOT / "phase24_memory_evaluation_harness_privacy_gates.json"

RAW_PAYLOAD_KEYS = {
    "raw_payload",
    "raw_text",
    "payload_text",
    "full_text",
    "document_text",
    "customer_document_text",
    "case_facts",
    "callback_body",
}

FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN"),
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"secret\s*[:=]", re.IGNORECASE),
    re.compile(r"token\s*[:=]", re.IGNORECASE),
    re.compile(r"/home/[^\s]+"),
    re.compile(r"\bgateway\b", re.IGNORECASE),
    re.compile(r"(^|\s)/(new|resume|help|status|memory)\b", re.IGNORECASE),
)


class Phase24MemoryEvalHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE24_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_id_and_schema_validation(self) -> None:
        """Fixture has expected id and passes validate_event_bundle."""
        self.assertEqual(
            self.fixture["fixture_id"],
            "phase24-memory-evaluation-harness-privacy-gates-001",
        )
        validate_event_bundle(self.fixture, self.schemas)

    def test_eval_harness_evidence_documents_all_eval_requirements(self) -> None:
        """eval_harness_evidence must document all EVAL-01..EVAL-04."""
        evidence = self.fixture["metadata"]["eval_harness_evidence"]

        self.assertTrue(evidence["eval_01_all_six_scenarios_covered"])                        # EVAL-01
        self.assertTrue(evidence["eval_02_relevance_source_traceability_deletion_correctness_privacy_per_scenario"])  # EVAL-02
        self.assertTrue(evidence["eval_03_hard_gate_enforced_cross_tenant_privacy_deletion_false_recall"])  # EVAL-03
        self.assertTrue(evidence["eval_04_baseline_score_established_for_native_path"])       # EVAL-04
        self.assertAlmostEqual(evidence["baseline_score"], 1.0)
        self.assertTrue(evidence["all_scenarios_passed"])
        self.assertTrue(evidence["no_raw_text_in_eval_fixtures"])

    def test_all_six_scenario_results_present(self) -> None:
        """EVAL-01: eval_results must cover all six canonical scenarios."""
        results = self.fixture["metadata"]["eval_results"]
        scenario_names = {r["scenario"] for r in results}

        expected = {
            "multi_turn_recall",
            "cross_session_continuity",
            "deletion_and_export",
            "tenant_isolation",
            "feedback_learning_integration",
            "false_recall_rejection",
        }
        self.assertEqual(scenario_names, expected)

    def test_all_scenario_results_have_required_eval02_fields(self) -> None:
        """EVAL-02: each scenario result must carry relevance, traceability, deletion, privacy."""
        for r in self.fixture["metadata"]["eval_results"]:
            with self.subTest(scenario=r["scenario"]):
                self.assertIn("relevance_score", r)
                self.assertIn("source_traceability", r)
                self.assertIn("deletion_correctness", r)
                self.assertIn("privacy_passed", r)
                self.assertIn("cross_tenant_leaked", r)

    def test_all_scenarios_pass_and_privacy_gates_green(self) -> None:
        """EVAL-01/03: all scenarios must pass; no cross-tenant leaks or privacy failures."""
        for r in self.fixture["metadata"]["eval_results"]:
            with self.subTest(scenario=r["scenario"]):
                self.assertTrue(r["passed"])
                self.assertFalse(r["cross_tenant_leaked"])
                self.assertTrue(r["privacy_passed"])

    def test_hard_gate_definitions_cover_all_four_gates(self) -> None:
        """EVAL-03: hard gate definitions must cover the four critical failure modes."""
        gates = self.fixture["metadata"]["hard_gate_definitions"]

        self.assertIn("cross_tenant_leak", gates)
        self.assertIn("privacy_failure", gates)
        self.assertIn("deletion_correctness_failure", gates)
        self.assertIn("false_recall_failure", gates)

    def test_baseline_score_established_for_native_path(self) -> None:
        """EVAL-04: baseline_score of 1.0 establishes the native path benchmark."""
        score = self.fixture["metadata"]["eval_harness_evidence"]["baseline_score"]
        self.assertAlmostEqual(score, 1.0)

    def test_execution_trace_records_scenarios_run_and_baseline(self) -> None:
        """EVAL-02/04: trace metadata must record scenarios_run and baseline_score."""
        trace_meta = self.fixture["events"]["execution_trace"]["metadata"]

        self.assertEqual(trace_meta["scenarios_run"], 6)
        self.assertAlmostEqual(trace_meta["baseline_score"], 1.0)
        self.assertEqual(trace_meta["hard_gate_failures"], [])

    def test_fixture_is_privacy_safe(self) -> None:
        """No forbidden raw payload keys or secret-like values at any level."""
        for object_path, value in iter_mapping_values(self.fixture):
            with self.subTest(path=object_path):
                forbidden = RAW_PAYLOAD_KEYS & set(value)
                self.assertEqual(forbidden, set(), f"{object_path}: forbidden keys {forbidden}")

        for text_path, value in iter_string_values(self.fixture):
            with self.subTest(path=text_path):
                for pattern in FORBIDDEN_TEXT_PATTERNS:
                    self.assertIsNone(
                        pattern.search(value),
                        f"{text_path} matched forbidden pattern {pattern.pattern!r}",
                    )

    def test_verification_commands_cover_all_required_test_files(self) -> None:
        commands = self.fixture["metadata"]["verification_commands"]

        self.assertTrue(any("test_memory_eval.py" in cmd for cmd in commands))
        self.assertTrue(any("test_phase24_memory_evaluation_harness_privacy_gates.py" in cmd for cmd in commands))
        self.assertTrue(any("test_schema_validation.py" in cmd for cmd in commands))


def iter_mapping_values(value: Any, path: str = "$") -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        yield path, value
        for key, item in value.items():
            yield from iter_mapping_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_mapping_values(item, f"{path}[{index}]")


def iter_string_values(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield from iter_string_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_string_values(item, f"{path}[{index}]")


if __name__ == "__main__":
    unittest.main()
