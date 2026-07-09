---
phase: 62-qq-egress-sender-text-markdown-keyboard
plan: 03
subsystem: channels
tags: [qqbot, egress, adapter, deliver, passive-reply, keyboard, wecom-isolation]

requires:
  - phase: 62-01
    provides: Envelope builders and strip_for_wire
  - phase: 62-02
    provides: check_passive_reply_window + send_message + MessageTransport
provides:
  - QQBotChannelAdapter.deliver() wired to sender builders and window gate
  - Optional injectable token_manager/transport live-send path (default fixture network_io=False)
  - Adapter/loop fixture assertions for integer msg_type and keyboard
  - AST wecom isolation coverage for sender.py
affects:
  - Phase 63+ rich media / host session reply_count durability

tech-stack:
  added: []
  patterns:
    - "Metadata-only QQ specifics on frozen ChannelDelivery (no Protocol edits)"
    - "Fail-closed window whenever msg_id present (missing received_at never skips gate)"
    - "Logical message_type text|markdown|card in DeliveryResult; OpenAPI msg_type ints in envelope"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
    - packages/channels/qqbot/tests/test_qqbot_channel_adapter.py
    - packages/channels/qqbot/tests/test_qqbot_channel_loop.py
    - packages/channels/qqbot/tests/test_no_wecom_import.py

key-decisions:
  - "msg_id absent → skip window gate; fixture builders use delivery_id as msg_id fallback"
  - "Card feedback_target defaults to unknown when metadata/result omit it (fixture-safe)"
  - "Live send only when transport+token_manager injected and enabled; CI stays network_io=False"

patterns-established:
  - "Pattern: _delivery_type/_delivery_text/_feedback_target local helpers (WeCom naming, no wecom import)"
  - "Pattern: window fail → accepted=False + issue_code + interim_notice before builders/send"

requirements-completed: [EGRESS-02, EGRESS-03, EGRESS-04, EGRESS-07]

duration: 2min
completed: 2026-07-09
---

# Phase 62 Plan 03: Adapter Deliver Wiring Summary

**QQBotChannelAdapter.deliver() routes text/markdown/card through sender builders with fail-closed passive-reply gating and optional injectable send, keeping default fixture network_io=False**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-09T09:53:43Z
- **Completed:** 2026-07-09T09:55:08Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Removed string `msg_type` stubs; deliver uses `build_text_envelope` / `build_markdown_envelope` / `build_feedback_keyboard_envelope`
- Whenever `msg_id` is present, `check_passive_reply_window` runs (missing `received_at` fails closed with `qqbot_passive_reply_window_expired`)
- Fixture/loop tests assert integer OpenAPI `msg_type` and keyboard nesting; `test_sender_does_not_import_wecom_service` added
- Full qqbot unittest discover suite green (189 tests); `dependencies = []` unchanged; frozen protocols untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire adapter.deliver() to sender builders, window gate, and optional transport** - `39d82b5` (feat)
2. **Task 2: Update adapter/loop tests and extend test_no_wecom_import for sender.py** - `45d79ed` (test)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` - deliver() → sender + window + optional send_message
- `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py` - integer msg_type, markdown, window expiry / fail-closed cases
- `packages/channels/qqbot/tests/test_qqbot_channel_loop.py` - envelope msg_type ints while keeping logical message_type
- `packages/channels/qqbot/tests/test_no_wecom_import.py` - AST isolation for sender.py

## Decisions Made

- Skip passive-window gate only when `msg_id` is absent (fixture deliveries without inbound correlation); when present, never skip even if `received_at` is missing
- Card path uses `_feedback_target` with `"unknown"` default so fixture cards without result still build keyboards
- Capabilities metadata left fixture_only/network_io=False unchanged

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ROADMAP criterion 5 satisfied: adapter.deliver uses sender
- EGRESS-02/03/04/07 observable through DeliveryResult envelopes and window-failure metadata
- Ready for phase verification / next QQBot production phase (rich media deferred)

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`
- FOUND: `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`
- FOUND: `packages/channels/qqbot/tests/test_qqbot_channel_loop.py`
- FOUND: `packages/channels/qqbot/tests/test_no_wecom_import.py`
- FOUND: commit `39d82b5`
- FOUND: commit `45d79ed`

---
*Phase: 62-qq-egress-sender-text-markdown-keyboard*
*Completed: 2026-07-09*
