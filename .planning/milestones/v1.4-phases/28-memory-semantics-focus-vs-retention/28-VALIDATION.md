---
phase: 28
slug: memory-semantics-focus-vs-retention
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-03
verified: 2026-07-03
---

# Phase 28 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Retroactively recorded during v1.4 tech debt closure.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_memory_policy.py'` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `test_memory_policy.py`.
- **After every plan wave:** Run full `packages/platform-runtime/tests/` discover.
- **Before `$gsd-verify-work`:** Full V2 gate suite must be green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 28-1 | 28 | 1 | MEM-10 | T-28-01 | `MemoryContentClassifier` classifies durable vs transient deterministically (LLM-free) | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_memory_policy.py'` | Yes | green |
| 28-2 | 28 | 1 | MEM-09 | T-28-02 | `MemoryRetentionPolicy` defines which categories are retained (user_preference, project_fact, lesson_learned) | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_memory_policy.py'` | Yes | green |
| 28-3 | 28 | 1 | MEM-08 | T-28-03 | `MemoryFocusPolicy` defines recall scope (top-N by relevance, optional minimum threshold) | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_memory_policy.py'` | Yes | green |
| 28-4 | 28 | 1 | MEM-08, MEM-10 | T-28-04 | `FakeMemory` applies classifier before storage and focus policy during recall | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_long_term_memory.py'` | Yes | green |
| 28-5 | 28 | 1 | MEM-08 | T-28-05 | `HindsightMemory` respects `focus_policy.max_results` | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_long_term_memory.py'` | Yes | green |
| 28-6 | 28 | 1 | MEM-19 | T-28-06 | V2 gate suite passes with no regressions | gate | `python scripts/run_v2_gates.py` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `packages/platform-runtime/src/platform_runtime/memory_policy.py` — `MemoryContentClassifier`, `MemoryRetentionPolicy`, `MemoryFocusPolicy`.
- [x] `packages/platform-runtime/tests/test_memory_policy.py` — 10 policy tests.
- [x] Policy types exported from `platform_runtime.__init__`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | MEM-08, MEM-09, MEM-10 | All phase behaviors have automated verification paths (deterministic, LLM-free classifier) | N/A |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — 10 policy tests pass; 8 long-term-memory tests pass; V2 gates green.
