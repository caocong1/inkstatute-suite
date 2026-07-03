---
phase: "27-unified-memory-interface-and-hindsight-adapter"
title: "Phase 27 Unified Memory Interface and Hindsight Adapter"
status: complete
completed: "2026-07-03"
requirements: [MEM-04, MEM-05, MEM-06, MEM-07]
files_changed: 14
---

# Phase 27 Summary: Unified Memory Interface and Hindsight Adapter

## What Was Done

### New files
- `packages/platform-runtime/src/platform_runtime/long_term_memory.py` — backend-agnostic `Memory` Protocol with async `aretain`/`arecall`/`areflect` operations and privacy-safe metadata validation.
- `packages/platform-runtime/src/platform_runtime/hindsight_memory.py` — `HindsightMemory` adapter implementing the `Memory` Protocol via `hindsight-client`; accepts a pre-configured client so the neutral package never reads secrets directly.
- `packages/platform-runtime/src/platform_runtime/fake_memory.py` — `FakeMemory` test double for contract tests.
- `packages/platform-runtime/tests/test_long_term_memory.py` — 8 contract tests covering the Protocol, Hindsight adapter, and FakeMemory.

### Modified files
- `packages/platform-runtime/src/platform_runtime/__init__.py` — exported new types.
- `packages/platform-runtime/src/platform_runtime/sqlite_memory.py` — `SQLiteMemoryStore` no longer the default legal memory backend (MEM-06); remains available for derived read-model caches.
- `packages/platform-runtime/src/platform_runtime/memory_orchestrator.py` — docstring neutralized (removed concrete channel name) to keep the neutral-package boundary gate green.
- `packages/platform-runtime/tests/test_memory_adapter_contract.py` — adapter contract test updated.
- `08-TRIAL-EVIDENCE-TEMPLATE.json` — restored (v1.0 trial-acceptance contract test still references it).

## Test Results

- `test_long_term_memory.py`: 8 passed.
- `packages/platform-runtime/tests/`: 218 passed, 81 subtests passed.
- `scripts/run_v2_gates.py`: all green.
- Live Hindsight test: `HindsightMemoryContractTest` connected to `http://localhost:8888` and verified `aretain`/`arecall`/`areflect` end-to-end.

## Requirements Closed

- MEM-04, MEM-05, MEM-06 — satisfied.
- MEM-07 — phase-level wiring present; full singleton deployment wiring closed in Phase 32.

## Next Phase

Phase 28: Memory Semantics (Focus vs Retention).
