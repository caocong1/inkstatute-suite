---
phase: 36
slug: m2-pre-implementation-safety
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-04
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | `packages/contract-test-suite/pyproject.toml`, `services/wecom-service/pyproject.toml`, `packages/platform-runtime/pyproject.toml` |
| **Quick run command** | `python scripts/run_v2_gates.py --suite wecom-service --suite platform-runtime --suite contract-test-suite` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~60 seconds (all 9 gates) |

---

## Sampling Rate

- **After every task commit:** Run quick command (3 affected gates)
- **After every plan wave:** Run `python scripts/run_v2_gates.py` (all 9 gates)
- **Before `/gsd-verify-work`:** Full suite must be green (all 9 gates, 479+ tests)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 36-01-01 | 01 | 1 | SAFETY-01 | T-36-01 | Non-Hermes modes cannot bypass live_acceptance gate | unit | `pytest services/wecom-service/tests/test_agent_backend.py -k bypass` | ❌ W0 | ⬜ pending |
| 36-01-02 | 01 | 1 | SAFETY-02 | T-36-02 | Contract method/field counts frozen at v1.5 baseline | unit | `pytest packages/contract-test-suite/tests/test_contract_count_freeze.py` | ❌ W0 | ⬜ pending |
| 36-01-03 | 01 | 1 | SAFETY-03 | T-36-03 | 11 forbidden keys unified, scrub applied to all API paths | unit | `pytest packages/platform-runtime/tests/test_privacy_keys.py` + `pytest services/conversation-read-view/tests/test_privacy_scrub.py` | ❌ W0 | ⬜ pending |
| 36-01-04 | 01 | 1 | SAFETY-04 | — | 6 M2 feature flags default False | unit | `pytest packages/platform-runtime/tests/test_feature_flags.py -k m2` | ❌ W0 | ⬜ pending |
| 36-01-05 | 01 | 1 | SAFETY-05 | T-36-05 | Provider/model noise blocked, legal text allowed | unit+fixture | `pytest packages/platform-runtime/tests/test_output_boundary.py -k provider` | ❌ W0 | ⬜ pending |
| 36-01-06 | 01 | 1 | SAFETY-06 | T-36-06 | Contract schema hash matches v1.5 baseline | unit | `pytest packages/contract-test-suite/tests/test_contract_freeze.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/contract-test-suite/tests/test_contract_count_freeze.py` — stub for SAFETY-02
- [ ] `packages/contract-test-suite/tests/test_contract_freeze.py` — stub for SAFETY-06
- [ ] `packages/platform-runtime/tests/test_privacy_keys.py` — stub for SAFETY-03
- [ ] `packages/platform-runtime/src/platform_runtime/privacy_keys.py` — shared forbidden keys module
- [ ] `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` — baseline hash file
- [ ] `packages/contract-test-suite/fixtures/provider_noise_cases.json` — output boundary fixtures for SAFETY-05

*Existing infrastructure (pytest, run_v2_gates.py) covers framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification — this is a safety/test phase with assertion-based verification by design.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
