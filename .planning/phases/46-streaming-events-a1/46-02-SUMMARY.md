---
phase: 46-streaming-events-a1
plan: 02
subsystem: api
tags: [streaming, sse, run-events, provider-model, openai, async-generator]

# Dependency graph
requires:
  - phase: 40-provider-model-prototype
    provides: ProviderModelBackendAdapter with injectable ProviderModelRunner and OpenAIClientRunner
provides:
  - StreamingProviderModelRunner Protocol for injected SSE streaming runners
  - ProviderModelStreamDelta frozen dataclass for SSE delta chunks
  - parse_sse_deltas() SSE line parser
  - FakeStreamingProviderModelRunner test helper
  - ProviderModelBackendAdapter.stream_events() async generator with terminal event guarantee
  - Configurable stream_event_support capability in provider_model manifest
affects: [provider-model-adapter, run-runtime, streaming-events-consumers]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Async-generator stream_events with try/except terminal STATE_CHANGED guarantee (SUCCEEDED/FAILED, never 'completed')"
    - "SSE 'data: ' line parsing with [DONE] end-of-stream marker and JSONDecodeError skip"
    - "Configurable manifest capability driven by injected runner presence"

key-files:
  created:
    - packages/backends/provider_model/tests/test_streaming_runner.py
    - packages/backends/provider_model/tests/test_stream_events.py
  modified:
    - packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py
    - packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py
    - packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py
    - packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py
    - packages/backends/provider_model/tests/test_adapter.py

key-decisions:
  - "Terminal event uses RunEventType.STATE_CHANGED + AsyncTaskState.SUCCEEDED/FAILED value (never 'completed')"
  - "stream_events uses platform_runtime.RunEvent (payload/metadata dicts), not platform_contract.RunEvent"
  - "stream_event_support capability is True only when a streaming_runner is injected"
  - "FakeStreamingProviderModelRunner.stream annotated as AsyncIterator to match the Protocol"

patterns-established:
  - "Streaming runner Protocol: single async stream(req) -> AsyncIterator[Delta] method"
  - "Terminal event guarantee: every stream_events() call ends with exactly one STATE_CHANGED event"
  - "Manifest capability configurability via keyword-only bool parameter"

requirements-completed:
  - STREAM-01

# Metrics
duration: 22min
completed: 2026-07-06
---

# Phase 46 Plan 02: Provider Model Adapter Streaming Events Summary

**ProviderModelBackendAdapter.stream_events() productized with real SSE delta streaming via injected StreamingProviderModelRunner, guaranteed terminal STATE_CHANGED event, and configurable stream_event_support capability**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-07-06T12:20:00Z
- **Completed:** 2026-07-06T12:42:00Z
- **Tasks:** 2
- **Files modified:** 5 (3 source + 2 test), 2 test files created

## Accomplishments
- Added `StreamingProviderModelRunner` Protocol and `ProviderModelStreamDelta` frozen dataclass to adapter.py, exported from the package
- Implemented `parse_sse_deltas()` SSE line parser and `FakeStreamingProviderModelRunner` test helper in openai_runner.py
- Replaced the `if False: yield` stub in `stream_events()` with a real async generator that yields MESSAGE_DELTA RunEvent records from injected streaming runner deltas, ending with a guaranteed terminal STATE_CHANGED event (SUCCEEDED on normal completion, FAILED on exception)
- Made `stream_event_support` capability configurable based on whether a streaming runner is injected (manifest accepts keyword-only `stream_event_support` parameter)
- Preserved `dependencies = []` invariant — openai SDK remains lazy-imported only inside OpenAIClientRunner.invoke

## Task Commits

Each task was committed atomically:

1. **Task 1: Add StreamingProviderModelRunner Protocol, ProviderModelStreamDelta dataclass, and SSE delta parser** - `cea11c7` (feat)
2. **Task 2: Implement ProviderModelBackendAdapter.stream_events() with terminal event guarantee + manifest update** - `fae672b` (feat)

## Files Created/Modified
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` - Added StreamingProviderModelRunner Protocol, ProviderModelStreamDelta dataclass, streaming_runner injection, _run_requests storage, real stream_events() async generator, _status_value helper, RunEvent/RunEventType imports
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` - Added parse_sse_deltas() SSE parser, FakeStreamingProviderModelRunner test helper, re-exports in __all__
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py` - Added stream_event_support keyword parameter to build_provider_model_manifest and provider_model_prototype_capabilities
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` - Exported StreamingProviderModelRunner, ProviderModelStreamDelta, FakeStreamingProviderModelRunner, parse_sse_deltas
- `packages/backends/provider_model/tests/test_streaming_runner.py` - 6 tests for parse_sse_deltas and FakeStreamingProviderModelRunner
- `packages/backends/provider_model/tests/test_stream_events.py` - 6 tests for stream_events terminal guarantee, delta streaming, exception handling, capability reflection
- `packages/backends/provider_model/tests/test_adapter.py` - Updated existing test to assert new terminal-event behavior (was asserting empty events list under old stub)

