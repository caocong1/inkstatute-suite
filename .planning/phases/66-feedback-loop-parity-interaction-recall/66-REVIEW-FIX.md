---
phase: 66-feedback-loop-parity-interaction-recall
fixed_at: 2026-07-09T11:59:12Z
review_path: .planning/phases/66-feedback-loop-parity-interaction-recall/66-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 66: Code Review Fix Report

**Fixed at:** 2026-07-09T11:59:12Z
**Source review:** `.planning/phases/66-feedback-loop-parity-interaction-recall/66-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Missing wakeup basis defaults to now (softens 30-day window)

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`, `packages/channels/qqbot/tests/test_wakeup_recall.py`
**Commit:** `24d5263`
**Applied fix:** Fail closed with `qqbot_wakeup_outside_window` when neither `last_user_message_at` nor store basis exists. Seeding `now` requires explicit `wakeup_basis_unknown_ok=True`. Happy-path wakeup test now supplies `last_user_message_at`; added fail-closed and opt-in coverage.

### WR-02: Wakeup quota check-then-send is non-atomic

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`, `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`, `packages/channels/qqbot/tests/test_wakeup_recall.py`
**Commit:** `f244557`
**Applied fix:** `InMemoryWakeupPeriodStore` gained locked `try_reserve` / `release` / `commit`. `_deliver_wakeup` reserves before `send_message`, commits on success, releases on send failure. Legacy `record_send` retained for stores without reserve APIs. Added reserve concurrency unit test.

## Test results

```text
PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src
python -m unittest discover -s packages/channels/qqbot/tests -p 'test_wakeup*.py'
→ Ran 10 tests — OK

PYTHONPATH=...:services/feedback-service/src
python -m unittest discover -s packages/channels/qqbot/tests -p 'test_*feedback*.py'
→ Ran 24 tests — OK
```

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-07-09T11:59:12Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
