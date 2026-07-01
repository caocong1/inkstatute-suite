from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE17_FIXTURE = LOCAL_FIXTURE_ROOT / "phase17_long_term_memory_feedback_learning.json"
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
    re.compile(r"\bgateway\b", re.IGNORECASE),
    re.compile(r"\badmin\b", re.IGNORECASE),
    re.compile(r"\bdebug\b", re.IGNORECASE),
    re.compile(r"(^|\s)/(new|resume|help|status|debug|memory)\b", re.IGNORECASE),
)
FOCUSED_RUNTIME_COMMAND = (
    "PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src "
    "python -m unittest packages/platform-runtime/tests/test_memory_store.py "
    "packages/platform-runtime/tests/test_feedback_learning.py"
)
FOCUSED_CONTRACT_COMMAND = (
    "PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src "
    "python -m unittest discover -s packages/contract-test-suite/tests "
    "-p 'test_phase17_long_term_memory_feedback_learning.py'"
)


class Phase17LongTermMemoryFeedbackLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE17_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_validates_with_existing_bundle_validator(self) -> None:
        self.assertEqual(self.fixture["fixture_id"], "phase17-long-term-memory-feedback-learning-001")
        validate_event_bundle(self.fixture, self.schemas)

    def test_memory_refs_and_memory_uses_link_to_context_bundle(self) -> None:
        events = self.fixture["events"]
        context_bundle = events["context_bundle"]
        records = {record["memory_id"]: record for record in events["memory_records"]}
        uses = events["memory_uses"]

        self.assertEqual(context_bundle["memory_refs"], ["memory-phase17-active-001"])
        for memory_id in context_bundle["memory_refs"]:
            self.assertIn(memory_id, records)
            self.assertEqual(records[memory_id]["status"], "active")

        self.assertEqual(len(uses), 1)
        self.assertEqual(uses[0]["memory_id"], "memory-phase17-active-001")
        self.assertEqual(uses[0]["context_bundle_id"], context_bundle["context_bundle_id"])
        self.assertEqual(uses[0]["purpose"], "feedback_learning_context")
        self.assertGreaterEqual(uses[0]["relevance_score"], 0.8)

    def test_feedback_corrections_are_context_refs_not_raw_text(self) -> None:
        bundle_metadata = self.fixture["events"]["context_bundle"]["metadata"]
        feedback_metadata = self.fixture["events"]["feedback_event"]["metadata"]

        self.assertEqual(
            bundle_metadata["feedback_correction_refs"],
            ["feedback://feedback-phase17-correction-001/correction"],
        )
        self.assertEqual(feedback_metadata["correction_ref"], "feedback://feedback-phase17-route-001/correction")
        self.assertIn("message_sha256_16", feedback_metadata)
        self.assertIn("message_length", feedback_metadata)

    def test_repeated_negative_candidate_has_source_refs_confidence_and_pending_status(self) -> None:
        repeat_candidate = self._candidate("memory-candidate-phase17-repeat-001")

        self.assertEqual(repeat_candidate["status"], "pending")
        self.assertEqual(repeat_candidate["proposed_action"], "create_memory_candidate")
        self.assertEqual(repeat_candidate["metadata"]["feedback_count"], 2)
        self.assertEqual(repeat_candidate["confidence"], 0.7)
        self.assertIn("feedback://feedback-phase17-correction-001", repeat_candidate["source_refs"])
        self.assertIn("raw_payload_ref", repeat_candidate)

    def test_route_skill_candidate_is_human_reviewed_no_auto_modify(self) -> None:
        feedback = self.fixture["events"]["feedback_event"]
        route_candidate = self._candidate("memory-candidate-phase17-route-001")

        self.assertTrue(feedback["route_mismatch"])
        self.assertTrue(feedback["skill_candidate"]["requires_human_review"])
        self.assertTrue(feedback["skill_candidate"]["metadata"]["no_auto_modify"])
        self.assertEqual(route_candidate["status"], "pending")
        self.assertTrue(route_candidate["requires_human_review"])
        self.assertTrue(route_candidate["metadata"]["no_auto_modify"])
        self.assertEqual(route_candidate["proposed_action"], "review_route_or_skill_candidate")

    def test_memory_policy_evidence_excludes_deleted_record_from_context(self) -> None:
        events = self.fixture["events"]
        deleted = self._memory("memory-phase17-deleted-001")

        self.assertEqual(deleted["status"], "deleted")
        self.assertEqual(deleted["deletion_reason"], "user_deletion_request")
        self.assertNotIn(deleted["memory_id"], events["context_bundle"]["memory_refs"])
        self.assertTrue(events["context_bundle"]["metadata"]["memory_search_policy"]["restricted_excluded_by_default"])

    def test_fixture_is_reference_first_and_privacy_safe(self) -> None:
        text = json.dumps(self.fixture, ensure_ascii=False, sort_keys=True)
        self.assertIn("raw_payload_ref", text)
        self.assertIn("fixture://", text)
        self.assertIn("memory://", text)
        self.assertIn("feedback://", text)

        for object_path, value in iter_mapping_values(self.fixture):
            with self.subTest(path=object_path):
                self.assertEqual(RAW_PAYLOAD_KEYS & set(value), set())

        for text_path, value in iter_string_values(self.fixture):
            with self.subTest(path=text_path):
                for pattern in FORBIDDEN_TEXT_PATTERNS:
                    self.assertIsNone(pattern.search(value), f"{text_path} matched {pattern.pattern}")

    def test_prepared_local_verification_commands_are_documented(self) -> None:
        commands = self.fixture["metadata"]["verification_commands"]

        self.assertIn(FOCUSED_CONTRACT_COMMAND, commands)
        self.assertIn("test_memory_store.py", FOCUSED_RUNTIME_COMMAND)
        self.assertIn("test_feedback_learning.py", FOCUSED_RUNTIME_COMMAND)

    def _candidate(self, candidate_id: str) -> Mapping[str, Any]:
        return next(
            candidate
            for candidate in self.fixture["events"]["memory_candidates"]
            if candidate["candidate_id"] == candidate_id
        )

    def _memory(self, memory_id: str) -> Mapping[str, Any]:
        return next(
            memory
            for memory in self.fixture["events"]["memory_records"]
            if memory["memory_id"] == memory_id
        )


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
