---
phase: 62-qq-egress-sender-text-markdown-keyboard
plan: 02
subsystem: channels
tags: [qqbot, egress, passive-reply, MessageTransport, retry, TokenManager]

requires:
  - phase: 62-01
    provides: Envelope builders and strip_for_wire
  - phase: 61-access-token-manager
    provides: TokenManager + FakeTokenTransport twin pattern
  - phase: channel-core
    provides: build_owned_notice long_processing templates
provides:
  - Passive-reply window gate (C2C 60min/4, group 5min/5) with fail-closed missing received_at
  - MessageTransport / FakeMessageTransport / UrllibMessageTransport twin
  - send_message with transient retry, 401 invalidate-once, terminal QQ codes, sanitized SendError
  - wire_url_for_scene hardcoded to api.sgroup.qq.com
affects:
  - 62-03 (adapter.deliver wiring of window + send_message)

tech-stack:
  added: []
  patterns:
    - "Phase-61 transport twin for message POST (Protocol + Fake + lazy urllib)"
    - "Fail-closed passive window with issue_code qqbot_passive_reply_window_expired + long_processing notice"
    - "Bounded backoff 0.05/0.1/0.2s via injectable sleep; Authorization QQBot {token}"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
    - packages/channels/qqbot/tests/test_sender.py

key-decisions:
  - "Missing/unparseable received_at fails closed (never allow)"
  - "C2C max replies locked at 4 (CONTEXT), not stale doc 5"
  - "Interim notice kind long_processing seeded by msg_id"
  - "Backoff schedule 0.05/0.1/0.2s injectable; no new HTTP deps"

patterns-established:
  - "Pattern: check_passive_reply_window before live send; adapter maps issue_code + interim_notice"
  - "Pattern: send_message strip_for_wire → get_token → QQBot auth → classify transient/auth/terminal"

requirements-completed: [EGRESS-02, EGRESS-04]

duration: 2min
completed: 2026-07-09
---

# Phase 62 Plan 02: Passive-Reply Window + MessageTransport Send Summary

**EGRESS-04 passive-reply window (C2C 60min/4, group 5min/5, fail-closed missing received_at) plus injectable MessageTransport send_message with transient retry, 401 invalidate-once, and token-sanitized SendError**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-09T09:51:29Z
- **Completed:** 2026-07-09T09:53:06Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- PassiveReplyWindowTests lock C2C/group age and reply limits plus missing-`received_at` fail-closed
- FakeMessageTransport-only SendRetryTests cover 500 retry, 401 invalidate+refresh once, terminal 304027, token non-leak, and wire URLs
- `sender.py` exports window gate + MessageTransport twin + `send_message` without wecom imports or top-level urllib

## Task Commits

Each task was committed atomically:

1. **Task 1: Add PassiveReplyWindowTests and SendRetryTests to test_sender.py** - `cd4c87f` (test)
2. **Task 2: Implement passive-reply window, MessageTransport twin, and send_message retry** - `23f7bd4` (feat)

**Plan metadata:** `a3109e0` (docs: complete plan)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_sender.py` - PassiveReplyWindowTests + SendRetryTests (FakeMessageTransport / FakeTokenTransport only)
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` - window gate, transport twin, wire_url_for_scene, send_message retry/auth

## Decisions Made

- Fail closed when `received_at` is missing/empty/unparseable (`qqbot_passive_reply_window_expired` + owned interim notice)
- C2C max replies = 4 per CONTEXT (not stale “5次” doc)
- Interim notice uses `build_owned_notice("long_processing", seed=msg_id|received_at)`
- Backoff delays 0.05 / 0.1 / 0.2s via injectable `sleep`; host fixed to `https://api.sgroup.qq.com`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03 can wire `adapter.deliver()` to `check_passive_reply_window` + envelope builders + `send_message`
- Durable `reply_count` / `is_wakeup` remain deferred (Phase 64 / later)

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`
- FOUND: `packages/channels/qqbot/tests/test_sender.py`
- FOUND: commit `cd4c87f`
- FOUND: commit `23f7bd4`
- FOUND: unittest module exits 0 (18 tests)

---
*Phase: 62-qq-egress-sender-text-markdown-keyboard*
*Completed: 2026-07-09*
