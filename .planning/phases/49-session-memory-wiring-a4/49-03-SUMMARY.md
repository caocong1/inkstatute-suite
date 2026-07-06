# Plan 49-03 Summary: Integration Tests and Contract Verification

## Objective

Add end-to-end integration tests that verify the full session memory wiring flow: runtime → MemoryOrchestrator → ContextBundle with memory_refs → backend adapter. Also verify that adapters never import memory providers directly, and that the V2 gate suite remains green.

## Tasks Completed

### Task 1: Integration tests for session memory wiring end-to-end flow

**Files modified:**
- `packages/platform-runtime/tests/test_session_memory_integration.py` — 6 integration tests:
  - `test_full_session_memory_flow_injects_memory_refs`: Full flow with InMemoryMemoryStore containing 2 memories, MemoryOrchestrator injected, session_memory_enabled=True — verifies ContextBundle with memory_refs in submitted request metadata, correct tenant scope, context_bundle_id consistency.
  - `test_session_memory_disabled_no_context_bundle_injected`: When session_memory_enabled=False, no context_bundle in submitted request metadata (identical to v1.6 behavior).
  - `test_session_memory_resume_interrupt_injects_memory_refs`: resume_interrupt with session_memory_enabled=True also injects memory_refs into ContextBundle.
  - `test_session_memory_isolation_wrong_tenant_no_leak`: Memories from tenant-002 are not recalled when request is scoped to tenant-001.
  - `test_session_memory_empty_store_produces_empty_memory_refs`: When store has no matching memories, memory_refs is empty but context_bundle still exists.
  - `test_no_adapter_imports_memory_provider`: Grep verification that no adapter source file imports hindsight or HindsightMemory.

**Commit:** `611d4c8` — `feat(49-03): session memory integration tests`

## Deviations

- **[Path fix]** The `test_no_adapter_imports_memory_provider` test initially used `Path(__file__).resolve().parents[2]` which resolved to `packages/` instead of the repo root. Fixed to `parents[3]` to correctly resolve to the repo root.
- **[Scope fix]** The `test_session_memory_resume_interrupt_injects_memory_refs` test initially used `bot_instance_id="bot-001"` in `make_scope()` but the RunRequest didn't set `bot_instance_id`, causing a scope mismatch. Fixed to use `bot_instance_id=""` to match the runtime's `_scope_from_request` output.

## Test Results

- **Session memory integration tests:** 6 tests pass
  - `python3 -m unittest packages.platform-runtime.tests.test_session_memory_integration -v` — OK

## Key Design Decisions

1. **Integration tests use InMemoryMemoryStore** (not HindsightMemory) — the MemoryOrchestrator uses the sync `MemoryStoreAdapter` Protocol, which `InMemoryMemoryStore` implements. This keeps tests deterministic and network-free.
2. **Grep verification for adapter isolation** — the `test_no_adapter_imports_memory_provider` test uses subprocess to grep adapter source files, ensuring no adapter imports `hindsight` or `HindsightMemory`.
3. **Resume interrupt test** — verifies that the session memory wiring works not only in `create_run` but also in `resume_interrupt`, which also calls `_attach_context_bundle`.
