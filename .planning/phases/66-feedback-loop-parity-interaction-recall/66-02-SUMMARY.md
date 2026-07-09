---
phase: 66-feedback-loop-parity-interaction-recall
plan: 02
subsystem: api
tags: [qqbot, feedback, ack, parity, unittest]

requires:
  - phase: 66-01
    provides: FEEDBACK-03 idempotency stamp + handle_feedback_callback + Wave 0 RED TestEnsureInteractionAck
  - phase: 65-two-tier-ack
    provides: ack_interaction + interaction_ack_status metadata (sent/pending_host/skipped_fixture)
  - phase: 62
    provides: build_feedback_keyboard_envelope button_data actions
provides:
  - ensure_interaction_ack no-op-if-sent post-normalize ACK completion
  - FEEDBACK-01 E2E QQ FeedbackEvent → feedback-service queue parity without wecom_service
  - Keyboard egress ↔ ingress action mapping assertions (Phase 62 reuse)
affects:
  - 66-03 is_wakeup recall
  - Host PYTHONPATH composition of qqbot + feedback-service

tech-stack:
  added: []
  patterns:
    - "ensure_interaction_ack: noop when sent; PUT only for pending_host via ack_interaction"
    - "Sync host API: access_token or token_manager + message_transport; qq_code==3 → sent+duplicate"
    - "FEEDBACK-01 composition via contract_feedback_events only (no bridge service, deps=[])"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/feedback_ingress.py
    - packages/channels/qqbot/tests/test_feedback_pipeline.py
    - packages/channels/qqbot/tests/test_no_wecom_import.py
    - services/feedback-service/tests/test_qqbot_feedback_parity.py

key-decisions:
  - "OQ-1: default no-op-if-sent after normalize; deferred PUT only for pending_host"
  - "Sync ensure_interaction_ack wraps async ack_interaction via asyncio.run for host/Wave 0 tests"
  - "Parity tests load as tests.test_qqbot_feedback_parity (services.feedback_service.tests dotted path is invalid layout)"

patterns-established:
  - "Pattern: ensure_interaction_ack evidence dict with status noop|sent|skipped|failed"
  - "Pattern: keyboard FEEDBACK_ACTIONS button_data must equal normalize_interaction_event action"

requirements-completed: [FEEDBACK-01, FEEDBACK-02]

duration: 3min
completed: 2026-07-09
---

# Phase 66 Plan 02: Feedback Loop Parity + ACK Summary

**FEEDBACK-02 `ensure_interaction_ack` no-op-if-sent plus FEEDBACK-01 QQ→feedback-service queue parity via `contract_feedback_events` composition**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-09T11:45:07Z
- **Completed:** 2026-07-09T11:48:09Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `ensure_interaction_ack` no-ops when Phase 65 already `sent`; PUTs once for `pending_host`; skips fixture without PUT; treats QQ `code==3` as non-fatal sent
- E2E: INTERACTION fixture → `handle_feedback_callback` → `normalize_feedback_inputs` → pending queue with `route_wrong` human-review / `no_auto_modify`
- Required keyboard↔ingress mapping: Phase 62 `build_feedback_keyboard_envelope` `button_data` matches normalize actions for all `FEEDBACK_ACTIONS`
- Privacy + ADAPTER-03 gates: `raw_payload` rejected at normalize; `deps=[]`; no wecom imports in qqbot/`feedback_ingress`

## Task Commits

Each task was committed atomically:

1. **Task 1: ensure_interaction_ack no-op-if-sent (FEEDBACK-02)** - `f769120` (feat)
2. **Task 2: E2E feedback-service composition parity (FEEDBACK-01)** - `83d3dff` (feat)

**Plan metadata:** (docs SUMMARY only — STATE.md / ROADMAP.md not updated per executor instructions)

## Files Created/Modified
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/feedback_ingress.py` - Added `ensure_interaction_ack` + `_StaticTokenManager`
- `packages/channels/qqbot/tests/test_feedback_pipeline.py` - Green `TestEnsureInteractionAck`; strengthened E2E keyboard/privacy/deps/ACK composition
- `packages/channels/qqbot/tests/test_no_wecom_import.py` - Explicit `feedback_ingress.py` wecom scan
- `services/feedback-service/tests/test_qqbot_feedback_parity.py` - Privacy, deps=[], wecom_normalizer import gates

## Decisions Made
- Keep Phase 65 eager ACK; post-normalize path is idempotent no-op-if-sent (OQ-1 RESOLVED)
- No `defer_interaction_ack` feature flag; no bridge service; compose via PYTHONPATH only
- Prefer helper in `feedback_ingress` (no adapter re-export required)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan verify dotted path `services.feedback_service.tests.*` cannot import**
- **Found during:** Task 2 verification
- **Issue:** `unittest` module path `services.feedback_service.tests.test_qqbot_feedback_parity` fails (`No module named 'services.feedback_service'`) because tests live under `services/feedback-service/tests/` without a `services.feedback_service.tests` package
- **Fix:** Run parity as `tests.test_qqbot_feedback_parity` with `PYTHONPATH` including `services/feedback-service` + `src` (same layout as other feedback-service tests). Pipeline/idempotency/no-wecom still use plan dotted paths
- **Files modified:** none (verify command only)
- **Verification:** `python3 -m unittest tests.test_qqbot_feedback_parity -v` → OK
- **Committed in:** N/A (documentation in SUMMARY)

---

**Total deviations:** 1 auto-fixed (Rule 3 ×1)
**Impact on plan:** Correctness of verify invocation only; no production scope change.

## Issues Encountered
None beyond the unittest discovery path mismatch above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 03 can green wakeup recall (`TestWakeupEnvelope` / `PeriodGate` / `AdapterDeliver`)
- Hosts can compose: normalize → queue → `ensure_interaction_ack(prior_ack_metadata=…)`

## Known Stubs
None for Plan 02 goals. Wakeup Wave 0 stubs remain intentionally RED for Plan 03.

## Self-Check: PASSED
- `feedback_ingress.py` contains `ensure_interaction_ack`
- Commits `f769120`, `83d3dff` present in git log
- `TestEnsureInteractionAck` + full pipeline + parity + no-wecom green

---
*Phase: 66-feedback-loop-parity-interaction-recall*
*Completed: 2026-07-09*
