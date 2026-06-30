---
phase: 09-architecture-contracts-schema-foundation
plan: 09-03
subsystem: contract-test-suite
tags: [fixtures, replay, json-schema, platform-contract, relationship-checks]

requires:
  - phase: 09-02
    provides: Additive platform contract schemas and Python bindings for channel, run, artifact, delivery, and feedback relationships
provides:
  - Sanitized non-legal platform-foundation fixture mirrored in platform-contract and contract-test-suite
  - Optional replay validation for ChannelMessage, Run, RunStep, RunEvent, ArtifactRecord, and ChannelDelivery objects
  - Focused unittest coverage for platform-foundation schema validation, relationship replay, async states, artifacts, and non-legal neutrality
affects: [phase-09, phase-10, phase-11, phase-12, phase-13, platform-contract, contract-test-suite]

tech-stack:
  added: []
  patterns:
    - "Optional platform-extension fixture keys validate only when present, preserving old five-event fixture behavior"
    - "Relationship failures report fixture ID, relationship name, field path, expected value, and actual value"

key-files:
  created:
    - packages/platform-contract/fixtures/platform_foundation_non_legal_run.json
    - packages/contract-test-suite/fixtures/platform_foundation_non_legal_run.json
    - packages/contract-test-suite/tests/test_platform_foundation_contracts.py
  modified:
    - packages/contract-test-suite/scripts/run_contract_tests.py
    - packages/contract-test-suite/src/contract_test_suite/fixture_replay.py
    - packages/contract-test-suite/src/contract_test_suite/schema_validation.py
    - packages/contract-test-suite/tests/test_fixture_replay.py
    - packages/contract-test-suite/tests/test_schema_validation.py
    - packages/platform-contract/scripts/self_check.py

key-decisions:
  - "Model the platform-foundation fixture as a synthetic education-domain run with only fixture:// references and no legal-only top-level fields."
  - "Keep platform-foundation replay optional so existing five-event fixtures continue to validate unchanged."
  - "Use ChannelDelivery.delivery_id as the feedback target while preserving AgentResult.feedback_target for existing feedback relationship checks."

patterns-established:
  - "New platform fixture arrays use plural keys in fixture bundles while each item validates against its singular schema."
  - "Contract runner owns its required local source paths for discovered package tests."

requirements-completed:
  - REQ-platform-contract-extension
  - REQ-boundary-scan-allowlist

duration: 7m20s
completed: 2026-06-28
---

# Phase 09 Plan 03: Platform Relationship Fixtures And Replay Gates Summary

**Sanitized education-domain platform fixture with replay gates proving ChannelMessage -> AgentTurn -> Run -> RunEvent/RunStep -> AgentResult/ArtifactRecord -> ChannelDelivery -> FeedbackEvent composition.**

## Performance

- **Duration:** 7m20s
- **Started:** 2026-06-28T18:53:25Z
- **Completed:** 2026-06-28T19:00:45Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added mirrored sanitized platform-foundation fixtures with stable relationship IDs and no raw payload bodies, secrets, customer documents, logs, DBs, media, or legal-only top-level fields.
- Extended contract-test-suite validation and replay helpers to validate optional platform-foundation objects without requiring old fixtures to include them.
- Added focused tests for schema validation, full relationship replay, async-state reuse, dual artifact representation, non-legal neutrality, and broken-ID detection.

## Task Commits

Each task was committed atomically:

1. **Task 09-03-01: Create sanitized non-legal platform-foundation fixture** - `f29e851` (feat)
2. **Task 09-03-02: Extend validation helpers for optional platform-foundation objects** - `2e59b49` (test)
3. **Task 09-03-03: Add focused platform relationship replay tests** - `1c01060` (test)

## Files Created/Modified

