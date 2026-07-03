---
phase: 27
slug: unified-memory-interface-and-hindsight-adapter
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-03
verified: 2026-07-03
---

# Phase 27 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Retroactively recorded during v1.4 tech debt closure.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_long_term_memory.py'` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~20 seconds (live Hindsight tests skip/error when provider unreachable) |

---

## Sampling Rate

- **After every task commit:** Run `test_long_term_memory.py` (non-live classes).
- **After every plan wave:** Run full `packages/platform-runtime/tests/` discover.
- **Before `$gsd-verify-work`:** Full V2 gate suite must be green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 27-1 | 27 | 1 | MEM-04 | T-27-01 | `Memory` Protocol defines async `aretain`/`arecall`/`areflect` with privacy-safe metadata | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_long_term_memory.py'` | Yes | green |
| 27-2 | 27 | 1 | MEM-05 | T-27-02 | `HindsightMemory` implements `Memory` Protocol via `hindsight-client`; accepts pre-configured client (no secret reads in neutral package) | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_long_term_memory.py'` | Yes | green |
| 27-3 | 27 | 1 | MEM-04 | T-27-03 | `FakeMemory` test double provided for contract tests | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_long_term_memory.py'` | Yes | green |
| 27-4 | 27 | 1 | MEM-06 | T-27-04 | `SQLiteMemoryStore` no longer the default legal memory backend; adapter contract test updated | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_memory_adapter_contract.py'` | Yes | green |
| 27-5 | 27 | 1 | MEM-04, MEM-05 | T-27-05 | New types exported from `platform_runtime.__init__` | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -c "from platform_runtime import Memory, HindsightMemory, FakeMemory; print('ok')"` | Yes | green |
| 27-6 | 27 | 1 | MEM-19 | T-27-06 | V2 gate suite passes with no regressions | gate | `python scripts/run_v2_gates.py` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `packages/platform-runtime/src/platform_runtime/long_term_memory.py` — `Memory` Protocol.
- [x] `packages/platform-runtime/src/platform_runtime/hindsight_memory.py` — `HindsightMemory` adapter.
- [x] `packages/platform-runtime/src/platform_runtime/fake_memory.py` — `FakeMemory` test double.
- [x] `packages/platform-runtime/tests/test_long_term_memory.py` — 8 contract tests (7 non-live pass; 2 live Hindsight tests pass when provider reachable, skip/error otherwise).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Hindsight `aretain`/`arecall`/`areflect` end-to-end | MEM-05 | Requires running Hindsight instance at `HINDSIGHT_BASE_URL` | Start Hindsight; run `HindsightMemoryContractTest` — verify retain/recall/reflect return expected results |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — 7 non-live tests pass; 14 adapter contract tests pass; V2 gates green. Live Hindsight test passes when provider reachable (external quota dependency noted in audit).
