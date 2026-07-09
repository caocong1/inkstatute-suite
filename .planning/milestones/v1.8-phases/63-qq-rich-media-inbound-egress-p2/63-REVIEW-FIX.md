---
phase: 63-qq-rich-media-inbound-egress-p2
fixed_at: 2026-07-09T10:39:15Z
review_path: .planning/phases/63-qq-rich-media-inbound-egress-p2/63-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 63: Code Review Fix Report

**Fixed at:** 2026-07-09T10:39:15Z
**Source review:** `.planning/phases/63-qq-rich-media-inbound-egress-p2/63-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: Upload/send failure evidence always reports `attempts=max_attempts`

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`, `packages/channels/qqbot/tests/test_sender.py`
**Commit:** 473cac8
**Applied fix:** `SendError` now carries `attempts`; `_post_with_retry` sets the actual POST count before raising; `upload_rich_media` / `send_rich_media` failure evidence uses `exc.attempts` instead of `max_attempts`. Added terminal-failure attempt assertion test.

### WR-02: Successful `send_rich_media` evidence hardcodes send `attempts=1` and overwrites upload attempts

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`, `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`, `packages/channels/qqbot/tests/test_sender.py`
**Commit:** af87917
**Applied fix:** Added `_send_message_with_attempts`; success evidence keeps distinct `upload_attempts` / `send_attempts` (plus stage `attempts` for send). Adapter metadata allowlist accepts the new keys. Added retry-path evidence test.

### WR-03: Missing `file_info` after upload HTTP success raises without evidence / misclassified issue_code

**Files modified:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`, `packages/channels/qqbot/tests/test_sender.py`, `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`
**Commit:** e2a69e1
**Applied fix:** Missing `file_info` raises `SendError` with upload-stage evidence and `qqbot_rich_media_upload_failed`. Adapter/sender tests assert stage + issue_code classification.

## Skipped Issues

None — IN-01 left as Info (fixture sanitization asymmetry; not in critical_warning scope).

---

_Fixed: 2026-07-09T10:39:15Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
