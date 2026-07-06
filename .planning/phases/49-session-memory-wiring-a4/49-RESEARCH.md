# Phase 49: Session Memory Wiring (A4) - Research

**Researched:** 2026-07-06
**Domain:** Runtime dependency injection, memory orchestration, ContextBundle assembly, adapter capability declarations
**Confidence:** HIGH

## Summary

Phase 49 wires the existing `MemoryOrchestrator` into `DefaultRunRuntime` as an optional injected dependency, gated by the existing `session_memory_enabled` feature flag (default False). When enabled, the runtime delegates context assembly to `MemoryOrchestrator.recall_and_assemble()`, which queries a `MemoryStoreAdapter` scoped by `(tenant_id, workspace_id, user_id)` and injects recalled `memory_refs` into the `ContextBundle` before `backend.submit_run()`. Adapters declare `session_memory_support=True` in their manifests and consume the `ContextBundle` from `RunRequest.metadata["context_bundle"]` — no adapter ever calls `HindsightMemory` or any memory provider directly.

The codebase already contains all the building blocks: `MemoryOrchestrator` (Phase 22), `HindsightMemory` (Phase 26), `ContextAssembler` (Phase 16), `ContextBundle` contract event (Phase 16), `MemoryStoreAdapter` Protocol (Phase 25), `InMemoryMemoryStore` (Phase 17), and the `session_memory_enabled` flag (Phase 10, M3 flags). The runtime already accepts an optional `context_assembler` parameter and has a `_attach_context_bundle` method that assembles context when `context_assembly_enabled=True`. Phase 49 extends this pattern: when `session_memory_enabled=True`, the runtime uses the `MemoryOrchestrator` for recall + assembly instead of the bare `ContextAssembler`.

**Primary recommendation:** Add `memory_orchestrator` as an optional keyword-only parameter to `DefaultRunRuntime.__init__`. Modify `_attach_context_bundle` to check `session_memory_enabled` first — when True, require `memory_orchestrator` and call `recall_and_assemble()` to produce a `ContextAssemblyResult` with memory refs; when False, fall through to the existing `context_assembly_enabled` path. Update the three adapter manifests (codex, provider_model, hermes) to declare `session_memory_support=True`. Update the Phase 22 contract test that blocks `memory_orchestrator` on the constructor — this constraint is superseded by Phase 49's explicit requirement.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per `workflow.skip_discuss`. All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Claude's Discretion
All implementation choices are at Claude's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SESSMEM-01 | `DefaultRunRuntime` accepts optional `memory_orchestrator` and `context_assembler` injected dependencies; when `session_memory_enabled=True`, `MemoryOrchestrator.recall()` queries `HindsightMemory` scoped by `(tenant_id, workspace_id, user_id)` and injects recalled memory refs into `ContextBundle` before `backend.submit_run()` | §Architecture Patterns (runtime memory wiring), §Code Examples (recall_and_assemble flow) |
| SESSMEM-02 | Adapters declare `session_memory_support=True` in their manifest and consume the `ContextBundle` from `RunRequest.metadata`; no adapter calls `HindsightMemory` or any memory provider directly. When `session_memory_enabled=False` (default), no memory orchestration occurs and the runtime behaves identically to v1.6 | §Architecture Patterns (adapter capability declaration), §Common Pitfalls (frozen contract surfaces) |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.** Memory refs are `memory://<id>` URIs, not raw text. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Contract logs should prefer references.** ContextBundle uses `memory_refs` (URI strings), not embedded text. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Do not introduce a new service, database, queue, or runtime dependency.** `dependencies = []` invariant on adapter packages. `MemoryOrchestrator` and `HindsightMemory` already exist. [VERIFIED: AGENTS.md §Coding Rules]
- **Keep changes scoped to the active GSD phase and its plan.** [VERIFIED: AGENTS.md §Coding Rules]
- **Add tests before or with behavior changes.** [VERIFIED: AGENTS.md §Coding Rules]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Memory recall orchestration | Platform runtime (runtime.py) | — | Runtime owns the wiring of MemoryOrchestrator into create_run/resume_interrupt |
| ContextBundle assembly with memory refs | MemoryOrchestrator | ContextAssembler | Orchestrator delegates to ContextAssembler after recalling memory refs |
| Memory store scoping (tenant/workspace/user) | MemoryStoreAdapter (InMemoryMemoryStore) | — | Store enforces isolation; orchestrator passes scope from SessionScope |
| Feature flag gating | Platform runtime (feature_flags) | — | `session_memory_enabled` gates the memory orchestration lane |
| Adapter capability declaration | Backend adapters (codex, provider_model, hermes) | — | Each adapter manifest declares `session_memory_support=True` |
| ContextBundle consumption | Backend adapters | — | Adapters read `RunRequest.metadata["context_bundle"]` — never call memory providers |

