# Phase 20: Durable Native Memory Store - Research

**Researched:** 2026-07-02
**Domain:** Python stdlib durable memory persistence for InkStatute platform-runtime
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
No locked implementation decisions were recorded in `.planning/phases/20-durable-native-memory-store/20-CONTEXT.md`. [VERIFIED: codebase grep]

### the agent's Discretion
All implementation choices are at the agent's discretion - discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None - discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEM-01 | Durable platform-native `MemoryStore` persists `MemoryRecord`, `MemoryCandidate`, and `MemoryUse` evidence without an external memory service. | Implement a stdlib `sqlite3` store in `packages/platform-runtime` that preserves Phase 17 memory classes and Phase 18 adapter protocol. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] [VERIFIED: packages/platform-runtime/src/platform_runtime/memory_adapters.py] |
| MEM-02 | Stored memory remains reference-first with refs, hashes, lengths, scopes, TTL/expiry, deletion metadata, sensitivity, confidence, review state, and safe summaries only. | Persist contract-shaped JSON plus indexed reference-first columns; reuse recursive metadata/privacy validation before every write. [VERIFIED: packages/platform-contract/src/platform_contract/events.py] [VERIFIED: docs/architecture/memory/context-memory-contracts.md] |
| MEM-03 | Storage rejects raw legal/customer payloads, full document text, callback bodies, secrets, and unsafe full-text metadata recursively. | Extend the existing Phase 17 forbidden-key and secret-like-value checks across records, candidates, uses, queries, export filters, and serialized JSON payloads. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| MEM-04 | Memory records can be queried by tenant, workspace, user, session, labels, source refs, sensitivity, confidence, TTL, deletion status, and deterministic relevance. | Keep `MemoryQuery`/`MemoryStorePolicy`, add indexed SQLite filters and deterministic post-filter/ranking parity with `InMemoryMemoryStore.search()`. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| MEM-05 | Memory deletion, tombstone, retention expiry, and export workflows are represented in code and tests. | Build methods and tests for `mark_deleted`, tombstone metadata, TTL expiry marking, and `export_records` through the Phase 18 adapter surface. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory_adapters.py] [CITED: docs/architecture/memory/production-memory-system-strategy.md] |
</phase_requirements>

## Summary

Phase 20 should extend the shipped Phase 17/18 memory surface rather than create a parallel memory API. The repo already has `MemoryRecord`, `MemoryCandidate`, `MemoryUse`, `MemoryQuery`, `MemoryStorePolicy`, `InMemoryMemoryStore`, `FeedbackLearningPolicy`, and `MemoryStoreAdapter`; Phase 20's gap is durable persistence, not new runtime or channel contracts. [VERIFIED: packages/platform-contract/src/platform_contract/events.py] [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] [VERIFIED: packages/platform-runtime/src/platform_runtime/memory_adapters.py]

Use a dependency-free `sqlite3` implementation inside `packages/platform-runtime`, because the package currently declares no runtime dependencies and prior runtime phases use stdlib `unittest`, injected clocks/IDs, copy-safe support stores, and no service/database/network side effects. [VERIFIED: packages/platform-runtime/pyproject.toml] [VERIFIED: .planning/phases/17-long-term-memory-and-feedback-learning/17-CONTEXT.md]

**Primary recommendation:** Implement `SQLiteMemoryStore` as the durable platform-native `MemoryStoreAdapter` with contract-shaped JSON persistence, indexed scope/filter columns, recursive privacy validation, delete/tombstone/expiry/export helpers, and parity tests against `InMemoryMemoryStore`. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] [VERIFIED: packages/platform-runtime/src/platform_runtime/memory_adapters.py]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Durable native memory persistence | API / Backend library | Database / Storage | `platform-runtime` owns backend-neutral support surfaces; SQLite owns durable bytes without changing WeCom or RunRuntime contracts. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory_adapters.py] |
| Scoped memory query and relevance ranking | API / Backend library | Database / Storage | Query policy and deterministic ranking already live in runtime memory code; SQLite should supply coarse filters and durable reads. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| Privacy guard before storage/export | API / Backend library | Database / Storage | Existing recursive guards are runtime-library behavior and must run before data reaches persistence. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| Delete, tombstone, retention expiry | API / Backend library | Database / Storage | Store methods update contract fields and tombstone metadata transactionally; no channel/runtime API changes are required. [VERIFIED: packages/platform-contract/src/platform_contract/events.py] |
| Contract fixture validation | Contract-test-suite | API / Backend library | Fixture validation already recognizes memory records, candidates, and uses as optional arrays. [VERIFIED: packages/contract-test-suite/src/contract_test_suite/schema_validation.py] |

