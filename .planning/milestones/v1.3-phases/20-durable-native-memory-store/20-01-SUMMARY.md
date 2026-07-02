---
phase: "20-durable-native-memory-store"
plan: "20-01"
title: "SQLiteMemoryStore durable core"
status: complete
completed: "2026-07-02"
duration: "~15min"
tasks_completed: 3
files_changed: 4
---

# Plan 20-01 Summary: SQLiteMemoryStore Durable Core

## What Was Done

Implemented the durable platform-native SQLite memory store and extracted shared helpers.

### New files
- `packages/platform-runtime/src/platform_runtime/sqlite_memory.py` — `SQLiteMemoryStore` using stdlib `sqlite3` only; three tables (`memory_records`, `memory_candidates`, `memory_uses`); full CRUD for records, candidates, and uses; `expire_records`, `export_records`, `capability_manifest`
- `packages/platform-runtime/tests/test_sqlite_memory_store.py` — 13 focused tests covering durable reload, privacy rejection, tenant isolation, search ranking, tombstone, export-includes-deleted, candidate/use persistence, TTL expiry, SQL injection safety, manifest, and protocol conformance

### Modified files
- `packages/platform-runtime/src/platform_runtime/memory.py` — Added `MemoryQuery` lifecycle filter fields (`sensitivities`, `statuses`, `minimum_confidence`, `ttl_expires_before`, `ttl_expires_after`, `include_deleted`, `include_expired`) with defaults for backward compatibility; added `_validate_candidate`, `_validate_use`, `_copy_candidate`, `_copy_use`, `_search_records` shared helpers; refactored `InMemoryMemoryStore.search` to use `_search_records`
- `packages/platform-runtime/src/platform_runtime/__init__.py` — Added `SQLiteMemoryStore` to public exports

## Key Decisions

- Used `:memory:` SQLite by default so tests never touch disk
- Stored all arrays/objects as JSON TEXT columns; no BLOB types
- `list_for_query` applies coarse SQL filters (parameterized) then Python `_record_visible` post-filter
- `export_records` bypasses visibility filter to include deleted/expired records
- Shared `_search_records` helper removes ranking duplication from `InMemoryMemoryStore`

## Test Results

- 13 new SQLiteMemoryStore tests: all pass
- All 112 runtime tests (99 pre-existing + 13 new): pass
