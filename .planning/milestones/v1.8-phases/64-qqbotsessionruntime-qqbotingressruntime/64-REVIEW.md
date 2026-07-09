---
phase: 64-qqbotsessionruntime-qqbotingressruntime
reviewed: 2026-07-09T11:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/ingress_runtime.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/__init__.py
  - packages/channels/qqbot/tests/test_session_runtime.py
  - packages/channels/qqbot/tests/test_ingress_runtime.py
  - packages/channels/qqbot/tests/test_session_memory_runtime.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: fixed
fixed_at: 2026-07-09T11:02:53Z
fix_report: .planning/phases/64-qqbotsessionruntime-qqbotingressruntime/64-REVIEW-FIX.md
---

# Phase 64: Code Review Report

**Reviewed:** 2026-07-09T11:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** fixed
**Fixed at:** 2026-07-09T11:02:53Z
**Fix report:** `.planning/phases/64-qqbotsessionruntime-qqbotingressruntime/64-REVIEW-FIX.md`

## Summary

Reviewed QQBot session/ingress runtime sources against Phase 64 focus constraints. **No critical issues.** Focus gates hold: no `wecom_service` imports (AST + substring), scene isolation via `qqbot:{scene}:{scene_id}:{user_openid}` / `SessionScope.conversation_id`, interrupt resume/duplicate/expiry paths behave correctly, memory fail-open defaults work, and `dependencies = []` is unchanged. Two warnings on ingress idempotency/`now` wiring were fixed in the review-fix pass; two info items on unused enum / export surface remain.

## Warnings

### WR-01: Ingress does not wire `message_id` as `idempotency_key`

**Status:** fixed (934a267)
**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/ingress_runtime.py:135`
**Issue:** `handle_callback` passes `idempotency_key=_string(turn.metadata.get("idempotency_key"))`, but Phase 60 normalization stores `message_id` and never sets `idempotency_key`. Interrupt duplicates can still be caught via stable `turn_id` after resolve, but CONTINUE/START retries have no in-process `_outcome_by_idempotency_key` key and can double-`create_run` on callback redelivery.
**Fix:**
```python
idempotency_key=(
    _string(turn.metadata.get("idempotency_key"))
    or _string(turn.metadata.get("message_id"))
    or turn.turn_id
),
```

### WR-02: Ingress does not pass `now=received_at` into `handle_turn`

**Status:** fixed (087a59f)
**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/ingress_runtime.py:129-137`
**Issue:** Expiry uses `now or _clock_now(self.clock)`. Callback `received_at` is accepted by ingress but never forwarded, so interrupt expiry can diverge from the event timestamp when host clock and callback time differ (same gap exists in WeCom ingress).
**Fix:**
```python
return await self.session_runtime.handle_turn(
    turn=turn,
    scope=scope,
    run_request=run_request,
    recent_session=recent_session,
    active_task=active_task,
    idempotency_key=...,
    now=received_at,
    metadata={"source": "qqbot_ingress_runtime"},
)
```

## Info

### IN-01: `INTERRUPT_CANCELLED` action is never produced

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py:70`
**Issue:** Enum value mirrors WeCom but `handle_turn` has no cancelled-interrupt branch. Dead surface until a later host/cancel path lands.
**Fix:** Either wire `interrupt_store` cancelled status → `INTERRUPT_CANCELLED`, or drop the unused enum member until needed.

### IN-02: Memory policy types not re-exported from package `__init__`

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/__init__.py:6-18`
**Issue:** `QQBotSessionRuntime` / ingress / Action / Outcome are public; `QQBotMemoryIntegrationPolicy` / failure / retention enums stay module-private. Fine if hosts import from `session_runtime`, but D-01 policy is harder to discover.
**Fix:** Optionally add the three memory policy symbols to `__all__` when hosts need them.

## Focus Constraint Checklist

| Constraint | Result |
| --- | --- |
| No `wecom_service` imports | Pass — session/ingress/`__init__` + AST tests |
| Scene isolation `qqbot:{scene}:{scene_id}:{user_openid}` | Pass — normalization + scope + C2C/group interrupt test |
| Interrupt resume correctness | Pass — resume / duplicate / expired / active bypass |
| Memory fail-open | Pass — default FAIL_OPEN; degraded create_run; finalize retain |
| `dependencies = []` | Pass — `packages/channels/qqbot/pyproject.toml` |

---

_Reviewed: 2026-07-09T11:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Fixed: 2026-07-09T11:02:53Z_
_Fixer: Claude (gsd-code-fixer)_