## Verification Results

- `python3 -m unittest packages.backends.provider_model.tests.test_streaming_runner -v` -> 6 tests OK
- `python3 -m unittest packages.backends.provider_model.tests.test_stream_events -v` -> 6 tests OK
- `python3 -m unittest discover -s packages/backends/provider_model/tests` -> 49 tests OK
- `python3 -m unittest discover -s packages/contract-test-suite/tests -p test_contract_freeze.py` -> 2 tests OK (no frozen surfaces modified)
- `python3 -m unittest discover -s packages/contract-test-suite/tests -p test_contract_count_freeze.py` -> 5 tests OK (BackendAdapter 9 methods, AdapterCapabilitySet 14 fields unchanged)
- Acceptance grep checks all pass (StreamingProviderModelRunner=1, ProviderModelStreamDelta=1, parse_sse_deltas=1, FakeStreamingProviderModelRunner=1, `if False`=0, exports work)

## Decisions Made
- Annotated `FakeStreamingProviderModelRunner.stream` return type as `AsyncIterator[ProviderModelStreamDelta]` (added AsyncIterator to openai_runner typing import) to match the StreamingProviderModelRunner Protocol signature exactly
- Re-exported StreamingProviderModelRunner and ProviderModelStreamDelta from openai_runner.__all__ (imported from .adapter) so the package re-export surface is consistent

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing test_adapter test to match new stream_events behavior**
- **Found during:** Task 2
- **Issue:** `test_stream_cancel_and_approval_are_deterministic_non_runner_paths` asserted `events == []` which matched the old `if False: yield` stub. The plan's Task 2 behavior explicitly requires stream_events to yield a single terminal STATE_CHANGED event when no streaming runner is injected, making the old assertion incorrect.
- **Fix:** Updated the assertion to expect exactly 1 event with event_type `state_changed` and payload status `succeeded`.
- **Files modified:** packages/backends/provider_model/tests/test_adapter.py
- **Verification:** `python3 -m unittest packages.backends.provider_model.tests.test_adapter -v` -> 11 tests OK
- **Committed in:** `fae672b` (part of task commit)

**2. [Note] Acceptance criteria grep count discrepancy for `stream_event_support=stream_event_support`**
- **Found during:** Task 2 verification
- **Issue:** The plan's acceptance criteria expected `grep -c 'stream_event_support=stream_event_support' manifest.py` to output `1`, but following the action steps exactly (step 6 adds the call-site in build_provider_model_manifest, step 7 changes the AdapterCapabilitySet field in provider_model_prototype_capabilities) produces `2` occurrences.
- **Fix:** Followed the explicit action steps (both changes required); the count of 2 is the correct result. The behavior is verified by tests and the capability reflection acceptance check.
- **Files modified:** none (no code change needed)
- **Verification:** capabilities() returns False without streaming runner, True with streaming runner

---

**Total deviations:** 1 auto-fixed (Rule 1) + 1 noted plan inconsistency
**Impact on plan:** Auto-fix necessary for correctness (existing test conflicted with new mandated behavior). No scope creep.

## Issues Encountered
- A parallel plan (46-01 codex backend streaming) had uncommitted working-tree changes and garbage artifact files (partial test-file copies with truncated names like `packages/back`, `packages/backends/provider`) present in the working directory. The first `git add -A` commit accidentally swept these codex changes and garbage files into the Task 2 commit. Resolved by soft-resetting the commit and re-staging only the provider_model files belonging to this plan. The codex changes were subsequently committed by the parallel 46-01 agent. No provider_model correctness impact.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Provider_model adapter now satisfies STREAM-01 with real SSE streaming and terminal event guarantee
- stream_event_support capability truthfully reflects streaming runner injection
- Frozen contract surfaces (BackendAdapter 9 methods, AdapterCapabilitySet 14 fields, RunEventType enum) unchanged
- Ready for downstream streaming event consumers and run-runtime integration

## Self-Check: PASSED

- FOUND: packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py
- FOUND: packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py
- FOUND: packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py
- FOUND: packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py
- FOUND: packages/backends/provider_model/tests/test_streaming_runner.py
- FOUND: packages/backends/provider_model/tests/test_stream_events.py
- FOUND: cea11c7 (Task 1 commit)
- FOUND: fae672b (Task 2 commit)

---
*Phase: 46-streaming-events-a1*
*Completed: 2026-07-06*
