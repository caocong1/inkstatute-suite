# Phase 32: v1.4 Gap Closure: Singleton Memory Wiring and Contract Event Observability - Context

**Gathered:** 2026-07-03
**Status:** Ready for planning
**Mode:** Auto-generated from v1.4 milestone audit gap closure

<domain>
## Phase Boundary

Close the two partial requirements identified in the v1.4 milestone audit:

1. **MEM-07 (Singleton Initialization):** The `Memory` interface and `HindsightMemory` adapter support singleton injection (memory is an optional constructor parameter on `WeComSessionRuntime`), but no deployment entrypoint constructs a singleton `HindsightMemory` instance. `WeComRuntimeIngress` instantiates `WeComSessionRuntime` WITHOUT a `memory` parameter, so production deployments have no memory wired by default.

2. **MEM-16 (Contract Event Observability):** `MemoryOperationEvent` and `MemoryObserver` Protocol are defined and `RetryableMemory` accepts an observer, but the WeCom service never wires a production observer to `RetryableMemory`. Events are emitted in tests (`InMemoryMemoryObserver`) but not recorded to any contract log in production.

</domain>

<decisions>
## Implementation Decisions

### From Audit Recommendations

1. **MEM-07 closure:** Add `memory` and `memory_policy` parameters to `WeComRuntimeIngress.__init__` and pass them through to `WeComSessionRuntime`. Create a memory factory function that constructs a singleton `HindsightMemory` from environment configuration (`HINDSIGHT_BASE_URL`, `HINDSIGHT_API_KEY`). Document the singleton pattern in deployment docs.

2. **MEM-16 closure:** Implement a `ContractLogMemoryObserver` that writes `MemoryOperationEvent` entries to a `ContractLogStore`. Wire it to `RetryableMemory` via the `WeComSessionRuntime` initialization chain. Add `memory_observer` parameter to `WeComRuntimeIngress` and pass through.

### Architecture Constraints

- `WeComRuntimeIngress` intentionally performs no network IO or backend construction — hosts inject dependencies. The memory factory should be a separate function the host calls, not embedded in the ingress class.
- `ContractLogStore` is a Protocol with a single `append(event_key, event)` method — the observer should adapt to this interface.
- The `platform-runtime` package must remain neutral (no env var reads for secrets). The host constructs `HindsightMemory` and passes it in.

</decisions>

<code_context>
## Existing Code Insights

### Current State (Gaps)

- `services/wecom-service/src/wecom_service/ingress_runtime.py` lines 27-68: `WeComRuntimeIngress.__init__` does NOT accept `memory`, `memory_policy`, or `memory_observer` parameters. It constructs `WeComSessionRuntime` without memory wiring.
- `services/wecom-service/src/wecom_service/session_runtime.py` line 116: `RetryableMemory(memory)` is instantiated WITHOUT an `observer` parameter.
- `packages/platform-runtime/src/platform_runtime/memory_events.py`: `MemoryObserver` Protocol and `InMemoryMemoryObserver` exist but no production observer writes to `ContractLogStore`.
- `packages/platform-runtime/src/platform_runtime/ports.py` line 30: `ContractLogStore` Protocol with `append(event_key, event)` method.

### Existing Infrastructure (Reusable)

- `packages/platform-runtime/src/platform_runtime/hindsight_memory.py`: `HindsightMemory` adapter accepts a pre-configured `hindsight_client.Hindsight` instance.
- `packages/platform-runtime/src/platform_runtime/retryable_memory.py`: `RetryableMemory` already accepts an optional `observer: MemoryObserver`.
- `packages/platform-runtime/src/platform_runtime/memory_events.py`: `MemoryOperationEvent.as_json()` returns a JSON-serializable dict.
- `docs/deployment/hindsight.md`: Already documents secrets, setup, and configuration.

</code_context>

<specifics>
## Specific Ideas

### MEM-07: Singleton Memory Wiring

1. Add `memory: Memory | None = None` and `memory_policy: Any | None = None` parameters to `WeComRuntimeIngress.__init__`.
2. Pass `memory` and `memory_policy` through to `WeComSessionRuntime` constructor.
3. Create a `build_memory_from_env()` factory function in a new `services/wecom-service/src/wecom_service/memory_factory.py` module that:
   - Reads `HINDSIGHT_BASE_URL` and `HINDSIGHT_API_KEY` from environment
   - Constructs a `hindsight_client.Hindsight` instance
   - Wraps it in `HindsightMemory`
   - Returns `None` if `HINDSIGHT_BASE_URL` is not set (graceful opt-out)
4. Update deployment docs to show the singleton initialization pattern.

### MEM-16: Contract Event Observer

1. Create `ContractLogMemoryObserver` class (in `platform-runtime` or `wecom-service`) that implements `MemoryObserver` and writes events to a `ContractLogStore` via `append("memory_operation", event.as_json())`.
2. Add `memory_observer: MemoryObserver | None = None` parameter to `WeComRuntimeIngress.__init__`.
3. Pass `memory_observer` through to `WeComSessionRuntime` which passes it to `RetryableMemory(memory, observer=memory_observer)`.
4. Add tests verifying that memory operations produce events in the contract log.

</specifics>

<deferred>
## Deferred Ideas

None — this phase is scoped to the two audit gaps only.

</deferred>
