# Phase 20: Durable Native Memory Store - Pattern Map

**Mapped:** 2026-07-02
**Files analyzed:** 6
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/platform-runtime/src/platform_runtime/sqlite_memory.py` | service | CRUD, file-I/O, request-response | `packages/platform-runtime/src/platform_runtime/memory.py` | role-match |
| `packages/platform-runtime/src/platform_runtime/memory.py` | utility | transform, request-response | `packages/platform-runtime/src/platform_runtime/memory.py` | exact |
| `packages/platform-runtime/src/platform_runtime/__init__.py` | config | transform | `packages/platform-runtime/src/platform_runtime/__init__.py` | exact |
| `packages/platform-runtime/tests/test_sqlite_memory_store.py` | test | CRUD, file-I/O, request-response | `packages/platform-runtime/tests/test_memory_store.py` | exact |
| `packages/platform-runtime/tests/test_memory_adapter_contract.py` | test | request-response | `packages/platform-runtime/tests/test_memory_adapter_contract.py` | exact |
| `packages/contract-test-suite/tests/test_phase20_durable_native_memory_store.py` | test | transform | `packages/contract-test-suite/tests/test_phase18_external_memory_adapter_acceptance.py` | role-match |
| `packages/contract-test-suite/fixtures/phase20_durable_native_memory_store.json` | test fixture | transform | `packages/contract-test-suite/fixtures/phase18_external_memory_adapter_acceptance.json` | role-match |

## Pattern Assignments

### `packages/platform-runtime/src/platform_runtime/sqlite_memory.py` (service, CRUD/file-I/O/request-response)

**Analog:** `packages/platform-runtime/src/platform_runtime/memory.py`

**Imports pattern** (lines 5-13):
```python
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from platform_contract.events import JsonObject, MemoryCandidate, MemoryRecord, MemoryUse
```

Add stdlib `sqlite3` and `Path` only; do not add package dependencies.

**Store API pattern** (lines 55-121):
```python
class InMemoryMemoryStore:
    """Copy-safe, scoped memory store for tests and embedded hosts."""

    def __init__(self, *, clock: Callable[[], datetime | str] | Any | None = None) -> None:
        self._clock = clock
        self._records: dict[str, MemoryRecord] = {}

    def upsert(self, record: MemoryRecord) -> None:
        _validate_record(record)
        self._records[record.memory_id] = _copy_record(record)

    def get(self, memory_id: str) -> MemoryRecord | None:
        record = self._records.get(memory_id)
        return _copy_record(record) if record is not None else None
```

SQLite store should preserve these method names and copy-safe return behavior. Add durable helpers for `upsert_candidate`, `get_candidate`, `list_candidates`, `record_memory_use`, and `list_memory_uses` because Phase 20 must persist `MemoryCandidate` and `MemoryUse`.

**Search/ranking pattern** (lines 85-108):
```python
def search(
    self,
    query: MemoryQuery,
    *,
    policy: MemoryStorePolicy | None = None,
) -> tuple[MemorySearchResult, ...]:
    cfg = policy or MemoryStorePolicy()
    query_terms = _terms_from_query(query)
    results = [
        _search_result(record, query_terms)
        for record in self.list_for_query(query, policy=cfg)
    ]
    if query_terms:
        results = [result for result in results if result.matched_terms]
    results.sort(
        key=lambda item: (
            -item.relevance_score,
            -float(item.record.confidence if item.record.confidence is not None else 0.0),
            _reverse_timestamp_key(item.record.updated_at),
            item.record.memory_id,
        )
    )
    limit = max(0, int(query.max_results if query.max_results is not None else cfg.max_results))
    return tuple(results[:limit])
```

Use SQL for coarse tenant/workspace/status/sensitivity/session/user/TTL filters, then reuse this deterministic Python ranking behavior.

**Deletion/tombstone pattern** (lines 110-121):
```python
def mark_deleted(self, memory_id: str, *, deleted_at: str | datetime | None = None, reason: str = "") -> MemoryRecord:
    record = self._records[memory_id]
    timestamp = _timestamp(deleted_at or _clock_now(self._clock))
    deleted = replace(
        record,
        status="deleted",
        deleted_at=timestamp,
        deletion_reason=reason or "deleted_by_policy",
        updated_at=timestamp,
    )
    self.upsert(deleted)
    return _copy_record(deleted)