## Project Constraints (from AGENTS.md)

- Use `docs/requirements/V2-PRD.md` as current product specification; do not reintroduce V1 as an active source. [VERIFIED: AGENTS.md]
- Preserve V2 as a backend-neutral platform contract plus InkStatute-owned WeCom service and adapter layer; do not rebuild Hermes core/session/router/skills/MCP/model gateway unless explicitly scoped. [VERIFIED: AGENTS.md]
- User-facing WeCom ingress/egress belongs to InkStatute; Hermes meta/system/gateway/update/command/help notices must not leak to ordinary lawyer users. [VERIFIED: AGENTS.md]
- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads. [VERIFIED: AGENTS.md]
- Contract logs and memory records should prefer references such as `raw_payload_ref` and must not store sensitive full text by default. [VERIFIED: AGENTS.md]
- Keep legal-specific fields inside `industry_context`; platform-level schemas remain industry-neutral. [VERIFIED: AGENTS.md]
- High-risk legal feedback remains human-reviewed; V2 records candidates and does not auto-modify legal conclusion skills. [VERIFIED: AGENTS.md]
- Keep changes scoped to the active GSD phase and add tests with behavior changes, especially schemas, mappers, event ordering, dedupe, and fixture replay. [VERIFIED: AGENTS.md]
- Prefer structured parsers and schema validators over ad hoc string parsing. [VERIFIED: AGENTS.md]
- Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or active GSD plan requires it. [VERIFIED: AGENTS.md]

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `sqlite3` | SQLite 3.46.1 in current environment | Durable embedded storage for records/candidates/uses | Adds durability without a package dependency, external service, queue, or network call. [VERIFIED: local command] [VERIFIED: packages/platform-runtime/pyproject.toml] |
| Python stdlib `json` | Python 3.14.6 in current environment | Canonical serialization of contract dataclasses | Existing runtime helpers already use JSON clone/serialization for safe copy behavior. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| `platform_contract.events` | repo-local | Source dataclasses for `MemoryRecord`, `MemoryCandidate`, `MemoryUse` | Contract fields already include refs, scopes, TTL, deletion metadata, sensitivity, confidence, and candidate review state. [VERIFIED: packages/platform-contract/src/platform_contract/events.py] |
| `platform_runtime.memory` | repo-local | Query, policy, privacy, in-memory parity baseline | Phase 17 shipped deterministic scoped retrieval and privacy checks here. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| `platform_runtime.memory_adapters` | repo-local | Adapter protocol and capability manifest | Phase 18 defines `upsert`, `search`, `mark_deleted`, and `export_records` without RunRuntime/channel coupling. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory_adapters.py] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib `unittest` | Python 3.14.6 in current environment | Runtime and contract validation | Existing package tests use stdlib `unittest`; keep Phase 20 validation consistent. [VERIFIED: packages/platform-runtime/tests/test_memory_store.py] |
| `contract_test_suite.schema_validation` | repo-local | Validate memory fixture arrays | Use for Phase 20 fixture containing `memory_records`, `memory_candidates`, and `memory_uses`. [VERIFIED: packages/contract-test-suite/src/contract_test_suite/schema_validation.py] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib SQLite | PostgreSQL | Better hosted concurrency and JSON indexing, but adds service dependency and violates the phase goal unless a later plan approves deployment. [ASSUMED] |
| deterministic lexical ranking | vector database/search | Better semantic recall, but Phase 20 requires deterministic relevance and no external memory dependency; vector search remains later evaluation work. [CITED: docs/architecture/memory/production-memory-system-strategy.md] |
| contract JSON plus indexes | ORM | ORM adds a package dependency and abstraction not used in `platform-runtime`. [VERIFIED: packages/platform-runtime/pyproject.toml] |

**Installation:**
```bash
# No external packages required.
```

**Version verification:**
```bash
python - <<'PY'
import sqlite3, sys
print(sys.version)
print(sqlite3.sqlite_version)
PY
```

## Package Legitimacy Audit

