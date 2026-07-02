---
phase: 16-short-term-context-assembler
plan: 16-02
subsystem: platform-runtime
tags: [python, stdlib, run-runtime, context-bundle, interrupts, privacy, tdd]
requires:
  - phase: 16-short-term-context-assembler
    provides: Plan 16-01 ContextAssembler and ContextBundle assembly policy
  - phase: 15-session-resolver-and-interrupt-runtime
    provides: interrupt resume lifecycle, SessionScope, and PendingInterruptSnapshot support
provides:
  - Default-off RuntimeFeatureFlags.context_assembly_enabled lane
  - Optional DefaultRunRuntime ContextAssembler injection
  - Backend-bound RunRequest metadata replacement with sanitized ContextBundle evidence
  - create_run and resume_interrupt context assembly tests with privacy and idempotency coverage
affects: [phase-16, phase-17-memory-contracts, backend-adapters, platform-runtime]
tech-stack:
  added: []
  patterns: [default-off feature flag, dependency-injected assembler, dataclasses.replace request cloning, reference-first contract-log evidence]
key-files:
  created:
    - .planning/phases/16-short-term-context-assembler/16-02-SUMMARY.md
  modified:
    - packages/platform-runtime/src/platform_runtime/feature_flags.py
    - packages/platform-runtime/src/platform_runtime/runtime.py
    - packages/platform-runtime/tests/test_run_runtime_lifecycle.py
key-decisions:
  - "Context assembly remains opt-in and fails before backend submission when enabled without an injected assembler."
  - "Runtime request metadata is cloned and replaced rather than mutating caller-owned RunRequest objects."
  - "Resume interrupt assembly runs after scope/pending validation and after sanitized resume metadata is built, preserving interrupt and output-policy refs."
patterns-established:
  - "ContextBundle events are appended before run records when contract logging is enabled."
  - "Runtime context assembly input is built from refs, IDs, hashes, lengths, and output policy refs, not raw turn or answer text."
requirements-completed: [STM-01, STM-02, STM-04]
duration: 7min
completed: 2026-07-01T11:30:02Z
---

# Phase 16 Plan 16-02: Runtime Opt-In Wiring Summary

**Default-off runtime context assembly now attaches sanitized ContextBundle metadata to create-run and interrupt-resume backend requests.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-01T11:23:29Z
- **Completed:** 2026-07-01T11:30:02Z
- **Tasks:** 2
- **Files modified:** 3 source/test files plus this summary

## Accomplishments

- Added `RuntimeFeatureFlags.context_assembly_enabled`, defaulting to `False` and enforced by the existing `require_enabled` path.
- Extended `DefaultRunRuntime` with optional `ContextAssembler` injection and pre-submit `RunRequest` replacement for context-enabled `create_run`.
- Routed `resume_interrupt` through the same context assembly helper after pending-interrupt validation while preserving sanitized resume metadata.
- Added lifecycle tests for default-off behavior, missing dependency failure before backend submission, create-run metadata replacement, context contract-log privacy, resume protected refs, output-policy refs, and duplicate resume idempotency.

## Task Commits

Each TDD gate was committed separately:

1. **Task 1 RED:** `4b628c2` test(16-02): add failing context assembly create-run tests
2. **Task 1 GREEN:** `9a1b179` feat(16-02): wire create-run context assembly lane
3. **Task 2 RED:** `12a3537` test(16-02): add failing context assembly resume tests
4. **Task 2 GREEN:** `1538867` feat(16-02): preserve context assembly on interrupt resume

## Files Created/Modified

- `packages/platform-runtime/src/platform_runtime/feature_flags.py` - Added the default-off `context_assembly_enabled` flag.
- `packages/platform-runtime/src/platform_runtime/runtime.py` - Added optional assembler injection, context input construction, request metadata replacement, context bundle logging, and resume-interrupt wiring.
- `packages/platform-runtime/tests/test_run_runtime_lifecycle.py` - Added runtime integration coverage for create-run and resume context assembly behavior.
- `.planning/phases/16-short-term-context-assembler/16-02-SUMMARY.md` - Plan execution summary.

## Decisions Made

- Kept context assembly strictly default-off and dependency-injected; enabling it without `context_assembler` raises `RunRuntimeStateError` before `BackendAdapter.submit_run`.
- Used `dataclasses.replace` with cloned metadata to avoid mutating caller-owned `RunRequest` objects or their metadata dictionaries.
- Used request and output-constraint metadata refs as the runtime source for recent turns, memory refs, current-turn refs, and output-policy refs; no backend, channel, tokenizer, database, or external memory dependency was introduced.
- Appended `context_bundle` contract-log records before `run` and `run_event` records when contract logging is enabled.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Optional output refs were treated as mandatory**
- **Found during:** Task 1 implementation verification
- **Issue:** The initial helper reused the required current-turn-ref lookup for optional output constraint refs, causing context-enabled create_run without output constraints to raise `RunRuntimeStateError`.
- **Fix:** Split optional ref lookup into `_optional_first_text` while keeping current-turn ref mandatory.
- **Files modified:** `packages/platform-runtime/src/platform_runtime/runtime.py`
- **Verification:** `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_run_runtime_lifecycle.py` passed.
- **Committed in:** `9a1b179`

**Total deviations:** 1 auto-fixed bug.
**Impact on plan:** The fix was required for default create_run behavior and did not expand scope.

## Issues Encountered

- Existing unrelated dirty files were present before execution in `.planning/`, `packages/platform-contract/`, and `packages/contract-test-suite/`. They were not staged, reverted, or modified by this plan.
- Per the execution scope, `STATE.md` and `ROADMAP.md` were not modified; shared tracking remains owned by the orchestrator.

## Verification

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_run_runtime_lifecycle.py` passed: 18 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` passed: 75 tests.
- `rg -n "context_assembly_enabled|context_assembler|context_bundle" packages/platform-runtime/src/platform_runtime/feature_flags.py packages/platform-runtime/src/platform_runtime/runtime.py packages/platform-runtime/tests/test_run_runtime_lifecycle.py` confirmed expected symbols and coverage.

## Known Stubs

None. Empty defaults and `None` defaults in runtime constructors/tests are normal optional dependency and fixture defaults, not unfinished data-source stubs.

## Threat Flags

None. This plan added no new network endpoint, auth path, file access path, service, database, queue, or external memory adapter. The only trust-boundary change is the planned backend-bound sanitized `context_bundle` metadata path.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 16 can proceed to contract-test-suite fixture evidence or downstream memory-context integration with runtime assembly now available behind an explicit opt-in flag. Backend adapters can inspect `RunRequest.metadata["context_bundle"]` when hosts enable the lane.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/16-short-term-context-assembler/16-02-SUMMARY.md`.
- Task commits exist: `4b628c2`, `9a1b179`, `12a3537`, `1538867`.
- No tracked files were deleted by task commits.
- Only plan-scoped source/test files and this summary were staged for 16-02 commits.

---
*Phase: 16-short-term-context-assembler*
*Completed: 2026-07-01*
