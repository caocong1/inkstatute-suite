from __future__ import annotations

import hashlib
import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE16_FIXTURE = LOCAL_FIXTURE_ROOT / "phase16_short_term_context_assembler.json"
RAW_PAYLOAD_KEYS = {
    "raw_payload",
    "raw_text",
    "payload_text",
    "full_text",
    "document_text",
    "customer_document_text",
    "case_facts",
}
FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN"),
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"secret\s*[:=]", re.IGNORECASE),
    re.compile(r"token\s*[:=]", re.IGNORECASE),
    re.compile(r"/home/[^\s]+"),
    re.compile(r"\bhermes\b", re.IGNORECASE),
    re.compile(r"\bgateway\b", re.IGNORECASE),
    re.compile(r"\badmin\b", re.IGNORECASE),
    re.compile(r"\bdebug\b", re.IGNORECASE),
    re.compile(r"(^|\s)/(new|resume|help|status|debug|memory)\b", re.IGNORECASE),
)


class Phase16ShortTermContextAssemblerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE16_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_validates_with_existing_bundle_validator(self) -> None:
        self.assertEqual(self.fixture["fixture_id"], "phase16-short-term-context-assembler-001")
        validate_event_bundle(self.fixture, self.schemas)

    def test_stm01_context_bundle_contains_high_signal_source_refs(self) -> None:
        bundle = self.fixture["events"]["context_bundle"]
        metadata = bundle["metadata"]

        self.assertEqual(bundle["turn_id"], self.fixture["events"]["agent_turn"]["turn_id"])
        self.assertEqual(metadata["current_turn_ref"], "fixture://phase16/turns/turn-phase16-current-001")
        self.assertGreaterEqual(len(bundle["recent_turn_refs"]), 1)
        self.assertEqual(bundle["summary_ref"], "summary://phase16/session-phase16-001/rolling-summary-004")
        self.assertEqual(bundle["active_task_refs"], ["runtime://phase16/tasks/active-task-001"])
        self.assertEqual(bundle["artifact_refs"], ["artifact://phase16/artifacts/context-evidence-001"])
        self.assertEqual(metadata["feedback_corrections"][0]["feedback_correction_ref"], "fixture://phase16/feedback/feedback-phase16-correction-001")
        self.assertEqual(metadata["pending_clarification_ref"], "runtime://phase16/interrupts/interrupt-phase16-001/prompt")
        self.assertEqual(bundle["interrupt_id"], "interrupt-phase16-001")

    def test_stm02_trim_evidence_proves_bounded_backend_context(self) -> None:
        bundle = self.fixture["events"]["context_bundle"]
        metadata = bundle["metadata"]

        self.assertEqual(metadata["input_recent_turn_count"], 64)
        self.assertEqual(metadata["emitted_recent_turn_count"], len(bundle["recent_turn_refs"]))
        self.assertEqual(metadata["dropped_recent_turn_count"], 60)
        self.assertLess(metadata["emitted_recent_turn_count"], metadata["input_recent_turn_count"])
        self.assertGreater(metadata["dropped_recent_turn_count"], 0)
        self.assertEqual(metadata["budget_tokens"], bundle["budget_tokens"])
        self.assertLessEqual(metadata["estimated_tokens"], metadata["budget_tokens"])
        self.assertTrue(metadata["long_conversation_policy"]["recent_turn_refs_are_bounded"])
        self.assertFalse(metadata["long_conversation_policy"]["complete_history_embedded"])
        self.assertNotIn("fixture://phase16/recent-turns/turn-001", bundle["recent_turn_refs"])

    def test_stm03_rolling_summary_is_refs_hashes_and_lengths_only(self) -> None:
        rolling_summary = self.fixture["events"]["context_bundle"]["metadata"]["rolling_summary"]

        self.assertEqual(rolling_summary["summary_ref"], "summary://phase16/session-phase16-001/rolling-summary-004")
        self.assertEqual(rolling_summary["task_intent_ref"], "summary://phase16/session-phase16-001/intent-004")
        self.assertEqual(rolling_summary["constraint_refs"], ["summary://phase16/session-phase16-001/constraints-004"])
        self.assertEqual(rolling_summary["open_question_refs"], ["summary://phase16/session-phase16-001/questions-004"])
        self.assertEqual(rolling_summary["artifact_refs"], ["artifact://phase16/artifacts/context-evidence-001"])
        self.assertEqual(rolling_summary["outcome_ref"], "summary://phase16/session-phase16-001/outcome-003")
        self.assertEqual(rolling_summary["summary_sha256_16"], "f2e4926ef6b89694")
        self.assertEqual(rolling_summary["summary_length"], 34)
        self.assertFalse(rolling_summary["content_embedded"])
        self.assertTrue({"summary_text", "raw_text", "full_text", "content"}.isdisjoint(rolling_summary))

    def test_stm04_protected_sections_survive_trimming(self) -> None:
        bundle = self.fixture["events"]["context_bundle"]
        metadata = bundle["metadata"]
        protected = metadata["protected_sections"]

        self.assertEqual(metadata["protected_section_count"], len(protected))
        self.assertIn("current_turn_ref", protected)
        self.assertIn("pending_clarification_ref", protected)
        self.assertIn("output_constraints_ref", protected)
        self.assertEqual(metadata["current_turn_ref"], "fixture://phase16/turns/turn-phase16-current-001")
        self.assertEqual(metadata["pending_clarification_ref"], "runtime://phase16/interrupts/interrupt-phase16-001/prompt")
        self.assertEqual(bundle["interrupt_id"], "interrupt-phase16-001")
        self.assertEqual(metadata["output_constraints_ref"], "fixture://phase16/output-constraints/output-policy-001")
        self.assertTrue(metadata["protected_sections_survived_trimming"])

    def test_current_turn_hash_and_length_evidence_matches_synthetic_content(self) -> None:
        events = self.fixture["events"]
        content = events["agent_turn"]["content"]
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        expected_length = len(content.encode("utf-8"))

        self.assertEqual(events["agent_turn"]["metadata"]["content_sha256_16"], expected_hash)
        self.assertEqual(events["agent_turn"]["metadata"]["content_length"], expected_length)
        self.assertEqual(events["context_bundle"]["metadata"]["current_turn_sha256_16"], expected_hash)
        self.assertEqual(events["context_bundle"]["metadata"]["current_turn_length"], expected_length)
        self.assertEqual(events["run"]["metadata"]["content_sha256_16"], expected_hash)
        self.assertEqual(events["run"]["metadata"]["content_length"], expected_length)

    def test_fixture_is_reference_first_and_privacy_safe(self) -> None:
        text = json.dumps(self.fixture, ensure_ascii=False, sort_keys=True)
        self.assertIn("raw_payload_ref", text)
        self.assertIn("raw_payload_refs", text)
        self.assertIn("fixture://", text)
        self.assertIn("runtime://", text)
        self.assertIn("summary://", text)
        self.assertIn("artifact://", text)

        for object_path, value in iter_mapping_values(self.fixture):
            with self.subTest(path=object_path):
                self.assertEqual(RAW_PAYLOAD_KEYS & set(value), set())

        for text_path, value in iter_string_values(self.fixture):
            with self.subTest(path=text_path):
                for pattern in FORBIDDEN_TEXT_PATTERNS:
                    self.assertIsNone(pattern.search(value), f"{text_path} matched {pattern.pattern}")


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
