---
phase: 67-one-click-smoke-test-toolkit
plan: 01
subsystem: testing
tags: [qqbot, smoke, dry-run, cli, fake-transport, ed25519]

requires:
  - phase: 59-qqbot-signature
    provides: derive_keypair / verify_callback_signature / DEMO vectors
  - phase: 62-qqbot-egress
    provides: build_text_envelope / build_feedback_keyboard_envelope / FakeMessageTransport
  - phase: 66-qqbot-feedback
    provides: handle_feedback_callback + INTERACTION fixture

provides:
  - Wave 0 test_smoke_toolkit.py with seven named classes (SMOKE-01..04)
  - scripts/smoke_test.py default --dry-run orchestration (signature + text + keyboard + callback)
  - Importable run_smoke / sanitize_evidence / load_credentials surface for Plans 02–03

affects:
  - 67-02 evidence sanitize + runbook
  - 67-03 live fail-closed / human gate

tech-stack:
  added: []
  patterns:
    - "stdlib scripts/smoke_test.py path-bootstraps qqbot/channel-core/platform-contract/platform-runtime"
    - "argparse store_const dest=mode with default dry-run (mutually exclusive --live)"
    - "FakeTokenTransport + FakeMessageTransport only on dry-run; DEMO BotSecret + fixture openid/msg_id"

key-files:
  created:
    - packages/channels/qqbot/tests/test_smoke_toolkit.py
    - scripts/smoke_test.py
  modified: []

key-decisions:
  - "Dry-run is default via store_const dest=mode; never construct Urllib* transports on dry-run path"
  - "sanitize_evidence is identity pass-through in Plan 01; Plan 02 hardens ban-list redaction"
  - "--live fails closed with incomplete env (key names only); full OpenAPI path deferred to Plan 03"

patterns-established:
  - "Pattern: smoke is orchestrator-only — call production signature/sender/feedback helpers"
  - "Pattern: evidence schema inkstatute.qqbot.smoke_evidence.v1 with not_live_acceptance true for dry-run"

requirements-completed: [SMOKE-01, SMOKE-02]

duration: 3min
completed: 2026-07-09
---

# Phase 67 Plan 01: Dry-Run Smoke Toolkit Summary

**Stdlib `scripts/smoke_test.py --dry-run` reuses qqbot signature/sender/feedback modules with Fake transports and DEMO vectors; Wave 0 unittest stubs encode SMOKE-01..04 for Plans 02–03.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-07-09T12:06:57Z
- **Completed:** 2026-07-09T12:09:39Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Wave 0 RED `test_smoke_toolkit.py` with seven exact class names for Plans 01–03
- Green dry-run CLI: DEMO Ed25519 verify, text msg_type=0, keyboard msg_type=2, fixture INTERACTION normalize (no ACK PUT)
- CI-safe Fake transports only; no wecom imports; no new package dependencies

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED test_smoke_toolkit stubs** - `440f73e` (test)
2. **Task 2: Dry-run smoke CLI orchestration** - `6d4208a` (feat)

**Plan metadata:** (docs commit after SUMMARY)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_smoke_toolkit.py` - Wave 0 + Plan 01 dry-run coverage; Plan 02/03 stubs
- `scripts/smoke_test.py` - One-click smoke CLI (default dry-run)

## Decisions Made

- Used `store_const` on `dest="mode"` so default is dry-run without the `store_true default=True` argparse bug
- Left `sanitize_evidence` as JSON round-trip (clean evidence already); recursive ban-list is Plan 02
- `--live` with missing env exits non-zero listing key *names* only; full live OpenAPI deferred to Plan 03

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Plan 02 classes `TestEvidenceSanitized` / `TestRunbookExists` correctly remain RED. `TestEvidenceSchema` and `TestLiveEnvFailClosed` already pass with Plan 01 surface (acceptable early green).

## User Setup Required

None - no external service configuration required for dry-run / CI.

## Next Phase Readiness

- Plan 02: harden `sanitize_evidence` ban-list + ship `runbook/SMOKE_TEST_RUNBOOK.md`
- Plan 03: complete `--live` OpenAPI path behind human gate; keep fail-closed coverage

## Self-Check: PASSED

- FOUND: `scripts/smoke_test.py`
- FOUND: `packages/channels/qqbot/tests/test_smoke_toolkit.py`
- FOUND: commit `440f73e`
- FOUND: commit `6d4208a`
- Verified: `TestDryRunNoNetwork` / `TestDryRunEgress` / `TestDryRunCallback` green; `python3 scripts/smoke_test.py --dry-run` exits 0

---
*Phase: 67-one-click-smoke-test-toolkit*
*Completed: 2026-07-09*
