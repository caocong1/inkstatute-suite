---
phase: 02-contract-test-suite-foundation
plan: 01
subsystem: contract-test-suite
tags: [python, unittest, json-schema, stdlib, contracts]

requires:
  - phase: 01-platform-contract-foundation
    provides: Phase 1 platform contract schemas, fixtures, and stdlib validation patterns
provides:
  - Dependency-free inkstatute-contract-test-suite package shell
  - Repo-local path helpers for platform contract schemas and fixtures
  - Stdlib JSON Schema subset validator for Phase 1 contract artifacts
  - unittest coverage for valid fixtures and invalid schema cases across all five events
affects: [hermes-contract-layer, feedback-service, conversation-read-view, ci-gates]

tech-stack:
  added: []
  patterns:
    - Standard-library-only package-local contract validation
    - JSON Schema subset resolver for sibling schema refs and common $defs
    - TDD gate for contract harness behavior

key-files:
  created:
    - packages/contract-test-suite/pyproject.toml
    - packages/contract-test-suite/src/contract_test_suite/paths.py
    - packages/contract-test-suite/src/contract_test_suite/schema_validation.py
    - packages/contract-test-suite/tests/test_schema_validation.py
  modified:
    - packages/contract-test-suite/src/contract_test_suite/__init__.py

key-decisions:
  - "Keep the contract-test-suite dependency-free and use only Python stdlib unittest/json/pathlib."
  - "Consume Phase 1 platform-contract schemas and fixtures by path instead of duplicating contract definitions."
  - "Reject forbidden legal/sensitive top-level fields in the validator even if a future schema accidentally allows them."

patterns-established:
  - "Contract harness helpers derive paths from package file locations rather than current working directory."
  - "ContractValidationError messages include fixture id, event key, and precise field path."
  - "TDD RED/GREEN commits are used for schema validation harness behavior."

requirements-completed:
  - REQ-contract-test-suite

duration: 3m55s
completed: 2026-06-27
---

# Phase 2 Plan 01: Contract Test Suite Foundation Summary

**Dependency-free Python contract test suite with stdlib JSON Schema subset validation for all five Phase 1 platform events**

## Performance

- **Duration:** 3m55s
- **Started:** 2026-06-27T16:58:19Z
- **Completed:** 2026-06-27T17:02:14Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Created `inkstatute-contract-test-suite` package metadata with `requires-python = ">=3.11"` and no runtime dependencies.
- Added package-local path constants for platform contract schemas and fixtures, derived from `Path(__file__).resolve()`.
- Implemented `ContractValidationError`, schema/fixture loaders, `validate_event`, and `validate_event_bundle`.
- Covered valid Phase 1 fixtures plus required-field, enum, type, range, `oneOf`, `additionalProperties`, forbidden top-level, and extension-container behavior in stdlib `unittest`.

## Task Commits

1. **Task 1: Create contract-test-suite package shell and path helpers** - `f5a6ed3` (feat)
2. **Task 2 RED: Add failing schema validation coverage** - `d08cc2a` (test)
3. **Task 2 GREEN: Implement stdlib schema validation** - `0459466` (feat)

## Files Created/Modified

- `packages/contract-test-suite/pyproject.toml` - Dependency-free Python package metadata.
- `packages/contract-test-suite/src/contract_test_suite/__init__.py` - Public exports for schema validation helpers.
- `packages/contract-test-suite/src/contract_test_suite/paths.py` - Repo-local constants for package, platform schema, and fixture roots.
- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` - Stdlib JSON Schema subset validator and fixture/schema loaders.
- `packages/contract-test-suite/tests/test_schema_validation.py` - unittest coverage for valid fixtures and invalid mutations.
- `.planning/phases/02-contract-test-suite-foundation/02-01-SUMMARY.md` - Execution summary.

## Verification

| Command | Result |
|---|---|
| `python -m compileall packages/contract-test-suite/src packages/contract-test-suite/tests` | PASS |
| `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python -m unittest discover -s tests -p 'test_schema_validation.py' -v` | PASS - 7 tests |
| `python -c "import pathlib, tomllib; data=tomllib.loads(pathlib.Path('packages/contract-test-suite/pyproject.toml').read_text()); assert data['project'].get('dependencies', []) == []"` | PASS |

## Decisions Made

- Used no external JSON Schema validator so the package remains dependency-free and aligned with Phase 1 tooling.
- Resolved `$ref` values against local Phase 1 schema files only: `common.schema.json#/$defs/...`, local `#/$defs/...`, and sibling event schemas.
- Treated legal/sensitive top-level field rejection as validator policy, not just schema shape, so accidental schema drift remains caught by tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tightened invalid-field error message paths**
- **Found during:** Task 2 (Implement stdlib schema validation with invalid-case coverage)
- **Issue:** Unknown and forbidden top-level fields were rejected correctly, but error text placed the field list after the failure category, making path-focused assertions less precise.
- **Fix:** Changed errors to report `fixture.event.field` before `additionalProperties` or `forbidden top-level field`.
- **Files modified:** `packages/contract-test-suite/src/contract_test_suite/schema_validation.py`
- **Verification:** Package-local unittest command passed with all 7 tests.
- **Committed in:** `0459466`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix improved required error clarity without changing scope.

## Issues Encountered

- The Task 2 RED gate failed as expected with `ModuleNotFoundError: No module named 'contract_test_suite.schema_validation'` before implementation.

## TDD Gate Compliance

- RED commit present: `d08cc2a` (`test(...)`)
- GREEN commit present after RED: `0459466` (`feat(...)`)
- No refactor commit was needed.

## Known Stubs

None. Stub scan hits were intentional dependency/accumulator values (`dependencies = []`, local empty dict/list accumulators) and not unfinished behavior or mock UI data.

## Threat Flags

None. This plan introduced local file reads for repo-owned schemas and fixtures only; no network endpoints, auth paths, databases, secrets, runtime services, Hermes hooks, or WeCom integrations were added.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02-02 can build fixture replay and relationship checks on top of the package shell, repo-local path constants, and deterministic stdlib schema validator.

## Self-Check: PASSED

- Confirmed all created package, test, and summary files exist on disk.
- Confirmed task commits `f5a6ed3`, `d08cc2a`, and `0459466` are reachable in git history.
- Confirmed all plan verification commands passed after implementation.

---
*Phase: 02-contract-test-suite-foundation*
*Completed: 2026-06-27*
