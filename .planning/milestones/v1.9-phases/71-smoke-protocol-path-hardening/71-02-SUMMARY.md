---
phase: 71-smoke-protocol-path-hardening
plan: 02
subsystem: testing
tags: [qqbot, smoke, evidence, sanitization]

requires:
  - phase: 71-smoke-protocol-path-hardening
    provides: Protocol-path dry-run steps adapter_ack/session_ingress/adapter_deliver
provides:
  - Full RESEARCH Protocol step allowlist under smoke_evidence.v1
  - TestProtocolEvidenceSanitized SMOKE-02 proofs
affects:
  - 71-03 CI honesty / full toolkit regression

tech-stack:
  added: []
  patterns:
    - Protocol steps share leaf sanitize_evidence + _strip_forbidden + ban-list

key-files:
  created: []
  modified:
    - scripts/smoke_test.py
    - packages/channels/qqbot/tests/test_smoke_toolkit.py

key-decisions:
  - "Keep schema inkstatute.qqbot.smoke_evidence.v1 (no v2 fork)"
  - "Protocol allowlist matches RESEARCH Pattern 2 exact key sets"

patterns-established:
  - "Pattern 2: adapter_ack/session_ingress/adapter_deliver allowlisted fields only"

requirements-completed: [SMOKE-02]

duration: 2min
completed: 2026-07-10
---

# Phase 71 Plan 02: Protocol Evidence Allowlist Summary

**Protocol-path dry-run evidence now survives sanitize under schema v1 with RESEARCH-safe keys only, forced `not_live_acceptance=true`, and zero secrets/raw bodies.**

## Performance

- **Duration:** 2min
- **Started:** 2026-07-10T05:12:12Z
- **Completed:** 2026-07-10T05:13:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `TestProtocolEvidenceSanitized` proving full Protocol allowlist keys and dirty-payload stripping
- Extended `TestEvidenceSchema` to require Protocol steps after sanitize
- Expanded `_STEP_KEY_ALLOW` for `adapter_ack` / `session_ingress` / `adapter_deliver` per RESEARCH Pattern 2

## Task Commits

1. **Task 1: RED — Protocol evidence sanitization tests** - `caa256b` (test)
2. **Task 2: GREEN — Allowlist Protocol steps in sanitize_evidence** - `d38133c` (feat)

## Files Created/Modified
- `packages/channels/qqbot/tests/test_smoke_toolkit.py` - TestProtocolEvidenceSanitized + schema Protocol expectations
- `scripts/smoke_test.py` - full Protocol `_STEP_KEY_ALLOW` frozensets

## Decisions Made
- No schema bump — reuse `inkstatute.qqbot.smoke_evidence.v1`
- Exact RESEARCH key sets (no extra composition fields)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None

## Known Stubs
None

## Threat Flags
None

## TDD Gate Compliance
- RED gate: `caa256b` test(71-02)
- GREEN gate: `d38133c` feat(71-02)

## Self-Check: PASSED
- FOUND: scripts/smoke_test.py
- FOUND: packages/channels/qqbot/tests/test_smoke_toolkit.py
- FOUND: caa256b
- FOUND: d38133c
