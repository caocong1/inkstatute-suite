---
phase: 02-contract-test-suite-foundation
plan: 03
subsystem: contract-test-suite
tags: [python, unittest, fixtures, composability, runner, stdlib]

requires:
  - phase: 02-contract-test-suite-foundation
    provides: Plan 02-01 schema validation and Plan 02-02 fixture replay relationship integrity helpers
provides:
  - Finance/tax and education synthetic non-legal fixture bundles
  - Local composability tests covering finance/tax, engineering, and education fixtures
  - Package-local unittest runner command for later Phase 7 CI enforcement
  - Contract-test-suite README documenting Phase 2 scope and deferred boundaries
affects: [ci-gates, composability-validation, hermes-contract-layer]

tech-stack:
  added: []
  patterns:
    - Standard-library-only unittest runner with repo-local sys.path setup
    - Non-legal fixture domain details stored in industry_context or metadata
    - Synthetic composability tests reuse validate_event_bundle and assert_relationship_integrity

key-files:
  created:
    - packages/contract-test-suite/fixtures/non_legal_finance_tax_task.json
    - packages/contract-test-suite/fixtures/non_legal_education_task.json
    - packages/contract-test-suite/tests/test_composability.py
    - packages/contract-test-suite/scripts/run_contract_tests.py
    - packages/contract-test-suite/README.md
  modified:
    - packages/contract-test-suite/tests/test_schema_validation.py

key-decisions:
  - "Keep Phase 2 composability evidence local and synthetic; Phase 7 owns .github CI enforcement."
  - "Reuse existing schema validation and fixture replay helpers rather than adding another validator."
  - "Use fixture:// references for synthetic source material and keep domain-specific fields in industry_context or metadata."

patterns-established:
  - "Package-local contract test runner inserts only contract-test-suite src and platform-contract src before unittest discovery."
  - "Composability tests scan both fixture event top-level keys and schema required arrays for lawfirm-only fields."
  - "Local non-legal fixtures mirror the Phase 1 event bundle shape: agent_turn, route_decision, execution_trace, agent_result, feedback_event."

requirements-completed:
  - REQ-contract-test-suite

duration: 4m27s
completed: 2026-06-27
---

# Phase 2 Plan 03: Local Synthetic Composability and Runner Summary

**Finance/tax, engineering, and education synthetic contract fixtures validated through the same schema and relationship harness with a local unittest runner**

## Performance

- **Duration:** 4m27s
- **Started:** 2026-06-27T17:15:18Z
- **Completed:** 2026-06-27T17:19:45Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added finance/tax and education synthetic event bundles under `packages/contract-test-suite/fixtures/`.
- Added composability tests proving finance/tax, engineering, and education examples validate and preserve relationships without legal-only top-level fields.
- Added a package-local `scripts/run_contract_tests.py` runner and README that document Phase 2 coverage while deferring `.github` CI enforcement to Phase 7.

## Task Commits

1. **Task 1: Add finance/tax and education synthetic contract fixtures** - `90e796d` (feat)
2. **Task 2 RED: Add failing composability coverage** - `abe2689` (test)
3. **Task 2 GREEN: Validate synthetic composability examples** - `bb11d5b` (feat)
4. **Task 3: Add local runner and package documentation** - `7fa3f39` (docs)

## Files Created/Modified

- `packages/contract-test-suite/fixtures/non_legal_finance_tax_task.json` - Synthetic finance/tax bundle with `fixture://` source references and intact event relationships.
- `packages/contract-test-suite/fixtures/non_legal_education_task.json` - Synthetic education bundle with `fixture://` source references and intact event relationships.
- `packages/contract-test-suite/tests/test_composability.py` - unittest coverage for non-legal fixture validation, relationship integrity, domain coverage, forbidden top-level fields, schema required fields, and mutation failure.
- `packages/contract-test-suite/tests/test_schema_validation.py` - Updated expected valid fixture ids to include package-local fixtures loaded by `load_contract_fixtures`.
- `packages/contract-test-suite/scripts/run_contract_tests.py` - stdlib runner that sets package import paths, runs unittest discovery, and returns non-zero on failure.
- `packages/contract-test-suite/README.md` - Package usage, coverage boundary, local command, and Phase 7 CI ownership documentation.
- `.planning/phases/02-contract-test-suite-foundation/02-03-SUMMARY.md` - Execution summary.

## Verification

| Command | Result |
|---|---|
| `python -c "import json, pathlib; files=[...]; ..."` | PASS - two local fixtures have expected ids and all five event keys |
| `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python -m unittest discover -s tests -p 'test_composability.py' -v` | PASS - 5 tests |
| `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` | PASS - 18 tests |
| `python -c "from pathlib import Path; text=Path('packages/contract-test-suite/README.md').read_text(); ..."` | PASS |
| `python -m compileall packages/contract-test-suite/src packages/contract-test-suite/tests packages/contract-test-suite/scripts` | PASS |
| `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python -m unittest discover -s tests -v` | PASS - 18 tests |

## Decisions Made

- Kept the runner dependency-free and avoided package-manager changes.
- Treated local composability as Phase 2 evidence only; `.github` workflow wiring and CI enforcement remain Phase 7 scope.
- Reused `validate_event_bundle` and `assert_relationship_integrity` so composability tests exercise the same harness as schema and replay tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated schema fixture expectation after adding local fixtures**
- **Found during:** Task 2 (Add local composability tests for non-legal examples)
- **Issue:** `load_contract_fixtures()` correctly loads package-local fixtures after Task 1, but `test_schema_validation.py` still expected only the two Phase 1 platform fixtures.
- **Fix:** Updated the expected fixture id set to include `non-legal-finance-tax-task-001` and `non-legal-education-task-001`.
- **Files modified:** `packages/contract-test-suite/tests/test_schema_validation.py`
- **Verification:** Full package unittest discovery passed with 18 tests.
- **Committed in:** `bb11d5b`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix kept existing schema tests aligned with the planned local fixture expansion and did not expand scope.

## Issues Encountered

- Task 2 RED failed as expected with `NameError: name 'load_non_legal_composability_fixtures' is not defined` before the GREEN implementation.

## TDD Gate Compliance

- RED commit present: `abe2689` (`test(...)`)
- GREEN commit present after RED: `bb11d5b` (`feat(...)`)
- No refactor commit was needed.

## Known Stubs

None. Stub scan found no `TODO`, `FIXME`, placeholder text, or hardcoded empty UI/data placeholders in files created or modified by this plan.

## Threat Flags

None. This plan introduced local JSON fixtures, unittest coverage, a local test runner, and README documentation only; it added no network endpoints, auth paths, databases, secrets, runtime services, Hermes hooks, WeCom integrations, feedback-service work, read-view APIs, or `.github` workflows.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 2 now has schema validation, fixture replay, relationship integrity checks, local synthetic composability coverage, and a single package-local runner command that Phase 7 CI can later call.

## Self-Check: PASSED

- Confirmed all created fixture, test, runner, README, and summary files exist on disk.
- Confirmed task commits `90e796d`, `abe2689`, `bb11d5b`, and `7fa3f39` are reachable in git history.
- Confirmed all plan verification commands passed after implementation.

---
*Phase: 02-contract-test-suite-foundation*
*Completed: 2026-06-27*
