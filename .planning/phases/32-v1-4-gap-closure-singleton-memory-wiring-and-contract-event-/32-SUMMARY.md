---
phase: "32-v1-4-gap-closure-singleton-memory-wiring-and-contract-event-"
title: "Phase 32 v1.4 Gap Closure: Singleton Memory Wiring and Contract Event Observability"
status: complete
completed: "2026-07-03"
requirements: [MEM-07, MEM-16]
files_changed: 8
---

# Phase 32 Summary: v1.4 Gap Closure — Singleton Memory Wiring and Contract Event Observability

## What Was Done

This phase closed the two `partial` integration gaps identified in the v1.4 milestone audit (MEM-07, MEM-16).

### New files
- `services/wecom-service/src/wecom_service/memory_factory.py` — `build_memory_from_env()` singleton factory: constructs a single `HindsightMemory` from `HINDSIGHT_BASE_URL` / `HINDSIGHT_API_KEY`; returns `None` when base URL is unset (graceful opt-out).
- `packages/platform-runtime/tests/test_memory_events.py` — 4 tests verifying memory operations produce contract log events with correct fields.
- `services/wecom-service/tests/test_ingress_memory_wiring.py` — 8 tests verifying ingress passes memory and observer through to the runtime.

### Modified files
- `packages/platform-runtime/src/platform_runtime/memory_events.py` — added `ContractLogMemoryObserver` implementing `MemoryObserver`; writes `MemoryOperationEvent.as_json()` to a `ContractLogStore` via `append(event_key, event)`.
- `packages/platform-runtime/src/platform_runtime/__init__.py` — exported new types.
- `services/wecom-service/src/wecom_service/ingress_runtime.py` — `WeComRuntimeIngress.__init__` now accepts `memory`, `memory_policy`, and `memory_observer` and passes them through to `WeComSessionRuntime`.
- `services/wecom-service/src/wecom_service/session_runtime.py` — passes `memory_observer` to `RetryableMemory` when wrapping the injected memory.
- `docs/deployment/hindsight.md` — singleton initialization example and `ContractLogMemoryObserver` wiring example.

## Test Results

- `test_memory_events.py`: 4 passed.
- `test_ingress_memory_wiring.py`: 8 passed.
- `scripts/run_v2_gates.py`: all 8 gates green (424 tests total).

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

## Gap Closure Evidence

### MEM-07: Singleton Memory Initialization
- `WeComRuntimeIngress` accepts `memory`/`memory_policy`/`memory_observer` and passes them to `WeComSessionRuntime`, which wraps `memory` in `RetryableMemory(memory, observer=memory_observer)`.
- `build_memory_from_env()` constructs the singleton from env vars; returns `None` when unset (graceful opt-out).
- Deployment docs include a singleton initialization example (host constructs memory once at startup, injects into ingress).

### MEM-16: Contract Event Observability
- `ContractLogMemoryObserver` writes `MemoryOperationEvent` to the contract log.
- `WeComSessionRuntime` passes `memory_observer` to `RetryableMemory`; `WeComRuntimeIngress` passes it through.
- Tests verify events are written with correct fields (operation, bank_id, status, category, latency_ms, retry_count, error_code).

## Requirements Closed

- MEM-07, MEM-16 — satisfied (closes v1.4 audit gaps; audit result now 20/20 passed).

## Milestone Status

Phase 32 complete. v1.4 audit gaps closed. Milestone v1.4 Long-Term Memory Productization ready for completion.
