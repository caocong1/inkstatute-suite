---
phase: 03-hermes-integration-spike-and-risk-closure
plan: 04
subsystem: testing
tags: [contract-test-suite, fixtures, replay, idempotency, privacy]

requires:
  - phase: 03-02
    provides: Hook ordering and AgentTurn source decisions
  - phase: 03-03
    provides: Identifier, async state, privacy, idempotency, and safety rules
provides:
  - Four Phase 3 non-happy-path contract fixtures
  - Focused unittest coverage for route mismatch, long-task failure, repeated feedback clicks, and non-legal wild tasks
  - Full contract-test-suite validation with Phase 3 fixtures included in exact fixture expectations
affects: [phase-04-hermes-shadow-event-layer, phase-06-feedback-service, phase-07-ci-composability-privacy-gates]

tech-stack:
  added: []
  patterns:
    - Reuse validate_event_bundle and assert_relationship_integrity for fixture proof
    - Model duplicate feedback callbacks as one canonical FeedbackEvent plus idempotency metadata

key-files:
  created:
    - packages/contract-test-suite/fixtures/phase3_route_error_contract_fixture.json
    - packages/contract-test-suite/fixtures/phase3_long_task_failure_contract_fixture.json
    - packages/contract-test-suite/fixtures/phase3_repeated_feedback_clicks_contract_fixture.json
    - packages/contract-test-suite/fixtures/phase3_non_legal_wild_task_contract_fixture.json
    - packages/contract-test-suite/tests/test_phase3_non_happy_paths.py
    - .planning/phases/03-hermes-integration-spike-and-risk-closure/03-04-SUMMARY.md
  modified:
    - packages/contract-test-suite/tests/test_schema_validation.py

key-decisions:
  - "Phase 3 non-happy-path evidence lives in contract-test-suite fixtures and reuses the Phase 2 schema/replay harness."
  - "Repeated feedback clicks are represented as one canonical FeedbackEvent with idempotency metadata and duplicate callback references."
  - "Route mismatch fixtures require skill_candidate.requires_human_review and explicit metadata showing no automatic skill modification."

patterns-established:
  - "Synthetic failure fixtures use exact async state vocabulary: queued, running, failed."
  - "Non-legal composability fixtures keep domain data in industry_context and avoid forbidden top-level fields."

requirements-completed:
  - REQ-implementation-risk-resolution

duration: 10min
completed: 2026-06-28
---

# Phase 03 Plan 04: Non-Happy-Path Fixtures and Contract Tests Summary

**Phase 3 now has schema-valid non-happy-path contract fixtures and focused replay tests for route errors, long-task failures, repeated feedback clicks, and non-legal wild tasks.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-28T01:25:10Z
- **Completed:** 2026-06-28T01:35:38Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added four reusable Phase 3 JSON fixture bundles under `packages/contract-test-suite/fixtures/`.
- Added `Phase3NonHappyPathTests`, which validates schema shape, relationship integrity, route mismatch safety, async failure states, idempotency metadata, privacy references, and non-legal composability.
- Updated the existing schema fixture id exact-set assertion so fixture drift remains visible.

## Task Commits

1. **Task 1: Add Phase 3 non-happy-path fixture bundles** - `d12d4f0` (test)
2. **Task 2: Add Phase 3 fixture validation tests using existing harness helpers** - `2b73f45` (test)
3. **Task 3: Update existing fixture id expectation and run full contract suite** - `b3e93d9` (test)

**Plan metadata:** this summary/tracking commit (`docs(03-04): complete non-happy-path fixtures plan`)

## Files Created/Modified

- `packages/contract-test-suite/fixtures/phase3_route_error_contract_fixture.json` - Route mismatch fixture with human-review-only skill candidate evidence.
- `packages/contract-test-suite/fixtures/phase3_long_task_failure_contract_fixture.json` - Long-task failure fixture with `queued`, `running`, and `failed` states plus runtime error data.
- `packages/contract-test-suite/fixtures/phase3_repeated_feedback_clicks_contract_fixture.json` - Repeated feedback click fixture with one canonical `FeedbackEvent` and idempotency metadata.
- `packages/contract-test-suite/fixtures/phase3_non_legal_wild_task_contract_fixture.json` - Non-lawfirm simple-QA/wild-task fixture proving industry-neutral composability.
- `packages/contract-test-suite/tests/test_phase3_non_happy_paths.py` - Focused unittest coverage for Phase 3 fixture behaviors.
- `packages/contract-test-suite/tests/test_schema_validation.py` - Exact fixture id expectation updated for the new Phase 3 fixtures.

## Decisions Made

- Use only existing `validate_event_bundle` and `assert_relationship_integrity`; no new validator or dependency was introduced.
- Keep repeated callback raw data out of events by modeling duplicate callback refs as `fixture://raw/...` references in metadata.
- Keep route-mismatch skill candidates human-reviewed and explicitly non-automatic.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Initial privacy test assertion matched the substring `raw_payload` and therefore incorrectly rejected valid `raw_payload_ref` keys. The test was corrected to assert no exact `raw_payload` key exists while still requiring `raw_payload_ref` references.

## User Setup Required

None - no external service configuration required.

## Verification

- PASS: Task 1 structure check verified all four fixture ids and all five event keys.
- PASS: Phase 3 fixture schema validation and relationship integrity checks passed with zero broken relationships.
- PASS: `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python -m unittest discover -s tests -p 'test_phase3_non_happy_paths.py' -v` ran 7 tests successfully.
- PASS: `python -m compileall packages/contract-test-suite/src packages/contract-test-suite/tests packages/contract-test-suite/scripts && cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` ran 28 tests successfully.
- PASS: Plan-level helper check confirmed `test_phase3_non_happy_paths.py` imports `validate_event_bundle` and `assert_relationship_integrity`.
- PASS: No `services/`, `.github/`, database, queue, or runtime hook files were created.

## Self-Check: PASSED

- Key files exist on disk.
- Contract-test-suite passes with the new fixtures.
- Relationship integrity for all Phase 3 fixtures has zero broken relationships.
- Scope stayed inside synthetic fixtures and unittest coverage.

## Next Phase Readiness

Phase 3 implementation-risk fixture coverage is complete. Phase-level verification can now evaluate whether Phase 3 fully closes the Hermes integration spike and whether Phase 4 can start with the documented after-filter hook-order constraints.

---
*Phase: 03-hermes-integration-spike-and-risk-closure*
*Completed: 2026-06-28*
