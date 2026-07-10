---
phase: 72-controlled-live-integration
plan: 01
subsystem: qqbot-smoke
tags: [qqbot, live, human-gate, fail-closed, honesty]

requires:
  - phase: 71-smoke-protocol-path-hardening
    provides: Protocol-path dry-run smoke + existing load_live_credentials fail-closed
  - phase: 67-one-click-smoke-test-toolkit
    provides: smoke_test.py --live leaf OpenAPI path and TestLiveEnvFailClosed
provides:
  - TestLiveHumanGateHonesty LIVE-01 proofs without live QQ network
  - sanitize_evidence always stamps not_live_acceptance=true (never False)
  - Phase 72 HUMAN GATE ownership clarified in docstring/--live help
affects: [72-02-runbook, phase-72-verification]

tech-stack:
  added: []
  patterns:
    - "Live honesty via unittest source/sanitize proofs — no live network in CI"
    - "sanitize_evidence forces not_live_acceptance=True for structured smoke evidence"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/tests/test_smoke_toolkit.py
    - scripts/smoke_test.py

key-decisions:
  - "sanitize_evidence always forces not_live_acceptance=True for structured evidence (dry-run and live) so tainted payloads cannot flip acceptance"
  - "Preserve leaf OpenAPI --live path; do not rewrite through handle_qqbot_webhook_request"
  - "CI honesty asserted by scanning run_v2_gates.py — no --live smoke invocation"

patterns-established:
  - "LIVE-01 verifiable via fail-closed + honesty tests alone; live QQ evidence remains HUMAN GATE"

requirements-completed: [LIVE-01]

duration: 2min
completed: 2026-07-10
---

# Phase 72 Plan 01: LIVE-01 Human-Gate Honesty Summary

**Controlled `--live` path honesty-gated: fail-closed env, forced `not_live_acceptance=true`, and CI never invokes live smoke — without live QQ network evidence.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-07-10T05:19:52Z
- **Completed:** 2026-07-10T05:21:20Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `TestLiveHumanGateHonesty` covering stamp honesty, CI gate scan, `--help` HUMAN GATE cue, and full `LIVE_ENV_KEYS` listing
- Hardened `sanitize_evidence` so structured evidence never emits `not_live_acceptance=False`
- Clarified Phase 72 HUMAN GATE ownership in module docstring and `--live` help text

## Task Commits

1. **Task 1: RED — LIVE-01 human-gate honesty tests** - `7def74b` (test)
2. **Task 2: GREEN — Harden live path honesty stamps** - `cae5021` (feat)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_smoke_toolkit.py` — `TestLiveHumanGateHonesty`
- `scripts/smoke_test.py` — sanitize stamp force-True + Phase 72 docstring/help

## Decisions Made

- Force `not_live_acceptance=True` in `sanitize_evidence` for all structured smoke evidence (not only dry-run), so a tainted live payload cannot claim acceptance
- Keep leaf OpenAPI live path unchanged (RESEARCH R-01); no Protocol-path live rewrite
- Do not add `--live` to `run_v2_gates.py`

## Deviations from Plan

### Auto-fixed Issues

None - plan executed as written. RED correctly failed on sanitize allowing `False` for mode=live; GREEN forced True.

## TDD Gate Compliance

- RED commit: `7def74b` (test)
- GREEN commit: `cae5021` (feat)
- No refactor commit needed

## Known Stubs

None — live path remains operator HUMAN GATE by design; script never auto-claims acceptance.

## Threat Flags

None beyond plan threat model (T-72-01..T-72-04 mitigated by honesty tests + stamp force).

## Verification Results

- `TestLiveEnvFailClosed` + `TestLiveHumanGateHonesty` green
- `python3 scripts/smoke_test.py --help` includes HUMAN GATE
- Cleared-env `--live` exits non-zero listing key names only
- No live QQ network used

## Self-Check: PASSED
