---
phase: 72-controlled-live-integration
plan: 02
subsystem: qqbot-smoke
tags: [qqbot, runbook, dual-knob, human-gate, live]

requires:
  - phase: 72-controlled-live-integration
    provides: LIVE-01 honesty tests + sanitize stamp force-True
  - phase: 69-runtime-registration
    provides: dual-knob wiring documented in qqbot-service README
provides:
  - LIVE-02 operator runbook (host enablement, dual-knob, ACK windows)
  - TestRunbookLiveEnablement cue lock
  - Phase 72 archival path; Phase 5/8 remain carried human gates
affects: [phase-72-verification, operator-live-smoke]

tech-stack:
  added: []
  patterns:
    - "Runbook cue assertions lock LIVE-02 without live network"
    - "Smoke value env vs host *_REF documented as distinct tables"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/tests/test_smoke_toolkit.py
    - runbook/SMOKE_TEST_RUNBOOK.md

key-decisions:
  - "Archival path moved from Phase 67 to .planning/phases/72-controlled-live-integration/evidence/"
  - "Phase 5 WeCom UAT and Phase 8 lawyer trial remain explicitly carried human gates in runbook"
  - "Host dual-knob docs cross-link qqbot-service README rather than duplicating secret maps"

patterns-established:
  - "LIVE-02 verifiable via runbook cue unittests; live archive never required for phase complete"

requirements-completed: [LIVE-02, LIVE-01]

duration: 3min
completed: 2026-07-10
---

# Phase 72 Plan 02: LIVE-02 Runbook Enablement Summary

**Operator runbook now documents host dual-knob enablement, dry-run vs live HUMAN GATE, ACK/passive-reply windows, Phase 72 archival path, and Phase 5/8 carried gates — locked by unittest cues without live QQ network.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-07-10T05:22:30Z
- **Completed:** 2026-07-10T05:25:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added `TestRunbookLiveEnablement` covering host enablement, dual-knob, dry-run vs live, ACK windows, Phase 5/8, archival path
- Expanded `runbook/SMOKE_TEST_RUNBOOK.md` with LIVE-02 sections while preserving Phase 71 Protocol-path dry-run docs
- Full smoke toolkit (29 tests) + dry-run Protocol path green; `run_v2_gates.py` has no `--live` smoke

## Task Commits

1. **Task 1: RED — Runbook LIVE-02 cue tests** - `7ab1da4` (test)
2. **Task 2: GREEN — Expand runbook for LIVE-02 enablement** - `92b6710` (feat)
3. **Task 3: Full smoke toolkit + dry-run regression** - verification only (no code change; 29/29 green)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_smoke_toolkit.py` — `TestRunbookLiveEnablement`
- `runbook/SMOKE_TEST_RUNBOOK.md` — host enablement, dual-knob, carried gates, Phase 72 archival

## Decisions Made

- Move human archival path to Phase 72 directory (was Phase 67)
- Explicitly state Phase 5/8 remain carried human gates — not v1.9 done
- Cross-link `services/qqbot-service/README.md` for secret-ref tables

## Deviations from Plan

None - plan executed as written.

## TDD Gate Compliance

- RED commit: `7ab1da4` (test)
- GREEN commit: `92b6710` (feat)
- Task 3 verification-only (no commit)

## Known Stubs

None — live QQ operator run and acceptance archival remain HUMAN GATE by design.

## Threat Flags

None beyond plan threat model (T-72-05..T-72-08 mitigated by runbook language + cue tests).

## Verification Results

- `TestRunbookLiveEnablement` + live honesty classes green
- Full `test_smoke_toolkit` 29/29 green
- Dry-run Protocol path ok (`adapter_ack` / `session_ingress` / `adapter_deliver`)
- `run_v2_gates.py` has no `--live` smoke invocation
- No live QQ network used

## Self-Check: PASSED
