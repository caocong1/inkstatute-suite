---
phase: 67-one-click-smoke-test-toolkit
plan: 02
subsystem: testing
tags: [qqbot, smoke, evidence, runbook, privacy]

requires:
  - phase: 67-one-click-smoke-test-toolkit
    provides: dry-run smoke CLI + Wave 0 TestEvidence*/TestRunbookExists stubs
  - phase: 62-qqbot-egress
    provides: _rich_media_evidence sha256[:16] hashing pattern

provides:
  - sanitize_evidence allowlist + recursive ban-list redaction (SMOKE-04)
  - runbook/SMOKE_TEST_RUNBOOK.md operator docs (SMOKE-03)
  - Green TestEvidenceSanitized / TestEvidenceSchema / TestRunbookExists

affects:
  - 67-03 live fail-closed / human gate OpenAPI path
  - Human archival of sanitized live evidence under .planning/

tech-stack:
  added: []
  patterns:
    - "sanitize_evidence: strip forbidden keys then rebuild allowlisted schema/mode/steps"
    - "Dry-run always forces not_live_acceptance=true (Pitfall 5)"
    - "Runbook documents value env vars (not *_REF) and human-only archival copy"

key-files:
  created:
    - runbook/SMOKE_TEST_RUNBOOK.md
  modified:
    - scripts/smoke_test.py

key-decisions:
  - "Arbitrary dirty payloads return stripped remnant; structured smoke records rebuild to schema v1"
  - "Script never auto-writes under .planning/; archival is human copy of sanitized JSON only"
  - "Runbook forbids *_REF keys and embedding secrets; live remains HUMAN GATE"

patterns-established:
  - "Pattern: evidence ban-list scanned on serialized JSON (Authorization/access_token/DEMO secret/URLs)"
  - "Pattern: operator runbook under repo-root runbook/ with credential/dry-run/live/expected/evidence cues"

requirements-completed: [SMOKE-03, SMOKE-04]

duration: 2min
completed: 2026-07-09
---

# Phase 67 Plan 02: Evidence Sanitize + Runbook Summary

**Hardened `sanitize_evidence` allowlist/ban-list for SMOKE-04 and shipped `runbook/SMOKE_TEST_RUNBOOK.md` for dry-run plus live HUMAN GATE (SMOKE-03).**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-07-09T12:10:18Z
- **Completed:** 2026-07-09T12:12:06Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Recursive sanitize drops tokens, Authorization, BotSecret strings, content bodies, and URL keys; dry-run stamps `not_live_acceptance=true`
- Operator runbook covers value env vars, dry-run CLI, live HUMAN GATE, passive-reply window, optional ACK PUT, evidence ban-list, and archival path
- `TestEvidenceSanitized`, `TestEvidenceSchema`, and `TestRunbookExists` green; Plan 01 dry-run classes remain green

## Task Commits

Each task was committed atomically:

1. **Task 1: sanitize_evidence + schema stamps** - `cae1c71` (feat)
2. **Task 2: Operator SMOKE_TEST_RUNBOOK** - `20a304f` (docs)

**Plan metadata:** (docs commit after SUMMARY; STATE/ROADMAP intentionally not updated per executor prompt)

## Files Created/Modified

- `scripts/smoke_test.py` - Allowlist rebuild + recursive ban-list redaction for evidence stdout/`--evidence-out`
- `runbook/SMOKE_TEST_RUNBOOK.md` - Operator credential setup, commands, expected outputs, evidence/archival

## Decisions Made

- Structured smoke evidence always rebuilds to `inkstatute.qqbot.smoke_evidence.v1`; dirty ad-hoc dicts return stripped remnants without forbidden keys
- Dry-run never claims live acceptance; archival under `.planning/.../evidence/YYYYMMDD-smoke-live.json` is human copy only
- Runbook lists value env vars only (`APP_ID` / `CLIENT_SECRET` / `BOT_SECRET` / `USER_OPENID` / `REPLY_MSG_ID`)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. `TestLiveEnvFailClosed` remains green from Plan 01 (Plan 03 owns full live OpenAPI).

## Threat Flags

None beyond plan threat model (T-67-02 / T-67-03 mitigated by sanitize + runbook).

## Known Stubs

None — sanitize and runbook deliver plan goals; live OpenAPI path remains Plan 03 by design.

## User Setup Required

None for dry-run / CI. Live HUMAN GATE requires operator-exported value env vars and a fresh passive-reply `msg_id` (documented in runbook).

## Next Phase Readiness

- Plan 03: complete `--live` OpenAPI path behind human gate; keep fail-closed coverage

## Self-Check: PASSED

- FOUND: `scripts/smoke_test.py` (`sanitize_evidence`)
- FOUND: `runbook/SMOKE_TEST_RUNBOOK.md`
- FOUND: commit `cae1c71`
- FOUND: commit `20a304f`
- Verified: `TestEvidenceSanitized` / `TestEvidenceSchema` / `TestRunbookExists` green; dry-run `--evidence-out` ban-list clean

---
*Phase: 67-one-click-smoke-test-toolkit*
*Completed: 2026-07-09*
