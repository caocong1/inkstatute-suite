"""Contract tests for Phase 22 recall orchestrator and context injection fixture."""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE22_FIXTURE = LOCAL_FIXTURE_ROOT / "phase22_recall_orchestrator_context_injection.json"

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


class Phase22RecallOrchestratorContextInjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE22_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_id_and_schema_validation(self) -> None:
        """Fixture has the expected id and passes validate_event_bundle."""
        self.assertEqual(
            self.fixture["fixture_id"],
            "phase22-recall-orchestrator-context-injection-001",
        )
        validate_event_bundle(self.fixture, self.schemas)

    def test_orchestrator_evidence_documents_all_rec_requirements(self) -> None:
        """orchestrator_evidence metadata must document all REC-01..REC-05 behaviors."""
        evidence = self.fixture["metadata"]["orchestrator_evidence"]

        self.assertIn("recall_scope", evidence)
        self.assertGreater(evidence["memories_recalled"], 0)            # REC-01
        self.assertTrue(evidence["rolling_summary_injected"])           # REC-02
        self.assertTrue(evidence["isolation_enforced"])                 # REC-03
        self.assertTrue(evidence["cross_tenant_query_raises_error"])    # REC-03
        self.assertTrue(evidence["memory_use_recorded"])                # REC-04
        self.assertTrue(evidence["no_raw_text_in_bundle_metadata"])     # REC-04: no raw text embedded
        self.assertTrue(evidence["run_runtime_constructor_unchanged"])  # REC-05

    def test_context_bundle_contains_memory_refs_and_summary_ref(self) -> None:
        """REC-01/02: context_bundle must have memory_refs and summary_ref populated."""
        bundle = self.fixture["events"]["context_bundle"]

        self.assertGreater(len(bundle.get("memory_refs", [])), 0)
        self.assertIsNotNone(bundle.get("summary_ref"))
        self.assertTrue(bundle["summary_ref"].startswith("summary://"))

    def test_context_bundle_metadata_has_no_raw_summary_text(self) -> None:
        """REC-04: bundle metadata must not embed raw summary text."""
        rolling = self.fixture["events"]["context_bundle"]["metadata"].get("rolling_summary", {})

        self.assertIn("summary_ref", rolling)
        self.assertNotIn("summary_text", rolling)
        self.assertNotIn("raw_text", rolling)
        self.assertNotIn("full_text", rolling)

    def test_memory_records_are_scoped_to_tenant_and_workspace(self) -> None:
        """REC-03: all memory records must share the same tenant/workspace as the bundle."""
        bundle = self.fixture["events"]["context_bundle"]
        tenant_id = bundle["tenant_id"]
        workspace_id = bundle["workspace_id"]

        for record in self.fixture["events"]["memory_records"]:
            with self.subTest(memory_id=record["memory_id"]):
                self.assertEqual(record["tenant_id"], tenant_id)
                self.assertEqual(record["workspace_id"], workspace_id)

    def test_memory_uses_are_reference_first_with_no_raw_text(self) -> None:
        """REC-04: MemoryUse records carry only refs, IDs, scores — no raw text."""
        for use in self.fixture["events"]["memory_uses"]:
            with self.subTest(use_id=use["use_id"]):
                self.assertEqual(use["purpose"], "context_assembly")
                for ref in use["source_refs"]:
                    self.assertIn("://", ref, f"MemoryUse source_ref must be URI, got {ref!r}")
                # No raw text keys
                forbidden = RAW_PAYLOAD_KEYS & set(use)
                self.assertEqual(forbidden, set(), f"Forbidden keys in MemoryUse: {forbidden}")

    def test_memory_use_context_bundle_id_links_to_bundle(self) -> None:
        """REC-04: MemoryUse.context_bundle_id must match context_bundle.context_bundle_id."""
        bundle_id = self.fixture["events"]["context_bundle"]["context_bundle_id"]
        for use in self.fixture["events"]["memory_uses"]:
            with self.subTest(use_id=use["use_id"]):
                self.assertEqual(use["context_bundle_id"], bundle_id)

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
        commands = self.fixture["metadata"]["verification_commands"]

        self.assertTrue(
            any("test_memory_orchestrator.py" in cmd for cmd in commands),
            "verification_commands must include test_memory_orchestrator.py",
        )
        self.assertTrue(
            any("test_phase22_recall_orchestrator_context_injection.py" in cmd for cmd in commands),
        )
        self.assertTrue(
            any("test_schema_validation.py" in cmd for cmd in commands),
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
