---
phase: 67-one-click-smoke-test-toolkit
plan: 03
subsystem: testing
tags: [qqbot, smoke, live-gate, safety, adapter-04, fail-closed]

requires:
  - phase: 67-one-click-smoke-test-toolkit
    provides: dry-run smoke CLI + sanitize_evidence + runbook + Wave 0 TestLiveEnvFailClosed
  - phase: 61-qqbot-token
    provides: TokenManager + UrllibTokenTransport
  - phase: 62-qqbot-egress
    provides: UrllibMessageTransport + send_message + ack_interaction

provides:
  - load_live_credentials fail-closed env injection (value vars only)
  - --live HUMAN GATE path with Urllib transports after validation
  - Green TestLiveEnvFailClosed; ADAPTER-03/04 safety still green
  - qqbot-channel gate PYTHONPATH includes feedback-service (Phase 66 e2e)

affects:
  - Phase 67 verification / UAT (live remains human gate)
  - Operator live smoke via runbook

tech-stack:
  added: []
  patterns:
    - "load_live_credentials before any Urllib* construction (Pattern 2)"
    - "Live ACK PUT only when --callback-json has real non-fixture interaction_id (OQ-1)"
    - "Live evidence mode=live with not_live_acceptance=true (human may relabel archive)"

key-files:
  created:
    - .planning/phases/67-one-click-smoke-test-toolkit/deferred-items.md
  modified:
    - scripts/smoke_test.py
    - packages/channels/qqbot/tests/test_smoke_toolkit.py
    - scripts/run_v2_gates.py

key-decisions:
  - "Urllib transports constructed only on validated --live path; dry-run remains default"
  - "Fixture interaction ids never trigger live ACK PUT"
  - "Extended existing qqbot-channel gate path (no new gate name — OQ-2)"
  - "STATE.md / ROADMAP.md intentionally not updated per executor prompt"

patterns-established:
  - "Pattern: live fail-closed lists missing env key names only, never values"
  - "Pattern: smoke live path stamps mode=live but keeps not_live_acceptance=true from script"

requirements-completed: [SMOKE-01, SMOKE-02]

duration: 4min
completed: 2026-07-09
---

# Phase 67 Plan 03: Live Fail-Closed + Safety Summary

**Completed `--live` as a fail-closed HUMAN GATE with env-only credentials and Urllib transports after validation; CI stays dry-run with ADAPTER-03/04 invariants green.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-07-09T12:13:39Z
- **Completed:** 2026-07-09T12:17:16Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `load_live_credentials()` fails closed on missing value env vars (key names only; no secret echo)
- Validated `--live` constructs `UrllibTokenTransport` + `UrllibMessageTransport`; dry-run still Fake-only default
- Live callback always normalizes; ACK PUT only for real (non-fixture) `interaction_id` from `--callback-json` (OQ-1)
- Full qqbot discover green (321) with feedback-service on path; no wecom; `dependencies = []`; no new `run_v2_gates` gate name

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: strengthen TestLiveEnvFailClosed** - `0cf4f9b` (test)
2. **Task 1 GREEN: live fail-closed + Urllib human gate** - `e264cc9` (feat)
3. **Task 2: Safety freeze + qqbot-channel regression** - `87a50f1` (chore)

**Plan metadata:** `20ea7d7` (docs: complete plan; STATE/ROADMAP intentionally not updated per executor prompt)

## Files Created/Modified

- `scripts/smoke_test.py` - `load_live_credentials`, live Urllib path, OQ-1 ACK gating, evidence `mode=live`
- `packages/channels/qqbot/tests/test_smoke_toolkit.py` - Green `TestLiveEnvFailClosed` + wecom_service zero-match assertion
- `scripts/run_v2_gates.py` - Existing `qqbot-channel` gate PYTHONPATH includes `feedback-service/src`
- `.planning/phases/67-one-click-smoke-test-toolkit/deferred-items.md` - Gate path fix note

## Decisions Made

- Live remains HUMAN GATE — CI never requires live QQ network success
- Script prefers `not_live_acceptance=true` even for `mode=live`; human archival may relabel
- No new `run_v2_gates.py` entry for smoke (OQ-2); rely on discover + dry-run CLI

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] qqbot-channel discover missing feedback_service**
- **Found during:** Task 2 (full unittest discover)
- **Issue:** Four Phase 66 e2e tests import `feedback_service.queue`; gate PYTHONPATH omitted `services/feedback-service/src`, so discover failed with 4 errors
- **Fix:** Extended existing `qqbot-channel` gate path tuple to include `feedback_src` (no new gate name)
- **Files modified:** `scripts/run_v2_gates.py`, `deferred-items.md`
- **Verification:** `unittest discover -s packages/channels/qqbot/tests` → 321 OK with feedback path
- **Committed in:** `87a50f1` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3)
**Impact on plan:** Necessary for plan acceptance criterion “full qqbot discover exits 0”; no scope creep into live network or new gate names.

## Issues Encountered

None beyond the pre-existing gate PYTHONPATH gap fixed above.

## User Setup Required

None for CI/dry-run. Live HUMAN GATE still requires operator-exported value env vars per `runbook/SMOKE_TEST_RUNBOOK.md` (not executed in this plan).

## Next Phase Readiness

- Phase 67 toolkit complete for autonomous delivery: dry-run CI + fail-closed live path + runbook
- Live platform execution remains open HUMAN GATE (deferred from autonomous delivery)
- Ready for phase verification / UAT without requiring live QQ

## Threat Flags

None — no new network endpoints beyond existing Urllib OpenAPI clients behind explicit `--live`; secrets stay env-only and sanitized.

## Known Stubs

None — live path is real wiring behind HUMAN GATE; CI does not stub network success.

## Self-Check: PASSED

- FOUND: `scripts/smoke_test.py` (`load_live_credentials`, `UrllibMessageTransport`, `--live`)
- FOUND: `packages/channels/qqbot/tests/test_smoke_toolkit.py` (`TestLiveEnvFailClosed`)
- FOUND: commits `0cf4f9b`, `e264cc9`, `87a50f1`
---
*Phase: 67-one-click-smoke-test-toolkit*
*Completed: 2026-07-09*
