---
phase: 10-embeddable-runruntime-fake-backend
plan: 10-03
subsystem: runtime
tags: [python, platform-runtime, output-boundary, streaming, privacy-audit]

# Dependency graph
requires:
  - phase: 10-embeddable-runruntime-fake-backend
    provides: [DefaultRunRuntime lifecycle, fake backend stream events, default-off runtime feature flags]
provides:
  - neutral assistant output boundary with allow/rewrite/block decisions
  - runtime stream enforcement for visible message deltas
  - sanitized hash-only policy audit metadata for stream output decisions
  - leak fixture tests for allowed, lifecycle, tool approval, and secret/path stream samples
affects: [platform-runtime, run-runtime, output-boundary, contract-test-suite]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - generic output-boundary rule IDs with hash-only audit metadata
    - cloned stream events for policy-enforced visibility without backend event mutation
    - fake backend stream scripting for deterministic leak fixture tests

key-files:
  created:
    - packages/platform-runtime/src/platform_runtime/output_boundary.py
    - packages/platform-runtime/tests/test_output_boundary.py
  modified:
    - packages/platform-runtime/src/platform_runtime/__init__.py
    - packages/platform-runtime/src/platform_runtime/runtime.py
    - packages/platform-runtime/src/platform_runtime/fakes.py

key-decisions:
  - "DefaultRunRuntime now defaults to DefaultAssistantOutputBoundary so visible stream deltas cannot bypass policy when callers omit an explicit boundary."
  - "Allow decisions preserve visible business/legal text exactly while still attaching sanitized policy metadata to cloned stream events."
  - "Block decisions yield a sanitized stream event with visible text removed and hash-only audit metadata, never the original blocked text."

patterns-established:
  - "Runtime output-boundary source uses generic rule names and keeps concrete leak samples in tests only."
  - "Policy audit metadata records rule_id, input_hash_prefix, input_length, and privacy=no_original_text_stored."
  - "Runtime stream enforcement uses dataclass replacement and copied mappings to avoid mutating backend events."

requirements-completed:
  - REQ-platform-run-runtime
  - REQ-runlane-output-boundary

# Metrics
duration: 5m56s
completed: 2026-06-28
---

# Phase 10 Plan 10-03: Streaming Output Boundary For Run Events Summary

**Runtime stream deltas now pass through a neutral assistant output boundary with exact allow preservation, owned rewrites, sanitized blocks, and hash-only audit evidence**

## Performance

- **Duration:** 5m56s
- **Started:** 2026-06-28T19:55:39Z
- **Completed:** 2026-06-28T20:01:35Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added `BoundaryAction`, `BoundaryDecision`, and `DefaultAssistantOutputBoundary` with generic allow/rewrite/block rules and no concrete backend/channel leak samples in runtime source.
- Wired `DefaultRunRuntime.stream` so every visible stream delta is policy-processed before yielding to ordinary-user visibility.
- Added deterministic stream leak coverage proving allowed business/legal text is unchanged, owned rewrites contain no backend terms, and blocked originals never appear in yielded events or audit metadata.

## Task Commits

Each task was committed atomically:

1. **Task 10-03-01: Create neutral assistant output-boundary implementation** - `90fb3d0` (feat)
2. **Task 10-03-02: Apply output boundary to runtime stream events** - `fc04b91` (feat)
3. **Task 10-03-03: Add leak fixture tests for stream output policy behavior** - `ba20397` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `packages/platform-runtime/src/platform_runtime/output_boundary.py` - Neutral boundary implementation with generic rule IDs, owned service rewrite text, and hash-only audit metadata.
- `packages/platform-runtime/src/platform_runtime/runtime.py` - Applies the boundary to visible stream text, yields cloned events, and removes visible text for blocked deltas.
- `packages/platform-runtime/src/platform_runtime/fakes.py` - Adds `append_message_delta` for deterministic fake stream fixture setup.
- `packages/platform-runtime/src/platform_runtime/__init__.py` - Exports boundary types and default implementation.
- `packages/platform-runtime/tests/test_output_boundary.py` - Covers boundary decisions, audit privacy, source neutrality, stream gating, allow/rewrite/block behavior, and backend event immutability.

## Decisions Made

- Default runtime construction uses `DefaultAssistantOutputBoundary` when no boundary is injected, because visible stream paths must fail closed through policy rather than relying on host setup.
- Rewritten stream text uses an InkStatute-owned neutral service notice and never includes backend, channel, or operator terms.
- Blocked stream deltas remain observable only as sanitized policy metadata with visible text removed; original blocked/replaced text is never stored in audit metadata.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed output-boundary rule priority for lifecycle rewrites containing slash commands**
- **Found during:** Task 10-03-01 (neutral assistant output-boundary implementation)
- **Issue:** A self-update lifecycle notice containing a slash command matched the hard-block operator command rule before the lifecycle rewrite rule.
- **Fix:** Split hard-block rules from operator-command rules so secret-like values, internal paths, and debug traces still block first; lifecycle/progress/approval notices rewrite before standalone operator commands block.
- **Files modified:** `packages/platform-runtime/src/platform_runtime/output_boundary.py`, `packages/platform-runtime/tests/test_output_boundary.py`
- **Verification:** `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/platform-runtime/tests/test_output_boundary.py` exited 0.
- **Committed in:** `90fb3d0`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix preserves the plan's rewrite/block distinction and does not expand runtime scope.

## Issues Encountered

- Initial Task 10-03-01 boundary test run failed on lifecycle rewrite priority; fixed before the task commit.

## Verification

- `python -m compileall packages/platform-runtime/src packages/platform-runtime/tests` exited 0:
  - `Listing 'packages/platform-runtime/src'...`
  - `Listing 'packages/platform-runtime/src/platform_runtime'...`
  - `Listing 'packages/platform-runtime/tests'...`
- `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/platform-runtime/tests/test_output_boundary.py packages/platform-runtime/tests/test_run_runtime_lifecycle.py` exited 0: ran 19 tests, OK.
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_boundary_allowlist.py packages/contract-test-suite/tests/test_thin_layer_boundaries.py` exited 0: ran 18 tests, OK.

## Known Stubs

None. Stub scan found no placeholder/TODO/FIXME/empty UI-data patterns in files created or modified by this plan.

## Threat Flags

None. The plan adds library-only stream filtering and fake test support; it introduces no network endpoint, auth path, file access path, database, queue, service process, or trust-boundary schema change beyond the planned runtime stream boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 10-04 to add contract fixture and replay evidence for the fake runtime lane. The streaming boundary is default-off through `streaming_lane_enabled`, policy-enforced when enabled, and validated against source neutrality and leak fixtures.

## Self-Check: PASSED

- Created/modified files exist: `output_boundary.py`, `test_output_boundary.py`, `runtime.py`, `fakes.py`, `__init__.py`, and this summary.
- Task commits exist: `90fb3d0`, `fc04b91`, and `ba20397`.

---
*Phase: 10-embeddable-runruntime-fake-backend*
*Completed: 2026-06-28*
