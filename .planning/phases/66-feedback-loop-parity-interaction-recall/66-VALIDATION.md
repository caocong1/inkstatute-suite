---
phase: 66
slug: feedback-loop-parity-interaction-recall
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 66 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (stdlib; asyncio where adapter/sender async) |
| **Config file** | `packages/channels/qqbot/pyproject.toml`, `services/feedback-service/pyproject.toml` (both `dependencies = []`) |
| **Quick run command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/feedback-service/src" python3 -m unittest packages.channels.qqbot.tests.test_feedback_pipeline packages.channels.qqbot.tests.test_feedback_idempotency packages.channels.qqbot.tests.test_wakeup_recall -v` |
| **Full suite command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/feedback-service/src" python3 -m unittest discover -s packages/channels/qqbot/tests -v && PYTHONPATH="packages/platform-contract/src:packages/contract-test-suite/src:services/feedback-service/src" python3 -m unittest discover -s services/feedback-service/tests -v` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command (feedback pipeline + idempotency + wakeup)
- **After every plan wave:** Run full suite command (qqbot + feedback-service)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 66-W0-01 | 01 | 0 | FEEDBACK-01 | T-66-01 | Wave 0: RED stubs for E2E normalize→queue path | unit | `test -f packages/channels/qqbot/tests/test_feedback_pipeline.py` | ❌ W0 | ⬜ pending |
| 66-W0-02 | 01 | 0 | FEEDBACK-03 | T-66-02 | Wave 0: RED stubs for msg_id+button idempotency | unit | `test -f packages/channels/qqbot/tests/test_feedback_idempotency.py` | ❌ W0 | ⬜ pending |
| 66-W0-03 | 01 | 0 | RECALL-01 | T-66-03 | Wave 0: RED stubs for is_wakeup period gate + mutual exclusion | unit | `test -f packages/channels/qqbot/tests/test_wakeup_recall.py` | ❌ W0 | ⬜ pending |
| 66-W0-04 | 01 | 0 | FEEDBACK-01 | T-66-01 | Wave 0: RED stubs for feedback-service QQ parity | unit | `test -f services/feedback-service/tests/test_qqbot_feedback_parity.py` | ❌ W0 | ⬜ pending |
| 66-01-01 | 01 | 1 | FEEDBACK-03 | T-66-02 | `normalize_interaction_event` stamps `metadata.idempotency_key` = msg_id:button | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_feedback_idempotency -v` | ❌ W0 | ⬜ pending |
| 66-01-02 | 01 | 1 | FEEDBACK-03 | T-66-02 | Duplicate INTERACTION payloads collapse to one canonical FeedbackEvent in feedback-service | unit | `PYTHONPATH="…:services/feedback-service/src" python3 -m unittest services.feedback-service.tests.test_qqbot_feedback_parity -v` | ❌ W0 | ⬜ pending |
| 66-01-03 | 01 | 1 | FEEDBACK-01 | T-66-01 | Feedback ingress helper returns FeedbackEvent dict consumable by `contract_feedback_events` | unit | same PYTHONPATH + `test_feedback_pipeline` | ❌ W0 | ⬜ pending |
| 66-02-01 | 02 | 2 | FEEDBACK-01 | T-66-01 | E2E: keyboard fixture → INTERACTION fixture → normalize → classify → pending queue | unit | quick run command | ❌ W0 | ⬜ pending |
| 66-02-02 | 02 | 2 | FEEDBACK-02 | T-66-04 | After normalize, interaction ACK is complete; no-op when `interaction_ack_status=="sent"`; pending_host can PUT | unit | `… test_feedback_pipeline` + `test_adapter_two_tier_ack` | ✅ extend | ⬜ pending |
| 66-02-03 | 02 | 2 | FEEDBACK-01 | T-66-05 | `route_wrong` remains human-review / `no_auto_modify`; no wecom_service import | unit | `… test_feedback_pipeline` + `test_no_wecom_import` | ✅ | ⬜ pending |
| 66-03-01 | 03 | 3 | RECALL-01 | T-66-03 | C2C wakeup envelope has `is_wakeup=true` and omits `msg_id`/`event_id` | unit | `… test_wakeup_recall` | ❌ W0 | ⬜ pending |
| 66-03-02 | 03 | 3 | RECALL-01 | T-66-03 | Four 30-day periods enforce 1 send/period; second send in same period fails closed | unit | same as 66-03-01 | ❌ W0 | ⬜ pending |
| 66-03-03 | 03 | 3 | RECALL-01 | T-66-06 | Group / missing openid wakeup unsupported; passive expiry without wakeup still returns interim notice | unit | same as 66-03-01 + existing window tests | ✅ extend | ⬜ pending |
| 66-03-04 | 03 | 3 | ADAPTER-03/04 | T-66-07 | no wecom imports; Protocol/platform-contract/channel-core untouched; deps=[] | unit | `… test_no_wecom_import test_contract_freeze_not_violated test_v1_8_safety_baseline` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/channels/qqbot/tests/test_feedback_pipeline.py` — INTERACTION fixture → FeedbackEvent → `normalize_feedback_inputs` → pending queue; ACK no-op-if-sent
- [ ] `packages/channels/qqbot/tests/test_feedback_idempotency.py` — msg_id + button_id/button_data key; duplicate clicks collapse
- [ ] `packages/channels/qqbot/tests/test_wakeup_recall.py` — mutual exclusion, period quotas, C2C-only, Fake transport body assertions
- [ ] `services/feedback-service/tests/test_qqbot_feedback_parity.py` — QQ-shaped contract events dedupe/classify without wecom normalizer
- [ ] Extend `packages/channels/qqbot/fixtures/qqbot_interaction_create.json` with `resolved.message_id` for FEEDBACK-03
- [ ] Privacy assertions: no `raw_payload`, tokens, or Authorization in feedback/delivery metadata
- [ ] Keep `test_qqbot_channel_loop.py` and Phase 65 two-tier ACK tests green

*Existing unittest infrastructure covers framework setup; Wave 0 adds missing requirement-mapped files.*

---

## Manual-Only Verifications

*No live QQ network required for Phase 66 CI. Live button click + wakeup delivery is Phase 67 human gate.*

Optional human gate (not blocking):
1. Flag on + credentials: click feedback keyboard → client loading clears (ACK) → feedback appears in pending queue export.
2. After passive window expiry on C2C long task: one `is_wakeup` completion notice succeeds; second in same period fails as expected.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 35s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** researcher drafted 2026-07-09 — planner should map Wave 0 into 66-0x-PLAN.md
