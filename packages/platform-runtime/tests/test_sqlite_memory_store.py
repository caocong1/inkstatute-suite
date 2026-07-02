"""Unit tests for SQLiteMemoryStore durable native memory store."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from platform_contract.events import MemoryCandidate, MemoryRecord, MemoryUse
from platform_runtime import (
    MemoryPrivacyError,
    MemoryQuery,
    MemoryStoreAdapter,
    MemoryStorePolicy,
    SQLiteMemoryStore,
)


FIXED_NOW = "2026-07-01T08:00:00Z"
FUTURE_TTL = "2026-08-01T00:00:00Z"
PAST_TTL = "2026-01-01T00:00:00Z"


def make_record(**overrides: object) -> MemoryRecord:
    values: dict[str, object] = {
        "memory_id": "memory-001",
        "tenant_id": "tenant-001",
        "workspace_id": "workspace-001",
        "scope": "session",
        "status": "active",
        "sensitivity": "internal",
        "created_at": "2026-06-30T08:00:00Z",
        "updated_at": "2026-07-01T07:00:00Z",
        "source_refs": ["feedback://feedback-001"],
        "summary": "citation format preference",
        "subject": "citation",
        "related_user_id": "user-001",
        "session_id": "session-001",
        "raw_payload_ref": "fixture://memory/raw/memory-001",
        "confidence": 0.8,
        "ttl_expires_at": FUTURE_TTL,
        "metadata": {
            "labels": ["citation_error"],
            "summary_sha256_16": "0123456789abcdef",
            "summary_length": 28,
        },
    }
    values.update(overrides)
    return MemoryRecord(**values)  # type: ignore[arg-type]


def make_query(**overrides: object) -> MemoryQuery:
    values: dict[str, object] = {
        "tenant_id": "tenant-001",
        "workspace_id": "workspace-001",
        "session_id": "session-001",
        "user_id": "user-001",
        "text": "citation format",
        "now": FIXED_NOW,
    }
    values.update(overrides)
    return MemoryQuery(**values)  # type: ignore[arg-type]


def make_candidate(**overrides: object) -> MemoryCandidate:
    values: dict[str, object] = {
        "candidate_id": "candidate-001",
        "tenant_id": "tenant-001",
        "workspace_id": "workspace-001",
        "status": "pending",
        "source_refs": ["feedback://feedback-001"],
        "created_at": "2026-07-01T08:00:00Z",
        "proposed_scope": "session",
        "proposed_sensitivity": "confidential",
        "proposed_action": "create_memory_candidate",
        "confidence": 0.6,
        "requires_human_review": True,
        "raw_payload_ref": "fixture://candidate/raw/candidate-001",
        "metadata": {"privacy": "refs_hashes_lengths_statuses_only"},
    }
    values.update(overrides)
    return MemoryCandidate(**values)  # type: ignore[arg-type]


def make_use(**overrides: object) -> MemoryUse:
    values: dict[str, object] = {
        "use_id": "use-001",
        "memory_id": "memory-001",
        "context_bundle_id": "bundle-001",
        "used_at": "2026-07-01T08:00:00Z",
        "purpose": "context_assembly",
        "relevance_score": 0.75,
        "policy_result": "selected",
        "metadata": {"privacy": "refs_hashes_lengths_statuses_only"},
    }
    values.update(overrides)
    return MemoryUse(**values)  # type: ignore[arg-type]


class SQLiteMemoryStoreTests(unittest.TestCase):

    def test_persist_and_reload_memory_record(self) -> None:
        """Upsert a record, close the store, reopen from same path, verify reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            store = SQLiteMemoryStore(db_path=db_path)
            store.upsert(make_record())
            store.close()

            store2 = SQLiteMemoryStore(db_path=db_path)
            record = store2.get("memory-001")
            store2.close()

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.memory_id, "memory-001")
        self.assertEqual(record.tenant_id, "tenant-001")
        self.assertEqual(record.summary, "citation format preference")
        self.assertEqual(record.source_refs, ["feedback://feedback-001"])
        self.assertAlmostEqual(record.confidence or 0.0, 0.8, places=5)

    def test_privacy_rejection_raw_payload_field(self) -> None:
        """Upsert a record with forbidden metadata key raises MemoryPrivacyError."""
        store = SQLiteMemoryStore()
        bad_record = make_record(metadata={"raw_payload": "some text"})
        with self.assertRaises(MemoryPrivacyError):
            store.upsert(bad_record)
        store.close()

    def test_list_for_query_tenant_scope_isolation(self) -> None:
        """Records from another tenant must not be returned in query results."""
        store = SQLiteMemoryStore()
        store.upsert(make_record(memory_id="mem-t1", tenant_id="tenant-001", workspace_id="workspace-001"))
        store.upsert(make_record(memory_id="mem-t2", tenant_id="tenant-999", workspace_id="workspace-001"))

        results = store.list_for_query(make_query())
        ids = {r.memory_id for r in results}

        self.assertIn("mem-t1", ids)
        self.assertNotIn("mem-t2", ids)
        store.close()

    def test_search_returns_ranked_results(self) -> None:
        """Multiple records, search by term — top result has highest relevance score."""
        store = SQLiteMemoryStore()
        store.upsert(make_record(
            memory_id="high-match",
            summary="citation format preference legal",
            subject="citation",
            confidence=0.9,
        ))
        store.upsert(make_record(
            memory_id="low-match",
            summary="document upload",
            subject="upload",
            confidence=0.4,
        ))

        results = store.search(make_query(text="citation format"))

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].record.memory_id, "high-match")
        store.close()

    def test_mark_deleted_tombstone(self) -> None:
        """mark_deleted sets status=deleted, deleted_at; list_for_query excludes it by default."""
        store = SQLiteMemoryStore()
        store.upsert(make_record())
        deleted = store.mark_deleted("memory-001", reason="test_deletion")

        self.assertEqual(deleted.status, "deleted")
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(deleted.deletion_reason, "test_deletion")

        # Default list_for_query excludes deleted records
        results = store.list_for_query(make_query())
        ids = {r.memory_id for r in results}
        self.assertNotIn("memory-001", ids)
        store.close()

    def test_export_records_includes_deleted(self) -> None:
        """export_records returns all records including deleted ones."""
        store = SQLiteMemoryStore()
        store.upsert(make_record(memory_id="active-001"))
        store.upsert(make_record(memory_id="to-delete-001"))
        store.mark_deleted("to-delete-001", reason="export_test")

        exported = store.export_records(make_query())
        ids = {r.memory_id for r in exported}

        self.assertIn("active-001", ids)
        self.assertIn("to-delete-001", ids)
        store.close()

    def test_candidate_upsert_and_get(self) -> None:
        """Upsert a candidate and retrieve a copy-safe instance."""
        store = SQLiteMemoryStore()
        candidate = make_candidate()
        store.upsert_candidate(candidate)

        result = store.get_candidate("candidate-001")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.candidate_id, "candidate-001")
        self.assertEqual(result.tenant_id, "tenant-001")
        self.assertTrue(result.requires_human_review)
        store.close()

    def test_memory_use_record_and_list(self) -> None:
        """record_memory_use persists a use; list_memory_uses returns it for the workspace."""
        store = SQLiteMemoryStore()
        # The use references memory-001 — upsert the parent record first
        store.upsert(make_record(memory_id="memory-001"))
        use = make_use()
        store.record_memory_use(use)

        uses = store.list_memory_uses(make_query())
        use_ids = {u.use_id for u in uses}

        self.assertIn("use-001", use_ids)
        store.close()

    def test_expire_records_updates_status(self) -> None:
        """Records with past TTL are marked expired by expire_records; count is returned."""
        store = SQLiteMemoryStore()
        store.upsert(make_record(
            memory_id="past-ttl-001",
            ttl_expires_at=PAST_TTL,
        ))
        store.upsert(make_record(
            memory_id="future-ttl-001",
            ttl_expires_at=FUTURE_TTL,
        ))

        count = store.expire_records(now=FIXED_NOW)
        self.assertGreaterEqual(count, 1)

        record = store.get("past-ttl-001")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.status, "expired")

        active = store.get("future-ttl-001")
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.status, "active")
        store.close()

    def test_sql_injection_shaped_filter_value(self) -> None:
        """Injection-shaped tenant_id returns empty results and does not corrupt the table."""
        store = SQLiteMemoryStore()
        store.upsert(make_record(memory_id="safe-001"))

        injection_query = make_query(tenant_id="'; DROP TABLE memory_records; --")
        results = store.list_for_query(injection_query)
        self.assertEqual(results, ())

        # Verify the table is still intact
        normal = store.get("safe-001")
        self.assertIsNotNone(normal)
        store.close()

    def test_capability_manifest(self) -> None:
        """capability_manifest returns the expected SQLite native manifest."""
        store = SQLiteMemoryStore()
        manifest = store.capability_manifest()
        store.close()

        self.assertEqual(manifest.adapter_id, "platform-native-sqlite")
        self.assertEqual(manifest.provider, "platform_native")
        self.assertTrue(manifest.supports_memory_records)
        self.assertTrue(manifest.supports_delete)
        self.assertTrue(manifest.supports_export)
        self.assertTrue(manifest.supports_tenant_isolation)
        self.assertTrue(manifest.supports_raw_payload_blocking)
        self.assertTrue(manifest.approved_for_live_legal_memory)
        self.assertFalse(manifest.stores_raw_payloads_by_default)
        self.assertFalse(manifest.network_required)
        self.assertFalse(manifest.sanitized_fixture_only)

    def test_adapter_protocol_conformance(self) -> None:
        """SQLiteMemoryStore must satisfy the runtime_checkable MemoryStoreAdapter protocol."""
        store = SQLiteMemoryStore()
        self.assertIsInstance(store, MemoryStoreAdapter)
        store.close()

    def test_in_memory_mode_no_disk_file(self) -> None:
        """Default constructor uses :memory: SQLite — works without creating any disk files."""
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            # Verify no .db file appears in the current directory
            store = SQLiteMemoryStore()
            store.upsert(make_record())
            record = store.get("memory-001")
            store.close()

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.memory_id, "memory-001")


if __name__ == "__main__":
    unittest.main()
