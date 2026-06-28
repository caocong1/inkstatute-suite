---
phase: 05-wecom-shadow-loop-validation
plan: 01
subsystem: hermes-contract-layer
tags: [wecom, hermes, validation, contract-logs]

requires:
  - phase: 04-03
    provides: Contract JSONL event-stream replay helper and sanitized Phase 4 stream fixtures
provides:
  - Phase 5 WeCom evidence validation helper
  - Structured WeCom validation issue and report dataclasses
  - Unit coverage for feedback target, channel, ACK timing, stream errors, and privacy blockers
  - Opt-in live WeCom validation runbook with rollback and blocked evidence format
affects: [phase-05-plan-02, phase-05-plan-03, phase-06-read-and-feedback-service-apis]

tech-stack:
  added: []
  patterns:
    - Layer Phase 5 evidence checks on top of contract-test-suite stream replay
    - Return structured validation issues instead of raising for evidence blockers
    - Separate fixture validation from live WeCom validation status

key-files:
  created:
    - services/hermes-contract-layer/src/hermes_contract_layer/wecom_validation.py
    - services/hermes-contract-layer/tests/test_wecom_validation.py
    - services/hermes-contract-layer/docs/wecom_shadow_loop_validation.md
    - .planning/phases/05-wecom-shadow-loop-validation/05-01-SUMMARY.md
  modified:
    - services/hermes-contract-layer/README.md
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "Validate WeCom acceptance evidence with sanitized contract JSONL streams and optional ACK timing metadata."
  - "Require `AgentResult.feedback_target` only when feedback is expected and report missing source evidence as `missing_feedback_target`."
  - "Treat live WeCom validation as explicit operator work; repo tests never mutate `/home/sorawatcher/.hermes`."

patterns-established:
  - "WeCom validation helpers return `WeComValidationReport` with blocker codes rather than throwing for expected validation failures."
  - "Runbooks must record live status as `passed` or `blocked`; fixture results cannot be promoted to live acceptance."

requirements-completed:
  - REQ-wecom-daily-test-loop

duration: 5min
completed: 2026-06-28
---

# Phase 05 Plan 01: WeCom Validation Harness Summary

WeCom result-side evidence can now be validated locally against sanitized contract streams, with an operator runbook for opt-in live checks.

## Performance

- **Duration:** 5min
- **Started:** 2026-06-28T03:07:27Z
- **Completed:** 2026-06-28T03:12:20Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `validate_wecom_shadow_evidence`, `WeComValidationIssue`, and `WeComValidationReport`.
- Added unit tests for valid WeCom fixture evidence, missing feedback target, non-WeCom channel evidence, exact `raw_payload` keys, ACK timeout, and missing stream handling.
- Added a live validation runbook covering fixture status, live status, opt-in hook deployment, evidence collection, rollback, privacy rules, and blocked evidence format.
- Updated the Hermes contract layer README with the Phase 5 validation entrypoint and no-runtime-mutation statement.

## Task Commits

1. **Task 1: Add WeCom evidence validation helper** - `a1b118a` (feat)
2. **Task 2: Document opt-in live validation runbook** - `9793109` (docs)

## Files Created/Modified

- `services/hermes-contract-layer/src/hermes_contract_layer/wecom_validation.py` - validates Phase 5 WeCom evidence on top of event-stream replay.
- `services/hermes-contract-layer/tests/test_wecom_validation.py` - focused stdlib tests for validation outcomes and blockers.
- `services/hermes-contract-layer/docs/wecom_shadow_loop_validation.md` - operator runbook for fixture and live validation.
- `services/hermes-contract-layer/README.md` - links the runbook and states that repo tests never mutate live Hermes runtime files.

## Decisions Made

- The helper catches stream loading/schema errors and returns `stream_invalid` so validation reports remain structured.
- ACK timing is optional metadata; when supplied, both timestamps are required and must complete within the configured timeout.
- Privacy scanning rejects exact nested `raw_payload` keys and secret-like strings across all event payloads.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## Verification

- PASS: `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -p 'test_wecom_validation.py' -v`
- PASS: `rg -n "Fixture validation status|Live WeCom status|Opt-in hook deployment|INKSTATUTE_CONTRACT_LOG_PATH|blocked" services/hermes-contract-layer/docs/wecom_shadow_loop_validation.md && rg -n "WeCom shadow loop validation|repo tests never mutate" services/hermes-contract-layer/README.md`
- PASS: `python -m compileall services/hermes-contract-layer/src services/hermes-contract-layer/tests`

## User Setup Required

None for fixture validation. Live WeCom validation remains explicit operator work and is documented in `services/hermes-contract-layer/docs/wecom_shadow_loop_validation.md`.

## Next Phase Readiness

Plan 05-02 can add the minimal feedback normalizer using sanitized `feedback.jsonl` and `pending_previews.jsonl` samples, then link normalized feedback to the result-side `feedback_target` evidence.

---
*Phase: 05-wecom-shadow-loop-validation*
*Completed: 2026-06-28*
