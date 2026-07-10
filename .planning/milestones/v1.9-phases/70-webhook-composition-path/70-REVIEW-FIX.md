---
phase: 70-webhook-composition-path
fixed_at: 2026-07-10T05:04:51Z
review_path: .planning/phases/70-webhook-composition-path/70-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 70: Code Review Fix Report

**Fixed at:** 2026-07-10T05:04:51Z
**Source review:** `.planning/phases/70-webhook-composition-path/70-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01, CR-02, WR-01, WR-02, WR-03)
- Fixed: 5
- Skipped: 0
- Out of scope (info): IN-01, IN-02

## Fixed Issues

### CR-01: Group delivery metadata maps `scene_id` into `user_openid` and omits `group_openid`

**Files modified:** `services/qqbot-service/src/qqbot_service/webhook.py`, `services/qqbot-service/tests/test_webhook_composition.py`
**Commit:** `4f971ce`
**Applied fix:** Build delivery metadata with scene-aware openid mapping — `user_openid` from message `user_id`, `group_openid` from `scene_id` when `scene=="group"`, no default `"c2c"`. Added signed group-at composition test asserting group/member openids and `/v2/groups/...` wire URL. Also refreshed `FIXED_NOW` to wall-clock-relative so C2C/group passive-reply windows stay valid.

### CR-02: Default post-ACK scheduler swallows all composition failures

**Files modified:** `services/qqbot-service/src/qqbot_service/http_server.py`, `services/qqbot-service/tests/test_webhook_http_raw_body.py`
**Commit:** `fb00e85`
**Applied fix:** Added injectable `on_error` / `default_post_ack_error_handler` (stderr: exception type only) and `server.on_post_ack_error` wiring. Unit test asserts `RuntimeError` surfaces via the callback.

### WR-01: HTTP wrapper never supplies a reply source — production path ends `completed_no_reply`

**Files modified:** `services/qqbot-service/src/qqbot_service/http_server.py`, `services/qqbot-service/src/qqbot_service/webhook.py`, `services/qqbot-service/tests/test_webhook_http_raw_body.py`
**Commit:** `8204f22`
**Applied fix:** Plumbed optional `server.reply_text` / `server.reply_resolver` through `do_POST` into `handle_qqbot_webhook_request`. Composition evidence now sets `issue_code=qqbot_no_reply_source` when no reply is available. HTTP test proves server-supplied reply reaches deliver.

### WR-02: `read_request_body_once` does not require a full Content-Length read

**Files modified:** `services/qqbot-service/src/qqbot_service/http_server.py`, `services/qqbot-service/tests/test_webhook_http_raw_body.py`
**Commit:** `fed186f`
**Applied fix:** Loop `rfile.read` until Content-Length bytes are collected; raise `ValueError("incomplete_body")` on EOF shortfall. Added short-chunk and incomplete-body tests.

### WR-03: Post-ACK `ensure_interaction_ack` reaches into private adapter attributes

**Files modified:** `services/qqbot-service/src/qqbot_service/wiring.py`, `services/qqbot-service/src/qqbot_service/webhook.py`
**Commit:** `bcd5e3c`
**Applied fix:** Exposed read-only `message_transport` / `token_manager` on `QQBotWiredRuntime` from the wiring factory; feedback path uses those instead of `adapter._transport` / `adapter._token_manager`.

## Remaining Findings (out of scope)

### IN-01: Fragile `SolutionBinding.backend_id` resolution
**File:** `services/qqbot-service/src/qqbot_service/webhook.py:211-216`
**Reason:** Info-tier; `fix_scope=critical_warning` excludes IN-*.

### IN-02: `bot_secret` remains on `RawInbound.metadata` for the full post-ACK lifetime
**File:** `services/qqbot-service/src/qqbot_service/webhook.py:75-76,337-338`
**Reason:** Info-tier; `fix_scope=critical_warning` excludes IN-*.

## Host Test Results

```
Ran 70 tests in 0.216s
OK
```

(`python -m unittest discover -s services/qqbot-service/tests` — expect 65+)

---

_Fixed: 2026-07-10T05:04:51Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
