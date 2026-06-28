---
phase: 09-architecture-contracts-schema-foundation
plan: 09-04
subsystem: contract-test-suite
tags: [boundary-allowlist, privacy-gates, neutral-contracts, unittest]

requires:
  - phase: 09-03
    provides: Platform-foundation fixture replay and Phase 09 contract verification gates
provides:
  - Allowlist-aware neutral boundary policy for concrete enum/example names
  - Hard-deny scans for private Hermes paths, WeCom payload internals, exact raw payload keys, plaintext secret patterns, runtime artifacts, and legal-only schema fields
  - Focused unittest coverage for allowed contexts and forbidden coupling
affects: [phase-09, phase-10, phase-11, phase-12, phase-13, platform-contract, contract-test-suite]

tech-stack:
  added: []
  patterns:
    - "BoundaryAllowlistPolicy separates allowed concrete enum/example contexts from hard-deny privacy and coupling checks"
    - "Boundary tests construct secret-like values at runtime instead of committing complete token-shaped literals"

key-files:
  created:
    - packages/contract-test-suite/tests/test_boundary_allowlist.py
    - .planning/phases/09-architecture-contracts-schema-foundation/09-04-SUMMARY.md
  modified:
    - packages/contract-test-suite/src/contract_test_suite/boundary_checks.py
    - packages/contract-test-suite/tests/test_thin_layer_boundaries.py
    - packages/contract-test-suite/tests/test_boundary_allowlist.py

key-decisions:
  - "Use BoundaryAllowlistPolicy for path-aware allowed contexts while keeping hard-deny checks independent from the allowlist."
  - "Allow hermes, codex, provider_model, wecom, qqbot, web, and desktop only in their intended enum/schema/docs/concrete-package contexts."
  - "Do not store complete token-shaped test literals; construct secret-like samples at runtime for scanner coverage."

patterns-established:
  - "Neutral package boundary scans run as part of thin-layer tests through assert_neutral_boundary_allowlist(REPO_ROOT)."
  - "Exact raw_payload data keys are rejected while raw_payload_ref remains allowed."

requirements-completed:
  - REQ-boundary-scan-allowlist
  - REQ-platform-contract-extension
  - REQ-platform-north-star

duration: 6 min
completed: 2026-06-29
---

# Phase 09 Plan 04: Neutral Boundary Allowlist Gates Summary

**Allowlist-aware neutral boundary gates permit legitimate platform enum names while preserving strict privacy and coupling hard-denies.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-28T19:04:59Z
- **Completed:** 2026-06-28T19:11:09Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `BoundaryAllowlistPolicy` and `assert_neutral_boundary_allowlist` to enforce path-aware allowed contexts for backend/channel enum names and architecture/concrete package examples.
- Preserved hard-deny checks for private Hermes paths, WeCom callback payload internals, exact `raw_payload` keys in data artifacts, plaintext secret patterns, runtime DB/log/media artifacts, and legal-only top-level schema fields.
- Added focused stdlib `unittest` coverage for allowed contexts and forbidden coupling, then wired the new gate into existing thin-layer boundary tests.
- Verified all Phase 09 foundation gates together without starting servers, calling Hermes, calling live WeCom, or accessing runtime databases.

## Task Commits

Each task was committed atomically:

1. **Task 09-04-01: Implement allowlist-aware neutral boundary policy** - `822316c` (feat)
2. **Task 09-04-02: Add allowlist tests and thin-layer gate wiring** - `b825251` (test)
3. **Task 09-04-03: Verify Phase 09 foundation gates** - `1d3c434` (test, empty verification record)

Additional auto-fix commit:

- **Rule 2 fix: Avoid secret-shaped test literal** - `436dbe4` (fix)

## Files Created/Modified

- `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py` - Added path-aware allowlist policy, new neutral boundary assertion, and hard-deny scanners.
- `packages/contract-test-suite/tests/test_boundary_allowlist.py` - Added focused tests for allowed enum/docs/concrete contexts and rejected private/runtime/privacy/legal coupling.
- `packages/contract-test-suite/tests/test_thin_layer_boundaries.py` - Runs `assert_neutral_boundary_allowlist(REPO_ROOT)` with the existing thin-layer checks.
- `.planning/phases/09-architecture-contracts-schema-foundation/09-04-SUMMARY.md` - Execution summary and verification evidence.

## Decisions Made

- The allowlist controls where concrete names are valid; privacy/safety hard-denies do not depend on allowlist membership.
- Existing neutral enum/schema contexts remain legitimate for `hermes`, `codex`, `provider_model`, `wecom`, `qqbot`, `web`, and `desktop`.
- Test coverage for secret scanning uses runtime string construction, avoiding committed complete secret-shaped literals.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Removed complete secret-shaped test literal**
- **Found during:** Close-out stub/privacy scan after Task 09-04-03
- **Issue:** `test_boundary_allowlist.py` used a complete synthetic `sk-...` token-shaped string to test plaintext secret rejection. Although fake, AGENTS.md forbids committing secrets or secret-like values.
- **Fix:** Constructed the secret-like value at runtime by concatenating safe string fragments, preserving scanner coverage without storing a complete token-shaped literal in the repository.
- **Files modified:** `packages/contract-test-suite/tests/test_boundary_allowlist.py`
- **Verification:** Boundary allowlist suite passed and a touched-file literal scan reported no complete secret-like literals.
- **Committed in:** `436dbe4`

---

**Total deviations:** 1 auto-fixed (1 missing critical).
**Impact on plan:** The fix strengthened the privacy posture without changing the intended boundary policy behavior.

## Issues Encountered

- One scratch import probe failed before Task 09-04-01 commit because it intentionally omitted `PYTHONPATH`; it was not part of plan verification and was rerun with the correct environment through the acceptance probes.

## Verification Results

- `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/platform-runtime/tests/test_protocols.py`
  - Result: PASS
  - Output: `Ran 4 tests in 0.000s` and `OK`
- `PYTHONPATH=packages/platform-contract/src python packages/platform-contract/scripts/self_check.py`
  - Result: PASS
  - Output: `platform-contract self-check passed`
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_platform_foundation_contracts.py`
  - Result: PASS
  - Output: `Ran 4 tests in 0.002s` and `OK`
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_boundary_allowlist.py`
  - Result: PASS
  - Output: `Ran 10 tests in 0.119s` and `OK`
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python packages/contract-test-suite/scripts/run_contract_tests.py`
  - Result: PASS
  - Output: `Ran 102 tests in 0.440s` and `OK`

## Known Stubs

None.

## Threat Flags

None. This plan added test-suite boundary scanning logic and tests only; it introduced no network endpoint, auth path, storage implementation, database, queue, service behavior, or runtime file access path.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 09 foundation gates are complete. Phase 10 can build on the neutral contracts with boundary scanning in place, while Phase 08 live lawyer trial evidence remains a separate human gate.

## Self-Check: PASSED

- Found created test file: `packages/contract-test-suite/tests/test_boundary_allowlist.py`
- Found modified boundary checker: `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py`
- Found thin-layer wiring: `packages/contract-test-suite/tests/test_thin_layer_boundaries.py`
- Found task commit: `822316c`
- Found task commit: `b825251`
- Found task commit: `1d3c434`
- Found auto-fix commit: `436dbe4`
- Final verification commands all passed after the auto-fix.

---
*Phase: 09-architecture-contracts-schema-foundation*
*Completed: 2026-06-29*
