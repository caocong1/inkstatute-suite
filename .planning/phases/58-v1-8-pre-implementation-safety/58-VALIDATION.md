---
phase: 58
slug: v1-8-pre-implementation-safety
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-07
---

# Phase 58 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (Python 3.14 stdlib) |
| **Config file** | `pyproject.toml` (root) + per-package `pyproject.toml` |
| **Quick run command** | `python3 scripts/run_v2_gates.py` |
| **Full suite command** | `python3 scripts/run_v2_gates.py && python3 -m pytest packages/ services/ -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 scripts/run_v2_gates.py`
- **After every plan wave:** Run `python3 scripts/run_v2_gates.py && python3 -m pytest packages/ services/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 58-01-01 | 01 | 1 | ADAPTER-04 | — | N/A | gate | `python3 scripts/run_v2_gates.py` | ✅ | ⬜ pending |
| 58-01-02 | 01 | 1 | ADAPTER-04 | — | N/A | unit | `python3 -m pytest tests/test_contract_count_freeze.py tests/test_contract_freeze.py -q` | ✅ | ⬜ pending |
| 58-01-03 | 01 | 1 | ADAPTER-04 | — | N/A | unit | `python3 -m pytest services/qqbot-channel/tests/test_no_wecom_import.py -q` | ✅ | ⬜ pending |
| 58-01-04 | 01 | 1 | ADAPTER-04 | — | N/A | unit | `python3 -m pytest tests/test_feature_flags_default.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test stubs needed — all safety tests already exist from v1.6/v1.7.

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
