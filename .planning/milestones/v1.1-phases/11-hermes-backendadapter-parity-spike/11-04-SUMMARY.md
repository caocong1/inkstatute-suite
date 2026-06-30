---
phase: 11-hermes-backendadapter-parity-spike
plan: 11-04
subsystem: testing
tags: [hermes, parity, fixtures, contract-test-suite]

requires:
  - phase: 11-hermes-backendadapter-parity-spike
    provides: 11-03 default-off /v1/runs lane
provides:
  - Six sanitized one-shot vs /v1/runs parity cases
  - Deterministic parity evaluator and report dataclasses
  - Contract-test-suite Phase 11 parity evidence
  - Hermes backend README with default-off and rollback rules
affects: [hermes-backend, contract-test-suite, parity-gates]

tech-stack:
  added: []
  patterns: [sanitized parity fixture, deterministic report, no-promotion-on-failure gate]

key-files:
  created:
    - packages/backends/hermes/src/inkstatute_backends_hermes/parity.py
    - packages/backends/hermes/fixtures/parity_cases.json
    - packages/backends/hermes/tests/test_parity_report.py
    - packages/contract-test-suite/tests/test_phase11_hermes_parity.py
    - packages/backends/hermes/README.md
  modified:
    - packages/backends/hermes/src/inkstatute_backends_hermes/__init__.py
    - packages/contract-test-suite/scripts/run_contract_tests.py

key-decisions:
  - "Parity fixtures intentionally include a sanitized route-mismatch failure, so promote_api_runs=False and default_lane remains oneshot."
  - "Parity comparison uses hashes, refs, state sequences, and policy actions rather than raw backend text."
  - "The contract runner now includes packages/backends/hermes/src so Phase 11 parity evidence is discoverable."

patterns-established:
  - "Backend parity fixtures must be not-live evidence and cannot promote live defaults alone."
  - "Parity reports expose reason codes only, not raw mismatched values."

requirements-completed:
  - REQ-hermes-run-parity-spike

duration: 5min
completed: 2026-06-29
---

# Phase 11 Plan 04: Parity Fixtures, Report, And Contract Evidence Summary

**Sanitized Hermes one-shot vs `/v1/runs` parity fixture/report gate integrated into the contract-test-suite**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-29T00:15:19Z
- **Completed:** 2026-06-29T00:20:46Z
- **Tasks:** 4
- **Files modified:** 7

## Accomplishments

- Added six sanitized parity cases: `legal_qa`, `drafting_artifact`, `follow_up`, `route_mismatch`, `mcp_tool_task`, and `non_legal`.
- Added `ParityCase`, `ParityDimensionResult`, `ParityReport`, `load_parity_cases`, and `evaluate_parity_cases`.
- Checked route, skills/gates, MCP/tool trace, artifacts, visible output hash, output policy, state transitions, and feedback targets.
- Integrated Phase 11 parity evidence into the contract-test-suite.
- Added README guidance for one-shot default, safe probe endpoints, default-off `/v1/runs`, parity semantics, approval safety, and rollback.

## Task Commits

Tasks were grouped into one coherent parity evidence feature commit:

1. **Tasks 11-04-01 through 11-04-04: fixtures, evaluator, tests, contract-suite integration, and docs** - `e2baf60` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `packages/backends/hermes/fixtures/parity_cases.json` - Six sanitized parity cases with refs/hashes only.
- `packages/backends/hermes/src/inkstatute_backends_hermes/parity.py` - Deterministic parity evaluator.
- `packages/backends/hermes/tests/test_parity_report.py` - Backend parity/privacy/promotion tests.
- `packages/contract-test-suite/tests/test_phase11_hermes_parity.py` - Contract-suite parity evidence test.
- `packages/contract-test-suite/scripts/run_contract_tests.py` - Adds Hermes backend source path.
- `packages/backends/hermes/README.md` - Operator-facing safety and rollback notes.
- `packages/backends/hermes/src/inkstatute_backends_hermes/__init__.py` - Parity public exports.

## Verification

- `python -m compileall packages/backends/hermes/src packages/backends/hermes/tests packages/contract-test-suite/tests` - PASS
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_parity_report.py` - PASS, 6 tests OK
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest discover packages/backends/hermes/tests` - PASS, 29 tests OK
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/backends/hermes/src python -m unittest packages/contract-test-suite/tests/test_phase11_hermes_parity.py` - PASS, 3 tests OK
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/backends/hermes/src python packages/contract-test-suite/scripts/run_contract_tests.py` - PASS, 110 tests OK
- Fixture forbidden-marker scan - PASS
- README acceptance text scan - PASS

## Decisions Made

- The fixture refutes promotion in this phase: the route-mismatch case intentionally differs, so `/v1/runs` stays opt-in and default-off.
- Passing synthetic parity is representable in tests, but even that does not mutate adapter defaults.
- The README avoids live acceptance or live rollout claims.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added Hermes source path to contract runner**
- **Found during:** Task 11-04-04
- **Issue:** The new contract-suite test imports `inkstatute_backends_hermes`; the local runner needed the backend source path for self-contained discovery.
- **Fix:** Added `packages/backends/hermes/src` to `run_contract_tests.py`.
- **Files modified:** `packages/contract-test-suite/scripts/run_contract_tests.py`
- **Verification:** Full contract runner passes 110 tests.
- **Committed in:** `e2baf60`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Required for contract-suite integration; no runtime dependency or neutral package coupling introduced.

## Issues Encountered

The README spot-check initially rejected a negated phrase containing "production promotion." It was reworded to avoid brittle claim text while preserving the safety message.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

All Phase 11 plans are implemented. Phase-level verification can now assess the full Hermes adapter/probe/runs/parity goal.

---
*Phase: 11-hermes-backendadapter-parity-spike*
*Completed: 2026-06-29*
