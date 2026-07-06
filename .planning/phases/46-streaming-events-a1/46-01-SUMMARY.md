# Plan 46-01 Summary: Codex Adapter Streaming Events

## Objective

Productize `CodexBackendAdapter.stream_events()` by replacing the `if False: yield` stub with a real async generator that yields `RunEvent` records from Codex exec JSONL streaming via an injected `StreamingCodexExecRunner` protocol. Every stream ends with a terminal `STATE_CHANGED` event with `status=SUCCEEDED` or `status=FAILED` (never "completed"). The manifest's `stream_event_support` capability becomes configurable based on whether a streaming runner is injected.

## Tasks Completed

### Task 1: StreamingCodexExecRunner Protocol, CodexStreamEvent dataclass, and JSONL stream parser

**Files modified:**
- `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` — Added `StreamingCodexExecRunner` Protocol (async `stream()` method) and `CodexStreamEvent` frozen dataclass (`event_type: str`, `payload: JsonObject`). Added `Iterator` to typing imports.
- `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py` — Added `parse_codex_jsonl_stream(lines)` generator that yields `CodexStreamEvent` records from JSONL lines (MESSAGE_DELTA for item.completed/updated, STATE_CHANGED+SUCCEEDED for turn.completed, STATE_CHANGED+FAILED for turn.failed/error). Added `FakeStreamingCodexRunner` test helper class. Updated imports (`RunEventType`, `CodexStreamEvent`, `StreamingCodexExecRunner`, `AsyncIterator`, `Iterator`). Updated `__all__`.
- `packages/backends/codex/src/inkstatute_backends_codex/__init__.py` — Added exports for `CodexStreamEvent`, `StreamingCodexExecRunner`, `FakeStreamingCodexRunner`, `parse_codex_jsonl_stream`.
- `packages/backends/codex/tests/fixtures/codex_exec_stream.jsonl` — Test fixture with 4 JSONL lines (thread.started, 2x item.completed assistant_message, turn.completed).
- `packages/backends/codex/tests/test_streaming_runner.py` — 4 tests: parse yields message deltas, parse yields failed on turn.failed, parse skips unparseable lines, FakeStreamingCodexRunner yields events.

**Commit:** `666de29` — `feat(46-01): add StreamingCodexExecRunner Protocol, CodexStreamEvent, and JSONL stream parser`

### Task 2: CodexBackendAdapter.stream_events() with terminal event guarantee + manifest update

**Files modified:**
- `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` — Replaced `if False: yield` stub with real async generator. Added `streaming_runner` parameter to `__init__`, `_run_requests` dict to store RunRequest per run. `submit_run` now stores the request. `stream_events` yields RunEvent records from the streaming runner with incremental seq numbers, guarantees terminal STATE_CHANGED event (SUCCEEDED on normal completion, FAILED on exception). `capabilities()` passes `stream_event_support` to manifest builder. Added `_status_value()` helper. Added `RunEvent` and `RunEventType` imports.
- `packages/backends/codex/src/inkstatute_backends_codex/manifest.py` — Added `stream_event_support: bool = False` keyword-only parameter to `build_codex_manifest()` and `codex_prototype_capabilities()`.
- `packages/backends/codex/tests/test_stream_events.py` — 6 tests: without streaming runner yields single terminal, with streaming runner yields deltas and terminal, terminal never says "completed", on exception yields failed terminal, unknown run raises KeyError, capabilities reflect streaming runner.
- `packages/backends/codex/tests/test_adapter.py` — Updated `test_stream_cancel_and_approval_are_deterministic_non_runner_paths` to expect terminal event instead of empty list (Rule 3 auto-fix: existing test matched old stub behavior).

**Commit:** `8f8cb76` — `feat(46-01): codex adapter streaming events with terminal event guarantee`

## Deviations

- **[Rule 3 - Auto-fix blocking issue]** Updated `test_stream_cancel_and_approval_are_deterministic_non_runner_paths` in `test_adapter.py` (line 149) to expect a single terminal STATE_CHANGED event instead of an empty list. The old assertion `self.assertEqual(events, [])` matched the `if False: yield` stub; the new behavior yields a terminal event per the plan's stream_events implementation.
- **[Plan discrepancy - non-blocking]** Acceptance criteria for Task 2 states `grep -c 'stream_event_support=stream_event_support' manifest.py` outputs `1`, but the plan's action steps 6 and 7 both specify `stream_event_support=stream_event_support`, resulting in 2 occurrences (one in `build_codex_manifest` call, one in `AdapterCapabilitySet` constructor). Both are correct per the action steps.

## Test Results

- **Codex package tests:** 42 tests pass (32 existing + 4 new streaming runner + 6 new stream events)
  - `python3 -m unittest discover -s packages/backends/codex/tests -v` — OK
- **Contract freeze tests:** 2 tests pass
  - `test_contract_freeze` — OK (schema files match baseline hash)
- **Contract count freeze tests:** 5 tests pass
  - `test_contract_count_freeze` — OK (BackendAdapter 9 methods, AdapterCapabilitySet 14 fields unchanged)
- **Codex backend contract tests:** 7 tests pass
  - `test_codex_backend_contract` — OK

## FROZEN Contract Surfaces Verified

- BackendAdapter: 9 methods (unchanged)
- AdapterCapabilitySet: 14 fields (unchanged)
- RunEventType enum: unchanged
- RunEvent dataclass: unchanged
- `dependencies = []` invariant preserved — no new external imports at module top level

## Key Design Decisions

1. **Terminal event uses STATE_CHANGED + status=SUCCEEDED/FAILED** — never "completed", matching the platform runtime lifecycle contract.
2. **`platform_runtime.RunEvent`** used (not `platform_contract.RunEvent`) — payload/metadata are `JsonObject` dicts.
3. **stream_event_support capability** is `False` by default, `True` only when a `StreamingCodexExecRunner` is injected via the `streaming_runner` parameter.
4. **Exception handling** catches `Exception` (not `GeneratorExit`) — yields a terminal FAILED event with sanitized error info (`code: "codex_stream_error"`, `message: exception type name`).
5. **`_status_value()` helper** converts `AsyncTaskState` to its string value, matching the pattern in `fakes.py` and `runtime.py`.