No external packages are recommended or installed for Phase 20. The durable store should use Python stdlib `sqlite3`, `json`, `dataclasses`, and `unittest`; package slopcheck is not applicable. [VERIFIED: packages/platform-runtime/pyproject.toml]

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| None | — | — | — | — | — | No external package install |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
Host / tests / future recall orchestrator
        |
        v
MemoryStoreAdapter API
  upsert(record) / search(query) / mark_deleted(id) / export_records(query)
        |
        v
Recursive privacy guard
  reject forbidden keys, secret-like values, unsafe refs, unsafe metadata
        |
        v
Contract dataclass copy + canonical JSON serialization
        |
        v
SQLite transaction
  memory_records + record_source_refs + record_labels
  memory_candidates + candidate_source_refs
  memory_uses + use_source_refs
        |
        v
Query path
  indexed tenant/workspace/user/session/status/sensitivity/TTL filters
        |
        v
deterministic relevance scoring + bounded results
        |
        v
MemorySearchResult / MemoryRecord export / tombstone evidence
```

### Recommended Project Structure

```text
packages/platform-runtime/src/platform_runtime/
├── memory.py                 # Existing query, policy, in-memory store, shared privacy/ranking helpers
├── sqlite_memory.py          # New durable SQLiteMemoryStore implementation
├── memory_adapters.py        # Existing adapter protocol; no breaking signature change
└── __init__.py               # Export SQLiteMemoryStore and durable helper types

packages/platform-runtime/tests/
├── test_memory_store.py              # Existing in-memory parity remains green
├── test_sqlite_memory_store.py       # New durable persistence/query/privacy/delete/export tests
└── test_memory_adapter_contract.py   # Add durable adapter conformance case

