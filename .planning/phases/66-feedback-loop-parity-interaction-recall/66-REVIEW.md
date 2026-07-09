---
phase: 66-feedback-loop-parity-interaction-recall
reviewed: 2026-07-09T11:54:00Z
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
status: issues_found
---

# Phase 66: Code Review Report

**Reviewed:** 2026-07-09T11:54:00Z
**Depth:** quick
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Quick adversarial review of Phase 66 feedback/wakeup changes, focused on: no WeCom imports, FEEDBACK-03 `idempotency_key`, ACK no-op-if-sent, C2C-only `is_wakeup` period gate, and `deps=[]`.

**Focus gates:** all five pass.

- No `wecom` / `wecom_service` imports in qqbot production modules (AST + string scan clean).
- `normalize_interaction_event` stamps `metadata.idempotency_key = "{msg_id}:{button_identity}"`.
- `ensure_interaction_ack` returns `noop` when `interaction_ack_status=="sent"` and only PUTs for `pending_host`.
- Wakeup is C2C-only (`wakeup_scene_supported`); group fail-closed; P0–P3 Asia/Shanghai period gate present; wakeup envelopes omit `msg_id`/`event_id`/`msg_seq`.
- `packages/channels/qqbot/pyproject.toml` and `services/feedback-service/pyproject.toml` both have `dependencies = []`.

Two robustness warnings remain around wakeup quota enforcement under missing basis / concurrency.

## Warnings

### WR-01: Missing wakeup basis defaults to now (softens 30-day window)

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:556-563`
**Issue:** When `allow_wakeup`/`is_wakeup` is set but neither `last_user_message_at` nor a prior store basis exists, `_deliver_wakeup` calls `note_user_message(user_openid, datetime.now(UTC))`. That forces P0 and never returns `qqbot_wakeup_outside_window`. Hosts that omit the real user-message timestamp can send wakeups indefinitely (1/day via P0) past the RECALL-01 30-day bound. Documented as intentional OQ-2 default, but it weakens the period gate under incomplete metadata.
**Fix:** Prefer fail-closed when basis is missing (return outside-window / unsupported), or require an explicit host flag such as `wakeup_basis_unknown_ok=True` before seeding `now`:

```python
if (
    last_user_message_at is None
    and store.last_user_message_at(user_openid) is None
):
    result_meta["issue_code"] = "qqbot_wakeup_outside_window"
    result_meta["interim_notice"] = build_owned_notice(
        "long_processing", seed=delivery.delivery_id
    )
    return DeliveryResult(
        delivery_id=delivery.delivery_id,
        accepted=False,
        delivered_at=None,
        idempotency_key=idempotency_key,
        metadata=result_meta,
    )
```

### WR-02: Wakeup quota check-then-send is non-atomic

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:568-646`
**Issue:** `check_wakeup_quota` then `send_message` then `store.record_send` has no lock or compare-and-set. Concurrent `_deliver_wakeup` calls for the same `(openid, period)` can both observe `ok=True` and both POST, violating the 1-send-per-period guarantee. `InMemoryWakeupPeriodStore` is process-local and unlocked.
**Fix:** Reserve the period before send (or under a lock), and only keep the reservation on success:

```python
# Pseudocode: reserve → send → commit; release reservation on send failure
if not store.try_reserve(user_openid, quota.period_id):
    return DeliveryResult(..., accepted=False, metadata={..., "issue_code": "qqbot_wakeup_quota_exhausted"})
try:
    await send_message(...)
except Exception:
    store.release(user_openid, quota.period_id)
    raise
else:
    store.commit(user_openid, quota.period_id)
```

## Info

### IN-01: Idempotency key falls back to interaction_id when message_id absent

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py:379-386`
**Issue:** `msg_id = resolved.message_id or interaction_id`. If QQ omits `resolved.message_id`, duplicate clicks on the same card button may not collapse under FEEDBACK-03 (each interaction id is unique). Fixture path is covered; live payloads without `message_id` are weaker.
**Fix:** Prefer failing normalize (or stamping a card-stable key from another QQ field) when `message_id` is missing, if live traffic proves the field can be absent.

## Focus Gate Checklist

| Gate | Result |
|------|--------|
| No WeCom imports | PASS |
| `idempotency_key` stamped | PASS |
| ACK no-op-if-sent | PASS |
| `is_wakeup` C2C-only + period gate | PASS (see WR-01/WR-02) |
| `deps=[]` | PASS |

---

_Reviewed: 2026-07-09T11:54:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
