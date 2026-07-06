---
phase: 45
slug: m3-pre-implementation-safety
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-06
---

# Phase 45 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib) |
| **Config file** | none — gates use `unittest discover -s <dir>` |
| **Quick run command** | `python -m unittest discover -s packages/platform-runtime/tests` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m unittest discover -s packages/platform-runtime/tests`
- **After every plan wave:** Run `python scripts/run_v2_gates.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 45-01-01 | 01 | 1 | SAFETY-01 | T-45-01 / — | 9 M3 flags default False; `require_enabled` raises when off | unit | `python -m unittest packages/platform-runtime.tests.test_feature_flags -v` | ✅ (extend) | ⬜ pending |
| 45-01-02 | 01 | 1 | SAFETY-04 | T-45-01 / — | Flag-default test per new M3 flag asserts default False + inactive lane | unit | `python -m unittest packages.platform-runtime.tests.test_feature_flags -v` | ✅ (extend) | ⬜ pending |
| 45-02-01 | 02 | 1 | SAFETY-02 | T-45-02 / — | Contract-count freeze extended to RouterPort(1) + SkillRegistryPort(3) | unit | `python -m unittest packages.contract-test-suite.tests.test_contract_count_freeze -v` | ✅ (extend) | ⬜ pending |
| 45-02-02 | 02 | 1 | SAFETY-02 | T-45-02 / — | SHA-256 baseline hash unchanged (31 files, no new entries) | unit | `python -m unittest packages.contract-test-suite.tests.test_contract_freeze -v` | ✅ (unchanged) | ⬜ pending |
| 45-03-01 | 03 | 2 | SAFETY-01 | T-45-01 / — | Hardcoded 12-flag assertion updated to 21 flags in admin-console-api | unit | `python -m unittest services.admin-console-api.tests.test_contract_freeze -v` | ✅ (extend) | ⬜ pending |
| 45-04-01 | 04 | 2 | SAFETY-03 | — / — | All 19 V2 gates pass green (966+ tests, no regressions) | integration | `python scripts/run_v2_gates.py` | ✅ (existing) | ⬜ pending |
| 45-04-02 | 04 | 2 | SAFETY-05 | — / — | V2 human gate isolation documented (M3 flags OFF = no contamination) | documentation | `grep "M3" .planning/phases/45-m3-pre-implementation-safety/*-VERIFICATION.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/platform-runtime/tests/test_feature_flags.py` — extend with 9 M3 flag-default tests (SAFETY-01, SAFETY-04)
- [ ] `packages/contract-test-suite/tests/test_contract_count_freeze.py` — extend with RouterPort + SkillRegistryPort count assertions (SAFETY-02)
- [ ] `services/admin-console-api/tests/test_contract_freeze.py` — update hardcoded 12-flag set to 21 flags (SAFETY-01 regression fix)
- [ ] V2 human gate isolation documentation artifact (SAFETY-05) — document in VERIFICATION.md or SUMMARY.md

*Existing `test_contract_freeze.py` baseline hash test requires NO changes — it already covers 31 files and must continue passing unchanged.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| V2 human gate evidence (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial) remains carried forward, not executed by Phase 45 | SAFETY-05 | Live human gates are carried forward per STATE.md; Phase 45 only documents non-contamination | Confirm STATE.md still carries Phase 5 + Phase 8 human gates; confirm all 9 M3 flags default False so no M3 lane can be active during human gates |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
