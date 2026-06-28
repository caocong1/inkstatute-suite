---
phase: 08-lawyer-trial-acceptance
plan: 08-01
subsystem: testing
tags: [trial-acceptance, unittest, metrics, privacy]
requires:
  - phase: 07-ci-composability-and-privacy-gates
    provides: local V2 gates and sanitized coverage-reporting patterns
provides:
  - Phase 8 trial evidence row model
  - dependency-free lawyer-trial threshold evaluator
  - sanitized trial acceptance summary and assertion helpers
affects: [contract-test-suite, phase-08-trial, lawyer-trial-acceptance]
tech-stack:
  added: []
  patterns: [stdlib dataclass reports, fail-closed live evidence gating, sanitized JSON summaries]
key-files:
  created:
    - packages/contract-test-suite/src/contract_test_suite/trial_acceptance.py
    - packages/contract-test-suite/tests/test_trial_acceptance.py
  modified: []
key-decisions:
  - "Only sanitized_runtime, operator_annotation, and live_external_ref rows count toward lawyer trial acceptance."
  - "Fixture rows can exercise readiness tooling but cannot pass live Phase 8 acceptance."
  - "Positive feedback below 60% can only produce passed_with_repair_plan when a repair plan ref is linked."
patterns-established:
  - "Trial reports expose counts, rates, status, and issue codes without raw task rows."
  - "Negative feedback and route mismatch failures remain explicit human-review evidence gates."
requirements-completed:
  - REQ-lawyer-trial-acceptance
  - REQ-v2-development-order
duration: 6 min
completed: 2026-06-28
---

# Phase 08 Plan 08-01: Trial Metrics Model And Acceptance Checker Summary

**Dependency-free Phase 8 lawyer-trial checker with live-evidence gating, PRD threshold evaluation, and sanitized summaries**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-28T09:32:42Z
- **Completed:** 2026-06-28T09:38:25Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added `TrialTaskEvidence`, `TrialAcceptanceIssue`, and `TrialAcceptanceReport` for minimized Phase 8 trial rows and report output.
- Added `evaluate_trial_acceptance` with fail-closed semantics for missing live evidence, missing readiness gates, PRD thresholds, negative feedback response actions, route mismatch candidate evidence, output-boundary checks, and Hermes meta leaks.
- Added `assert_trial_acceptance_ready` and `format_trial_acceptance_summary` so downstream reports can expose sanitized counts/status/issue codes without raw task rows.

## Task Commits

Each task was committed atomically:

1. **Task 08-01-01: Evidence row dataclasses and privacy checks** - `28cbf5c` (feat)
2. **Task 08-01-02: Trial acceptance threshold evaluator** - `b02b61b` (feat)
3. **Task 08-01-03: Sanitized summary formatting and assertion helpers** - `c40ea78` (feat)

## Files Created/Modified

- `packages/contract-test-suite/src/contract_test_suite/trial_acceptance.py` - Phase 8 trial evidence dataclasses, evaluator, readiness assertion, and sanitized summary formatter.
- `packages/contract-test-suite/tests/test_trial_acceptance.py` - stdlib unittest coverage for privacy rejection, fixture-not-live behavior, blocked readiness gates, passing thresholds, repair-plan exception, negative-feedback response timing, route mismatch candidates, and sanitized summaries.

## Verification

- `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py` - 9 tests passed.
- `python -m compileall packages/contract-test-suite/src/contract_test_suite/trial_acceptance.py` - passed.
- Source assertions for evaluator, status, and required test names passed with `rg`.

## Decisions Made

- Live acceptance counts only `sanitized_runtime`, `operator_annotation`, and `live_external_ref` evidence kinds.
- Empty evidence returns `pending`; fixture-only or missing readiness gates return `blocked`; threshold or safety failures return `failed`.
- The checker supports `passed_with_repair_plan` only for the positive-feedback exception and only when a categorized repair plan ref is provided.

## Deviations from Plan

None - plan executed exactly as written.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 08-02 to create the operator runbook and evidence template against the implemented checker. Live lawyer acceptance remains human-needed until external five-workday trial evidence is supplied.

## Self-Check: PASSED

- Key files exist on disk.
- Commits for `08-01` are present in git history.
- Verification commands passed.
- Summary does not claim live trial acceptance.

---
*Phase: 08-lawyer-trial-acceptance*
*Completed: 2026-06-28*