packages/contract-test-suite/
├── fixtures/phase20_durable_native_memory_store.json
└── tests/test_phase20_durable_native_memory_store.py
```

### Pattern 1: Adapter-Compatible Durable Store

**What:** Add `SQLiteMemoryStore` with the same public behavior as `InMemoryMemoryStore` plus candidate/use persistence helpers. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] [VERIFIED: packages/platform-runtime/src/platform_runtime/memory_adapters.py]

**When to use:** Use for Phase 20 durable native memory while preserving `MemoryStoreAdapter` compatibility and avoiding `DefaultRunRuntime` constructor changes. [VERIFIED: packages/platform-runtime/tests/test_memory_adapter_contract.py]

**Example:**
```python
# Source: packages/platform-runtime/src/platform_runtime/memory_adapters.py
store = SQLiteMemoryStore(path)
store.upsert(memory_record)
results = store.search(query, policy=MemoryStorePolicy(minimum_confidence=0.5))
deleted = store.mark_deleted("memory-001", reason="user_deletion_request")
exported = store.export_records(query)
```

### Pattern 2: Contract JSON Plus Indexed Columns

**What:** Store the full dataclass event as canonical JSON and duplicate query-critical fields into indexed columns/side tables. [VERIFIED: packages/platform-contract/src/platform_contract/events.py]

**When to use:** Use for `MemoryRecord`, `MemoryCandidate`, and `MemoryUse` so exports can round-trip contract objects while queries remain scoped and deterministic. [VERIFIED: packages/contract-test-suite/src/contract_test_suite/schema_validation.py]

**Example:**
```sql
-- Source: repo-local planning recommendation from existing contract fields
CREATE TABLE memory_records (
  memory_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  scope TEXT NOT NULL,
  status TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  session_id TEXT,
  related_user_id TEXT,
  confidence REAL,
  ttl_expires_at TEXT,
  deleted_at TEXT,
  updated_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX memory_records_scope_idx
  ON memory_records (tenant_id, workspace_id, status, sensitivity, session_id, related_user_id);
```

### Pattern 3: Shared Privacy Validation Before Persistence

**What:** Validate dataclasses and query/export metadata before serialization and before writing any SQLite row. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py]

**When to use:** Every write path: record upsert, candidate upsert, memory-use insert, delete/tombstone metadata update, TTL expiry marking, and export filter creation. [CITED: docs/architecture/memory/production-memory-system-strategy.md]

**Example:**
```python
# Source: packages/platform-runtime/src/platform_runtime/memory.py
def upsert(self, record: MemoryRecord) -> None:
    validate_memory_record(record)  # extract from existing _validate_record
    payload = memory_record_to_json(record)
    with self._transaction() as conn:
        conn.execute(..., indexed_values + (payload,))
```

### Anti-Patterns to Avoid

- **New RunRuntime or WeCom constructor parameter:** Phase 18 tests assert `DefaultRunRuntime.__init__` has no `memory_adapter` or `memory_store` parameter, so durable memory must remain an injected support surface for future orchestration. [VERIFIED: packages/platform-runtime/tests/test_memory_adapter_contract.py]
- **Divergent in-memory vs durable relevance:** Copying ranking logic into a second implementation risks behavioral drift; extract shared validation/ranking helpers from `memory.py` and test parity. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py]
- **Raw SQLite fixture/database commits:** AGENTS.md forbids committing runtime databases/logs/customer payloads; tests should use temp directories or `:memory:` and synthetic fixtures only. [VERIFIED: AGENTS.md]
- **Semantic legal text classifier as privacy gate:** Phase 20 can enforce deterministic key/value/ref/length guards, but a reliable semantic detector for "full legal/customer text" is not present in the repo. [ASSUMED]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Durable embedded storage | Custom file format or ad hoc append log | Python stdlib `sqlite3` | SQLite gives transactions, indexes, uniqueness, and local durability without external packages. [VERIFIED: local command] |
| Contract serialization | Manual string concatenation | `dataclasses` plus `json.dumps(..., sort_keys=True)` | Existing runtime code uses JSON cloning for safe structured data. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| Privacy recursion | A second scanner with different forbidden fields | Extract/reuse Phase 17 guard vocabulary | Current tests already cover forbidden raw/full-text keys and secret-like values. [VERIFIED: packages/platform-runtime/tests/test_memory_store.py] |
| External semantic/vector recall | Vector DB or hosted memory SDK | Deterministic lexical relevance from `MemoryQuery` | Phase 20 requires native durable memory and deterministic relevance without external memory dependency. [CITED: docs/architecture/memory/production-memory-system-strategy.md] |
| Schema validation | Hand-written fixture assertions only | Existing contract-test-suite validator | The validator already recognizes memory fixture arrays. [VERIFIED: packages/contract-test-suite/src/contract_test_suite/schema_validation.py] |

**Key insight:** The hard part is not storage bytes; it is preserving the existing privacy, scope, deletion, and deterministic-relevance semantics when the store becomes durable. [VERIFIED: .planning/phases/17-long-term-memory-and-feedback-learning/17-REVIEW.md]

## Common Pitfalls

### Pitfall 1: Durability That Bypasses Privacy Guards
**What goes wrong:** JSON payloads are inserted directly into SQLite without the recursive checks that in-memory writes already apply. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py]
**Why it happens:** Durable code often starts as serialization code and forgets the in-memory store's policy boundary. [ASSUMED]
**How to avoid:** Centralize validation helpers and call them from both stores before persistence. [VERIFIED: packages/platform-runtime/tests/test_memory_store.py]
**Warning signs:** `sqlite_memory.py` imports `MemoryRecord` but not `MemoryPrivacyError` or validation helpers. [ASSUMED]

### Pitfall 2: Query Filters Only Work In Python After Loading All Rows
**What goes wrong:** Tenant/workspace/deletion filters are applied after reading all durable records, increasing leakage risk and making tests miss storage-boundary mistakes. [ASSUMED]
**Why it happens:** Full JSON storage is easy, but scoped persistence needs indexed columns. [ASSUMED]
**How to avoid:** Apply tenant/workspace/status/sensitivity/TTL coarse filters in SQL, then apply labels/source refs/relevance deterministically in Python. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py]
**Warning signs:** `search()` starts with `SELECT payload_json FROM memory_records` without `WHERE tenant_id = ? AND workspace_id = ?`. [ASSUMED]

### Pitfall 3: Deletion Removes Audit Evidence Needed For Tombstones
**What goes wrong:** Hard deletion makes export/deletion evidence impossible to prove later. [CITED: docs/architecture/memory/production-memory-system-strategy.md]
**Why it happens:** `mark_deleted` can be mistaken for `DELETE FROM memory_records`. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py]
**How to avoid:** Represent tombstone as `status="deleted"`, `deleted_at`, `deletion_reason`, and minimal tombstone metadata; add optional purge only if later retention policy approves. [VERIFIED: packages/platform-contract/src/platform_contract/events.py]
**Warning signs:** A deletion test expects `get(memory_id)` to return `None` immediately instead of a deleted/tombstoned record for export evidence. [ASSUMED]

### Pitfall 4: Candidate And Use Evidence Are Treated As Second-Class
**What goes wrong:** Durable store only persists `MemoryRecord`, leaving `MemoryCandidate` and `MemoryUse` in memory. [VERIFIED: .planning/REQUIREMENTS.md]
**Why it happens:** Phase 17's `InMemoryMemoryStore` only stores records; candidates/uses are produced by `FeedbackLearningPolicy`. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py]
**How to avoid:** Add explicit durable helpers for `upsert_candidate`, `get_candidate`, `list_candidates`, `record_memory_use`, and `list_memory_uses`. [VERIFIED: packages/platform-contract/src/platform_contract/events.py]
**Warning signs:** MEM-01 tests only call `upsert(MemoryRecord)` and never restart the store with candidate/use evidence. [ASSUMED]

## Code Examples

### Durable Store Construction

```python
# Source: recommended Phase 20 pattern based on existing adapter protocol
store = SQLiteMemoryStore(
    db_path,
    clock=lambda: "2026-07-02T08:00:00Z",
)
store.initialize()
store.upsert(record)
same_record = store.get(record.memory_id)
```

### Query Parity

```python
# Source: packages/platform-runtime/src/platform_runtime/memory.py
query = MemoryQuery(
    tenant_id="tenant-001",
    workspace_id="workspace-001",
    session_id="session-001",
    user_id="user-001",
    labels=("citation_error",),
    source_refs=("feedback://feedback-001",),
    text="citation format",
    now="2026-07-02T08:00:00Z",
)
results = store.search(query, policy=MemoryStorePolicy(minimum_confidence=0.5))
```

### Tombstone And Export

```python
# Source: packages/platform-runtime/src/platform_runtime/memory_adapters.py
deleted = store.mark_deleted("memory-001", reason="user_deletion_request")
assert deleted.status == "deleted"

exported = store.export_records(
    MemoryQuery(
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        user_id="user-001",
        now="2026-07-02T08:00:00Z",
    )
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 17 copy-safe in-memory `MemoryRecord` store | Phase 20 durable SQLite-backed native store with same query/policy surface | v1.3 Phase 20 | Adds persistence while preserving memory semantics. [VERIFIED: .planning/phases/17-long-term-memory-and-feedback-learning/17-VERIFICATION.md] |
| External memory provider selection before native baseline | Native memory first, external providers only as gated sanitized adapters | v1.3 strategy | Keeps legal data in platform-controlled memory until privacy/deletion/export/isolation gates pass. [CITED: docs/architecture/memory/production-memory-system-strategy.md] |
| Record-only memory evidence | Durable records, candidates, and uses | Phase 20 requirement | Supports review workflow and context-use audit evidence. [VERIFIED: .planning/REQUIREMENTS.md] |

**Deprecated/outdated:**
- Treating Mem0/Zep/Hindsight/OpenViking/ReMe as live legal defaults is out of scope for this phase; Phase 18 kept them sanitized-spike candidates behind adapter gates. [VERIFIED: docs/architecture/memory/external-memory-adapter-recommendation.md]
- Storing raw legal/customer text, callback bodies, or document text in memory is disallowed by project constraints and memory contracts. [VERIFIED: AGENTS.md] [CITED: docs/architecture/memory/context-memory-contracts.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PostgreSQL would be a better hosted-concurrency option but is not appropriate for Phase 20 without an approved service dependency. | Standard Stack | Planner might over-constrain future deployment if SQLite is expected to be final production hosting storage. |
| A2 | A deterministic semantic detector for "full legal/customer text" is not present in the repo; Phase 20 should enforce structural guards, secret patterns, and summary length/policy controls. | Anti-Patterns / Pitfalls | Planner may need a human/legal decision if semantic raw legal text detection is required now. |
| A3 | SQL coarse filters plus Python post-filter/ranking are sufficient for Phase 20 scale. | Common Pitfalls | Very large memory volumes may require more indexes, FTS, or Postgres in a later phase. |

## Open Questions (RESOLVED)

1. **RESOLVED: Phase 20 will not add explicit platform schema fields for tombstone/export evidence.**
   - Resolution: Use existing `MemoryRecord.status`, `deleted_at`, and `deletion_reason` for tombstone state; use reference-first metadata, source refs, and Phase 20 fixture evidence for export/delete audit details. [VERIFIED: packages/platform-contract/src/platform_contract/events.py]
   - Scope guard: Do not add a new tombstone event schema, export event schema, or top-level platform contract field in Phase 20. A later phase can revisit separate tombstone/export event contracts only with an explicit requirement. [VERIFIED: .planning/REQUIREMENTS.md]
   - Test implication: Runtime and contract-suite tests must prove tombstones remain exportable through `MemoryRecord` evidence and do not require new schema fields. [VERIFIED: .planning/phases/20-durable-native-memory-store/20-VALIDATION.md]

2. **RESOLVED: `MemoryQuery` will grow only minimal backward-compatible caller-controlled filters required by MEM-04 tests.**
   - Resolution: Add defaulted `MemoryQuery` fields for sensitivities, statuses, minimum confidence, TTL before/after bounds, and include-deleted/include-expired behavior so callers can test sensitivity, status, confidence, TTL, and deletion filters directly. [VERIFIED: .planning/REQUIREMENTS.md]
   - Compatibility guard: Preserve old constructor usages by giving every new field a default and keeping `MemoryStorePolicy` as the default recall policy boundary. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py]
   - Privacy implication: `_validate_query` must validate the new fields, and both SQLite query and export paths must reject forbidden or secret-like query metadata before SQL/export processing. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Runtime/tests | yes | 3.14.6 | Package requires >=3.11. [VERIFIED: packages/platform-runtime/pyproject.toml] |
| SQLite via stdlib `sqlite3` | Durable native store | yes | 3.46.1 | None needed for local tests. [VERIFIED: local command] |
| `unittest` | Validation | yes | stdlib | None needed. [VERIFIED: packages/platform-runtime/tests/test_memory_store.py] |
| `gsd-tools` | Phase artifact workflow | yes | command available | Manual git/doc workflow. [VERIFIED: local command] |

**Missing dependencies with no fallback:** none. [VERIFIED: local command]

**Missing dependencies with fallback:** none. [VERIFIED: local command]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python stdlib `unittest` [VERIFIED: packages/platform-runtime/tests/test_memory_store.py] |
| Config file | none; tests are run with explicit `PYTHONPATH` [VERIFIED: .planning/phases/17-long-term-memory-and-feedback-learning/17-VALIDATION.md] |
| Quick run command | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_store.py packages/platform-runtime/tests/test_sqlite_memory_store.py` |
| Full suite command | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase20_durable_native_memory_store.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| MEM-01 | Durable store persists and reloads `MemoryRecord`, `MemoryCandidate`, and `MemoryUse` after store restart. | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_sqlite_memory_store.py` | no - Wave 0 |
| MEM-02 | Persisted objects preserve refs, hashes, lengths, scopes, TTL, deletion metadata, sensitivity, confidence, review state, and safe summaries. | unit + contract | same focused unit command plus Phase 20 contract fixture command | no - Wave 0 |
| MEM-03 | Recursive privacy guard rejects raw payloads, full-text keys, callback bodies, document text, and secret-like metadata before SQLite write/export. | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_sqlite_memory_store.py` | no - Wave 0 |
| MEM-04 | Queries filter by tenant/workspace/user/session/labels/source refs/sensitivity/confidence/TTL/deletion and rank deterministically. | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_sqlite_memory_store.py packages/platform-runtime/tests/test_memory_store.py` | partial - existing in-memory only |
| MEM-05 | Delete, tombstone, retention expiry, and export workflows are represented by code and fixture evidence. | unit + contract | focused unit command plus `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase20_durable_native_memory_store.py'` | no - Wave 0 |

### Sampling Rate

- **Per task commit:** `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_sqlite_memory_store.py`
- **Per wave merge:** `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests`
- **Phase gate:** Full runtime suite plus Phase 20 contract fixture plus schema validation suite green before `$gsd-verify-work`.

### Wave 0 Gaps

- [ ] `packages/platform-runtime/tests/test_sqlite_memory_store.py` - covers MEM-01 through MEM-05.
- [ ] `packages/contract-test-suite/fixtures/phase20_durable_native_memory_store.json` - synthetic durable memory fixture.
- [ ] `packages/contract-test-suite/tests/test_phase20_durable_native_memory_store.py` - privacy, relationships, export/delete/tombstone fixture checks.
- [ ] `packages/contract-test-suite/tests/test_schema_validation.py` - add `phase20-durable-native-memory-store-001` to expected fixture IDs.

### Baseline Checks Run During Research

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_store.py packages/platform-runtime/tests/test_memory_adapter_contract.py` passed: 18 tests. [VERIFIED: local command]
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` passed: 99 tests. [VERIFIED: local command]
- Phase 17 and Phase 18 focused contract tests passed: 8 and 9 tests. [VERIFIED: local command]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | Phase 20 is a library store and does not authenticate users. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory_adapters.py] |
| V3 Session Management | yes | Enforce tenant/workspace/user/session scope filters on every query and export. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| V4 Access Control | yes | Fail closed on cross-tenant/workspace/user/session retrieval; tests must include negative isolation cases. [VERIFIED: packages/platform-runtime/tests/test_memory_store.py] |
| V5 Input Validation | yes | Recursive privacy guard, schema dataclasses, and contract-suite validation. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] [VERIFIED: packages/contract-test-suite/src/contract_test_suite/schema_validation.py] |
| V6 Cryptography | yes | Use stdlib hashing only for evidence hashes; do not implement encryption or secret storage in Phase 20. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] [VERIFIED: AGENTS.md] |

