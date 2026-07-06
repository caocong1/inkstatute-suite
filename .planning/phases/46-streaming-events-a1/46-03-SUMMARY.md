---
phase: 46-streaming-events-a1
plan: 03
subsystem: runtime
tags: [streaming, cancellation, async-generator, output-boundary, event-allowlist]

# Dependency graph
requires:
  - phase: 46-01
    provides: streaming lane feature flag and backend stream_events contract surface
  - phase: 46-02
    provides: real adapter streaming implementations used by cancellation integration test
provides:
  - Runtime stream() try/finally + aclose() cancellation propagation (STREAM-02)
  - DefaultAssistantOutputBoundary event-type allowlist blocking ERROR, TOOL_CALL_STARTED, TOOL_CALL_COMPLETED
  - event_type parameter wired through runtime _apply_output_boundary to the output boundary
  - AssistantOutputBoundary Protocol gains optional event_type parameter (additive, non-breaking)
affects: [streaming-events, output-boundary, channel-delivery, wecom-service]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "try/finally + aclose() on backend async generator for cancellation propagation"
    - "event-type allowlist frozenset for stream event filtering before text-content regex"

key-files:
  created:
    - packages/platform-runtime/tests/test_stream_cancellation.py
  modified:
    - packages/platform-runtime/src/platform_runtime/output_boundary.py
    - packages/platform-runtime/src/platform_runtime/runtime.py
    - packages/platform-runtime/src/platform_runtime/ports.py
    - packages/platform-runtime/tests/test_output_boundary.py

key-decisions:
  - "event_type allowlist uses RunEventType .value strings in a module-level frozenset for O(1) membership check"
  - "event_type=None preserves backward compatibility for non-stream callers (existing text regex applies)"
  - "cancellation tests explicitly call stream.aclose() to simulate client cancellation since breaking out of async for does not auto-close the generator"

patterns-established:
  - "Pattern 1: runtime stream() wraps backend generator in try/finally with await gen.aclose() to propagate GeneratorExit on cancellation or exception"
  - "Pattern 2: output boundary event-type allowlist runs before text-content regex filtering, returning BLOCK with reason=event_type_not_allowed for disallowed types"

requirements-completed:
  - STREAM-02

# Metrics
duration: 18min
completed: 2026-07-06
---

# Phase 46 Plan 03: Runtime Stream Cancellation Propagation + Output Boundary Event-Type Allowlist Summary

