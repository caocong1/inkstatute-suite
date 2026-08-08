---
phase: 88
slug: unified-event-contract
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-07
---

# Phase 88 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python) + tsc (TypeScript) |
| **Config file** | `packages/platform-contract/pyproject.toml`, `packages/platform-sdk-ts/tsconfig.json` |
| **Quick run command** | `python scripts/run_v2_gates.py` |
| **Full suite command** | `python scripts/run_v2_gates.py && python -m pytest packages/platform-contract/tests/ packages/contract-test-suite/tests/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python scripts/run_v2_gates.py`
- **After every plan wave:** Run `python -m pytest packages/platform-contract/tests/ packages/contract-test-suite/tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 88-01-01 | 01 | 1 | EVT-01 | — | N/A | unit | `python -m pytest packages/platform-contract/tests/test_unified_events.py -x` | ❌ W0 | ⬜ pending |
| 88-01-02 | 01 | 1 | EVT-01 | — | N/A | unit | `python -m pytest packages/platform-contract/tests/test_event_schemas.py -x` | ❌ W0 | ⬜ pending |
| 88-01-03 | 01 | 1 | EVT-01 | — | N/A | compile | `cd packages/platform-sdk-ts && npx tsc --noEmit` | ❌ W0 | ⬜ pending |
| 88-02-01 | 02 | 1 | EVT-02 | — | N/A | unit | `python -m pytest packages/contract-test-suite/tests/test_event_stream_replay.py -x` | ✅ | ⬜ pending |
| 88-03-01 | 03 | 2 | EVT-03 | — | N/A | unit | `python -m pytest packages/platform-contract/tests/test_elicitation_contract.py -x` | ❌ W0 | ⬜ pending |
| 88-04-01 | 04 | 2 | EVT-04 | — | N/A | unit | `python -m pytest packages/platform-contract/tests/test_five_phase_progress.py -x` | ❌ W0 | ⬜ pending |
| 88-05-01 | 05 | 2 | EVT-05 | — | N/A | unit | `python -m pytest packages/platform-contract/tests/test_bot_degradation.py -x` | ❌ W0 | ⬜ pending |
| 88-06-01 | 06 | 3 | EVT-06 | — | N/A | gate | `python scripts/run_v2_gates.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/platform-contract/tests/test_unified_events.py` — stubs for EVT-01 (13 event types)
- [ ] `packages/platform-contract/tests/test_event_schemas.py` — stubs for EVT-01 (JSON Schema validation)
- [ ] `packages/platform-contract/tests/test_elicitation_contract.py` — stubs for EVT-03
- [ ] `packages/platform-contract/tests/test_five_phase_progress.py` — stubs for EVT-04
- [ ] `packages/platform-contract/tests/test_bot_degradation.py` — stubs for EVT-05
- [ ] TypeScript event type definitions in `packages/platform-sdk-ts/src/events.ts`

*Existing infrastructure (pytest, gates, contract-test-suite) covers the framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
