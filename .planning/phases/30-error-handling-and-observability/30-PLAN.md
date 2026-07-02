:aspect-plan: Error Handling and Observability

## 1. Phase 30: Error Handling and Observability

### 1.1. Scope

Add exponential backoff retry, failure classification, and contract events around the `Memory` interface. Keep the user-facing response unchanged on memory failures.

### 1.2. Success Criteria

1. `Memory` operations retry with exponential backoff up to a configured limit.
2. Failures are classified into transient, timeout, permanent, or auth.
3. A `MemoryOperationEvent` is emitted for every retain/recall/reflect attempt and failure.
4. `fail_open` mode keeps the runtime response unchanged when memory fails.
5. No silent fallback to a different backend occurs.
6. V2 gates remain green.

### 1.3. Deliverables

| Deliverable | Location |
|-------------|----------|
| RetryableMemory wrapper | `packages/platform-runtime/src/platform_runtime/retryable_memory.py` |
| Failure classification | `packages/platform-runtime/src/platform_runtime/memory_errors.py` |
| Memory operation events | `packages/platform-runtime/src/platform_runtime/memory_events.py` |
| Updated memory integration | `services/wecom-service/src/wecom_service/memory_integration.py` |
| Tests | `packages/platform-runtime/tests/test_retryable_memory.py`, `services/wecom-service/tests/test_memory_integration_observability.py` |

### 1.4. Execution Plan

#### Wave 1: Failure classification

- Define `MemoryFailureCategory` and `MemoryOperationError`.
- Add `_classify_exception` helper that maps exception types to categories.

#### Wave 2: RetryableMemory wrapper

- Implement `RetryableMemory` that wraps a `Memory`.
- Config: `max_retries`, `base_delay`, `max_delay`, `retryable_categories`.
- For each operation, retry on transient/timeout failures.
- On permanent/auth failure, fail immediately.
- Return result or raise classified `MemoryOperationError`.

#### Wave 3: Memory operation events

- Define `MemoryOperationEvent` dataclass with `operation`, `bank_id`, `status`, `category`, `latency_ms`, `retry_count`, `error_code`.
- Define `MemoryObserver` Protocol with `on_memory_event(event)`.
- `RetryableMemory` accepts an optional observer and emits events.

#### Wave 4: Update memory_integration

- Use `RetryableMemory` in `recall_for_turn` and `retain_turn_memory`.
- Pass a simple observer that records events in metadata.
- Ensure `fail_open` still swallows errors.

#### Wave 5: Tests and gates

- Test retry succeeds after transient failures.
- Test permanent failures do not retry.
- Test events are emitted.
- Test `fail_open` does not crash response.
- Run `scripts/run_v2_gates.py`.

### 1.5. Verification

- `pytest packages/platform-runtime/tests/test_retryable_memory.py` passes.
- `pytest services/wecom-service/tests/test_memory_integration_observability.py` passes.
- `scripts/run_v2_gates.py` passes.
