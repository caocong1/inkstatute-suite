---
phase: 71-smoke-protocol-path-hardening
plan: 01
subsystem: testing
tags: [qqbot, smoke, protocol-path, dry-run]

requires:
  - phase: 70-webhook-composition-path
    provides: handle_qqbot_webhook_request + build_qqbot_wired_runtime Fake composition harness
provides:
  - Mandatory Protocol-path dry-run stage (adapter_ack / session_ingress / adapter_deliver)
  - TestProtocolPathDryRun SMOKE-01 proofs
affects:
  - 71-02 evidence allowlist hardening
  - 71-03 CI honesty / runbook

tech-stack:
  added: []
  patterns:
    - Host-helper Protocol dry-run via Phase 70 webhook + wiring with Fake DI
    - RecordingScheduler sync post-ACK (no nested asyncio.run)

key-files:
  created: []
  modified:
    - scripts/smoke_test.py
    - packages/channels/qqbot/tests/test_smoke_toolkit.py

key-decisions:
  - "Protocol path uses handle_qqbot_webhook_request + build_qqbot_wired_runtime (not leaf-only)"
  - "Plan 01 allowlists only ok for Protocol steps; Plan 02 expands RESEARCH keys"
  - "Leaf steps remain secondary; Protocol steps are mandatory for dry-run success"

patterns-established:
  - "Pattern 1: _step_protocol_path_dry_run mirrors Phase 70 composition harness"
  - "Pattern: fail closed SystemExit if any Protocol step not ok"

requirements-completed: [SMOKE-01]

duration: 2min
completed: 2026-07-10
---

# Phase 71 Plan 01: Protocol-Path Dry-Run Summary

**Dry-run now drives verify_and_ack → ingress/session → deliver through Phase 70 host webhook helpers with Fake transports; leaf-only evidence can no longer satisfy success.**

## Performance

- **Duration:** 2min
- **Started:** 2026-07-10T05:10:10Z
- **Completed:** 2026-07-10T05:11:58Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `TestProtocolPathDryRun` covering Protocol step keys, host helper imports, Fake-only DI, and leaf-only insufficiency
- Implemented `_step_protocol_path_dry_run` using `build_qqbot_wired_runtime` + `handle_qqbot_webhook_request` with Fake transports and sync RecordingScheduler
- Wired mandatory Protocol steps into `run_smoke` dry-run; CLI exits 0 with `adapter_ack` / `session_ingress` / `adapter_deliver` ok

## Task Commits

1. **Task 1: RED — Protocol-path dry-run toolkit tests** - `650ff3d` (test)
2. **Task 2: GREEN — Mandatory Protocol-path stage in smoke dry-run** - `5f18b99` (feat)

## Files Created/Modified
- `packages/channels/qqbot/tests/test_smoke_toolkit.py` - TestProtocolPathDryRun SMOKE-01 proofs
- `scripts/smoke_test.py` - qqbot-service path bootstrap, Protocol-path helper, mandatory dry-run stage, minimal Protocol allowlist

## Decisions Made
- Reuse Phase 70 composition harness pattern (signed C2C fixture, FIXED_NOW, reply_text, RecordingScheduler)
- Keep leaf steps as secondary coverage; Protocol steps gate dry-run success
- Defer full Protocol allowlist keys to Plan 02 (Plan 01 keeps `ok` only so SMOKE-02 RED remains meaningful)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - dry-run uses DEMO/fixture credentials and Fake transports only.

## Known Stubs
None

## Threat Flags
None - no new network endpoints; Fake-only dry-run DI preserved (T-71-01/02 mitigated).

## TDD Gate Compliance
- RED gate: `650ff3d` test(71-01)
- GREEN gate: `5f18b99` feat(71-01)

## Self-Check: PASSED
- FOUND: scripts/smoke_test.py
- FOUND: packages/channels/qqbot/tests/test_smoke_toolkit.py
- FOUND: 650ff3d
- FOUND: 5f18b99
