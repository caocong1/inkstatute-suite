# Plan 47-02 Summary: Provider_model Adapter collect_artifacts + AgentResult.artifacts Population

## Objective

Productize `ProviderModelBackendAdapter.collect_artifacts()` by replacing the stub that returns an empty list with real artifact collection from `ProviderModelExecResult.artifact_refs`. In `submit_run`, build `ArtifactRecord` entries from `result.artifact_refs` (mirroring the Hermes `_artifact_records` pattern) and store them in `self._artifacts[run_id]`. Populate `AgentResult.artifacts` with ref-based `Artifact` entries. Update `collect_artifacts()` to call `_require_run()` before returning. Set `artifact_return_support=True` in the manifest. Update `parse_openai_response` to extract file output refs from provider responses into `artifact_refs`.

## Tasks Completed

### Task 1: Add _artifact_records helper and populate _artifacts + AgentResult.artifacts in submit_run

**Files modified:**
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` — Added `Artifact` and `ArtifactKind` imports. Added `_artifact_records()` and `_artifact_entries()` helper functions. Updated `submit_run` to populate `self._artifacts[run_id]` from refs and populate `AgentResult.artifacts` via `replace()`. Updated `collect_artifacts()` to call `self._require_run(run_id)`.
- `packages/backends/provider_model/tests/test_collect_artifacts.py` — 7 tests: collect_artifacts returns records from refs, raises KeyError for unknown run, populates AgentResult.artifacts, empty refs returns empty list, ref-based schema verification, metadata contains source, deterministic artifact IDs.

**Commit:** `daaf70f` — `feat(47-02): provider_model adapter collect_artifacts + AgentResult.artifacts population`

### Task 2: Update manifest artifact_return_support to True

**Files modified:**
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py` — Changed `artifact_return_support=False` to `artifact_return_support=True`.
- `packages/backends/provider_model/tests/test_adapter.py` — Updated `test_manifest_does_not_overclaim_unsupported_capabilities` to assert `artifact_return_support=True`.

**Commit:** `daaf70f` — `feat(47-02): provider_model adapter collect_artifacts + AgentResult.artifacts population`

### Task 3: Extract file output refs from OpenAI response into artifact_refs

**Files modified:**
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` — Added `_extract_file_refs()` function that extracts file output refs from a `files` field in the provider response. Updated `parse_openai_response` to populate `artifact_refs` on the returned `ProviderModelExecResult`.
- `packages/backends/provider_model/tests/test_collect_artifacts.py` — 4 tests: extracts file refs from response, no files returns empty refs, file ID only produces provider ref, skips non-dict file entries.

**Commit:** `daaf70f` — `feat(47-02): provider_model adapter collect_artifacts + AgentResult.artifacts population`

## Deviations

- None.

## Test Results

- **Provider_model package tests:** 61 tests pass (49 existing + 11 new collect_artifacts + 1 updated manifest test)
  - `python3 -m unittest discover -s packages/backends/provider_model/tests -v` — OK
- **Contract freeze tests:** 5 tests pass
  - `test_contract_count_freeze` — OK
- **Provider_model backend contract tests:** 9 tests pass
  - `test_provider_model_backend_contract` — OK

## FROZEN Contract Surfaces Verified

- BackendAdapter: 9 methods (unchanged)
- AdapterCapabilitySet: 14 fields (unchanged)
- ArtifactRecord: fields unchanged
- AgentResult.artifacts: list[Artifact] field unchanged
- `dependencies = []` invariant preserved — no new external imports at module top level

## Key Design Decisions

1. **`_extract_file_refs()` parses provider response `files` field** — extracts `uri`/`url`/`id` from each file entry, produces `provider://files/{id}` ref when only `id` is present.
2. **`_artifact_records()` and `_artifact_entries()` mirror Codex pattern** — consistent with Plan 01, using `"source": "provider_model"` metadata.
3. **`artifact_return_support=True`** — truthfully declares the capability now that artifacts are populated from provider response file outputs.
