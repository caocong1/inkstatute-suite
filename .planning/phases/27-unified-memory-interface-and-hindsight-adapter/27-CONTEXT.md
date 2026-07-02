# Phase 27 Context: Unified Memory Interface and Hindsight Adapter

**Date:** 2026-07-03
**Phase goal:** Define a single backend-agnostic `Memory` interface and implement it with Hindsight as the primary long-term memory backend.

---

## Current State

- Phase 26 selected Hindsight as the v1.4 long-term memory backend.
- A live Hindsight smoke test succeeded with local Ollama (qwen2.5:3b + nomic-embed-text).
- The existing runtime has a `MemoryStoreAdapter` Protocol in `memory_adapters.py` oriented toward native/SQLite stores (upsert/search/mark_deleted/export_records).
- `SQLiteMemoryStore` is the current production default and implements `MemoryStoreAdapter`.
- `MemoryOrchestrator` consumes `MemoryStoreAdapter` and produces `MemoryUse` evidence.

## What Needs to Change

1. Hindsight is not a native record store; it exposes `retain`, `recall`, and `reflect` operations.
2. The runtime needs a higher-level `Memory` abstraction that maps naturally to Hindsight.
3. The old `MemoryStoreAdapter` surface can be retained for SQLite and native stores, but the primary runtime seam should be the new `Memory` interface.
4. The default memory path must become Hindsight-backed; SQLite must become optional (read-model cache only).

## Key Decisions Already Made

- Hindsight is the primary backend for v1.4.
- Runtime secrets must stay outside the repo.
- Contract tests must not require a live provider.
- Existing V2 gates must remain green.

---

## Open Questions

1. Should the new `Memory` interface be async? Hindsight client is async-first.
2. How should tenant/workspace isolation map to Hindsight banks? One bank per user/workspace?
3. Should we keep the old `MemoryOrchestrator` or introduce a new `HindsightMemoryOrchestrator`?
4. What is the minimal cut to make Phase 27 shippable without breaking Phase 28/29 integration?

---

## Suggested Minimal Shippable Scope

- Define `Memory` interface: `aretain`, `arecall`, `areflect`.
- Implement `HindsightMemory` adapter using `hindsight-client` with environment-configurable base URL and key.
- Implement a fake in-memory `Memory` for contract tests.
- Add contract tests for the interface and adapter mapping.
- Deprecate the SQLite default path: keep SQLite as a `MemoryStoreAdapter` implementation but remove it as the default runtime dependency.
- Export the new types from `platform_runtime.__init__`.
