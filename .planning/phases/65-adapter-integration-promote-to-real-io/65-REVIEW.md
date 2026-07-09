---
phase: 65-adapter-integration-promote-to-real-io
reviewed: 2026-07-09T11:25:00Z
fixed_at: 2026-07-09T11:29:11Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
findings:
  critical: 2
  warning: 2
  info: 2
  total: 6
status: fixed
fix_iteration: 1
fix_report: .planning/phases/65-adapter-integration-promote-to-real-io/65-REVIEW-FIX.md
---

# Phase 65: Code Review Report

**Reviewed:** 2026-07-09T11:25:00Z
**Fixed:** 2026-07-09T11:29:11Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** fixed (CR/WR resolved in iteration 1)

## Summary

Phase 65 correctly wires two-tier ACK metadata (`http_callback_ack_body={"op":12}`), gates Tier-2 PUT behind `_live_io_ready()`, validates `interaction_id` charset, keeps `dependencies=[]`, avoids Protocol/wecom edits, and keeps webhook `network_io=False`. Critical and warning findings from the initial review were fixed: interaction PUT now rejects non-zero QQ `code`, `deliver` refuses when enabled without live IO, capabilities advertise `op12_plus_interaction_put` only when live, and the dead ACK `TokenError` branch was removed.

## Critical Issues

### CR-01: Interaction ACK treats non-zero QQ response code as success — FIXED

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:220-229`
**Also:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py:583-606`
**Issue:** `ack_interaction` returns the transport JSON without checking `code`. `verify_and_ack` marks `interaction_ack_status="sent"` whenever no exception is raised. A Fake/live response like `{"code": 5}` still yields `sent` + `ack_tier=webhook_op12+interaction_put`. Phase 66 may then no-op a failed ACK. `send_message` already rejects non-zero QQ codes via `_extract_qq_code`; ACK does not.
**Status:** Fixed in `85c1a1f` — `ack_interaction` raises `SendError` on non-zero QQ code; adapter marks `failed` (duplicate `qq_code==3` still non-fatal).
**Fix:**
```python
# sender.ack_interaction — after put_json:
result = await put_json(...)
qq_code = _extract_qq_code(result if isinstance(result, dict) else None)
if qq_code is not None and qq_code != 0:
    raise SendError(
        "QQ Bot interaction ACK failed",
        qq_code=qq_code,
    )
return result
```
Keep adapter duplicate handling for `qq_code == 3` as non-fatal.

### CR-02: `deliver` accepts when enabled but live IO is not ready — FIXED

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:391-446`
**Issue:** Text/markdown/card acceptance is `policy_ok && has_payload && enabled`. The send branch only runs when transport + token_manager are also present. With `enabled=True` and no transport, `deliver` returns `accepted=True`, sets `delivered_at`, leaves `network_io=False` / `fixture_only=True`, and never POSTs. Hosts that flip the flag without injecting deps get a false delivery success (message never reaches QQ).
**Status:** Fixed in `1914b7e` — `accepted` requires `_live_io_ready()`; otherwise `issue_code=live_io_not_ready`.
**Fix:**
```python
live = self._live_io_ready()
accepted = (
    policy_action != "block"
    and has_payload
    and self._config.enabled
    and live  # require real send path when channel is enabled
)
# ... existing send try/except when accepted ...
# If enabled but not live, prefer accepted=False + issue_code
# e.g. "qqbot_send_failed" / "live_io_not_ready"
```
Alternatively: if `enabled and not live`, refuse with an explicit issue code instead of fixture-success.

## Warnings

### WR-01: Capabilities always advertise `op12_plus_interaction_put` — FIXED

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:86-90`
**Issue:** `ack_strategy` is hardcoded even when `fixture_only=True` / `network_io=False`. Plan 02 / README describe this strategy when advertising live readiness. Fixture hosts may assume Tier-2 PUT is available when `_live_io_ready()` is false.
**Status:** Fixed in `150ed8a` — fixture path advertises `webhook_op12_only`.
**Fix:**
```python
"ack_strategy": (
    "op12_plus_interaction_put" if live else "webhook_op12_only"
),
```

### WR-02: Dead `except TokenError` on interaction ACK path — FIXED

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:246-249`
**Issue:** `ack_interaction` → `_bearer` maps `TokenError` to `SendError("QQ Bot token unavailable")` before re-raise. The adapter’s `except TokenError` never runs for the normal path; token failures are already handled as `SendError` with a generic message. Misleading control flow for maintainers.
**Status:** Fixed in `991bbbd` — dead branch removed; `TokenError` kept for deliver paths.
**Fix:** Remove the dead `except TokenError` block, or stop mapping inside `_bearer` for ACK and let `TokenError` propagate intentionally (prefer removing the dead branch and relying on `SendError`).

## Info

### IN-01: `skipped_fixture` interaction_ack_status is unreachable

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:250-253`
**Issue:** Verified-dispatch interaction metadata only runs after the `enabled=False` → 503 early return. In the `else` (not live) branch, `not self._config.enabled` is always false, so status is always `pending_host`. `skipped_fixture` is dead.
**Fix:** Use `meta["interaction_ack_status"] = "pending_host"` only, or set `skipped_fixture` on the disabled early-return path if that signal is still desired.
**Status:** Not in fix scope (info).

### IN-02: `TokenError` import used only for dead ACK branch (+ deliver)

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:35,246-249,426`
**Issue:** After WR-02, confirm `TokenError` remains needed for `deliver`’s `except (SendError, TokenError)`. Deliver still needs it if `send_message` can surface raw `TokenError` (today `_bearer` maps it). Low priority cleanup after WR-02.
**Status:** Not in fix scope (info). Import retained for deliver/rich-media.

---

_Reviewed: 2026-07-09T11:25:00Z_
_Fixed: 2026-07-09T11:29:11Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Fixer: Claude (gsd-code-fixer)_
_Depth: standard_
