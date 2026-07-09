---
phase: 62-qq-egress-sender-text-markdown-keyboard
plan: 01
subsystem: channels
tags: [qqbot, egress, envelope, markdown, keyboard, output-policy]

requires:
  - phase: 61-access-token-manager
    provides: TokenManager package layout and dependencies=[] invariant
  - phase: channel-core
    provides: apply_output_policy / OutputPolicyDecision
provides:
  - QQ text envelope builder (msg_type=0) with policy + msg_id/msg_seq
  - QQ markdown envelope builder (msg_type=2)
  - QQ markdown+keyboard feedback card builder with four callback actions
  - strip_for_wire audit-key removal for OpenAPI POST bodies
affects:
  - 62-02 (passive window + MessageTransport + send_message)
  - 62-03 (adapter.deliver wiring)

tech-stack:
  added: []
  patterns:
    - "Policy-first envelope builders (apply_output_policy before content attach)"
    - "Dual envelope: audit keys (policy/inkstatute) stripped via strip_for_wire before wire POST"
    - "keyboard.content.rows nesting with action.type=1 callbacks"

key-files:
  created:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
    - packages/channels/qqbot/tests/test_sender.py
  modified: []

key-decisions:
  - "Markdown envelopes set top-level content to empty string companion for group API (A4)"
  - "Feedback labels are Chinese: 有帮助/需改进/需要修正/路由错误"
  - "permission.type=2 (everyone) for feedback buttons; feedback_target stays in inkstatute audit metadata"

patterns-established:
  - "Pattern: _base_envelope(decision, msg_id, msg_seq) then attach QQ OpenAPI fields only on non-block"
  - "Pattern: FEEDBACK_ACTIONS tuple is the single egress vocabulary matching Phase 60 ingress"

requirements-completed: [EGRESS-02, EGRESS-03, EGRESS-07]

duration: 5min
completed: 2026-07-09
---

# Phase 62 Plan 01: QQ Egress Envelope Builders Summary

**Policy-checked QQ OpenAPI envelope builders for text (msg_type=0), markdown (msg_type=2), and markdown+keyboard feedback cards with strip_for_wire audit stripping**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-09T09:48:44Z
- **Completed:** 2026-07-09T09:53:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Wave-0/RED unit tests lock integer `msg_type` 0/2, `keyboard.content.rows` nesting, four feedback callbacks, policy block, and `strip_for_wire`
- GREEN `sender.py` builders call `apply_output_policy` before attaching user-visible content
- Wire body excludes `policy`/`inkstatute`; no `template_card`, no `wecom_service`, no HTTP deps

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_sender.py envelope, keyboard, and output-policy tests (Wave 0 + RED)** - `e976ce2` (test)
2. **Task 2: Implement sender.py envelope builders, FEEDBACK_ACTIONS, and strip_for_wire** - `3567801` (feat)

**Plan metadata:** `d8bc917` (docs: complete plan)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_sender.py` - SenderEnvelopeTests for EGRESS-02/03/07 shapes and policy
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` - build_text/markdown/feedback_keyboard envelopes + strip_for_wire

## Decisions Made

- Followed RESEARCH Pattern 1 and Code Examples for keyboard nesting and FEEDBACK_ACTIONS
- Markdown envelopes include empty top-level `content` string (group API companion per A4)
- Deferred MessageTransport / send_message / passive-window to Plan 02 as specified

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Envelope builders ready for Plan 02 (passive-reply window + injectable MessageTransport + send_message)
- Adapter `deliver()` wiring remains Plan 03
- `dependencies = []` unchanged; no frozen protocol edits

## TDD Gate Compliance

- RED gate: `e976ce2` test(62-01)
- GREEN gate: `3567801` feat(62-01)

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`
- FOUND: `packages/channels/qqbot/tests/test_sender.py`
- FOUND: `62-01-SUMMARY.md`
- FOUND commits: `e976ce2`, `3567801`
- SenderEnvelopeTests: 7 passed
