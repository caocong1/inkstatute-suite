---
phase: 02-contract-test-suite-foundation
plan: 02
subsystem: contract-test-suite
tags: [python, unittest, fixtures, replay, relationships, stdlib]

requires:
  - phase: 02-contract-test-suite-foundation
    provides: Plan 02-01 schema validation harness and repo-local platform-contract fixture paths
provides:
  - Fixture replay helpers for Phase 1 golden platform-contract fixtures
  - Relationship integrity checks across turn, route, trace, result, artifact, and feedback events
  - Replay reports with fixture counts, relationship check counts, broken relationship counts, and breakage rate
  - Mutation tests for relationship failure diagnostics and 5 percent tolerance enforcement
affects: [hermes-contract-layer, feedback-service, conversation-read-view, ci-gates]

tech-stack:
  added: []
  patterns:
    - Standard-library-only fixture replay using json, pathlib, dataclasses, and unittest
    - Schema-first replay via contract_test_suite.schema_validation.validate_event_bundle
    - Relationship diagnostics that report fixture id, field path, expected value, and actual value

key-files:
  created:
    - packages/contract-test-suite/src/contract_test_suite/fixture_replay.py
    - packages/contract-test-suite/tests/test_fixture_replay.py
  modified:
    - packages/contract-test-suite/src/contract_test_suite/__init__.py

key-decisions:
  - "Keep fixture replay dependency-free and reuse Plan 02-01 validate_event_bundle before relationship checks."
  - "Model relationship failures as structured RelationshipIssue records with fixture id, field path, expected value, and actual value."
  - "Treat the 5 percent relationship breakage threshold as an assertion policy in assert_relationship_integrity, while replay_fixtures still returns a report."

patterns-established:
  - "Replay helpers accept explicit fixture paths for tests and default to paths.PLATFORM_FIXTURE_ROOT for Phase 1 fixtures."
  - "Relationship checks are counted independently so breakage_rate = broken_checks / total_checks."
  - "Mutation tests use temporary JSON fixture files to exercise the same file loading path as real replay."

requirements-completed:
  - REQ-contract-test-suite

duration: 3m57s
completed: 2026-06-27
---

# Phase 2 Plan 02: Fixture Replay and Relationship Integrity Summary

**Fixture replay harness with schema-first validation and relationship breakage reporting across Phase 1 contract fixtures**

## Performance

- **Duration:** 3m57s
- **Started:** 2026-06-27T17:08:00Z
- **Completed:** 2026-06-27T17:11:57Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `fixture_replay.py` with `RelationshipIssue`, `ReplayReport`, fixture path loading, schema-first replay, and relationship assertion helpers.
- Validated current Phase 1 legal and non-legal fixtures with 26 relationship checks and zero broken relationships.
- Added unittest coverage for fixture loading, schema failure context, relationship mutations, breakage-rate calculation, and default 5 percent tolerance enforcement.

## Task Commits

1. **Task 1 RED: Add failing fixture replay coverage** - `daef453` (test)
2. **Task 1 GREEN: Add fixture replay report helpers** - `27ab97b` (feat)
3. **Task 2 RED: Add failing relationship replay coverage** - `7f77a21` (test)
4. **Task 2 GREEN: Enforce fixture relationship integrity** - `17b2b3d` (feat)

## Files Created/Modified

- `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` - Fixture replay API, structured report objects, relationship checks, and assertion policy.
- `packages/contract-test-suite/tests/test_fixture_replay.py` - unittest coverage for successful replay, malformed fixtures, mutation failures, and tolerance enforcement.
- `packages/contract-test-suite/src/contract_test_suite/__init__.py` - Public exports for replay helpers and report types.
- `.planning/phases/02-contract-test-suite-foundation/02-02-SUMMARY.md` - Execution summary.

## Verification

| Command | Result |
|---|---|
| `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python -m unittest discover -s tests -p 'test_fixture_replay.py' -v` | PASS - 6 tests |
| `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python -m unittest discover -s tests -v` | PASS - 13 tests |
| `python -m compileall packages/contract-test-suite/src packages/contract-test-suite/tests` | PASS |
| `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python - <<'PY' ... replay_fixtures()` | PASS - 26 relationship checks, breakage rate 0.0 |

## Decisions Made

- Reused `validate_event_bundle` for every replay before any relationship checks so schema failures remain separate from continuity failures.
- Counted every named relationship check, including optional route and trace metadata only when present.
- Kept failure output to synthetic fixture ids, field paths, and expected/actual identifiers; no raw legal payload content is printed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Task 1 RED failed as expected with `ModuleNotFoundError: No module named 'contract_test_suite.fixture_replay'`.
- Task 2 RED failed as expected because the initial replay report did not yet inspect broken relationships or enforce the 5 percent threshold.

## TDD Gate Compliance

- Task 1 RED commit present: `daef453` (`test(...)`)
- Task 1 GREEN commit present after RED: `27ab97b` (`feat(...)`)
- Task 2 RED commit present: `7f77a21` (`test(...)`)
- Task 2 GREEN commit present after RED: `17b2b3d` (`feat(...)`)
- No refactor commit was needed.

## Known Stubs

None. Stub scan hits were local list accumulators and optional type annotations, not unfinished behavior or mock data.

## Threat Flags

None. This plan introduced local JSON fixture reads and relationship assertions only; it added no network endpoints, auth paths, databases, secrets, runtime services, Hermes hooks, WeCom integrations, or raw legal payload logging.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02-03 can build composability and CI-ready harness behavior on top of schema validation plus fixture replay relationship checks.

## Self-Check: PASSED

- Confirmed created files exist: `fixture_replay.py`, `test_fixture_replay.py`, and this summary.
- Confirmed task commits `daef453`, `27ab97b`, `7f77a21`, and `17b2b3d` are reachable in git history.
- Confirmed all plan verification commands passed after implementation.

---
*Phase: 02-contract-test-suite-foundation*
*Completed: 2026-06-27*
