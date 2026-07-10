---
phase: 72-controlled-live-integration
fixed_at: 2026-07-10T05:27:52Z
review_path: .planning/phases/72-controlled-live-integration/72-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 72: Code Review Fix Report

**Fixed at:** 2026-07-10T05:27:52Z
**Source review:** `.planning/phases/72-controlled-live-integration/72-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: Whitespace-only live env bypasses fail-closed before network

**Files modified:** `scripts/smoke_test.py`, `packages/channels/qqbot/tests/test_smoke_toolkit.py`
**Commit:** 149f4f4
**Applied fix:** `load_live_credentials` now treats blank/whitespace-only env values as missing (`.strip()`), returns stripped values, and a new `test_whitespace_only_env_fails_closed` asserts SystemExit with key names only (no network).

### WR-02: Phase 5/8 carried-gate cue assertion is operator-precedence weak

**Files modified:** `packages/channels/qqbot/tests/test_smoke_toolkit.py`
**Commit:** 33c9cdd
**Applied fix:** Replaced weak `or`/`and` cue with parenthesized requirement: `("carried" and "human gate")` and `("not v1.9 done" or "not redefined")`.

### WR-03: Dual-knob comparison table abbreviates smoke value env names

**Files modified:** `runbook/SMOKE_TEST_RUNBOOK.md`
**Commit:** 4d90269
**Applied fix:** Dual-knob credentials row now lists full `INKSTATUTE_QQBOT_*` value env names (`APP_ID`, `CLIENT_SECRET`, `BOT_SECRET`, `USER_OPENID`, `REPLY_MSG_ID`).

## Remaining findings (out of scope / not fixed)

### IN-01: “Relabel” wording can be read as flipping `not_live_acceptance`
Info-tier; left for optional follow-up.

### IN-02: CI honesty scan covers only `run_v2_gates.py`
Info-tier; left for optional follow-up.

## Test results

Re-ran (no live QQ):

```
python -m unittest \
  packages.channels.qqbot.tests.test_smoke_toolkit.TestLiveEnvFailClosed \
  packages.channels.qqbot.tests.test_smoke_toolkit.TestRunbookLiveEnablement \
  packages.channels.qqbot.tests.test_smoke_toolkit.TestLiveHumanGateHonesty -v
```

**Result:** 13 passed, 0 failed. No live QQ / no live acceptance claimed.

---

_Fixed: 2026-07-10T05:27:52Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