```

SQLite must update the JSON payload and indexed status/deleted fields transactionally; do not hard-delete as the primary delete path.

**Privacy validation pattern** (lines 295-307, 445-469, 565-569):
```python
def _validate_record(record: MemoryRecord) -> None:
    _safe_metadata(record.metadata)
    _safe_metadata(record.industry_context)
    for ref in record.source_refs:
        _validate_ref(ref, field="source_refs")
    if record.raw_payload_ref is not None:
        _validate_ref(record.raw_payload_ref, field="raw_payload_ref")

def _validate_query(query: MemoryQuery) -> None:
    _safe_metadata(query.metadata)
    for ref in query.source_refs:
        _validate_ref(ref, field="source_refs")
```

```python
def _safe_metadata(value: Any, path: str = "$") -> JsonObject:
    if isinstance(value, Mapping):
        output: JsonObject = {}
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in _FORBIDDEN_KEYS or _SECRET_KEY_PATTERN.search(key_text):
                raise MemoryPrivacyError(f"memory metadata contains forbidden field at {child_path}")
            output[key_text] = _safe_value(child, child_path)
        return _json_clone(output)
    if value is None:
        return {}
    raise MemoryPrivacyError(f"memory metadata must be an object at {path}")
```

```python
def _validate_ref(value: str, *, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise MemoryPrivacyError(f"{field} must contain non-empty refs")
    if _SECRET_VALUE_PATTERN.search(value):
        raise MemoryPrivacyError(f"{field} contains secret-like value")
```

Extend these helpers rather than creating a second privacy vocabulary.

**Contract field pattern** (source `packages/platform-contract/src/platform_contract/events.py`, lines 457-514):
```python
@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    tenant_id: str
    workspace_id: str
    scope: MemoryScope | str
    status: MemoryStatus | str
    sensitivity: MemorySensitivity | str
    created_at: str
    updated_at: str
    source_refs: list[str]
    summary: str | None = None
    subject: str | None = None
    related_user_id: str | None = None
    session_id: str | None = None
    raw_payload_ref: str | None = None
    confidence: float | None = None
    ttl_expires_at: str | None = None
    deleted_at: str | None = None
    deletion_reason: str | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)
```

Persist full contract-shaped JSON for `MemoryRecord`, `MemoryCandidate`, and `MemoryUse`, with indexed columns copied from these dataclass fields.

---

### `packages/platform-runtime/src/platform_runtime/memory.py` (utility, transform/request-response)

**Analog:** `packages/platform-runtime/src/platform_runtime/memory.py`

**Shared visibility helper pattern** (lines 310-341):
```python
def _record_visible(
    record: MemoryRecord,
    query: MemoryQuery,
    policy: MemoryStorePolicy,
    now: datetime,
) -> bool:
    if record.tenant_id != query.tenant_id or record.workspace_id != query.workspace_id:
        return False
    if str(record.status) not in policy.active_statuses:
        return False
    if record.deleted_at is not None:
        return False
    if str(record.sensitivity) not in policy.allowed_sensitivities:
        return False
    if float(record.confidence if record.confidence is not None else 0.0) < policy.minimum_confidence:
        return False
    if record.ttl_expires_at is not None and _parse_timestamp(record.ttl_expires_at) <= now:
        return False
    return _scope_allows(record, query)
```

Make these helpers reusable by `sqlite_memory.py` if planner chooses extraction. Keep behavior identical to `InMemoryMemoryStore` parity tests.

**Copy-safe serialization pattern** (lines 572-598):
```python
def _copy_record(record: MemoryRecord) -> MemoryRecord:
    return MemoryRecord(
        memory_id=record.memory_id,
        tenant_id=record.tenant_id,
        workspace_id=record.workspace_id,
        scope=str(record.scope),
        status=str(record.status),
        sensitivity=str(record.sensitivity),
        created_at=record.created_at,
        updated_at=record.updated_at,
        source_refs=list(record.source_refs),
        summary=record.summary,
        subject=record.subject,
        related_user_id=record.related_user_id,
        session_id=record.session_id,
        raw_payload_ref=record.raw_payload_ref,
        confidence=record.confidence,
        ttl_expires_at=record.ttl_expires_at,
        deleted_at=record.deleted_at,
        deletion_reason=record.deletion_reason,
        industry_context=_safe_metadata(record.industry_context),
        metadata=_safe_metadata(record.metadata),
    )

