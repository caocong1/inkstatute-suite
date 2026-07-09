---
phase: 66-feedback-loop-parity-interaction-recall
plan: 01
subsystem: api
tags: [qqbot, feedback, idempotency, ingress, unittest]

requires:
  - phase: 60-qq-event-normalization
    provides: INTERACTION_CREATE → FeedbackEvent normalize_interaction_event
  - phase: 65-two-tier-ack
    provides: ack_interaction + interaction_ack_status metadata
provides:
  - FEEDBACK-03 metadata.idempotency_key stamped at normalize time
  - Pure handle_feedback_callback ingress helper for host composition
  - Wave 0 RED suite for pipeline ACK, wakeup recall, and feedback-service QQ parity
affects:
  - 66-02 feedback E2E + ensure_interaction_ack
  - 66-03 is_wakeup recall

tech-stack:
  added: []
  patterns:
    - "Stamp FEEDBACK-03 key in normalize_interaction_event (msg_id:button_identity)"
    - "Pure qqbot feedback_ingress; compose feedback-service only via PYTHONPATH"
    - "Wave 0 named unittest classes for Plan 02/03 narrowed verifies"

key-files:
  created:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/feedback_ingress.py
    - packages/channels/qqbot/tests/test_feedback_idempotency.py
    - packages/channels/qqbot/tests/test_feedback_pipeline.py
    - packages/channels/qqbot/tests/test_wakeup_recall.py
    - services/feedback-service/tests/test_qqbot_feedback_parity.py
  modified:
    - packages/channels/qqbot/fixtures/qqbot_interaction_create.json
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py

key-decisions:
  - "FEEDBACK-03 key stamped only in normalize_interaction_event (single source of truth)"
  - "feedback_ingress stays pure — no feedback_service/wecom imports; deps=[] preserved"
  - "TestEnsureInteractionAck and wakeup classes remain RED for Plans 02–03"

patterns-established:
  - "Pattern: metadata.idempotency_key = f\"{msg_id}:{button_identity}\" with dedupe_strategy"
  - "Pattern: handle_feedback_callback returns skipped vs normalized evidence dicts"

requirements-completed: [FEEDBACK-01, FEEDBACK-03]

duration: 4min
completed: 2026-07-09
---

# Phase 66 Plan 01: Feedback Idempotency + Ingress Summary

**FEEDBACK-03 msg_id+button idempotency stamped on interaction FeedbackEvents, pure `handle_feedback_callback` ingress helper, and Wave 0 RED suite for Plans 02–03**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-09T11:40:09Z
- **Completed:** 2026-07-09T11:43:51Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Interaction fixture now includes `resolved.message_id` (`FIXTURE_CARD_MSG_ID_001`) for stable FEEDBACK-03 keys
- `normalize_interaction_event` stamps `metadata.idempotency_key`, `dedupe_strategy`, and `msg_id`; duplicate clicks collapse via feedback-service
- Pure `feedback_ingress.handle_feedback_callback` returns FeedbackEvent + asdict dict for host composition without wecom/deps

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED tests + interaction fixture message_id** - `2486ab0` (test)
2. **Task 2: Stamp FEEDBACK-03 idempotency_key in normalize_interaction_event** - `9db7223` (feat)
3. **Task 3: Pure feedback_ingress handle_feedback_callback helper** - `712a0eb` (feat)

**Plan metadata:** `231712e` (docs: SUMMARY only — STATE.md / ROADMAP.md not updated per executor instructions)

## Files Created/Modified
- `packages/channels/qqbot/fixtures/qqbot_interaction_create.json` - Added sanitized `resolved.message_id`
- `packages/channels/qqbot/tests/test_feedback_idempotency.py` - FEEDBACK-03 key + dedupe coverage (green)
- `packages/channels/qqbot/tests/test_feedback_pipeline.py` - FEEDBACK-01 E2E green; `TestEnsureInteractionAck` RED for Plan 02
- `packages/channels/qqbot/tests/test_wakeup_recall.py` - RECALL-01 Wave 0 RED (`TestWakeupEnvelope` / `PeriodGate` / `AdapterDeliver`)
- `services/feedback-service/tests/test_qqbot_feedback_parity.py` - QQ `contract_feedback_events` parity without wecom_service
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` - FEEDBACK-03 stamp
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/feedback_ingress.py` - Pure ingress helper

## Decisions Made
- Stamp idempotency only inside `normalize_interaction_event` (RESEARCH Pattern 2)
- Prefer explicit module import of `feedback_ingress` (no package `__init__` re-export)
- Leave ACK ensure + wakeup production paths for Plans 02–03; Wave 0 encodes expected class names

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Parity no-wecom assertion matched docstring/source substrings**
- **Found during:** Task 1 / Task 2
- **Issue:** Asserting `wecom_service` / `wecom_normalizer` absent from module source failed because `queue.py` legitimately imports `wecom_normalizer` for WeCom paths, and docstring self-references tripped substring checks
- **Fix:** Switch to AST import checks on the parity test module + assert `wecom_service` absent from `queue.py`; exercise QQ `contract_feedback_events` path only
- **Files modified:** `services/feedback-service/tests/test_qqbot_feedback_parity.py`
- **Verification:** `python3 -m unittest services.feedback-service.tests.test_qqbot_feedback_parity -v` → OK
- **Committed in:** `9db7223` (Task 2)

**2. [Rule 1 - Bug] Pending queue item exposes top-level idempotency_key**
- **Found during:** Task 3
- **Issue:** E2E assertion used `queue[0]["metadata"]["idempotency_key"]` but `FeedbackQueueItem.to_dict()` flattens `idempotency_key`
- **Fix:** Assert `queue[0]["idempotency_key"]`
- **Files modified:** `packages/channels/qqbot/tests/test_feedback_pipeline.py`
- **Verification:** `TestFeedbackPipelineE2E` → OK
- **Committed in:** `712a0eb` (Task 3)

---

**Total deviations:** 2 auto-fixed (Rule 1 ×2)
**Impact on plan:** Correctness-only test fixes; no scope creep; production path matches plan.

## Issues Encountered
None beyond the auto-fixed assertion mismatches above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 02 can green `TestEnsureInteractionAck` and any remaining ACK composition
- Plan 03 can green `TestWakeupEnvelope` / `TestWakeupPeriodGate` / `TestWakeupAdapterDeliver`
- FEEDBACK-03 + pure ingress ready for host PYTHONPATH composition

## Known Stubs
- `TestEnsureInteractionAck` — intentionally RED until Plan 02 `ensure_interaction_ack`
- `TestWakeupEnvelope` / `TestWakeupPeriodGate` / `TestWakeupAdapterDeliver` — intentionally RED until Plan 03 wakeup builders + deliver branch

These stubs do not block Plan 01 goals (idempotency stamp + ingress helper + Wave 0 encoding).

## Self-Check: PASSED
- All created/modified artifacts present
- Commits `2486ab0`, `9db7223`, `712a0eb` present in git log

---
*Phase: 66-feedback-loop-parity-interaction-recall*
*Completed: 2026-07-09*
