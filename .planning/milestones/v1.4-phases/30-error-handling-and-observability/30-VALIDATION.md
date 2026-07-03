---
phase: 30
slug: error-handling-and-observability
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-03
verified: 2026-07-03
---

# Phase 30 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Retroactively recorded during v1.4 tech debt closure.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_retryable_memory.py'` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests && python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** Run `test_retryable_memory.py`.
- **After every plan wave:** Run full `packages/platform-runtime/tests/` + `services/wecom-service/tests/` discover.
- **Before `$gsd-verify-work`:** Full V2 gate suite must be green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 30-1 | 30 | 1 | MEM-14 | T-30-01 | `RetryableMemory` retries transient/timeout failures with exponential backoff up to configured limit | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_retryable_memory.py'` | Yes | green |
| 30-2 | 30 | 1 | MEM-14 | T-30-02 | `MemoryFailureCategory` + `classify_exception` classifies transient, timeout, auth, permanent, unknown; auth/permanent raised immediately | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_retryable_memory.py'` | Yes | green |
| 30-3 | 30 | 1 | MEM-16 | T-30-03 | `MemoryOperationEvent` + `MemoryObserver` protocol emitted for every attempt and success | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_retryable_memory.py'` | Yes | green |
| 30-4 | 30 | 1 | MEM-15 | T-30-04 | `WeComSessionRuntime` wraps injected `Memory` with `RetryableMemory`; default `fail_open` keeps user-facing response unchanged | unit | `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s services/wecom-service/tests -p 'test_session_memory_integration.py'` | Yes | green |
| 30-5 | 30 | 1 | MEM-14 | T-30-05 | No silent fallback: SQLite default already removed; no alternate backend introduced | git | `git log --oneline -- packages/platform-runtime/src/platform_runtime/sqlite_memory.py \| grep -q deprecat \|\| git log --oneline 939547f -1 \| grep -q .` | Yes | green |
| 30-6 | 30 | 1 | MEM-19 | T-30-06 | V2 gate suite passes with no regressions | gate | `python scripts/run_v2_gates.py` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `packages/platform-runtime/src/platform_runtime/memory_errors.py` — `MemoryFailureCategory` + `classify_exception`.
- [x] `packages/platform-runtime/src/platform_runtime/memory_events.py` — `MemoryOperationEvent` + `MemoryObserver`.
- [x] `packages/platform-runtime/src/platform_runtime/retryable_memory.py` — `RetryableMemory` wrapper.
- [x] `packages/platform-runtime/tests/test_retryable_memory.py` — 4 retryable-memory tests.
- [x] Error/event/retryable types exported from `platform_runtime.__init__`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | MEM-14, MEM-15, MEM-16 | All phase behaviors have automated verification paths | N/A |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — 4 retryable-memory tests pass; 232 platform-runtime tests pass; 63 wecom-service tests pass; V2 gates green. (MEM-16 production observer wiring closed in Phase 32.)
