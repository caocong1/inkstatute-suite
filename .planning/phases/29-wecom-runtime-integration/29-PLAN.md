:aspect-plan: WeCom/Runtime Integration

## 1. Phase 29: WeCom/Runtime Integration

### 1.1. Scope

Wire the unified `Memory` layer into the ordinary WeCom/runtime flow: pre-turn recall before agent invocation, post-turn retention after the reply is finalized.

### 1.2. Success Criteria

1. `WeComSessionRuntime` accepts an optional `Memory` instance.
2. When memory is present, it recalls relevant durable memory before the agent turn.
3. Recall result is passed to the runtime as a safe metadata summary (no raw text).
4. After the agent reply is finalized, durable memory is retained.
5. Memory failures do not block the user-facing response.
6. Existing Hermes one-shot adapter and V2 gates remain green.

### 1.3. Deliverables

| Deliverable | Location |
|-------------|----------|
| Memory integration policy | `packages/platform-runtime/src/platform_runtime/memory_integration_policy.py` |
| WeComSessionRuntime integration | `services/wecom-service/src/wecom_service/session_runtime.py` |
| Recall/retention helpers | `services/wecom-service/src/wecom_service/memory_integration.py` |
| Unit tests | `services/wecom-service/tests/test_session_memory_integration.py` |

### 1.4. Execution Plan

#### Wave 1: Memory integration policy

- Define `MemoryIntegrationPolicy` with `enabled`, `failure_mode`, `recall_max_results`, `retention_scope`.
- Failure modes: `fail_open`, `log_only`, `fail_closed` (fail_closed for dev only).
- Retention scope: `user_turn`, `agent_reply`, `both`.

#### Wave 2: WeComSessionRuntime integration

- Add `memory: Memory | None` and `memory_policy: MemoryIntegrationPolicy` to `WeComSessionRuntime.__init__`.
- In `handle_turn`, after turn scope resolution and before backend submission, call `memory.arecall` with the user turn text.
- Add the recalled memory summary to `run_request.metadata["memory_recall_summary"]`.
- After the run completes and the reply is finalized, call `memory.aretain` with the appropriate content (agent reply if scope allows).

#### Wave 3: Tests

- Add `test_session_memory_integration.py` with `FakeMemory`:
  - Recall before backend submission
  - Retention after reply
  - Memory isolation between users
  - Memory failure does not crash response

#### Wave 4: Gates

- Run `scripts/run_v2_gates.py`.

### 1.5. Verification

- `pytest services/wecom-service/tests/test_session_memory_integration.py` passes.
- `scripts/run_v2_gates.py` passes.
