---
phase: 66-feedback-loop-parity-interaction-recall
reviewed: 2026-07-09T11:54:00Z
fixed_at: 2026-07-09T11:59:12Z
depth: quick
files_reviewed: 5
files_reviewed_list:
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/feedback_ingress.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
  - packages/channels/qqbot/pyproject.toml
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
warnings_fixed: 2
status: warnings_fixed
---

# Phase 66: Code Review Report

**Reviewed:** 2026-07-09T11:54:00Z
**Fixed:** 2026-07-09T11:59:12Z
**Depth:** quick
**Files Reviewed:** 5
**Status:** warnings_fixed (WR-01, WR-02)

## Summary

Quick adversarial review of Phase 66 feedback/wakeup changes, focused on: no WeCom imports, FEEDBACK-03 `idempotency_key`, ACK no-op-if-sent, C2C-only `is_wakeup` period gate, and `deps=[]`.

**Focus gates:** all five pass.

- No `wecom` / `wecom_service` imports in qqbot production modules (AST + string scan clean).
- `normalize_interaction_event` stamps `metadata.idempotency_key = "{msg_id}:{button_identity}"`.
- `ensure_interaction_ack` returns `noop` when `interaction_ack_status=="sent"` and only PUTs for `pending_host`.
- Wakeup is C2C-only (`wakeup_scene_supported`); group fail-closed; P0–P3 Asia/Shanghai period gate present; wakeup envelopes omit `msg_id`/`event_id`/`msg_seq`.
- `packages/channels/qqbot/pyproject.toml` and `services/feedback-service/pyproject.toml` both have `dependencies = []`.

WR-01 and WR-02 were fixed in iteration 1 (`24d5263`, `f244557`). See `66-REVIEW-FIX.md`.

## Warnings

### WR-01: Missing wakeup basis defaults to now (softens 30-day window) — FIXED

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`
**Status:** fixed in `24d5263`
**Issue:** When `allow_wakeup`/`is_wakeup` is set but neither `last_user_message_at` nor a prior store basis exists, `_deliver_wakeup` previously called `note_user_message(user_openid, datetime.now(UTC))`, forcing P0 and never returning `qqbot_wakeup_outside_window`.
**Resolution:** Missing basis now fails closed with `qqbot_wakeup_outside_window`. Hosts may opt in with `wakeup_basis_unknown_ok=True` to seed `now`.

### WR-02: Wakeup quota check-then-send is non-atomic — FIXED

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` / `sender.py`
**Status:** fixed in `f244557`
**Issue:** `check_wakeup_quota` then `send_message` then `store.record_send` had no lock; concurrent `_deliver_wakeup` calls could both POST.
**Resolution:** `try_reserve` → send → `commit`, with `release` on send failure. `InMemoryWakeupPeriodStore` uses a threading lock.

## Info

### IN-01: Idempotency key falls back to interaction_id when message_id absent

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py:379-386`
**Issue:** `msg_id = resolved.message_id or interaction_id`. If QQ omits `resolved.message_id`, duplicate clicks on the same card button may not collapse under FEEDBACK-03 (each interaction id is unique). Fixture path is covered; live payloads without `message_id` are weaker.
**Fix:** Prefer failing normalize (or stamping a card-stable key from another QQ field) when `message_id` is missing, if live traffic proves the field can be absent.
**Status:** deferred (Info; out of Critical+Warning fix scope)

## Focus Gate Checklist

| Gate | Result |
|------|--------|
| No WeCom imports | PASS |
| `idempotency_key` stamped | PASS |
| ACK no-op-if-sent | PASS |
| `is_wakeup` C2C-only + period gate | PASS (WR-01/WR-02 fixed) |
| `deps=[]` | PASS |

---

_Reviewed: 2026-07-09T11:54:00Z_
_Fixed: 2026-07-09T11:59:12Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Fixer: Claude (gsd-code-fixer)_
_Depth: quick_
