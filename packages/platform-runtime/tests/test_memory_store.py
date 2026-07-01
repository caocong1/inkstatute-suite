from __future__ import annotations

from dataclasses import replace
import unittest

from platform_contract.events import MemoryRecord
from platform_runtime import (
    InMemoryMemoryStore,
    MemoryPrivacyError,
    MemoryQuery,
    MemoryStorePolicy,
)


FIXED_NOW = "2026-07-01T08:00:00Z"


def make_memory(**overrides: object) -> MemoryRecord:
    values = {
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
        "ttl_expires_at": "2026-08-01T00:00:00Z",
        "metadata": {
            "labels": ["citation_error", "format_issue"],
            "summary_sha256_16": "0123456789abcdef",
            "summary_length": 28,
        },
    }
    values.update(overrides)
    return MemoryRecord(**values)


def make_query(**overrides: object) -> MemoryQuery:
    values = {
        "tenant_id": "tenant-001",
        "workspace_id": "workspace-001",
        "session_id": "session-001",
        "user_id": "user-001",
        "text": "citation format",
        "labels": ("citation_error",),
        "now": FIXED_NOW,
    }
    values.update(overrides)
    return MemoryQuery(**values)


class InMemoryMemoryStoreTests(unittest.TestCase):
    def test_session_user_workspace_and_tenant_scope_filtering_is_explicit(self) -> None:
        store = InMemoryMemoryStore()
        store.upsert(make_memory(memory_id="session-memory", scope="session", session_id="session-001"))
        store.upsert(make_memory(memory_id="other-session", scope="session", session_id="session-999"))
        store.upsert(make_memory(memory_id="user-memory", scope="user", session_id=None, related_user_id="user-001"))
        store.upsert(make_memory(memory_id="other-user", scope="user", session_id=None, related_user_id="user-999"))
        store.upsert(make_memory(memory_id="workspace-memory", scope="workspace", session_id=None, related_user_id=None))
        store.upsert(make_memory(memory_id="tenant-memory", scope="tenant", session_id=None, related_user_id=None))
        store.upsert(make_memory(memory_id="other-workspace", workspace_id="workspace-999", scope="workspace"))

        results = store.search(make_query(text="citation"))

        self.assertEqual(
            {result.record.memory_id for result in results},
            {"session-memory", "user-memory", "workspace-memory", "tenant-memory"},
        )

    def test_search_is_bounded_deterministic_and_reports_policy_metadata(self) -> None:
        store = InMemoryMemoryStore()
        store.upsert(make_memory(memory_id="memory-b", summary="citation", confidence=0.7, updated_at="2026-07-01T06:00:00Z"))
        store.upsert(make_memory(memory_id="memory-a", summary="citation format", confidence=0.9, updated_at="2026-07-01T06:00:00Z"))
        store.upsert(
            make_memory(
                memory_id="memory-c",
                subject="unrelated",
                summary="unrelated",
                confidence=0.9,
                updated_at="2026-07-01T07:00:00Z",
                metadata={"labels": ["other"]},
            )
        )

        results = store.search(make_query(text="citation format", max_results=2))

        self.assertEqual([result.record.memory_id for result in results], ["memory-a", "memory-b"])
        self.assertEqual(results[0].matched_terms, ("citation", "citation_error", "format"))
        self.assertEqual(results[0].policy_result, "selected")
        self.assertEqual(results[0].metadata["privacy"], "refs_hashes_lengths_statuses_only")

    def test_search_excludes_zero_match_records_when_query_has_terms(self) -> None:
        store = InMemoryMemoryStore()
        store.upsert(make_memory(memory_id="matching", summary="citation format"))
        store.upsert(
            make_memory(
                memory_id="visible-but-unmatched",
                subject="billing",
                summary="invoice preference",
                metadata={"labels": ["billing"]},
            )
        )

        results = store.search(make_query(text="citation"))

        self.assertEqual([result.record.memory_id for result in results], ["matching"])

    def test_search_without_terms_can_list_visible_records_by_confidence(self) -> None:
        store = InMemoryMemoryStore()
        store.upsert(make_memory(memory_id="low", confidence=0.2))
        store.upsert(make_memory(memory_id="high", confidence=0.9))

        results = store.search(make_query(text=None, labels=()))

        self.assertEqual([result.record.memory_id for result in results], ["high", "low"])

    def test_policy_excludes_deleted_suppressed_expired_low_confidence_and_restricted(self) -> None:
        store = InMemoryMemoryStore()
        store.upsert(make_memory(memory_id="active"))
        store.upsert(make_memory(memory_id="deleted", status="deleted"))
        store.upsert(make_memory(memory_id="suppressed", status="suppressed"))
        store.upsert(make_memory(memory_id="expired", ttl_expires_at="2026-06-01T00:00:00Z"))
        store.upsert(make_memory(memory_id="low-confidence", confidence=0.2))
        store.upsert(make_memory(memory_id="restricted", sensitivity="restricted"))

        results = store.search(
            make_query(),
            policy=MemoryStorePolicy(minimum_confidence=0.5),
        )

        self.assertEqual([result.record.memory_id for result in results], ["active"])

    def test_mark_deleted_updates_status_and_removes_memory_from_retrieval(self) -> None:
        store = InMemoryMemoryStore(clock=lambda: FIXED_NOW)
        store.upsert(make_memory())

        deleted = store.mark_deleted("memory-001", reason="user_deletion_request")

        self.assertEqual(deleted.status, "deleted")
        self.assertEqual(deleted.deleted_at, FIXED_NOW)
        self.assertEqual(deleted.deletion_reason, "user_deletion_request")
        self.assertEqual(store.search(make_query()), ())

    def test_reads_are_copy_safe(self) -> None:
        store = InMemoryMemoryStore()
        store.upsert(make_memory())

        returned = store.get("memory-001")
        self.assertIsNotNone(returned)
        mutated = replace(returned, metadata={"labels": ["mutated"]})

        self.assertEqual(mutated.metadata["labels"], ["mutated"])
        self.assertEqual(store.get("memory-001").metadata["labels"], ["citation_error", "format_issue"])

    def test_privacy_rejects_raw_payload_full_text_and_secret_like_fields(self) -> None:
        store = InMemoryMemoryStore()
        forbidden_keys = [
            "raw_payload",
            "raw_text",
            "payload_text",
            "full_text",
            "document_text",
            "customer_document_text",
            "case_facts",
            "callback_body",
            "message_text",
            "api_key",
        ]

        for key in forbidden_keys:
            with self.subTest(key=key):
                with self.assertRaisesRegex(MemoryPrivacyError, key):
                    store.upsert(make_memory(metadata={key: "unsafe"}))

        store.upsert(make_memory(metadata={"raw_payload_ref": "fixture://safe/ref"}))
        self.assertEqual(store.get("memory-001").metadata["raw_payload_ref"], "fixture://safe/ref")

    def test_query_metadata_is_privacy_checked_before_retrieval(self) -> None:
        store = InMemoryMemoryStore()
        store.upsert(make_memory())

        with self.assertRaisesRegex(MemoryPrivacyError, "raw_payload"):
            store.search(make_query(metadata={"raw_payload": "unsafe"}))


if __name__ == "__main__":
    unittest.main()
