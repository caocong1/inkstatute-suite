# Plan 47-01 Summary: Codex Adapter collect_artifacts + AgentResult.artifacts Population

## Objective

Productize `CodexBackendAdapter.collect_artifacts()` by replacing the stub that returns an empty list with real artifact collection from `CodexExecResult.artifact_refs`. In `submit_run`, build `ArtifactRecord` entries from `result.artifact_refs` (mirroring the Hermes `_artifact_records` pattern) and store them in `self._artifacts[run_id]`. Populate `AgentResult.artifacts` with ref-based `Artifact` entries. Update `collect_artifacts()` to call `_require_run()` before returning. Set `artifact_return_support=True` in the manifest.

## Tasks Completed

### Task 1: Add _artifact_records helper and populate _artifacts + AgentResult.artifacts in submit_run

**Files modified:**
- `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` — Added `Artifact` and `ArtifactKind` imports. Added `_artifact_records()` and `_artifact_entries()` helper functions that build ref-based `ArtifactRecord` and `Artifact` entries from `result.artifact_refs`. Updated `submit_run` to populate `self._artifacts[run_id]` from refs and populate `AgentResult.artifacts` via `replace()`. Updated `collect_artifacts()` to call `self._require_run(run_id)` before returning.
- `packages/backends/codex/tests/test_collect_artifacts.py` — 7 tests: collect_artifacts returns records from refs, raises KeyError for unknown run, populates AgentResult.artifacts, empty refs returns empty list, ref-based schema verification, metadata contains source, deterministic artifact IDs.

**Commit:** `538d5e1` — `feat(47-01): codex adapter collect_artifacts + AgentResult.artifacts population`

### Task 2: Update manifest artifact_return_support to True

**Files modified:**
- `packages/backends/codex/src/inkstatute_backends_codex/manifest.py` — Changed `artifact_return_support=False` to `artifact_return_support=True`.
- `packages/backends/codex/tests/test_adapter.py` — Updated `test_manifest_does_not_overclaim_unsupported_capabilities` to assert `artifact_return_support=True`.

**Commit:** `538d5e1` — `feat(47-01): codex adapter collect_artifacts + AgentResult.artifacts population`

## Deviations

- None.

## Test Results

- **Codex package tests:** 50 tests pass (42 existing + 7 new collect_artifacts + 1 updated manifest test)
  - `python3 -m unittest discover -s packages/backends/codex/tests -v` — OK
- **Contract freeze tests:** 5 tests pass
  - `test_contract_count_freeze` — OK (BackendAdapter 9 methods, AdapterCapabilitySet 14 fields unchanged)
- **Codex backend contract tests:** 8 tests pass
  - `test_codex_backend_contract` — OK

## FROZEN Contract Surfaces Verified

- BackendAdapter: 9 methods (unchanged)
- AdapterCapabilitySet: 14 fields (unchanged)
- ArtifactRecord: fields unchanged (uri_ref, metadata)
- AgentResult.artifacts: list[Artifact] field unchanged
- `dependencies = []` invariant preserved — no new external imports at module top level

## Key Design Decisions

1. **`_artifact_records()` mirrors Hermes pattern** — builds `ArtifactRecord` from refs with deterministic IDs (`{run_id}-artifact-{index:03d}`).
2. **`_artifact_entries()` builds `Artifact` for `AgentResult.artifacts`** — uses `ArtifactKind.OTHER` as default kind, `uri` field for content reference.
3. **`collect_artifacts()` calls `_require_run()`** — matching Hermes pattern, raises `KeyError` for unknown run IDs.
4. **`artifact_return_support=True`** — truthfully declares the capability now that artifacts are populated.
