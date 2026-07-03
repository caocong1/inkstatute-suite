---
phase: "29-wecom-runtime-integration"
title: "Phase 29 WeCom Runtime Memory Integration"
status: complete
completed: "2026-07-03"
requirements: [MEM-11, MEM-12, MEM-13]
files_changed: 8
---

# Phase 29 Summary: WeCom/Runtime Integration

## What Was Done

### New files
- `services/wecom-service/src/wecom_service/memory_integration.py` — memory integration helpers.
- `services/wecom-service/tests/test_session_memory_integration.py` — 3 integration tests.

### Modified files
- `services/wecom-service/src/wecom_service/session_runtime.py` — `WeComSessionRuntime` now accepts a `Memory`:
  - Pre-turn recall via `_with_recall_context` before `runtime.create_run`.
  - Recall result injected as safe metadata (`memory_recall_summary`: refs + count only; raw memory texts stay in the backend).
  - Post-turn retention exposed as `finalize_memory()` (final reply text is produced after `handle_turn` returns).
  - Configurable failure mode; default `fail_open` so memory problems never break the user-facing reply.

## Test Results

- `test_session_memory_integration.py`: 3 passed (incl. `test_memory_failure_does_not_block_response`).
- `services/wecom-service/tests/`: 63 passed, 11 subtests passed.
- `scripts/run_v2_gates.py`: all green.

## Design Notes

- Hermes one-shot adapter unchanged — no edits to `hermes-contract-layer` (MEM-12).
- Output policy and delivery guard behavior preserved; memory integration does not leak internal notices or raw payloads (MEM-13).
- Actual recalled memory texts are not embedded in the run request metadata — privacy-safe.

## Requirements Closed

- MEM-11, MEM-12, MEM-13 — satisfied.

## Next Phase

Phase 30: Error Handling and Observability.
