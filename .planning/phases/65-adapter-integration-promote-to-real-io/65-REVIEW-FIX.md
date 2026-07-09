---
phase: 65-adapter-integration-promote-to-real-io
fixed_at: 2026-07-09T11:29:11Z
review_path: .planning/phases/65-adapter-integration-promote-to-real-io/65-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 65: Code Review Fix Report

**Fixed at:** 2026-07-09T11:29:11Z
**Source review:** `.planning/phases/65-adapter-integration-promote-to-real-io/65-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (CR-01, CR-02, WR-01, WR-02)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Interaction ACK treats non-zero QQ response code as success

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`, `packages/channels/qqbot/tests/test_sender.py`, `packages/channels/qqbot/tests/test_adapter_two_tier_ack.py`
**Commit:** 85c1a1f
**Applied fix:** `ack_interaction` now checks `_extract_qq_code` after PUT and raises `SendError` with `qq_code` when non-zero. Adapter duplicate handling for `qq_code == 3` remains non-fatal. Added sender + two-tier ACK regression tests for `{"code": 5}` → `interaction_ack_status=failed`.

### CR-02: `deliver` accepts when enabled but live IO is not ready

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`, `packages/channels/qqbot/tests/test_adapter_real_io.py`, `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`, `packages/channels/qqbot/tests/test_qqbot_channel_loop.py`, `packages/channels/qqbot/fixtures/qqbot_channel_loop.json`
**Commit:** 1914b7e
**Applied fix:** Text/markdown/card `accepted` now requires `_live_io_ready()`. When `enabled` but transport/token missing, returns `accepted=False`, `delivered_at=None`, `issue_code=live_io_not_ready`. Updated fixture loop expectations and adapter tests accordingly.

### WR-01: Capabilities always advertise `op12_plus_interaction_put`

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`, `packages/channels/qqbot/tests/test_adapter_real_io.py`, `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`
**Commit:** 150ed8a
**Applied fix:** `ack_strategy` is `op12_plus_interaction_put` only when live; otherwise `webhook_op12_only`.

### WR-02: Dead `except TokenError` on interaction ACK path

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`
**Commit:** 991bbbd
**Applied fix:** Removed dead `except TokenError` on ACK path. Token failures continue to surface as `SendError` via `_bearer`. `TokenError` import retained for `deliver` / rich-media handlers.

## Test Results

```
PYTHONPATH=packages/channels/qqbot/src:packages/platform-contract/src:packages/platform-runtime/src:packages/channel-core/src:. \
  python -m unittest discover -s packages/channels/qqbot/tests -v
Ran 286 tests in 0.351s
OK
```

---

_Fixed: 2026-07-09T11:29:11Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
