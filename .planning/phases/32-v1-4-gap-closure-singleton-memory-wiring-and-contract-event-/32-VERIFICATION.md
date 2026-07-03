# Phase 32 Verification

**Phase:** v1.4 Gap Closure: Singleton Memory Wiring and Contract Event Observability
**Date:** 2026-07-03
**Status:** PASS

---

## Checklist

| # | Requirement | Evidence | Status |
|---|-------------|----------|--------|
| 1 | WeComRuntimeIngress accepts memory, memory_policy, memory_observer | `ingress_runtime.py` constructor updated | PASS |
| 2 | Singleton HindsightMemory factory from env | `memory_factory.py` `build_memory_from_env()` | PASS |
| 3 | ContractLogMemoryObserver writes events to ContractLogStore | `memory_events.py` `ContractLogMemoryObserver` | PASS |
| 4 | WeComSessionRuntime passes observer to RetryableMemory | `session_runtime.py` constructor | PASS |
| 5 | Tests verify memory operations produce contract log events | `test_memory_events.py` (4 tests) | PASS |
| 6 | Tests verify ingress passes memory and observer through | `test_ingress_memory_wiring.py` (8 tests) | PASS |
| 7 | V2 gate suite passes | `scripts/run_v2_gates.py` — all 8 gates green | PASS |
| 8 | Deployment docs updated | `docs/deployment/hindsight.md` singleton + observer sections | PASS |

---

## Test Results

```
packages/platform-runtime/tests/test_memory_events.py: 4 passed
services/wecom-service/tests/test_ingress_memory_wiring.py: 8 passed
scripts/run_v2_gates.py: all 8 gates green (424 tests total)
```

### Gate Breakdown

| Gate | Tests | Status |
|------|-------|--------|
| platform-contract | 21 | OK |
| wecom-service | 71 | OK |
| hermes-contract-layer | 30 | OK |
| conversation-read-view | 18 | OK |
| feedback-service | 31 | OK |
| phase7-privacy-boundary | 13 | OK |
| contract-test-suite | 240 | OK |
| compileall | — | OK |

---

## Gap Closure Evidence

### MEM-07: Singleton Memory Initialization

- `WeComRuntimeIngress.__init__` now accepts `memory: Memory | None`, `memory_policy: Any | None`, and `memory_observer: MemoryObserver | None` parameters.
- These are passed through to `WeComSessionRuntime`, which wraps `memory` in `RetryableMemory(memory, observer=memory_observer)`.
- `build_memory_from_env()` factory in `memory_factory.py` constructs a singleton `HindsightMemory` from `HINDSIGHT_BASE_URL` and `HINDSIGHT_API_KEY` environment variables. Returns `None` when base URL is unset (graceful opt-out).
- Deployment docs (`docs/deployment/hindsight.md`) include a singleton initialization example showing the host constructing memory once at startup and injecting it into the ingress.

### MEM-16: Contract Event Observability

- `ContractLogMemoryObserver` class in `memory_events.py` implements `MemoryObserver` and writes `MemoryOperationEvent.as_json()` to a `ContractLogStore` via `append(event_key, event)`.
- `WeComSessionRuntime` now passes `memory_observer` to `RetryableMemory` when wrapping the injected memory.
- `WeComRuntimeIngress` passes `memory_observer` through to `WeComSessionRuntime`.
- Tests verify that events are written to the contract log with correct fields (operation, bank_id, status, category, latency_ms, retry_count, error_code).
- Deployment docs include a `ContractLogMemoryObserver` wiring example.

---

## Sign-off

Phase 32 complete. v1.4 audit gaps (MEM-07, MEM-16) are closed. Milestone v1.4 is ready for completion.