- `packages/platform-contract/fixtures/platform_foundation_non_legal_run.json` - Canonical sanitized education-domain platform run fixture.
- `packages/contract-test-suite/fixtures/platform_foundation_non_legal_run.json` - Mirrored fixture for contract-suite replay.
- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` - Optional object and array schema validation for platform-foundation fixture keys.
- `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` - Platform-foundation relationship checks and public assertion helper.
- `packages/contract-test-suite/tests/test_platform_foundation_contracts.py` - Focused unittest coverage for the new fixture and relationships.
- `packages/contract-test-suite/tests/test_fixture_replay.py` - Updated replay expectations and old-fixture compatibility coverage.
- `packages/contract-test-suite/tests/test_schema_validation.py` - Added the new fixture ID to contract fixture validation expectations.
- `packages/contract-test-suite/scripts/run_contract_tests.py` - Added the WeCom service source path required by already-discovered contract tests.
- `packages/platform-contract/scripts/self_check.py` - Optional platform-foundation fixture validation and relationship checks for platform-contract self-check.

## Decisions Made

- The fixture uses the `education` domain to prove platform neutrality outside the lawyer/lawfirm path.
- `run_steps`, `run_events`, and `artifact_records` remain optional fixture bundle arrays; each item validates against the singular schema from Plan 09-02.
- Existing five-event fixture replay remains the default compatibility path; platform-foundation checks activate only when the new optional objects are present.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated platform-contract self-check for optional platform objects**
- **Found during:** Task 09-03-02
- **Issue:** Adding the new platform fixture made `self_check.py` treat `channel_message`, `run`, arrays, and `channel_delivery` as core events with `turn_id`, failing on `channel_message.turn_id`.
- **Fix:** Limited the original turn relationship loop to the five core events and added optional platform-foundation schema and relationship validation.
- **Files modified:** `packages/platform-contract/scripts/self_check.py`
- **Verification:** `PYTHONPATH=packages/platform-contract/src python packages/platform-contract/scripts/self_check.py` passed.
- **Committed in:** `2e59b49`

**2. [Rule 3 - Blocking] Added service source path to the local contract runner**
- **Found during:** Task 09-03-02
- **Issue:** `run_contract_tests.py` discovered Phase 5.5 tests importing `wecom_service`, but the runner did not add `services/wecom-service/src` to `sys.path`.
- **Fix:** Added the service source path to the runner-owned `source_paths`.
- **Files modified:** `packages/contract-test-suite/scripts/run_contract_tests.py`
- **Verification:** `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python packages/contract-test-suite/scripts/run_contract_tests.py` passed.
- **Committed in:** `2e59b49`

---

**Total deviations:** 2 auto-fixed (2 blocking).
**Impact on plan:** Both fixes were necessary for the planned verification commands to pass. They did not add runtime behavior or new dependencies.

## Issues Encountered

- The new fixture required updating existing test expectations from 2 to 3 platform fixtures and adding the new fixture ID to schema validation expectations.

## Verification Results

- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_platform_foundation_contracts.py`
  - Result: PASS
  - Output: `Ran 4 tests in 0.002s` and `OK`
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_fixture_replay.py`
  - Result: PASS
  - Output: `Ran 9 tests in 0.011s` and `OK`
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python packages/contract-test-suite/scripts/run_contract_tests.py`
  - Result: PASS
  - Output: `Ran 91 tests in 0.227s` and `OK`
- `PYTHONPATH=packages/platform-contract/src python packages/platform-contract/scripts/self_check.py`
  - Result: PASS
  - Output: `platform-contract self-check passed`

## Known Stubs

None.

## Threat Flags

None. This plan added sanitized fixtures and validation/test harness logic only; it introduced no new network endpoint, auth path, file-ingestion runtime, database, queue, or service behavior.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 09-04. Platform schema objects now have fixture replay coverage, and old V2 fixtures still validate through the same runner.

## Self-Check: PASSED

- Found summary file: `.planning/phases/09-architecture-contracts-schema-foundation/09-03-SUMMARY.md`
- Found created fixture: `packages/platform-contract/fixtures/platform_foundation_non_legal_run.json`
- Found mirrored fixture: `packages/contract-test-suite/fixtures/platform_foundation_non_legal_run.json`
- Found focused test file: `packages/contract-test-suite/tests/test_platform_foundation_contracts.py`
- Found task commit: `f29e851`
- Found task commit: `2e59b49`
- Found task commit: `1c01060`

---
*Phase: 09-architecture-contracts-schema-foundation*
*Completed: 2026-06-28*