## Standard Stack

### Core

No new external packages are installed. This phase uses only existing project packages and Python stdlib.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `platform-contract` | existing | `ContextBundle`, `MemoryRecord`, `AdapterCapabilitySet` | Frozen contract — no modifications to Protocol or capability field count [VERIFIED: test_contract_freeze.py] |
| `platform-runtime` | existing | `DefaultRunRuntime`, `MemoryOrchestrator`, `ContextAssembler`, `InMemoryMemoryStore` | All exist and are tested [VERIFIED: codebase] |
| Python stdlib `inspect` | 3.14+ | Signature inspection for contract tests | Already used in existing tests [VERIFIED: test_memory_orchestrator.py] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `memory_orchestrator` parameter on `DefaultRunRuntime` | Host-side wrapper that calls orchestrator before `create_run` | Rejected — Phase 49 success criteria explicitly requires `DefaultRunRuntime` to accept `memory_orchestrator` as an injected dependency. Host-side wrapping would not satisfy the success criteria. |
| New `recall()` method on `MemoryOrchestrator` | Existing `recall_and_assemble()` | Use existing `recall_and_assemble()` — it already queries the store, assembles context, and records MemoryUse evidence. Adding a separate `recall()` would duplicate logic. |
| Making `session_memory_enabled` imply `context_assembly_enabled` | Separate gates | Use separate gates: `session_memory_enabled` takes precedence in `_attach_context_bundle`. When True, orchestrator does recall+assembly. When False, falls through to `context_assembly_enabled` path. This keeps the feature purely additive. |

## Package Legitimacy Audit

> No external packages are installed in this phase. All work uses existing project packages and Python stdlib. The `dependencies = []` invariant on all three adapter packages must be preserved. [VERIFIED: `packages/backends/codex/pyproject.toml`, `packages/backends/provider_model/pyproject.toml`, `packages/backends/hermes/pyproject.toml`]

## Architecture Patterns

### System Architecture Diagram

```
Operator (host)
    │
    ├── injects MemoryOrchestrator(memory_store=InMemoryMemoryStore())
    │
    ▼
DefaultRunRuntime.__init__(backend=..., memory_orchestrator=..., feature_flags=...)
    │
    ├── create_run(req)
    │       │
    │       ├── feature_flags.require_enabled("run_runtime_enabled")
    │       ├── feature_flags.require_enabled("session_memory_enabled")  [if enabled]
    │       │
    │       ▼
    │   _attach_context_bundle(req)
    │       │
    │       ├── if session_memory_enabled:
    │       │   ├── require memory_orchestrator is not None
    │       │   ├── build scope from req (tenant_id, workspace_id, user_id)
    │       │   ├── memory_orchestrator.recall_and_assemble(scope=..., ...)
    │       │   │   ├── MemoryStoreAdapter.search(MemoryQuery(tenant_id, workspace_id, user_id))
    │       │   │   ├── select top-N memory refs
    │       │   │   ├── ContextAssembler.assemble(ContextAssemblyInput(memory_refs=...))
    │       │   │   └── record MemoryUse evidence
    │       │   └── inject context_bundle into req.metadata["context_bundle"]
    │       │
    │       ├── elif context_assembly_enabled:
    │       │   └── (existing path: ContextAssembler.assemble without memory recall)
    │       │
    │       └── else: return req unchanged
    │
    ▼
backend.submit_run(req_with_context_bundle)
    │
    ├── adapter reads req.metadata["context_bundle"] (if present)
    ├── adapter NEVER calls HindsightMemory or any memory provider
    └── adapter uses context_bundle.memory_refs for grounding
```

### Key Design Decisions

1. **`memory_orchestrator` is a keyword-only optional parameter** — defaults to `None`. When `session_memory_enabled=True` and `memory_orchestrator is None`, the runtime raises `RunRuntimeStateError("session_memory_enabled requires memory_orchestrator")`. This mirrors the existing `context_assembly_enabled` / `context_assembler` pattern.

