---
phase: 71-smoke-protocol-path-hardening
plan: 03
subsystem: testing
tags: [qqbot, smoke, ci, runbook]

requires:
  - phase: 71-smoke-protocol-path-hardening
    provides: Protocol-path dry-run + sanitized evidence allowlist
provides:
  - TestProtocolPathCiHonesty CI honesty proofs
  - Runbook dry-run Protocol-path operator note
  - Full leaf+Protocol toolkit regression green
affects:
  - Phase 72 controlled live HUMAN GATE (docs only; no live claim)

tech-stack:
  added: []
  patterns:
    - CI honesty asserts host helper imports + Protocol evidence steps
    - Runbook documents Protocol path without expanding live scope

key-files:
  created: []
  modified:
    - packages/channels/qqbot/tests/test_smoke_toolkit.py
    - runbook/SMOKE_TEST_RUNBOOK.md

key-decisions:
  - "No new run_v2_gates.py gate — reuse qqbot-channel discover"
  - "Phase 72 owns live; dry-run never claims live acceptance"

patterns-established:
  - "TestProtocolPathCiHonesty locks leaf-vs-Protocol host-complete claim"

requirements-completed: [SMOKE-01, SMOKE-02]

duration: 2min
completed: 2026-07-10
---

# Phase 71 Plan 03: CI Honesty + Runbook Summary

**CI dry-run honesty and operator runbook now require host Protocol-path steps; full smoke toolkit (19 tests) and CLI dry-run remain green with `not_live_acceptance=true`.**

## Performance

- **Duration:** 2min
- **Started:** 2026-07-10T05:13:33Z
- **Completed:** 2026-07-10T05:14:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `TestProtocolPathCiHonesty` (CLI exit 0, host imports, runbook Protocol cues, callback fixture safety)
- Updated `runbook/SMOKE_TEST_RUNBOOK.md` dry-run section for verify_and_ack → ingress/session → deliver
- Full `test_smoke_toolkit` (19 tests) + dry-run CLI regression green with leaf + Protocol steps all ok

## Task Commits

1. **Task 1: CI honesty tests + runbook dry-run Protocol note** - `3d2524e` (feat)
2. **Task 2: Full smoke toolkit + leaf regression gate** - verification only (no code changes; suite already green)

## Files Created/Modified
- `packages/channels/qqbot/tests/test_smoke_toolkit.py` - TestProtocolPathCiHonesty
- `runbook/SMOKE_TEST_RUNBOOK.md` - Protocol-path dry-run documentation + evidence example keys

## Decisions Made
- Keep existing `qqbot-channel` gate; no new gate name
- Do not expand live credential/enablement docs (Phase 72)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None — dry-run remains Fake-only. Live remains Phase 72 HUMAN GATE.

## Known Stubs
None

## Threat Flags
None

## Self-Check: PASSED
- FOUND: packages/channels/qqbot/tests/test_smoke_toolkit.py
- FOUND: runbook/SMOKE_TEST_RUNBOOK.md
- FOUND: 3d2524e