**try/finally + aclose() cancellation propagation in runtime stream() and event-type allowlist in DefaultAssistantOutputBoundary blocking ERROR/TOOL_CALL events**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-06T12:35:00Z
- **Completed:** 2026-07-06T12:53:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Runtime `stream()` wraps `backend.stream_events()` in `try/finally` with `await gen.aclose()`, propagating `GeneratorExit` to the adapter on client cancellation or exception (no zombie runs)
- `DefaultAssistantOutputBoundary.apply()` accepts optional `event_type` parameter and blocks `ERROR`, `TOOL_CALL_STARTED`, `TOOL_CALL_COMPLETED` via a module-level `_ALLOWED_STREAM_EVENT_TYPES` frozenset allowlist
- Runtime `_apply_output_boundary` passes `event.event_type` to the boundary's `apply()` method
- `AssistantOutputBoundary` Protocol in ports.py gains additive `event_type: str | None = None` parameter (non-breaking for existing structural implementations)
- 7 new event-type allowlist tests + 5 new cancellation propagation tests, all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add event-type allowlist to DefaultAssistantOutputBoundary + wire event_type through runtime** - `d9f8105` (feat)
2. **Task 2: Wrap runtime stream() in try/finally with aclose() for cancellation propagation** - `d9f8105` (feat, amended into implementation commit)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` - Added RunEventType import, `_ALLOWED_STREAM_EVENT_TYPES` frozenset, and `event_type` parameter + allowlist check in `apply()`
- `packages/platform-runtime/src/platform_runtime/runtime.py` - Wrapped `stream()` in try/finally with `await gen.aclose()`; passed `event_type=event.event_type` to boundary in `_apply_output_boundary`
- `packages/platform-runtime/src/platform_runtime/ports.py` - Added optional `event_type: str | None = None` to `AssistantOutputBoundary` Protocol `apply` signature
- `packages/platform-runtime/tests/test_output_boundary.py` - Added `EventTypeAllowlistTests` class with 7 tests; updated `CountingBoundary.apply` signature to accept `event_type`
- `packages/platform-runtime/tests/test_stream_cancellation.py` - New file with `TrackingFakeBackend` and 5 cancellation/aclose propagation tests

## Decisions Made
- Used `RunEventType.<NAME>.value` strings in the allowlist frozenset so membership checks compare against the string values that `RunEvent.event_type` carries at runtime
- Cancellation tests explicitly call `await stream.aclose()` after breaking out of the `async for` loop, because Python does not auto-close an async generator when the consumer simply breaks (closure happens on GC or explicit aclose); this accurately simulates a real client cancellation path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Updated CountingBoundary.apply signature to accept event_type**
- **Found during:** Task 1 (test_output_boundary.py)
- **Issue:** The existing `CountingBoundary` test helper in `RuntimeStreamBoundaryTests.test_stream_applies_boundary_to_every_yielded_event` overrides `apply()` without an `event_type` parameter. After wiring `event_type=event.event_type` through the runtime, this test would raise `TypeError: apply() got an unexpected keyword argument 'event_type'`.
- **Fix:** Added `event_type: str | None = None` parameter to `CountingBoundary.apply` and forwarded it to `super().apply(...)`.
- **Files modified:** packages/platform-runtime/tests/test_output_boundary.py
- **Verification:** `test_stream_applies_boundary_to_every_yielded_event` passes with the updated signature
- **Committed in:** d9f8105 (part of implementation commit)

**2. [Rule 3 - Blocking issue] Cancellation tests use explicit stream.aclose() instead of bare break**
- **Found during:** Task 2 (test_stream_cancellation.py)
- **Issue:** The plan's action described breaking after the first event to test cancellation. In Python, breaking out of `async for` over an async generator does not automatically close the generator, so the backend's `finally` cleanup flag was never set before the assertion.
- **Fix:** Rewrote `test_stream_cancellation_propagates_aclose` and `test_stream_no_zombie_after_cancellation` to obtain the stream iterator explicitly and call `await stream.aclose()` after breaking, which triggers the runtime's `finally` block and propagates `aclose()` to the backend generator.
- **Files modified:** packages/platform-runtime/tests/test_stream_cancellation.py
- **Verification:** All 5 cancellation tests pass
- **Committed in:** d9f8105 (part of implementation commit)

---

**Total deviations:** 2 auto-fixed (2x Rule 3 - blocking issues)
**Impact on plan:** Both auto-fixes were necessary for tests to pass with the new behavior. No scope creep; changes stay within the plan's file scope.

## Issues Encountered
- Pre-existing test failure: `test_runtime_source_does_not_embed_concrete_leak_examples` (forbidden='gateway') fails on the clean tree before any changes, caused by `model_gateway_enabled` field in `packages/platform-runtime/src/platform_runtime/feature_flags.py`. This is unrelated to Plan 03 and was confirmed via `git stash` baseline run. The V2 gate suite remains green (19 gates pass).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Runtime stream() now propagates cancellation to backends via aclose(); downstream channel delivery and WeCom service can rely on no zombie runs
- Output boundary event-type allowlist is active; channels will not receive ERROR or TOOL_CALL events from the runtime stream
- Ready for subsequent streaming plans that build on event-type-aware delivery and SSE/channel fan-out

## Self-Check: PASSED

- Commit `d9f8105` found in git log
- `packages/platform-runtime/tests/test_stream_cancellation.py` exists on disk
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` contains `_ALLOWED_STREAM_EVENT_TYPES`
- `packages/platform-runtime/src/platform_runtime/runtime.py` contains `gen.aclose` and `finally`
- V2 gate suite: 19 gates green (exit 0)

---
*Phase: 46-streaming-events-a1*
*Completed: 2026-07-06*
