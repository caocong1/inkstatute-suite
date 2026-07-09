---
phase: 61-access-token-manager
fixed_at: 2026-07-09T09:15:00Z
review_path: .planning/phases/61-access-token-manager/61-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 61: Code Review Fix Report

**Fixed at:** 2026-07-09T09:15:00Z
**Source review:** `.planning/phases/61-access-token-manager/61-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (WR-01..WR-05)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### WR-01: Non-atomic cache update on failed expiry extract

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py`, `packages/channels/qqbot/tests/test_token_manager.py`
**Commit:** b600638
**Applied fix:** Extract `token` and `ttl` before assigning `_token` / `_expires_at`. Added regression test that a bad `expires_in` leaves the prior cache intact.

### WR-02: Non-finite `expires_in` (NaN/Inf) accepted — token never refreshes

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py`, `packages/channels/qqbot/tests/test_token_manager.py`
**Commit:** 0e0382b
**Applied fix:** Require finite numeric `expires_in` via `math.isfinite`; reject NaN/Inf. Added unit tests for both.

### WR-03: `bool` is accepted as `expires_in` (int subclass)

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py`, `packages/channels/qqbot/tests/test_token_manager.py`
**Commit:** 0e0382b
**Applied fix:** Reject `bool` before the `(int, float)` check. Added `test_invalid_expires_in_bool_rejected`.

### WR-04: `expires_in <= refresh_margin` causes perpetual refresh

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py`, `packages/channels/qqbot/tests/test_token_manager.py`
**Commit:** 1bf29e6
**Applied fix:** Raise `TokenError("QQ Bot token expires_in too short for refresh margin")` when TTL cannot outlive the margin. Added unit test for `expires_in=30` / `refresh_margin=60`.

### WR-05: Malformed HTTP body not mapped to `TokenError` (decode/JSON)

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py`, `packages/channels/qqbot/tests/test_token_manager.py`
**Commit:** 8f3eccd
**Applied fix:** Map `UnicodeDecodeError` / `JSONDecodeError` / `TypeError` / `ValueError` and non-dict JSON to sanitized `TokenError("QQ Bot token response invalid")` with `from None`. Also switched HTTP/URL errors to `from None`. Added urllib transport unit tests for invalid UTF-8, invalid JSON (no token leak), and non-dict JSON.

## Skipped Issues

None — all in-scope findings were fixed.

## Info findings

IN-01..IN-03 left untouched (out of fix scope).

---

_Fixed: 2026-07-09T09:15:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
