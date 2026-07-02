---
phase: "21-rolling-summary-pipeline"
plan: "21-01"
title: "RollingSummaryPolicy, RollingSummaryTrigger, and RollingSummaryProducer core"
status: complete
completed: "2026-07-02"
duration: "~20min"
tasks_completed: 4
files_changed: 3
---

# Plan 21-01 Summary: Rolling Summary Pipeline Core

## What Was Done

Added the policy-driven rolling summary pipeline on top of the existing `RollingSummaryRecord` and `InMemoryRollingSummaryStore`.

### New files
- `packages/platform-runtime/src/platform_runtime/rolling_summary.py` — `SummaryPrivacyError`, `RollingSummaryPolicy`, `RollingSummaryTrigger`, `RollingSummaryProducer`
- `packages/platform-runtime/tests/test_rolling_summary.py` — 21 tests covering all trigger modes, producer fields, fail-closed, privacy rejection, copy safety, and ContextBundle summary text exclusion

### Modified files
- `packages/platform-runtime/src/platform_runtime/__init__.py` — exported four new types

## Key Decisions

- `rolling_summary.py` is a new module; `context_assembler.py` is unchanged
- `RollingSummaryTrigger.should_trigger` returns `(bool, reason_code)` — reason is one of `explicit_request`, `task_completion`, `budget_pressure`, `turn_count`, `none`
- `RollingSummaryProducer` fails closed on: wrong `summary_ref` prefix, empty `source_refs` (when `require_source_refs=True`), forbidden metadata keys, and secret-like key names
- When `existing` record is provided, `created_at` is preserved; `updated_at` uses the new clock
- Privacy validation is recursive — same pattern as `memory.py`

## Test Results

- 21 new rolling summary tests: all pass
- All 138 runtime tests (117 pre-existing + 21 new): pass
