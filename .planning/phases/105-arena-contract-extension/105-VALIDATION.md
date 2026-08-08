---
phase: 105
slug: arena-contract-extension
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-08
---

# Phase 105 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (stdlib) |
| **Config file** | `packages/platform-contract/pyproject.toml` |
| **Quick run command** | `python scripts/run_v2_gates.py --filter platform-contract` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python scripts/run_v2_gates.py --filter platform-contract`
- **After every plan wave:** Run `python scripts/run_v2_gates.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 105-01-01 | 01 | 1 | CONTRACT-01 | — | N/A | unit | `python scripts/run_v2_gates.py --filter platform-contract` | ❌ W0 | ⬜ pending |
| 105-01-02 | 01 | 1 | CONTRACT-01 | — | N/A | unit | `python scripts/run_v2_gates.py --filter platform-contract` | ❌ W0 | ⬜ pending |
| 105-02-01 | 02 | 1 | CONTRACT-02 | — | N/A | unit | `python scripts/run_v2_gates.py --filter platform-contract` | ❌ W0 | ⬜ pending |
| 105-02-02 | 02 | 1 | CONTRACT-02 | — | N/A | unit | `python scripts/run_v2_gates.py --filter platform-contract` | ❌ W0 | ⬜ pending |
| 105-03-01 | 03 | 2 | CONTRACT-03 | — | N/A | unit | `python scripts/run_v2_gates.py --filter platform-runtime` | ❌ W0 | ⬜ pending |
| 105-04-01 | 04 | 2 | CONTRACT-04 | — | N/A | unit | `python scripts/run_v2_gates.py` | ❌ W0 | ⬜ pending |
| 105-04-02 | 04 | 2 | CONTRACT-04 | — | N/A | unit | `python scripts/run_v2_gates.py --filter contract-test-suite` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/platform-contract/tests/test_arena_contract.py` — stubs for CONTRACT-01..04 Arena event/dataclass/Protocol tests
- [ ] `packages/contract-test-suite/fixtures/arena/` — Arena fixture replay JSONL files

*Existing infrastructure (pytest, schema validator, fixture replay engine) covers the framework requirement.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
