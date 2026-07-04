---
phase: 44
slug: m2-gate-integration-full-suite-verification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-04
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python unittest (stdlib) — matches existing gate suite |
| **Config file** | `scripts/run_v2_gates.py` (gate runner) |
| **Quick run command** | `python scripts/run_v2_gates.py` |
| **Full suite command** | `python scripts/run_v2_gates.py` (same — gate suite is fast) |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python scripts/run_v2_gates.py`
- **After every plan wave:** Run `python scripts/run_v2_gates.py`
- **Before `/gsd-verify-work`:** Full gate suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 44-01-01 | 01 | 1 | GATE-01 | — | N/A | meta | `python scripts/run_v2_gates.py --list` shows new gates | ❌ W0 | ⬜ pending |
| 44-02-01 | 02 | 1 | GATE-01 | — | N/A | meta | `python -m unittest packages/contract-test-suite/tests/test_gate_coverage.py` exits 0 | ❌ W0 | ⬜ pending |
| 44-03-01 | 03 | 2 | GATE-01 | — | N/A | meta | `python -m unittest packages/contract-test-suite/tests/test_audit_v2_requirements.py::TestAudit::test_v2_gates_includes_traceability_gate` exits 0 | ✅ | ⬜ pending |
| 44-04-01 | 04 | 2 | GATE-01 | — | N/A | regression | `python scripts/run_v2_gates.py` exits 0 (all gates green) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/contract-test-suite/tests/test_gate_coverage.py` — meta-test stubs for GATE-01 (directory coverage + gate count)

*Existing infrastructure (unittest, gate runner) covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ROADMAP wording update reflects current gate count | GATE-01 | Documentation review | Read `.planning/ROADMAP.md` Phase 44 SC#2 — confirm "9 existing" replaced with "all existing" |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test_gate_coverage.py)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
