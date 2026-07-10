---
phase: 70
slug: webhook-composition-path
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-10
---

# Phase 70 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python unittest (stdlib) |
| **Config file** | none — explicit PYTHONPATH |
| **Quick run command** | `PYTHONPATH="services/qqbot-service/src:packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src" python3 -m unittest discover -s services/qqbot-service/tests -p 'test_webhook_*.py' -v` |
| **Full suite command** | `PYTHONPATH="services/qqbot-service/src:packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src" python3 -m unittest discover -s services/qqbot-service/tests -v` (also `python3 scripts/run_v2_gates.py` gate `qqbot-service`) |
| **Estimated runtime** | ~15–30s quick; full host discover ~20–40s |

---

## Sampling Rate

- **After every task commit:** Run the plan-scoped webhook unittest pattern
- **After every plan wave:** Run full `services/qqbot-service/tests` discover
- **Before `/gsd-verify-work`:** Full host discover + `qqbot-service` gate green
- **Max feedback latency:** 60 seconds for quick command

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 70-01-01 | 01 | 1 | HOST-02 | T-70-01 / T-70-04 | RED ACK-first tests (op=13/12/refuse/scheduler) | unit | `unittest discover -p 'test_webhook_ack_first.py'` (expect fail) | ✅ | ✅ green |
| 70-01-02 | 01 | 1 | HOST-02 | T-70-02 / T-70-03 | GREEN pure handler + raw-body identity | unit | `unittest discover -p 'test_webhook_ack_first.py'` | ✅ | ✅ green |
| 70-02-01 | 02 | 2 | HOST-01 | T-70-05 / T-70-07 | RED Fake composition tests | unit | `unittest discover -p 'test_webhook_composition.py'` (expect fail) | ✅ | ✅ green |
| 70-02-02 | 02 | 2 | HOST-01 | T-70-05 / T-70-06 / T-70-08 | GREEN post-ACK ingress/feedback/deliver + boundary | unit | `unittest discover -p 'test_webhook_*.py'` | ✅ | ✅ green |
| 70-03-01 | 03 | 3 | HOST-01 / HOST-02 | T-70-09 / T-70-11 | HTTP wrapper raw-body-once proofs | unit | `unittest discover -p 'test_webhook_http_raw_body.py'` | ✅ | ✅ green |
| 70-03-02 | 03 | 3 | HOST-01 / HOST-02 | T-70-10 | Exports + README + full host suite / no-wecom | unit | `unittest discover -s services/qqbot-service/tests` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Existing unittest + `qqbot-service` V2 gate PYTHONPATH (Phases 68–69) — no new framework
- [x] Test files created in-plan (70-01 / 70-02 / 70-03) — no separate Wave 0 stub plan required
- [x] `services/qqbot-service/tests/test_webhook_ack_first.py` — created in Plan 01
- [x] `services/qqbot-service/tests/test_webhook_composition.py` — created in Plan 02
- [x] `services/qqbot-service/tests/test_webhook_http_raw_body.py` — created in Plan 03

*Existing infrastructure covers runners; new webhook tests are phase deliverables.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | All Phase 70 behaviors have automated Fake verification. Live QQ webhook bind remains Phase 72 HUMAN GATE. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (tests created in-plan)
- [x] No watch-mode flags
- [x] Feedback latency < 60s for quick command
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending execution
