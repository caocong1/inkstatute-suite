---
phase: 07-ci-composability-and-privacy-gates
plan: 07-01
subsystem: testing
tags: [contract-gates, coverage, unittest, ci]
requires:
  - phase: 06-read-and-feedback-service-apis
    provides: read/feedback APIs and Phase 6 fixture evidence
provides:
  - repo-root local V2 gate runner
  - paired AgentTurn/AgentResult coverage reporter
  - sanitized fixture/runtime coverage status semantics
affects: [contract-test-suite, ci, privacy-gates, phase-08-trial]
tech-stack:
  added: []
  patterns: [stdlib subprocess gate runner, dataclass coverage reports, explicit PYTHONPATH]
key-files:
  created:
    - scripts/run_v2_gates.py
    - packages/contract-test-suite/src/contract_test_suite/coverage_report.py
    - packages/contract-test-suite/tests/test_coverage_report.py
  modified: []
key-decisions:
  - "Keep `scripts/run_v2_gates.py` as the local source of truth for CI-equivalent gates."
  - "Coverage reporting separates fixture evidence from sanitized runtime input and reports missing runtime input as `not_provided`."
  - "Threshold enforcement lives in `assert_coverage_thresholds`; summarizers remain inspectable report builders."
patterns-established:
  - "Repo-root gates run package/service unittest suites through explicit PYTHONPATH instead of installs."
  - "Coverage summaries expose counts and rates only, not raw event payloads."
requirements-completed:
  - REQ-composability-validation
  - REQ-security-privacy-baseline
  - REQ-v2-thin-contract-layer
duration: 5 min
completed: 2026-06-28
---

# Phase 07 Plan 07-01: Local V2 Gate Runner And Coverage Reporter Summary

**Repo-root V2 gate runner with sanitized paired turn/result coverage reporting for streams and fixture bundles**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-28T08:05:30Z
- **Completed:** 2026-06-28T08:10:51Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `scripts/run_v2_gates.py`, a dependency-free local command that runs all current platform, service, contract-suite, and compile gates.
- Added `contract_test_suite.coverage_report` for paired `AgentTurn`/`AgentResult` coverage and relationship breakage summaries.
- Added coverage tests proving stream and bundle coverage, threshold failures, runtime input absence, sanitized summaries, and sanitized runtime input semantics.

## Task Commits

1. **Task 1: Local gate runner skeleton** - `a1d02f6` (feat)
2. **Tasks 2-3: Coverage reporter and tests** - `4c59c57` (feat)

## Files Created/Modified

- `scripts/run_v2_gates.py` - repo-root local gate runner using stdlib subprocess and explicit `PYTHONPATH`.
- `packages/contract-test-suite/src/contract_test_suite/coverage_report.py` - coverage report dataclasses and threshold assertions.
- `packages/contract-test-suite/tests/test_coverage_report.py` - coverage behavior tests.

## Verification

- `python scripts/run_v2_gates.py --help` - passed.
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_coverage_report.py` - 5 tests passed.
- `python -m compileall scripts/run_v2_gates.py packages/contract-test-suite/src/contract_test_suite/coverage_report.py` - passed.
- `python scripts/run_v2_gates.py` - passed all gates:
  - platform-contract: 15 tests
  - wecom-service: 17 tests
  - hermes-contract-layer: 30 tests
  - conversation-read-view: 18 tests
  - feedback-service: 19 tests
  - contract-test-suite: 59 tests
  - compileall: passed

## Decisions Made

- Coverage summarizers build inspectable reports and do not enforce the 95% threshold directly; `assert_coverage_thresholds` owns policy enforcement.
- The local runner does not install packages or rely on editable installs.
- Fixture coverage remains explicitly non-live by default through `runtime_input_status="not_provided"`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Correctness] Moved coverage threshold enforcement out of summarizers**
- **Found during:** Task 3 coverage tests.
- **Issue:** `summarize_event_stream_coverage` failed before tests could inspect a below-threshold report.
- **Fix:** Return reports from summarizers and keep threshold checks in `assert_coverage_thresholds`.
- **Files modified:** `packages/contract-test-suite/src/contract_test_suite/coverage_report.py`
- **Verification:** Focused coverage tests and full local runner passed.
- **Committed in:** `4c59c57`

---

**Total deviations:** 1 auto-fixed correctness issue.
**Impact on plan:** The final behavior is cleaner: report construction and policy enforcement are separated without expanding scope.

## Issues Encountered

None beyond the auto-fixed threshold-placement issue above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Wave 2 can build privacy, composability, and thin-layer gates on top of the local runner and coverage reporting foundation.

---
*Phase: 07-ci-composability-and-privacy-gates*
*Completed: 2026-06-28*

