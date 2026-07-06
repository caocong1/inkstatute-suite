# Plan 49-01 Summary: Runtime Memory Wiring

## Objective

Add `memory_orchestrator` as an optional keyword-only injected dependency on `DefaultRunRuntime`. When `session_memory_enabled=True`, the runtime delegates context assembly to `MemoryOrchestrator.recall_and_assemble()`, which queries a `MemoryStoreAdapter` scoped by `(tenant_id, workspace_id, user_id)` and injects recalled `memory_refs` into the `ContextBundle` before `backend.submit_run()`. When `session_memory_enabled=False` (default), the runtime behaves identically to v1.6.

## Tasks Completed

### Task 1: Add memory_orchestrator parameter and wire session memory into _attach_context_bundle

**Files modified:**
- `packages/platform-runtime/src/platform_runtime/runtime.py` — Added `from .memory_orchestrator import MemoryOrchestrator` import. Added `memory_orchestrator: MemoryOrchestrator | None = None` keyword-only parameter to `DefaultRunRuntime.__init__`, stored as `self.memory_orchestrator`. Modified `_attach_context_bundle` to check `session_memory_enabled` first — when True, delegates to new `_attach_context_bundle_with_memory` method which requires `memory_orchestrator` (raises `RunRuntimeStateError` if None), builds `ContextAssemblyInput` via existing `_context_assembly_input`, calls `memory_orchestrator.recall_and_assemble()` with scope/session/turn refs, and injects the resulting `ContextBundle` into `req.metadata`. When `session_memory_enabled=False`, falls through to existing `context_assembly_enabled` path unchanged.
- `packages/platform-runtime/tests/test_memory_orchestrator.py` — Updated `test_run_runtime_constructor_has_no_memory_orchestrator_parameter` to assert `memory_orchestrator` IS in the constructor signature (Phase 49 supersedes Phase 22 REC-05 constraint), while still blocking `memory_store` and `recall_orchestrator`.
- `packages/platform-runtime/tests/test_session_memory_runtime.py` — 10 new tests: session_memory disabled by default, can be enabled, require_enabled raises when false, requires memory_orchestrator when enabled, injects memory_refs into ContextBundle, disabled produces no context_bundle, recall before submit, does not break context_assembly path, tenant isolation, contract log integration.

**Commit:** `2d2aaa6` — `feat(49-01): runtime memory wiring with MemoryOrchestrator injection`

## Deviations

- **[Phase 22 constraint supersession]** The test `test_run_runtime_constructor_has_no_memory_orchestrator_parameter` (test_memory_orchestrator.py:358) explicitly blocked `memory_orchestrator` from the constructor signature. Phase 49 SESSMEM-01 explicitly requires this parameter. The test was updated to assert `memory_orchestrator` IS present while still blocking `memory_store` and `recall_orchestrator`. This is a legitimate constraint supersession per the phase's success criteria, not a contract freeze violation.

## Test Results

- **Session memory runtime tests:** 10 tests pass
  - `python3 -m unittest packages.platform-runtime.tests.test_session_memory_runtime -v` — OK
- **Memory orchestrator tests:** 17 tests pass (including updated contract test)
  - `python3 -m unittest packages.platform-runtime.tests.test_memory_orchestrator -v` — OK
- **Memory adapter contract tests:** 12 tests pass
  - `python3 -m unittest packages.platform-runtime.tests.test_memory_adapter_contract -v` — OK
- **Run runtime lifecycle tests:** 20 tests pass
  - `python3 -m unittest packages.platform-runtime.tests.test_run_runtime_lifecycle -v` — OK

## FROZEN Contract Surfaces Verified

- BackendAdapter: 9 methods (unchanged)
- AdapterCapabilitySet: 14 fields (unchanged — `session_memory_support` field already existed)
- ContextBundle: unchanged
- RunRequest: unchanged
- RuntimeFeatureFlags: `session_memory_enabled` field already existed (default False)
- `dependencies = []` invariant preserved — no new external imports

## Key Design Decisions

1. **`session_memory_enabled` takes precedence over `context_assembly_enabled`** in `_attach_context_bundle` — when True, the orchestrator handles both recall and assembly. When False, the existing `context_assembly_enabled` path runs unchanged.
2. **`_attach_context_bundle_with_memory` reuses `_context_assembly_input`** — the same input builder is used for both the bare assembler path and the orchestrator path, ensuring consistent scope/refs extraction.
3. **`MemoryOrchestrator.recall_and_assemble()` is sync** — called directly from async `create_run`/`resume_interrupt`. This is safe because `InMemoryMemoryStore.search()` is sync.
4. **Contract log integration** — when `contract_log_enabled=True` and `session_memory_enabled=True`, the context_bundle event from the orchestrator is appended to the contract log, matching the existing assembler path.