def _json_clone(value: Mapping[str, Any]) -> JsonObject:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
```

Add equivalent copy helpers for `MemoryCandidate` and `MemoryUse` if the durable store returns those objects.

---

### `packages/platform-runtime/src/platform_runtime/__init__.py` (config, transform)

**Analog:** `packages/platform-runtime/src/platform_runtime/__init__.py`

**Import/export pattern** (lines 53-69, 115-137):
```python
from .memory import (
    FeedbackLearningInput,
    FeedbackLearningPolicy,
    FeedbackLearningResult,
    InMemoryMemoryStore,
    MemoryPrivacyError,
    MemoryQuery,
    MemorySearchResult,
    MemoryStorePolicy,
)
from .memory_adapters import (
    MemoryAdapterDecision,
    MemoryAdapterEvaluation,
    MemoryStoreAdapter,
    MemoryStoreCapabilityManifest,
    evaluate_memory_adapter_manifest,
)
```

```python
"FeedbackLearningInput",
"FeedbackLearningPolicy",
"FeedbackLearningResult",
"InMemoryMemoryStore",
"MemoryPrivacyError",
"MemoryQuery",
"MemorySearchResult",
"MemoryStorePolicy",
"MemoryAdapterDecision",
"MemoryAdapterEvaluation",
"MemoryStoreAdapter",
"MemoryStoreCapabilityManifest",
```

Add `from .sqlite_memory import SQLiteMemoryStore` near memory imports and include `"SQLiteMemoryStore"` in `__all__`.

---

### `packages/platform-runtime/tests/test_sqlite_memory_store.py` (test, CRUD/file-I/O/request-response)

**Analog:** `packages/platform-runtime/tests/test_memory_store.py`

**Test setup factory pattern** (lines 1-57):
```python
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
```

Use `tempfile.TemporaryDirectory()` for durable file tests and `SQLiteMemoryStore(path, clock=lambda: FIXED_NOW)` for deterministic timestamps.

**Parity assertions to copy** (lines 60-150):
```python
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
```

```python
def test_mark_deleted_updates_status_and_removes_memory_from_retrieval(self) -> None:
    store = InMemoryMemoryStore(clock=lambda: FIXED_NOW)
    store.upsert(make_memory())

    deleted = store.mark_deleted("memory-001", reason="user_deletion_request")

    self.assertEqual(deleted.status, "deleted")
    self.assertEqual(deleted.deleted_at, FIXED_NOW)
    self.assertEqual(deleted.deletion_reason, "user_deletion_request")
    self.assertEqual(store.search(make_query()), ())
```

Add Phase 20-specific durable restart assertions: write record/candidate/use, construct a second `SQLiteMemoryStore` over the same path, then verify objects and search results survive.

**Privacy assertions to copy** (lines 163-191):
```python
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
```

Repeat this for candidates, uses, and export/query filters.

---

### `packages/platform-runtime/tests/test_memory_adapter_contract.py` (test, request-response)

**Analog:** `packages/platform-runtime/tests/test_memory_adapter_contract.py`

**Manifest fixture pattern** (lines 22-51):
```python
def manifest(**overrides: object) -> MemoryStoreCapabilityManifest:
    values = {
        "adapter_id": "platform-native",
        "provider": "platform_native",
        "adapter_version": "0.1.0",
        "deployment_model": "in_process",
        "source_refs": ("docs/architecture/memory/context-memory-contracts.md",),
        "supports_memory_records": True,
        "supports_memory_candidates": True,
        "supports_memory_uses": True,
        "supports_ttl": True,
        "supports_delete": True,
        "supports_export": True,
        "supports_tenant_isolation": True,
        "supports_metadata_filters": True,
        "supports_raw_payload_blocking": True,
        "supports_human_review_gate": True,
        "stores_raw_payloads_by_default": False,
        "network_required": False,
        "requires_secrets": False,
        "sanitized_fixture_only": False,
        "default_for_legal_memory": True,
        "approved_for_live_legal_memory": True,
        "data_residency": "repo-local",
        "deletion_model": "ttl_and_tombstone",
        "export_model": "memory_record_fixture",
        "metadata": {"privacy": "refs_hashes_lengths_statuses_only"},
    }
    values.update(overrides)
    return MemoryStoreCapabilityManifest(**values)
