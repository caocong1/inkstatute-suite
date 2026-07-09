---
phase: 64-qqbotsessionruntime-qqbotingressruntime
fixed_at: 2026-07-09T11:02:53Z
review_path: .planning/phases/64-qqbotsessionruntime-qqbotingressruntime/64-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 64: Code Review Fix Report

**Fixed at:** 2026-07-09T11:02:53Z
**Source review:** `.planning/phases/64-qqbotsessionruntime-qqbotingressruntime/64-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Ingress does not wire `message_id` as `idempotency_key`

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/ingress_runtime.py`, `packages/channels/qqbot/tests/test_ingress_runtime.py`
**Commit:** 934a267
**Applied fix:** `handle_callback` now resolves `idempotency_key` as `metadata.idempotency_key` → `metadata.message_id` → `turn.turn_id`. Added redelivery test asserting a second identical C2C callback returns `DUPLICATE_ANSWER_IGNORED` with the fixture `message_id` and a single `create_run`.

### WR-02: Ingress does not pass `now=received_at` into `handle_turn`

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/ingress_runtime.py`, `packages/channels/qqbot/tests/test_ingress_runtime.py`
**Commit:** 087a59f
**Applied fix:** `handle_callback` forwards `now=received_at` into `session_runtime.handle_turn`. Added expiry test where host clock is before `expires_at` but callback `received_at` is after, asserting `INTERRUPT_EXPIRED` without resume/`create_run`.

## Skipped Issues

None — IN-01 / IN-02 left as Info (not in critical_warning scope).

## Test Results

```
PYTHONPATH=packages/channels/qqbot/src:packages/platform-runtime/src:packages/channel-core/src:packages/platform-contract/src
python -m unittest \
  packages.channels.qqbot.tests.test_ingress_runtime \
  packages.channels.qqbot.tests.test_session_runtime \
  packages.channels.qqbot.tests.test_session_memory_runtime -v
```

Ran 31 tests — OK.

---

_Fixed: 2026-07-09T11:02:53Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
