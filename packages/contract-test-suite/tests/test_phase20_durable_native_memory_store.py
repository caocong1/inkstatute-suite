"""Contract tests for Phase 20 durable native memory store fixture."""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE20_FIXTURE = LOCAL_FIXTURE_ROOT / "phase20_durable_native_memory_store.json"

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


class Phase20DurableNativeMemoryStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE20_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_id_and_schema_validation(self) -> None:
        """Fixture has the expected id and passes validate_event_bundle."""
        self.assertEqual(
            self.fixture["fixture_id"], "phase20-durable-native-memory-store-001"
        )
        validate_event_bundle(self.fixture, self.schemas)

    def test_store_metadata_is_sqlite_native_and_live_legal_ready(self) -> None:
        """Store manifest in fixture metadata must be the SQLiteMemoryStore approved config."""
        store = self.fixture["metadata"]["store"]

        self.assertEqual(store["adapter_id"], "platform-native-sqlite")
        self.assertEqual(store["provider"], "platform_native")
        self.assertEqual(store["deployment_model"], "in_process_sqlite")
        self.assertEqual(store["decision"], "accepted_for_current_legal_use")
        self.assertTrue(store["supports_memory_records"])
        self.assertTrue(store["supports_delete"])
        self.assertTrue(store["supports_export"])
        self.assertTrue(store["supports_tenant_isolation"])
        self.assertTrue(store["supports_raw_payload_blocking"])
        self.assertTrue(store["approved_for_live_legal_memory"])
        self.assertFalse(store["stores_raw_payloads_by_default"])
        self.assertFalse(store["network_required"])
        self.assertFalse(store["sanitized_fixture_only"])
        self.assertTrue(store["default_for_legal_memory"])

    def test_durable_store_evidence_fields_are_present(self) -> None:
        """durable_store_evidence keys in metadata document the key runtime behaviors."""
        evidence = self.fixture["metadata"]["durable_store_evidence"]

        self.assertIn("persist_reload", evidence)
        self.assertIn("tombstone_deletion", evidence)
        self.assertIn("retention_expiry", evidence)
        self.assertIn("export_includes_deleted", evidence)
        self.assertIn("privacy_rejection", evidence)
        self.assertIn("tenant_isolation", evidence)
        self.assertIn("sql_parameterization", evidence)

    def test_memory_records_are_reference_first(self) -> None:
        """All memory_records in the fixture carry source_refs and raw_payload_ref, no raw text."""
        memory_records = self.fixture["events"]["memory_records"]
        self.assertGreater(len(memory_records), 0)

        for record in memory_records:
            with self.subTest(memory_id=record["memory_id"]):
                self.assertIn("source_refs", record)
                self.assertTrue(len(record["source_refs"]) > 0)
                self.assertIn("raw_payload_ref", record)
                self.assertTrue(record["raw_payload_ref"].startswith("fixture://"))
                # No raw payload keys at top level
                forbidden = RAW_PAYLOAD_KEYS & set(record)
                self.assertEqual(forbidden, set(), f"Forbidden keys found: {forbidden}")

    def test_deleted_record_has_tombstone_fields(self) -> None:
        """The tombstone record has status=deleted, deleted_at, and deletion_reason."""
        records = {r["memory_id"]: r for r in self.fixture["events"]["memory_records"]}
        deleted = records["memory-phase20-deleted-001"]

        self.assertEqual(deleted["status"], "deleted")
        self.assertIn("deleted_at", deleted)
        self.assertIn("deletion_reason", deleted)
        self.assertIsNotNone(deleted.get("deleted_at"))
        self.assertIsNotNone(deleted.get("deletion_reason"))

    def test_retention_expiry_record_has_ttl_and_deletion_evidence(self) -> None:
        """The TTL-expired record has status=deleted with ttl-related deletion_reason."""
        records = {r["memory_id"]: r for r in self.fixture["events"]["memory_records"]}
        expired = records["memory-phase20-expired-001"]

        self.assertEqual(expired["status"], "deleted")
        self.assertIn("ttl_expires_at", expired)
        self.assertIn("deleted_at", expired)
        # deletion_reason or metadata must reference TTL/retain policy
        ttl_evidence = (
            (expired.get("deletion_reason") or "")
            + json.dumps(expired.get("metadata", {}), ensure_ascii=False)
        )
        self.assertIn("ttl", ttl_evidence.lower())

    def test_context_bundle_links_to_active_memory_record(self) -> None:
        """context_bundle.memory_refs must reference the active memory record."""
        events = self.fixture["events"]
        context_bundle = events["context_bundle"]
        memory_records = {r["memory_id"]: r for r in events["memory_records"]}

        self.assertTrue(
            any("memory-phase20-active-001" in ref for ref in context_bundle["memory_refs"])
        )
        self.assertIn("memory-phase20-active-001", memory_records)
        self.assertEqual(memory_records["memory-phase20-active-001"]["status"], "active")

    def test_memory_use_links_to_bundle_and_record(self) -> None:
        """memory_uses must reference the context_bundle_id and an existing memory_id."""
        events = self.fixture["events"]
        memory_uses = events["memory_uses"]
        memory_records = {r["memory_id"]: r for r in events["memory_records"]}
        context_bundle = events["context_bundle"]

        self.assertGreater(len(memory_uses), 0)
        use = memory_uses[0]
        self.assertEqual(use["context_bundle_id"], context_bundle["context_bundle_id"])
        self.assertIn(use["memory_id"], memory_records)

    def test_memory_candidate_is_pending_human_review(self) -> None:
        """The fixture candidate must be pending with requires_human_review=True."""
        candidates = self.fixture["events"]["memory_candidates"]
        self.assertGreater(len(candidates), 0)

        candidate = candidates[0]
        self.assertEqual(candidate["status"], "pending")
        self.assertTrue(candidate["requires_human_review"])
        self.assertIn("source_refs", candidate)
        self.assertTrue(len(candidate["source_refs"]) > 0)

    def test_fixture_is_reference_first_and_privacy_safe(self) -> None:
        """No forbidden keys at any mapping level; no secret-like strings anywhere."""
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

    def test_verification_commands_reference_sqlite_and_schema_tests(self) -> None:
        """Verification commands must include the SQLite and schema validation test commands."""
        commands = self.fixture["metadata"]["verification_commands"]

        self.assertTrue(
            any("test_sqlite_memory_store.py" in cmd for cmd in commands),
            "verification_commands must include test_sqlite_memory_store.py",
        )
        self.assertTrue(
            any("test_phase20_durable_native_memory_store.py" in cmd for cmd in commands),
            "verification_commands must include test_phase20_durable_native_memory_store.py",
        )
        self.assertTrue(
            any("test_schema_validation.py" in cmd for cmd in commands),
            "verification_commands must include test_schema_validation.py",
        )

    def test_sqlite_memory_py_referenced_in_store_source_refs(self) -> None:
        """Store source_refs must include the sqlite_memory.py implementation path."""
        source_refs = self.fixture["metadata"]["store"]["source_refs"]
        self.assertTrue(
            any("sqlite_memory.py" in ref for ref in source_refs),
            "store.source_refs must include sqlite_memory.py",
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