2. **`session_memory_enabled` takes precedence over `context_assembly_enabled`** in `_attach_context_bundle`. When `session_memory_enabled=True`, the orchestrator handles both recall and assembly. When False, the existing `context_assembly_enabled` path runs unchanged.

3. **The orchestrator's `recall_and_assemble` is sync** — the runtime calls it directly from the async `create_run` / `resume_interrupt` methods. This is safe because `InMemoryMemoryStore.search()` is sync. `HindsightMemory` is async and implements a different Protocol (`Memory`, not `MemoryStoreAdapter`); bridging them is out of scope for this phase.

4. **Adapter `session_memory_support=True` is a capability declaration** — it signals that the adapter can consume `ContextBundle.memory_refs`. The adapter reads `req.metadata["context_bundle"]` if present; no direct memory provider calls.

5. **Phase 22 contract test `test_run_runtime_constructor_has_no_memory_orchestrator_parameter` is superseded** — Phase 49 explicitly requires this parameter. The test is updated to allow `memory_orchestrator` while still blocking `memory_store` and `recall_orchestrator` (which are not added).

### Frozen Contract Surfaces (NOT MODIFIED)

| Surface | Current State | Phase 49 Action |
|---------|---------------|-----------------|
| `BackendAdapter` Protocol | 9 methods | No change |
| `AdapterCapabilitySet` | 14 fields (including `session_memory_support: bool = False`) | No change — field already exists |
| `RunRequest` dataclass | frozen, slots=True | No change |
| `ContextBundle` dataclass | frozen, slots=True | No change |
| `RunEvent` dataclass | frozen, slots=True | No change |
| `RuntimeFeatureFlags` | `session_memory_enabled: bool = False` already exists | No change |

### Existing Contract Tests to Update

| Test | File | Current Assertion | Phase 49 Action |
|------|------|-------------------|-----------------|
| `test_run_runtime_constructor_has_no_memory_orchestrator_parameter` | `test_memory_orchestrator.py:358` | `assertNotIn("memory_orchestrator", ...)` | Update: remove `memory_orchestrator` from blocked params; keep `memory_store` and `recall_orchestrator` blocked |
| `test_default_run_runtime_constructor_has_no_memory_adapter_parameter` | `test_memory_adapter_contract.py:373` | `assertNotIn("memory_adapter", ...)`, `assertNotIn("memory_store", ...)` | No change needed — `memory_orchestrator` is not `memory_adapter` or `memory_store` |
| `test_sqlite_does_not_change_run_runtime_or_wecom_constructors` | `test_memory_adapter_contract.py:468` | `assertNotIn("memory_adapter", ...)`, `assertNotIn("memory_store", ...)`, `assertNotIn("sqlite_memory", ...)` | No change needed |

## Code Examples

### Current `_attach_context_bundle` (runtime.py:147-168)

```python
def _attach_context_bundle(
    self,
    req: RunRequest,
    *,
    pending_interrupt: InterruptRecord | None = None,
) -> RunRequest:
    if not self.feature_flags.context_assembly_enabled:
        return req
    if self.context_assembler is None:
        raise RunRuntimeStateError("context_assembly_enabled requires context_assembler")

    assembly_input = self._context_assembly_input(req, pending_interrupt=pending_interrupt)
    result = self.context_assembler.assemble(assembly_input)
    context_event = result.as_event()
    metadata = {
        **dict(req.metadata),
        "context_bundle_id": context_event["context_bundle_id"],
        "context_bundle": context_event,
    }
    if self.feature_flags.contract_log_enabled:
        self._contract_log().append("context_bundle", context_event)
    return replace(req, metadata=metadata)
```

### Proposed `_attach_context_bundle` with session memory

```python
def _attach_context_bundle(
    self,
    req: RunRequest,
    *,
    pending_interrupt: InterruptRecord | None = None,
) -> RunRequest:
    if self.feature_flags.session_memory_enabled:
        return self._attach_context_bundle_with_memory(req, pending_interrupt=pending_interrupt)
    if not self.feature_flags.context_assembly_enabled:
        return req
    if self.context_assembler is None:
        raise RunRuntimeStateError("context_assembly_enabled requires context_assembler")
    # ... existing assembly path unchanged
```

### `MemoryOrchestrator.recall_and_assemble` signature (memory_orchestrator.py:103-117)

