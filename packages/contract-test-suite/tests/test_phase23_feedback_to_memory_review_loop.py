"""Contract tests for Phase 23 feedback-to-memory review loop fixture."""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE23_FIXTURE = LOCAL_FIXTURE_ROOT / "phase23_feedback_to_memory_review_loop.json"

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


class Phase23FeedbackToMemoryReviewLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE23_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_id_and_schema_validation(self) -> None:
        """Fixture has the expected id and passes validate_event_bundle."""
        self.assertEqual(
            self.fixture["fixture_id"],
            "phase23-feedback-to-memory-review-loop-001",
        )
        validate_event_bundle(self.fixture, self.schemas)

    def test_review_loop_evidence_documents_all_fbl_requirements(self) -> None:
        """review_loop_evidence metadata must document all FBL-01..FBL-05 behaviors."""
        evidence = self.fixture["metadata"]["review_loop_evidence"]

        self.assertTrue(evidence["fbl_01_correction_refs_produced"])                          # FBL-01
        self.assertTrue(evidence["fbl_02_repeated_negative_creates_pending_candidates"])      # FBL-02
        self.assertIn("approve", evidence["fbl_03_decisions_supported"])                      # FBL-03
        self.assertIn("reject", evidence["fbl_03_decisions_supported"])
        self.assertIn("defer", evidence["fbl_03_decisions_supported"])
        self.assertTrue(evidence["fbl_04_approved_candidate_promoted_to_active_memory_record"])  # FBL-04
        self.assertTrue(evidence["fbl_04_rejected_candidate_not_in_recall"])                  # FBL-04
        self.assertTrue(evidence["fbl_05_routing_candidate_cannot_be_auto_approved"])         # FBL-05
        self.assertTrue(evidence["fbl_05_routing_candidate_can_be_deferred"])                 # FBL-05
        self.assertTrue(evidence["no_raw_text_in_promoted_records"])

    def test_feedback_correction_ref_in_context_bundle_metadata(self) -> None:
        """FBL-01: context_bundle.metadata.feedback_correction_refs must be ref URIs."""
        correction_refs = (
            self.fixture["events"]["context_bundle"]["metadata"].get("feedback_correction_refs", [])
        )
        self.assertGreater(len(correction_refs), 0)
        for ref in correction_refs:
            self.assertIn("://", ref, f"correction_ref must be a URI, got {ref!r}")

    def test_memory_candidates_include_pending_and_routing_variants(self) -> None:
        """FBL-02/FBL-05: fixture has both create_memory_candidate and routing candidates."""
        candidates = self.fixture["events"]["memory_candidates"]
        actions = {c["proposed_action"] for c in candidates}

        self.assertIn("create_memory_candidate", actions)
        self.assertIn("review_route_or_skill_candidate", actions)

    def test_review_decisions_in_trace_metadata_reference_correct_actions(self) -> None:
        """FBL-03: execution_trace metadata.review_decisions records all three decisions."""
        trace_meta = self.fixture["events"]["execution_trace"]["metadata"]
        decisions = trace_meta.get("review_decisions", [])

        actions = {d["action"] for d in decisions}
        self.assertIn("approve", actions)
        self.assertIn("reject", actions)
        self.assertIn("defer", actions)

    def test_approved_candidate_memory_id_in_context_bundle_memory_refs(self) -> None:
        """FBL-04: memory_refs in context_bundle must include promoted memory id."""
        memory_refs = self.fixture["events"]["context_bundle"].get("memory_refs", [])
        promoted_ids = self.fixture["events"]["execution_trace"]["metadata"].get("promoted_memory_ids", [])

        for promoted_id in promoted_ids:
            self.assertIn(promoted_id, memory_refs)

    def test_routing_candidate_deferred_not_promoted(self) -> None:
        """FBL-05: routing candidates appear in deferred_candidate_ids, not promoted_memory_ids."""
        trace_meta = self.fixture["events"]["execution_trace"]["metadata"]
        deferred_ids = trace_meta.get("deferred_candidate_ids", [])
        promoted_ids = trace_meta.get("promoted_memory_ids", [])

        for candidate_id in deferred_ids:
            self.assertNotIn(candidate_id, promoted_ids)

    def test_memory_candidates_are_reference_first_no_raw_text(self) -> None:
        """Memory candidates must have only ref URIs in source_refs."""
        for candidate in self.fixture["events"]["memory_candidates"]:
            for ref in candidate["source_refs"]:
                self.assertIn("://", ref, f"source_ref must be URI, got {ref!r}")

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

        self.assertTrue(any("test_memory_review.py" in cmd for cmd in commands))
        self.assertTrue(any("test_phase23_feedback_to_memory_review_loop.py" in cmd for cmd in commands))
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