### Known Threat Patterns for Platform-Runtime Memory

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant/workspace memory recall | Information Disclosure | SQL `WHERE tenant_id/workspace_id` plus Python scope checks and negative tests. [VERIFIED: packages/platform-runtime/tests/test_memory_store.py] |
| Raw legal/customer text persistence | Information Disclosure | Recursive forbidden-key/value checks and safe-summary length/hash/ref requirements before write. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| Secret-like metadata or refs | Information Disclosure | Reject secret-like keys/values in metadata and refs. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| Deleted memory still recalled | Information Disclosure | Exclude `status="deleted"` and non-null `deleted_at` in SQL and policy checks. [VERIFIED: packages/platform-runtime/src/platform_runtime/memory.py] |
| SQL injection through filters | Tampering | Use parameterized SQLite queries; never format query values into SQL strings. [ASSUMED] |
| Audit loss on hard delete | Repudiation | Tombstone with status/deleted_at/deletion_reason and exportable deletion evidence. [VERIFIED: packages/platform-contract/src/platform_contract/events.py] |

## Sources

### Primary (HIGH confidence)

- `AGENTS.md` - project source of truth, safety/privacy, and coding rules.
- `.planning/phases/20-durable-native-memory-store/20-CONTEXT.md` - Phase 20 context and discretion scope.
- `.planning/REQUIREMENTS.md` - MEM-01 through MEM-05 definitions.
- `.planning/ROADMAP.md` - Phase 20 goal, dependencies, and success criteria.
- `docs/architecture/memory/production-memory-system-strategy.md` - v1.3 native-first memory strategy and durable store target.
- `docs/architecture/memory/context-memory-contracts.md` - memory vocabulary, privacy policy, deletion/retention contract.
- `.planning/phases/17-long-term-memory-and-feedback-learning/17-CONTEXT.md` and `17-VERIFICATION.md` - shipped in-memory memory and feedback-learning decisions/evidence.
- `.planning/phases/18-external-memory-adapter-evaluation-and-acceptance-gates/18-CONTEXT.md` and `18-VERIFICATION.md` - adapter protocol and external provider gate decisions.
- `packages/platform-contract/src/platform_contract/events.py` - `MemoryRecord`, `MemoryCandidate`, `MemoryUse`, `ContextBundle` fields.
- `packages/platform-runtime/src/platform_runtime/memory.py` - current memory query/policy/privacy/relevance implementation.
- `packages/platform-runtime/src/platform_runtime/memory_adapters.py` - adapter protocol and manifest gate.
- `packages/platform-runtime/tests/test_memory_store.py` and `test_memory_adapter_contract.py` - existing behavior and contract boundaries.
- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` - fixture validation support.

### Secondary (MEDIUM confidence)

- `docs/architecture/memory/external-memory-adapter-recommendation.md` - Phase 18 recommendation preserving platform-native memory as current legal path.

### Tertiary (LOW confidence)

- None used.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - repo-local package has zero dependencies, Python/stdout commands verified `sqlite3`, and roadmap requires no external memory dependency.
- Architecture: HIGH - based on shipped Phase 17/18 runtime classes, adapter protocol, and contract schemas.
- Pitfalls: MEDIUM - privacy and scope pitfalls are verified locally; scale/concurrency concerns are inferred from SQLite/storage design.

**Research date:** 2026-07-02
**Valid until:** 2026-08-01 for repo-local architecture; re-check if Phase 20 is delayed past major runtime/schema changes.
