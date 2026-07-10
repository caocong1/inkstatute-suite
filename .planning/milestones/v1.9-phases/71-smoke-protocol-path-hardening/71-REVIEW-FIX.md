---
phase: 71-smoke-protocol-path-hardening
fixed_at: 2026-07-10T05:18:41Z
review_path: .planning/phases/71-smoke-protocol-path-hardening/71-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 71: Code Review Fix Report

**Fixed at:** 2026-07-10T05:18:41Z
**Source review:** `.planning/phases/71-smoke-protocol-path-hardening/71-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: Protocol evidence fields are inferred, not read from composition

**Files modified:** `scripts/smoke_test.py`
**Commit:** `9e74015`
**Applied fix:** `_RecordingScheduler` now stores thunk return values in `self.results`. `_step_protocol_path_dry_run` maps allowlisted `ingress_action`, `run_id_present`, `branch`, `deliver_accepted`, and `boundary_action` from the composition dict, with Fake side-effect counts as secondary fail-closed checks on `ok`.

### WR-02: Fail-closed Protocol gate is untested (false confidence)

**Files modified:** `packages/channels/qqbot/tests/test_smoke_toolkit.py`
**Commit:** `c280afe`
**Applied fix:** Replaced happy-path-only `test_protocol_path_required_for_success` with a patch that forces `_step_protocol_path_dry_run` to return failed `session_ingress`/`adapter_deliver` and asserts `SystemExit` mentioning `session_ingress`.

### WR-03: Runbook Expected outputs over-applies Protocol steps to live

**Files modified:** `runbook/SMOKE_TEST_RUNBOOK.md`
**Commit:** `958d4d6`
**Applied fix:** Scoped Protocol step list to dry-run and noted that `--live` records leaf steps only; host Protocol live coverage is Phase 72.

## Remaining findings (out of scope / Info)

### IN-01: `PROTOCOL_FIXED_NOW` is computed at import time
Not fixed (`fix_scope=critical_warning`).

### IN-02: Dry-run outcome metadata ignores Protocol Fake transport activity
Not fixed (`fix_scope=critical_warning`).

## Test results

Re-ran `python -m unittest packages.channels.qqbot.tests.test_smoke_toolkit -v` after fixes:

- **19 tests, OK** (4.111s)
- Did **not** run `--live`
- No live acceptance claimed

---

_Fixed: 2026-07-10T05:18:41Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
