---
phase: 05-wecom-shadow-loop-validation
plan: 03
subsystem: contract-test-suite
tags: [wecom, feedback-event, replay, validation-evidence, live-blocker]

requires:
  - phase: 05-01
    provides: WeCom evidence validation helper and live validation runbook
  - phase: 05-02
    provides: Minimal WeCom feedback normalizer and sanitized feedback/previews fixtures
provides:
  - Phase 5 WeCom result-to-feedback contract stream fixture
  - Full five-event fixture connecting AgentResult.feedback_target to FeedbackEvent.feedback_target
  - Contract-suite tests for Phase 5 replay, normalization shape, route-mismatch guardrails, and privacy
  - Evidence report separating fixture pass from blocked live WeCom validation
affects: [phase-06-read-and-feedback-service-apis, phase-07-ci-composability-privacy-gates, phase-08-lawyer-trial-acceptance]

tech-stack:
  added: []
  patterns:
    - Keep live WeCom acceptance separate from fixture replay
    - Register new full-bundle fixtures in schema validation expectations
    - Test service normalizer integration from contract-suite without changing the package runner

key-files:
  created:
    - packages/contract-test-suite/tests/test_phase5_wecom_loop.py
    - packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl
    - packages/contract-test-suite/fixtures/phase5_wecom_feedback_loop_fixture.json
    - .planning/phases/05-wecom-shadow-loop-validation/05-WECOM-VALIDATION.md
    - .planning/phases/05-wecom-shadow-loop-validation/05-03-SUMMARY.md
  modified:
    - packages/contract-test-suite/README.md
    - packages/contract-test-suite/tests/test_schema_validation.py
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "Fixture replay proves result-to-feedback continuity but does not prove live WeCom acceptance."
  - "Live WeCom status remains `blocked` until the operator runbook is actually completed with sanitized evidence references."
  - "The Phase 5 full JSON fixture is included in generic schema validation expectations."

patterns-established:
  - "Phase evidence reports must include separate `fixture_status` and `live_wecom_status` frontmatter."
  - "Contract-suite Phase 5 tests assert both replay relationships and normalizer-produced FeedbackEvent shape."

requirements-completed:
  - REQ-wecom-daily-test-loop

duration: 5min
completed: 2026-06-28
---

# Phase 05 Plan 03: WeCom Replay and Evidence Summary

Phase 5 now has fixture-backed WeCom result-to-feedback replay and an evidence report that honestly blocks live WeCom acceptance until runtime validation is performed.

## Performance

- **Duration:** 5min
- **Started:** 2026-06-28T03:18:48Z
- **Completed:** 2026-06-28T03:23:46Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added `phase5_wecom_contract_stream.jsonl` for sanitized result-side stream replay.
- Added `phase5_wecom_feedback_loop_fixture.json` connecting AgentResult and FeedbackEvent relationships.
- Added `test_phase5_wecom_loop.py` covering stream replay, full bundle replay, normalizer output shape, route-mismatch safeguards, and privacy scanning.
- Added `05-WECOM-VALIDATION.md` with fixture status passed and live WeCom status blocked.
- Updated contract-test-suite README with Phase 5 replay scope and live-validation distinction.

## Task Commits

1. **Task 1: Add Phase 5 result-to-feedback replay fixture and tests** - `6ee8c0d` (test)
2. **Task 2/3: Add evidence report and live blocker status** - `32d76c6` (docs)
3. **Verification fix: Register Phase 5 fixture id** - `a07024d` (test)

## Files Created/Modified

- `packages/contract-test-suite/tests/test_phase5_wecom_loop.py` - Phase 5 replay and privacy tests.
- `packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl` - sanitized four-event WeCom result stream.
- `packages/contract-test-suite/fixtures/phase5_wecom_feedback_loop_fixture.json` - full five-event fixture with result-feedback continuity.
- `.planning/phases/05-wecom-shadow-loop-validation/05-WECOM-VALIDATION.md` - fixture/live evidence report.
- `packages/contract-test-suite/README.md` - Phase 5 replay and live validation boundary.
- `packages/contract-test-suite/tests/test_schema_validation.py` - expected fixture ID registry update.

## Decisions Made

- Live WeCom validation was not run; `live_wecom_status` remains `blocked` with explicit missing prerequisites.
- The Phase 5 test inserts service source paths locally so the package runner remains unchanged.
- The full feedback fixture uses the normalizer's canonical rating event exactly, keeping the fixture and normalizer relationship shape aligned.

## Deviations from Plan

### Auto-fixed Issues

**1. Fixture registry expectation update**
- **Found during:** Full contract-test-suite runner
- **Issue:** `test_valid_platform_contract_fixtures_pass_for_all_events` expected a fixed set of JSON fixture IDs and failed after adding `phase5-wecom-feedback-loop-001`.
- **Fix:** Added the Phase 5 fixture ID to the expected set.
- **Files modified:** `packages/contract-test-suite/tests/test_schema_validation.py`
- **Verification:** `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py`
- **Committed in:** `a07024d`

**Total deviations:** 1 auto-fixed fixture-registry update.
**Impact on plan:** Required for the new full bundle fixture to participate in generic schema validation.

## Issues Encountered

Live Hermes/WeCom validation could not be completed in this session because no live runtime evidence was available. This is recorded as a blocker, not a pass.

## Verification

- PASS: `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src:../../services/feedback-service/src:../../services/hermes-contract-layer/src python -m unittest discover -s tests -p 'test_phase5_wecom_loop.py' -v`
- PASS: `rg -n "Live WeCom status: (passed|blocked)|Fixture validation|Feedback normalization|QQ Bot and WeChat" .planning/phases/05-wecom-shadow-loop-validation/05-WECOM-VALIDATION.md && rg -n "Phase 5|WeCom result-to-feedback|live validation" packages/contract-test-suite/README.md`
- PASS: `python -m compileall services/hermes-contract-layer/src services/hermes-contract-layer/tests services/feedback-service/src services/feedback-service/tests packages/contract-test-suite/src packages/contract-test-suite/tests`
- PASS: `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py`
- PASS: `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v`
- PASS: `PYTHONPATH=services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/feedback-service/tests -v`
- PASS: `git diff --check`

## User Setup Required

Live validation is still required before live WeCom acceptance can be claimed. Follow `services/hermes-contract-layer/docs/wecom_shadow_loop_validation.md` and update `05-WECOM-VALIDATION.md` with sanitized evidence references.

## Next Phase Readiness

Phase 6 can build read and feedback service APIs on top of the validated fixture contracts. It must preserve the live blocker until operator-run WeCom evidence exists.

---
*Phase: 05-wecom-shadow-loop-validation*
*Completed: 2026-06-28*
