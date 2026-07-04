---
phase: 41
plan: 41-02
title: "Trace Reconstruction by trace_id and CSV/JSON Export"
wave: 2
requirements:
  - READVIEW-02
  - READVIEW-03
status: complete
---

# Plan 41-02 — Summary

## Tasks Completed

| Task ID | Description | Commit |
|---------|-------------|--------|
| 41-02-01 | Extend `ContractLogReadModel` with `trace_events` index, `turn_to_trace` reverse index, and `get_trace_reconstruction(trace_id)` method; create `test_trace_reconstruction.py` with 8 `TraceReconstructionTests` | `fa8b589` |
| 41-02-02 | Add `/traces/{trace_id}` route to `api.py` with 404 for unknown trace_id and scrub via `_with_contract_metadata`; add 5 `TraceRouteTests` | `99d900b` |
| 41-02-03 | Create `export.py` with CSV/JSON serializers (stdlib only), add `/export` route to `api.py`, update `__init__.py` exports, create `test_export.py` with 12 `ExportTests` | `7fa1035` |

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| `test_trace_reconstruction.py` (TraceReconstructionTests) | 8 | PASS |
| `test_trace_reconstruction.py` (TraceRouteTests) | 5 | PASS |
| `test_export.py` (ExportTests) | 12 | PASS |
| Full conversation-read-view discover suite | 90 | PASS |
| `test_phase6_read_feedback_apis.py` (cross-package) | 6 | PASS |
| Full V2 gate suite (`scripts/run_v2_gates.py`) | 13 gates | PASS (exit 0) |

**Total: 90 conversation-read-view tests + 6 cross-package tests — all green, 0 failures.**

## Files Modified/Created

| File | Action |
|------|--------|
| `services/conversation-read-view/src/conversation_read_view/read_model.py` | Modified — added `trace_events` and `turn_to_trace` indexes to `__init__`/`from_records`, added `get_trace_reconstruction` method |
| `services/conversation-read-view/src/conversation_read_view/export.py` | Created — CSV/JSON export serializers using stdlib `csv`, `io`, `json` only |
| `services/conversation-read-view/src/conversation_read_view/api.py` | Modified — added `/traces/{trace_id}` route, `/export` route, `_handle_export` helper |
| `services/conversation-read-view/src/conversation_read_view/__init__.py` | Modified — exported `export_csv`, `export_json`, `csv_metadata`, `CONVERSATION_CSV_COLUMNS`, `TASK_CSV_COLUMNS` |
| `services/conversation-read-view/tests/test_trace_reconstruction.py` | Created — 13 tests across 2 test classes |
| `services/conversation-read-view/tests/test_export.py` | Created — 12 tests in `ExportTests` |

## Key Implementation Details

- **Trace reconstruction:** `get_trace_reconstruction(trace_id)` collects all `_Record` objects sharing the same `trace_id` from the `trace_events` index (built during `from_records`). Events are joined via `turn_id` — `trace_id` is resolved from `ExecutionTrace.trace_id` or `AgentResult.metadata.trace_id`, then all records with that `turn_id` are grouped. The `turn_to_trace` reverse index supports fallback lookups.
- **Occurrence order:** Events are sorted by `(occurred_at, ingested_at, seq)` via `_record_sort_key`.
- **`reconstruction_complete`:** `True` when an `execution_trace` event is present in the reconstructed set; `False` for partial traces (no execution_trace).
- **All 5 event types:** AgentTurn, RouteDecision, ExecutionTrace, AgentResult, and FeedbackEvent can all appear in the reconstruction (verified with synthetic fixtures).
- **`/traces/{trace_id}` route:** Returns 200 with scrubbed reconstruction body via `_with_contract_metadata`; 404 for unknown trace_id via `not_found_response`.
- **`/export` endpoint:** Accepts `resource=conversations|tasks`, `format=csv|json` (default json), plus `from`/`to`/`user_id`/`channel`/`status` filters and `limit` (clamped to `MAX_RESULT_LIMIT`). No cursor pagination (single bounded batch). Unknown `resource`/`format` → 400.
- **CSV export:** Uses stdlib `csv.DictWriter` with flat projection. Conversations: `conversation_id,turn_count,user_ids,occurred_at`. Tasks: `task_id,turn_id,conversation_id,trace_id,status,occurred_at`. Nested fields omitted.
- **JSON export:** Returns scrubbed items array with count and metadata.
- **Privacy:** All new endpoints route through `scrub_contract_payload` — JSON items scrubbed before serialization, CSV items scrubbed before projection. Verified by `test_export_json_items_are_scrubbed` and `test_export_csv_items_are_scrubbed` (raise `ValueError` on forbidden keys).
- **Backward compatibility:** Existing `/conversations/{id}`, `/tasks/{id}`, `/feedback`, `/conversations` list, `/tasks` list routes are unchanged. No existing test files modified.
- **Dependencies:** `pyproject.toml` still has `dependencies = []` — `export.py` imports only stdlib (`csv`, `io`, `json`, `typing`).
- **Contract freeze:** No files in `packages/platform-contract/` or `packages/platform-runtime/protocols.py` were modified.

## Deviations from Plan

- **`_handle_export` filter parsing:** The plan specified reusing `_parse_list_filters` from Wave 1, but `resource` and `format` query parameters would be rejected as unknown filters. The implementation strips `resource` and `format` from the query dict before passing to `_parse_list_filters`. This is consistent with the plan's intent (filters are `from`/`to`/`user_id`/`channel`/`status` only).
- **CSV `occurred_at` enrichment:** The plan noted that the caller must include `occurred_at` in the item dict for CSV projection. The implementation enriches each scrubbed item with `occurred_at` from the `(sort_key, occurred_at, item)` tuple before passing to `export_csv`.

## EXECUTION COMPLETE
