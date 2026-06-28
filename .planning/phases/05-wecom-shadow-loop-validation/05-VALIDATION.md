---
phase: 05
slug: wecom-shadow-loop-validation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-28
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none |
| **Quick run command** | `PYTHONPATH=services/hermes-contract-layer/src:services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v` |
| **Full suite command** | `python -m compileall services/hermes-contract-layer/src services/hermes-contract-layer/tests services/feedback-service/src services/feedback-service/tests packages/contract-test-suite/src packages/contract-test-suite/tests && cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py && cd ../.. && PYTHONPATH=services/hermes-contract-layer/src:services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v && PYTHONPATH=services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/feedback-service/tests -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run the plan-specific `python -m unittest ...` command in the task.
- **After every plan wave:** Run the full suite command.
- **Before `$gsd-verify-work`:** Full suite must be green and live WeCom evidence must be passed or explicitly blocked.
- **Max feedback latency:** 10 seconds for local fixture checks; live callback latency is recorded in the evidence document.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | REQ-wecom-daily-test-loop | T-05-01-I | Validation fixtures do not store raw legal payloads | unit | `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -p 'test_wecom_validation.py' -v` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | REQ-wecom-daily-test-loop | T-05-01-R | Live evidence is separated from fixture evidence | docs/test | `rg -n "Live WeCom status|Fixture validation status" services/hermes-contract-layer/docs/wecom_shadow_loop_validation.md` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | REQ-wecom-daily-test-loop | T-05-02-T | FeedbackEvent output is schema-valid and idempotent for repeated callbacks | unit | `PYTHONPATH=services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/feedback-service/tests -v` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 3 | REQ-wecom-daily-test-loop | T-05-03-I | End-to-end fixtures preserve result/feedback relationships without raw payloads | integration | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` | ❌ W0 | ⬜ pending |
| 05-03-02 | 03 | 3 | REQ-wecom-daily-test-loop | T-05-03-R | Live validation is passed or blocked honestly | manual/evidence | `rg -n "Live WeCom status: (passed|blocked)" .planning/phases/05-wecom-shadow-loop-validation/05-WECOM-VALIDATION.md` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live WeCom task ACK and card feedback | REQ-wecom-daily-test-loop | Requires running Hermes lawfirm profile and connected WeCom channel | Follow `services/hermes-contract-layer/docs/wecom_shadow_loop_validation.md`; record result in `05-WECOM-VALIDATION.md`. |
| QQ Bot/WeChat non-acceptance channel non-regression | REQ-wecom-daily-test-loop | Requires connected channels or operator confirmation | Record channel status or blocker in `05-WECOM-VALIDATION.md`; do not treat as V2 acceptance. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or explicit manual evidence.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target defined.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-28
