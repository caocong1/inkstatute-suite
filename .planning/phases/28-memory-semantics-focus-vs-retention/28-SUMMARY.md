---
phase: "28-memory-semantics-focus-vs-retention"
title: "Phase 28 Memory Semantics Focus vs Retention"
status: complete
completed: "2026-07-03"
requirements: [MEM-08, MEM-09, MEM-10]
files_changed: 12
---

# Phase 28 Summary: Memory Semantics (Focus vs Retention)

## What Was Done

### New files
- `packages/platform-runtime/src/platform_runtime/memory_policy.py` — deterministic, LLM-free policy layer:
  - `MemoryContentClassifier` — classifies content as durable (`user_preference`, `project_fact`, `lesson_learned`) vs transient.
  - `MemoryRetentionPolicy` — defines which categories are retained.
  - `MemoryFocusPolicy` — defines recall scope (top-N by relevance, optional minimum threshold).
- `packages/platform-runtime/tests/test_memory_policy.py` — 10 policy tests.

### Modified files
- `packages/platform-runtime/src/platform_runtime/__init__.py` — exported policy types.
- `packages/platform-runtime/src/platform_runtime/fake_memory.py` — applies classifier before storage and focus policy during recall.
- `packages/platform-runtime/src/platform_runtime/hindsight_memory.py` — respects `focus_policy.max_results`, falls back to `input.max_results`.
- `packages/platform-runtime/src/platform_runtime/long_term_memory.py` — policy hooks added.

## Test Results

- `test_memory_policy.py`: 10 passed.
- `test_long_term_memory.py`: 8 passed.
- `packages/platform-runtime/tests/`: 228 passed, 81 subtests passed.
- `scripts/run_v2_gates.py`: all green.

## Design Notes

- Default retention allows `user_preference`, `project_fact`, `lesson_learned`.
- Default focus recalls top-N by relevance with no minimum threshold.
- Classifier is deterministic and LLM-free, satisfying the CI-without-live-provider requirement (MEM-18 foundation).

## Requirements Closed

- MEM-08, MEM-09, MEM-10 — satisfied.

## Next Phase

Phase 29: WeCom/Runtime Integration.
