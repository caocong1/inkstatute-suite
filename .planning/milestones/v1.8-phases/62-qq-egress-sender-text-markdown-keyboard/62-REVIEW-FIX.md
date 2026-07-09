---
phase: 62-qq-egress-sender-text-markdown-keyboard
fixed_at: 2026-07-09T10:05:20Z
review_path: .planning/phases/62-qq-egress-sender-text-markdown-keyboard/62-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 62: Code Review Fix Report

**Fixed at:** 2026-07-09T10:05:20Z
**Source review:** `.planning/phases/62-qq-egress-sender-text-markdown-keyboard/62-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01, CR-02, WR-01, WR-02, WR-03)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: `TokenError` escapes `send_message` / `adapter.deliver`

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`, `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`, `packages/channels/qqbot/tests/test_sender.py`, `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`
**Commit:** 0279943
**Applied fix:** Added `_bearer()` that maps `TokenError` → sanitized `SendError("QQ Bot token unavailable")` for initial fetch and 401 refresh. `adapter.deliver` also catches `TokenError` as defense in depth with a sanitized `send_error` (no token leak). Added unit/adapter regression tests.

### CR-02: Missing `scene` defaults to C2C — window fail-open for group

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`, `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`, `packages/channels/qqbot/tests/test_sender.py`
**Commit:** 29dc9e6
**Applied fix:** Removed `or "c2c"` default. Missing/unknown scene uses `""` for the window gate (fail-closed). Live send rejects scenes outside `{c2c, group}` before POST. Added missing-scene window and live-send tests.

### WR-01: `user_openid` / `group_openid` interpolated into URL without validation

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`, `packages/channels/qqbot/tests/test_sender.py`
**Commit:** 2a3bf92
**Applied fix:** Added `_OPENID_RE` / `_require_openid` so path injection (`../`, `?`, `#`, `/`, overlong) raises `SendError("invalid …")` before URL build. Added rejection tests.

### WR-02: Empty content yields `accepted=True` with no wire body fields

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`, `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`
**Commit:** f167a34
**Applied fix:** `accepted` now requires `"msg_type" in envelope` so empty/blocked-without-payload deliveries are not accepted. Added empty-content delivery test.

### WR-03: Dead `window_ok = True` after early return

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`
**Commit:** c96fe36
**Applied fix:** Removed unused `window_ok` flag; acceptance uses policy + payload + enabled only (window failures still early-return).

## Skipped Issues

None — all in-scope findings were fixed.

## Info findings

IN-01..IN-02 left untouched (out of fix scope).

---

_Fixed: 2026-07-09T10:05:20Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
