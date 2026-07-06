# Plan 49-02 Summary: Adapter session_memory_support Declarations

## Objective

Update the three backend adapter manifests (codex, provider_model, hermes) to declare `session_memory_support=True` in their `AdapterCapabilitySet`. This signals that each adapter can consume `ContextBundle.memory_refs` from `RunRequest.metadata["context_bundle"]`. No adapter imports or calls `HindsightMemory` or any memory provider directly.

## Tasks Completed

### Task 1: Set session_memory_support=True in all three adapter manifests and add capability tests

**Files modified:**
- `packages/backends/codex/src/inkstatute_backends_codex/manifest.py` — Changed `session_memory_support=False` to `session_memory_support=True` in `codex_prototype_capabilities()`.
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py` — Changed `session_memory_support=False` to `session_memory_support=True` in `provider_model_prototype_capabilities()`.
- `packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py` — Changed `session_memory_support=False` to `session_memory_support=True` in `hermes_oneshot_capabilities()`.
- `packages/backends/codex/tests/test_adapter.py` — Added `test_codex_manifest_declares_session_memory_support` asserting `session_memory_support` is True.
- `packages/backends/provider_model/tests/test_adapter.py` — Added `test_provider_model_manifest_declares_session_memory_support` asserting `session_memory_support` is True.
- `packages/backends/hermes/tests/test_hermes_backend_adapter.py` — Added `test_hermes_manifest_declares_session_memory_support` asserting `session_memory_support` is True.

**Commit:** `846808e` — `feat(49-02): adapter session_memory_support=True declarations`

## Deviations

None.

## Test Results

- **Codex adapter tests:** 15 tests pass (including new session_memory_support test)
- **Provider_model adapter tests:** 12 tests pass (including new session_memory_support test)
- **Hermes adapter tests:** 10 tests pass (including new session_memory_support test)
- **No adapter imports memory provider:** `grep -ri 'hindsight\|HindsightMemory' packages/backends/*/src/` returns no matches

## FROZEN Contract Surfaces Verified

- `AdapterCapabilitySet`: 14 fields (unchanged — `session_memory_support` field already existed at position 14, just changed value from False to True)
- `BackendAdapter` Protocol: 9 methods (unchanged)
- `dependencies = []` invariant preserved — no new imports in adapter packages

## Key Design Decisions

1. **`session_memory_support=True` is a capability declaration** — it signals that the adapter can consume `ContextBundle.memory_refs`. The adapter reads `req.metadata["context_bundle"]` if present; no direct memory provider calls.
2. **All three adapters updated** — codex, provider_model, and hermes all declare `session_memory_support=True`, providing uniform capability across the backend adapter ecosystem.
3. **No adapter code changes needed** — adapters already receive `RunRequest` in `submit_run` and can read `req.metadata["context_bundle"]`. The manifest change is the only required modification.