```python
def recall_and_assemble(
    self,
    *,
    scope: SessionScope,
    session_id: str,
    turn_id: str,
    current_turn_ref: str,
    current_turn_text: str | None = None,
    recent_turn_refs: tuple[str, ...] = (),
    artifact_refs: tuple[str, ...] = (),
    feedback_correction_refs: tuple[str, ...] = (),
    output_policy_ref: str | None = None,
    run_id: str | None = None,
    now: str | None = None,
) -> ContextAssemblyResult:
```

### Adapter manifest `session_memory_support` field (already exists)

```python
# codex manifest.py:59
session_memory_support=False,  # → change to True

# provider_model manifest.py:63
session_memory_support=False,  # → change to True

# hermes manifest.py:57
session_memory_support=False,  # → change to True
```

## Common Pitfalls

1. **Do NOT modify frozen contract surfaces** — `BackendAdapter` Protocol (9 methods), `AdapterCapabilitySet` (14 fields), `RunRequest`, `ContextBundle`, `RunEvent` are all frozen by `test_contract_freeze.py` and `test_contract_count_freeze.py`. The `session_memory_support` field already exists on `AdapterCapabilitySet` — just change its value in manifest builders.

2. **Phase 22 contract test blocks `memory_orchestrator`** — `test_run_runtime_constructor_has_no_memory_orchestrator_parameter` explicitly asserts `memory_orchestrator` is NOT in the constructor signature. This test must be updated as part of Phase 49, since the phase's success criteria explicitly requires this parameter. This is a legitimate constraint supersession, not a contract freeze violation.

3. **`session_memory_enabled` defaults to False** — when False, the runtime must behave identically to v1.6. No memory orchestration occurs. The `_attach_context_bundle` method must check `session_memory_enabled` first and fall through to the existing path when False.

4. **`dependencies = []` on adapter packages** — no new imports of `hindsight_client`, `platform_runtime.memory_orchestrator`, or any memory provider in adapter code. Adapters only read `RunRequest.metadata["context_bundle"]`.

5. **`MemoryOrchestrator.recall_and_assemble` is sync** — do not make it async. The runtime calls it from async `create_run` but the call itself is synchronous (delegates to sync `MemoryStoreAdapter.search()`).

6. **`HindsightMemory` implements `Memory` (async), not `MemoryStoreAdapter` (sync)** — Phase 49 wires `MemoryOrchestrator` (which uses `MemoryStoreAdapter`), not `HindsightMemory` directly. Bridging `HindsightMemory` to `MemoryStoreAdapter` is a future phase. The runtime never imports or calls `HindsightMemory`.

## Test Strategy

### Plan 01 Tests (Runtime memory wiring)

- `test_session_memory_disabled_by_default` — `RuntimeFeatureFlags()` has `session_memory_enabled=False`
- `test_session_memory_enabled_requires_memory_orchestrator` — when `session_memory_enabled=True` and no `memory_orchestrator`, `create_run` raises `RunRuntimeStateError`
- `test_session_memory_enabled_injects_memory_refs_into_context_bundle` — with `memory_orchestrator` injected and memories in the store, `create_run` produces a `ContextBundle` with `memory_refs` in `req.metadata["context_bundle"]`
- `test_session_memory_disabled_behaves_identically_to_v1_6` — when `session_memory_enabled=False`, no `context_bundle` key in metadata (unless `context_assembly_enabled=True`)
- `test_session_memory_enabled_does_not_call_backend_before_recall` — memory recall happens before `backend.submit_run()`

### Plan 02 Tests (Adapter session_memory_support)

- `test_codex_manifest_declares_session_memory_support` — `codex_prototype_capabilities().session_memory_support` is True
- `test_provider_model_manifest_declares_session_memory_support` — `provider_model_prototype_capabilities().session_memory_support` is True
- `test_hermes_manifest_declares_session_memory_support` — `hermes_oneshot_capabilities().session_memory_support` is True
- `test_adapter_consumes_context_bundle_from_metadata` — adapter `submit_run` reads `req.metadata["context_bundle"]` when present

### Plan 03 Tests (Integration)

- `test_full_session_memory_flow` — runtime with `session_memory_enabled=True`, `memory_orchestrator` with `InMemoryMemoryStore` containing memories, `FakeBackendAdapter` receives `ContextBundle` with `memory_refs` in `req.metadata`
- `test_session_memory_off_no_context_bundle_injected` — runtime with `session_memory_enabled=False`, `FakeBackendAdapter` receives no `context_bundle` in `req.metadata`
- `test_no_adapter_imports_memory_provider` — grep adapter source files for `hindsight` / `HindsightMemory` imports; assert none found
