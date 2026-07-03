:aspect-plan: v1.4 Gap Closure: Singleton Memory Wiring and Contract Event Observability

## 1. Phase 32: v1.4 Gap Closure

### 1.1. Scope

Close two partial requirements from the v1.4 milestone audit:
- **MEM-07:** Wire singleton `HindsightMemory` into the WeCom deployment entrypoint.
- **MEM-16:** Wire `MemoryObserver` to `RetryableMemory` so memory operation events are recorded to the contract log.

### 1.2. Success Criteria

1. `WeComRuntimeIngress` accepts `memory`, `memory_policy`, and `memory_observer` parameters and passes them through to `WeComSessionRuntime`.
2. A `build_memory_from_env()` factory constructs a singleton `HindsightMemory` from environment configuration.
3. A `ContractLogMemoryObserver` writes `MemoryOperationEvent` entries to a `ContractLogStore`.
4. `WeComSessionRuntime` passes the observer to `RetryableMemory`.
5. Tests verify memory operations produce contract log events.
6. V2 gate suite passes.
7. Deployment docs updated with singleton initialization pattern.

### 1.3. Deliverables

| Deliverable | Location |
|-------------|----------|
| `ContractLogMemoryObserver` | `packages/platform-runtime/src/platform_runtime/memory_events.py` |
| `build_memory_from_env()` factory | `services/wecom-service/src/wecom_service/memory_factory.py` |
| `WeComRuntimeIngress` memory wiring | `services/wecom-service/src/wecom_service/ingress_runtime.py` |
| `WeComSessionRuntime` observer wiring | `services/wecom-service/src/wecom_service/session_runtime.py` |
| Observer contract tests | `packages/platform-runtime/tests/test_memory_events.py` |
| Ingress memory wiring tests | `services/wecom-service/tests/test_ingress_memory_wiring.py` |
| Deployment docs update | `docs/deployment/hindsight.md` |

### 1.4. Execution Plan

#### Wave 1: ContractLogMemoryObserver + ingress wiring

**32-01-PLAN.md — Contract log observer and ingress memory wiring**

Tasks:
1. Add `ContractLogMemoryObserver` class to `memory_events.py`:
   - Constructor accepts `contract_log_store: ContractLogStore` and optional `event_key: str = "memory_operation"`
   - `on_memory_event(event)` calls `contract_log_store.append(event_key, event.as_json())`
   - Export from `platform_runtime.__init__`
2. Add `memory`, `memory_policy`, and `memory_observer` parameters to `WeComRuntimeIngress.__init__`
3. Pass `memory`, `memory_policy`, and `memory_observer` through to `WeComSessionRuntime`
4. Update `WeComSessionRuntime.__init__` to accept `memory_observer: MemoryObserver | None = None` and pass it to `RetryableMemory(memory, observer=memory_observer)`
5. Create `build_memory_from_env()` factory in `services/wecom-service/src/wecom_service/memory_factory.py`:
   - Read `HINDSIGHT_BASE_URL` and `HINDSIGHT_API_KEY` from environment
   - Construct `hindsight_client.Hindsight` instance
   - Wrap in `HindsightMemory`
   - Return `None` if `HINDSIGHT_BASE_URL` is not set
6. Write tests:
   - `test_memory_events.py`: `ContractLogMemoryObserver` writes events to a fake `ContractLogStore`
   - `test_ingress_memory_wiring.py`: `WeComRuntimeIngress` passes memory and observer through to `WeComSessionRuntime`
   - `test_memory_factory.py`: `build_memory_from_env()` returns `None` when env var unset, returns `HindsightMemory` when set
7. Update `docs/deployment/hindsight.md` with singleton initialization pattern and observer wiring example
8. Run V2 gates

#### Wave 2: Verification

**32-02-PLAN.md — Verification and gate regression**

Tasks:
1. Run full V2 gate suite
2. Write VERIFICATION.md
3. Update REQUIREMENTS.md traceability table for MEM-07 and MEM-16
4. Update STATE.md

### 1.5. Verification

- `python -m unittest packages/platform-runtime/tests/test_memory_events.py` — passes
- `python -m unittest services/wecom-service/tests/test_ingress_memory_wiring.py` — passes
- `python -m unittest services/wecom-service/tests/test_memory_factory.py` — passes
- `python scripts/run_v2_gates.py` — all gates green
