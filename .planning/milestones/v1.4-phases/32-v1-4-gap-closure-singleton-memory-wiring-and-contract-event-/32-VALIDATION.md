---
phase: 32
slug: v1-4-gap-closure-singleton-memory-wiring-and-contract-event-
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-03
verified: 2026-07-03
---

# Phase 32 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Retroactively recorded during v1.4 tech debt closure. Phase 32 closed audit gaps MEM-07 and MEM-16.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_memory_events.py'` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_memory_events.py' && PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests -p 'test_ingress_memory_wiring.py' && python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `test_memory_events.py` + `test_ingress_memory_wiring.py`.
- **After every plan wave:** Run full V2 gate suite.
- **Before `$gsd-verify-work`:** Full V2 gate suite must be green; deployment docs updated.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 32-1 | 32 | 1 | MEM-07 | T-32-01 | `WeComRuntimeIngress.__init__` accepts `memory`, `memory_policy`, `memory_observer` and passes through to `WeComSessionRuntime` | unit | `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests -p 'test_ingress_memory_wiring.py'` | Yes | green |
| 32-2 | 32 | 1 | MEM-07 | T-32-02 | `build_memory_from_env()` constructs singleton `HindsightMemory` from env vars; returns `None` when unset (graceful opt-out) | unit | `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests -p 'test_ingress_memory_wiring.py'` | Yes | green |
| 32-3 | 32 | 1 | MEM-16 | T-32-03 | `ContractLogMemoryObserver` writes `MemoryOperationEvent.as_json()` to `ContractLogStore` via `append(event_key, event)` | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_memory_events.py'` | Yes | green |
| 32-4 | 32 | 1 | MEM-16 | T-32-04 | `WeComSessionRuntime` passes `memory_observer` to `RetryableMemory`; events written with correct fields (operation, bank_id, status, category, latency_ms, retry_count, error_code) | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_memory_events.py'` | Yes | green |
| 32-5 | 32 | 1 | MEM-19 | T-32-05 | V2 gate suite passes (424 tests, 8 gates) | gate | `python scripts/run_v2_gates.py` | Yes | green |
| 32-6 | 32 | 1 | MEM-20 | T-32-06 | Deployment docs updated with singleton + observer wiring examples | artifact | `grep -q 'build_memory_from_env' docs/deployment/hindsight.md && grep -q 'ContractLogMemoryObserver' docs/deployment/hindsight.md` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `services/wecom-service/src/wecom_service/memory_factory.py` — `build_memory_from_env()` singleton factory.
- [x] `packages/platform-runtime/src/platform_runtime/memory_events.py` — `ContractLogMemoryObserver` added.
- [x] `packages/platform-runtime/tests/test_memory_events.py` — 4 tests.
- [x] `services/wecom-service/tests/test_ingress_memory_wiring.py` — 8 tests.
- [x] `docs/deployment/hindsight.md` — singleton + observer sections.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | MEM-07, MEM-16 | All phase behaviors have automated verification paths | N/A |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — 4 memory-events tests pass; 8 ingress-memory-wiring tests pass; V2 gates green (424 tests, 8 gates). MEM-07 and MEM-16 audit gaps closed.
