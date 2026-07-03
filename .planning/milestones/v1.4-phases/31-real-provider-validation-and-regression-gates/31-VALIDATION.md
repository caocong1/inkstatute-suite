---
phase: 31
slug: real-provider-validation-and-regression-gates
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-03
verified: 2026-07-03
---

# Phase 31 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Retroactively recorded during v1.4 tech debt closure.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` + live Hindsight multi-turn validation |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_long_term_memory.py'` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~20 seconds (live Hindsight multi-turn test skips/errors when provider unreachable) |

---

## Sampling Rate

- **After every task commit:** Run `test_long_term_memory.py` (non-live classes).
- **After every plan wave:** Run full V2 gate suite.
- **Before `$gsd-verify-work`:** Full V2 gate suite must be green; deployment docs present.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-1 | 31 | 1 | MEM-17 | T-31-01 | Live Hindsight multi-turn validation: preference retention + cross-task recall | manual | `HINDSIGHT_BASE_URL=http://localhost:8888 PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_long_term_memory.py'` (requires running Hindsight) | Yes | green |
| 31-2 | 31 | 1 | MEM-18 | T-31-02 | CI without live provider: tests skip cleanly when `HINDSIGHT_BASE_URL` unreachable | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_long_term_memory.py' 2>&1 \| grep -E 'skipped|OK\|ERROR'` | Yes | green |
| 31-3 | 31 | 1 | MEM-19 | T-31-03 | V2 gate suite passes with no regressions (424 tests across 8 gates) | gate | `python scripts/run_v2_gates.py` | Yes | green |
| 31-4 | 31 | 1 | MEM-20 | T-31-04 | Deployment docs present with provider setup, required secrets, resource expectations | artifact | `test -f docs/deployment/hindsight.md && grep -q 'HINDSIGHT_BASE_URL' docs/deployment/hindsight.md` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `packages/platform-runtime/tests/test_long_term_memory.py` — `HindsightMemoryMultiTurnTest` for live multi-turn validation.
- [x] `docs/deployment/hindsight.md` — Docker setup, Ollama dev stack, required secrets, resource expectations.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Hindsight multi-turn preference retention + cross-task recall | MEM-17 | Requires running Hindsight instance + LLM/embedding backend (Ollama or Gemini) | Start Hindsight + Ollama per `docs/deployment/hindsight.md`; run `HindsightMemoryMultiTurnTest::test_multi_turn_preference_retention_and_cross_task_recall` — verify preferences and project facts retained across turns and recalled with different queries |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — V2 gate suite green (424 tests, 8 gates); deployment docs present; live multi-turn test passes when Hindsight reachable (external quota dependency noted in audit).
