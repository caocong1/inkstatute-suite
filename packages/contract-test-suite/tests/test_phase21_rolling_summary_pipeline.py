"""Contract tests for Phase 21 rolling summary pipeline fixture."""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE21_FIXTURE = LOCAL_FIXTURE_ROOT / "phase21_rolling_summary_pipeline.json"

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


class Phase21RollingSummaryPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE21_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_id_and_schema_validation(self) -> None:
        """Fixture has the expected id and passes validate_event_bundle."""
        self.assertEqual(
            self.fixture["fixture_id"], "phase21-rolling-summary-pipeline-001"
        )
        validate_event_bundle(self.fixture, self.schemas)

    def test_summary_pipeline_evidence_documents_trigger_and_privacy_behaviors(self) -> None:
        """summary_pipeline_evidence in metadata must record all four SUM requirements."""
        evidence = self.fixture["metadata"]["summary_pipeline_evidence"]

        self.assertIn("trigger_reason", evidence)
        self.assertIn(evidence["trigger_reason"], ("turn_count", "budget_pressure", "task_completion", "explicit_request"))
        self.assertFalse(evidence["summary_text_embedded_in_bundle"])
        self.assertTrue(evidence["raw_text_rejected_by_producer"])
        self.assertTrue(evidence["empty_source_refs_rejected"])
        self.assertTrue(evidence["wrong_ref_prefix_rejected"])

    def test_rolling_summary_metadata_carries_all_sum02_fields(self) -> None:
        """SUM-02: rolling_summary metadata must carry all required fields."""
        summary = self.fixture["metadata"]["rolling_summary"]

        self.assertTrue(summary["summary_ref"].startswith("summary://"))
        self.assertIn("session_id", summary)
        self.assertGreater(len(summary.get("source_refs", [])), 0)
        self.assertIn("task_intent_refs", summary)
        self.assertIn("user_constraint_refs", summary)
        self.assertIn("unanswered_question_refs", summary)
        self.assertIn("artifact_refs", summary)
        self.assertIn("outcome_refs", summary)
        self.assertIn("text_sha256_16", summary)
        self.assertIn("text_length", summary)
        self.assertIn("created_at", summary)
        self.assertIn("updated_at", summary)
        self.assertIn("trigger_reason", summary)

    def test_context_bundle_has_summary_ref_not_raw_text(self) -> None:
        """SUM-01: context_bundle.summary_ref is a ref URI; no raw summary text in metadata."""
        context_bundle = self.fixture["events"]["context_bundle"]

        summary_ref = context_bundle.get("summary_ref", "")
        self.assertTrue(
            isinstance(summary_ref, str) and summary_ref.startswith("summary://"),
            f"context_bundle.summary_ref must start with summary://, got: {summary_ref!r}",
        )

        rolling_summary_meta = context_bundle.get("metadata", {}).get("rolling_summary", {})
        self.assertIn("summary_ref", rolling_summary_meta)
        self.assertNotIn("summary_text", rolling_summary_meta)
        self.assertNotIn("raw_text", rolling_summary_meta)
        self.assertNotIn("full_text", rolling_summary_meta)

    def test_trigger_reason_documented_in_trace_and_summary_metadata(self) -> None:
        """SUM-03: the execution_trace and rolling_summary metadata must record trigger_reason."""
        trace_meta = self.fixture["events"]["execution_trace"]["metadata"]
        summary_meta = self.fixture["metadata"]["rolling_summary"]

        self.assertIn("trigger_reason", trace_meta)
        self.assertIn("trigger_reason", summary_meta)
        self.assertEqual(trace_meta["trigger_reason"], summary_meta["trigger_reason"])

    def test_source_refs_in_summary_metadata_are_valid_uris(self) -> None:
        """SUM-04 dependency: source_refs must be non-empty reference URIs, not raw text."""
        source_refs = self.fixture["metadata"]["rolling_summary"]["source_refs"]

        self.assertGreater(len(source_refs), 0)
        for ref in source_refs:
            with self.subTest(ref=ref):
                self.assertIsInstance(ref, str)
                self.assertTrue(
                    "://" in ref,
                    f"source_ref must be a URI with ://, got: {ref!r}",
                )

    def test_fixture_is_reference_first_and_privacy_safe(self) -> None:
        """No forbidden payload keys at any level; no secret-like string values."""
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
        """Verification commands must reference all four test targets."""
        commands = self.fixture["metadata"]["verification_commands"]

        self.assertTrue(
            any("test_rolling_summary.py" in cmd for cmd in commands),
            "verification_commands must include test_rolling_summary.py",
        )
        self.assertTrue(
            any("test_phase21_rolling_summary_pipeline.py" in cmd for cmd in commands),
            "verification_commands must include test_phase21_rolling_summary_pipeline.py",
        )
        self.assertTrue(
            any("test_schema_validation.py" in cmd for cmd in commands),
            "verification_commands must include test_schema_validation.py",
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