```

SQLite store `capability_manifest()` should satisfy this live platform-native manifest, with source refs pointing to `sqlite_memory.py` and the Phase 20 fixture.

**Protocol conformance pattern** (lines 331-370):
```python
class AdapterWrapper:
    def __init__(self) -> None:
        self.store = InMemoryMemoryStore()

    def capability_manifest(self) -> MemoryStoreCapabilityManifest:
        return manifest()

    def upsert(self, record: MemoryRecord) -> None:
        self.store.upsert(record)

    def search(
        self,
        query: MemoryQuery,
        *,
        policy: MemoryStorePolicy | None = None,
    ) -> tuple[MemorySearchResult, ...]:
        return self.store.search(query, policy=policy)

    def mark_deleted(self, memory_id: str, *, reason: str = "") -> MemoryRecord:
        return self.store.mark_deleted(memory_id, reason=reason)

    def export_records(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
        return self.store.list_for_query(query)
```

Add a direct `SQLiteMemoryStore` protocol test rather than only wrapper tests.

---

### `packages/contract-test-suite/tests/test_phase20_durable_native_memory_store.py` (test, transform)

**Analog:** `packages/contract-test-suite/tests/test_phase18_external_memory_adapter_acceptance.py`

**Imports and fixture loading pattern** (lines 1-13, 51-59):
```python
from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle

PHASE18_FIXTURE = LOCAL_FIXTURE_ROOT / "phase18_external_memory_adapter_acceptance.json"
```

```python
class Phase18ExternalMemoryAdapterAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE18_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_validates_with_existing_bundle_validator(self) -> None:
        self.assertEqual(self.fixture["fixture_id"], "phase18-external-memory-adapter-acceptance-001")
        validate_event_bundle(self.fixture, self.schemas)
```

Rename class and fixture constants for Phase 20.

**Memory evidence assertions pattern** (lines 81-99):
```python
def test_memory_evidence_links_to_context_bundle(self) -> None:
    events = self.fixture["events"]
    context_bundle = events["context_bundle"]
    memory_records = {item["memory_id"]: item for item in events["memory_records"]}
    memory_uses = events["memory_uses"]

    self.assertEqual(context_bundle["memory_refs"], ["memory-phase18-adapter-contract-001"])
    self.assertIn("memory-phase18-adapter-contract-001", memory_records)
    self.assertEqual(memory_records["memory-phase18-adapter-contract-001"]["status"], "active")
    self.assertEqual(memory_uses[0]["context_bundle_id"], context_bundle["context_bundle_id"])
    self.assertEqual(memory_uses[0]["memory_id"], "memory-phase18-adapter-contract-001")
```

For Phase 20, assert durable persistence metadata, tombstone/deletion evidence, export evidence, and candidate/use evidence.

**Reference-first privacy pattern** (lines 123-137, 147-165):
```python
def test_fixture_is_reference_first_and_privacy_safe(self) -> None:
    text = json.dumps(self.fixture, ensure_ascii=False, sort_keys=True)
    self.assertIn("raw_payload_ref", text)
    self.assertIn("fixture://", text)
    self.assertIn("adapter://", text)
    self.assertIn("memory://", text)

    for object_path, value in iter_mapping_values(self.fixture):
        with self.subTest(path=object_path):
            self.assertEqual(RAW_PAYLOAD_KEYS & set(value), set())

    for text_path, value in iter_string_values(self.fixture):
        with self.subTest(path=text_path):
            for pattern in FORBIDDEN_TEXT_PATTERNS:
                self.assertIsNone(pattern.search(value), f"{text_path} matched {pattern.pattern}")
```

```python
def iter_mapping_values(value: Any, path: str = "$") -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        yield path, value
        for key, item in value.items():
            yield from iter_mapping_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_mapping_values(item, f"{path}[{index}]")
```

Copy this structure and include Phase 20 verification commands for runtime SQLite tests and contract fixture tests.

---

### `packages/contract-test-suite/fixtures/phase20_durable_native_memory_store.json` (test fixture, transform)

**Analog:** `packages/contract-test-suite/fixtures/phase18_external_memory_adapter_acceptance.json`

**Fixture metadata pattern** (lines 1-15, 249-253):
```json
{
  "fixture_id": "phase18-external-memory-adapter-acceptance-001",
  "description": "Synthetic Phase 18 fixture proving external memory adapter evaluation remains sanitized, reference-first, and non-default for live legal memory.",
  "metadata": {
    "phase": "18",
    "requirements": [
      "EXT-02",
      "EXT-03",
      "EXT-04"
    ],
    "evidence_kind": "synthetic_local_fixture",
    "not_live_acceptance": true,
    "no_live_external_invocation": true,
    "privacy": "refs_hashes_lengths_statuses_only",
```

```json
"verification_commands": [
  "PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_contract.py",
  "PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase18_external_memory_adapter_acceptance.py'",
  "PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'"
]
```

Use Phase 20 IDs and commands. Keep synthetic references only; do not include runtime DB paths or raw legal text.

**Platform-native manifest pattern** (lines 16-43):
```json
{
  "adapter_id": "platform-native",
  "provider": "platform_native",
  "decision": "accepted_for_current_legal_use",
  "deployment_model": "in_process",
  "source_refs": [
    "docs/architecture/memory/context-memory-contracts.md",
    "packages/platform-runtime/src/platform_runtime/memory.py",
    "packages/platform-runtime/src/platform_runtime/memory_adapters.py"
  ],
  "supports_memory_records": true,
  "supports_memory_candidates": true,
  "supports_memory_uses": true,
  "supports_ttl": true,
  "supports_delete": true,
  "supports_export": true,
  "supports_tenant_isolation": true,
  "supports_raw_payload_blocking": true,
  "supports_human_review_gate": true,
  "stores_raw_payloads_by_default": false,
  "network_required": false,
  "requires_secret_refs": false,
  "sanitized_fixture_only": false,
  "default_for_legal_memory": true,
  "approved_for_live_legal_memory": true,
  "required_gates": [],
  "blockers": []
}
```

Add `packages/platform-runtime/src/platform_runtime/sqlite_memory.py` to `source_refs` and include durable evidence such as `storage_model: "sqlite_contract_json_plus_indexes"`.

**Bundle schema pattern** (source `packages/contract-test-suite/src/contract_test_suite/schema_validation.py`, lines 33-40 and 148-161):
```python
OPTIONAL_ARRAY_SCHEMA_BY_KEY = {
    "run_steps": "run_step",
    "run_events": "run_event",
    "artifact_records": "artifact_record",
    "memory_records": "memory_record",
    "memory_candidates": "memory_candidate",
    "memory_uses": "memory_use",
}
```

```python
for event_key, schema_name in OPTIONAL_ARRAY_SCHEMA_BY_KEY.items():
    if event_key not in events:
        continue
    values = events[event_key]
    if not isinstance(values, list):
        raise ContractValidationError(f"{fixture_id}.{event_key}: expected type array, got {_type_name(values)}")
    for index, value in enumerate(values):
        _validate_schema(
            loaded_schemas[schema_name],
            value,
            loaded_schemas,
            path=(fixture_id, f"{event_key}[{index}]"),
            is_event_top_level=True,
        )
```

No validator changes are needed if fixture uses existing `memory_records`, `memory_candidates`, and `memory_uses` arrays.

## Shared Patterns

### Privacy Guard
**Source:** `packages/platform-runtime/src/platform_runtime/memory.py` lines 295-307, 445-469, 601-618
**Apply to:** `sqlite_memory.py`, `test_sqlite_memory_store.py`, Phase 20 contract fixture/test

Use the existing forbidden key and secret-like value vocabulary. Storage paths must reject unsafe metadata before SQLite writes and before query/export filters run.

### Deterministic Query Semantics
**Source:** `packages/platform-runtime/src/platform_runtime/memory.py` lines 85-108, 310-380
**Apply to:** `sqlite_memory.py`, `test_sqlite_memory_store.py`

SQL may narrow rows, but visible-record logic and result ordering must match `InMemoryMemoryStore`.

### Tombstone Deletion
**Source:** `packages/platform-runtime/src/platform_runtime/memory.py` lines 110-121
**Apply to:** `sqlite_memory.py`, runtime tests, contract fixture

Represent deletion with status, `deleted_at`, `deletion_reason`, and updated payload/indexes. Preserve exportable tombstone evidence.

### Contract Fixture Validation
**Source:** `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` lines 33-40, 119-161
**Apply to:** `phase20_durable_native_memory_store.json`, `test_phase20_durable_native_memory_store.py`

Use existing event bundle schema validation. Do not invent Phase 20-only fixture keys under `events`.

### Package Exports
**Source:** `packages/platform-runtime/src/platform_runtime/__init__.py` lines 53-69, 84-160
**Apply to:** `__init__.py`

Import public runtime classes near their module group and add each exported symbol to `__all__`.

## No Analog Found

None. Every expected file has a close repo-local analog.

## Metadata

**Analog search scope:** `packages/platform-runtime`, `packages/contract-test-suite`, `packages/platform-contract/src/platform_contract/events.py`
**Files scanned:** 72 listed files plus targeted source/test excerpts
**Pattern extraction date:** 2026-07-02
