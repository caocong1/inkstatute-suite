---
phase: "22-recall-orchestrator-context-injection"
plan: "22-01"
title: "MemoryOrchestrator recall, isolation, and ContextBundle assembly"
status: complete
completed: "2026-07-02"
duration: "~20min"
tasks_completed: 3
files_changed: 3
---

# Plan 22-01 Summary: MemoryOrchestrator Core

## What Was Done

### New files
- `packages/platform-runtime/src/platform_runtime/memory_orchestrator.py` — `MemoryOrchestratorPolicy`, `MemoryOrchestrator`, `OrchestratorIsolationError`
- `packages/platform-runtime/tests/test_memory_orchestrator.py` — 13 tests covering all REC-01..REC-05

### Modified files
- `packages/platform-runtime/src/platform_runtime/__init__.py` — exported three new types

## Key Decisions

- `MemoryOrchestrator` is standalone; `DefaultRunRuntime` and WeCom constructors unchanged
- Isolation enforced via `_check_isolation` before query is sent to store
- `record_memory_use` uses `hasattr` guard — silently skips for `InMemoryMemoryStore`
- `RollingSummaryRecord` injected via `summary_store.get(scope, session_id)` — no raw text in bundle

## Test Results

- 13 new orchestrator tests: all pass
- 1 pre-existing `test_output_boundary` failure (WeCom word scan in fakes.py) — not introduced by Phase 22
