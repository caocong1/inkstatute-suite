---
phase: 47-artifact-return-a2
verified: 2026-07-06T06:21:54Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 47: Artifact Return (A2) Verification Report

**Phase Goal:** Operator can call `collect_artifacts(run_id)` on Codex and provider_model adapters and receive `ArtifactRecord` entries with ref-based schema (`content_ref`, `sha256`, `size_bytes` — never inline binaries), and `AgentResult.artifacts` is populated with terminal artifacts, with output boundary enforcement on artifact metadata.
**Verified:** 2026-07-06T06:21:54Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Roadmap Success Criteria are the non-negotiable contract; PLAN frontmatter must-haves add plan-specific detail. Both are merged below.

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Adapters return artifacts via frozen `collect_artifacts()` with ref-based schema (`content_ref`, `sha256`, `size_bytes`); no inline binary content appears in any artifact record or contract event (ARTIFACT-01) | ✓ VERIFIED | `codex/adapter.py:246-248` calls `_require_run()` then returns `list(self._artifacts[run_id])`. `provider_model/adapter.py:245-247` same pattern. `_artifact_records()` (codex:306-325, provider_model:307-326) builds `ArtifactRecord` with `uri_ref=ref` (never inline content). 7 codex + 7 provider_model collect_artifacts tests pass. `test_artifact_records_use_ref_based_schema` asserts no `content`/`data`/`binary`/`base64` keys in metadata. |
| 2 | `AgentResult.artifacts` is populated with terminal artifacts (ARTIFACT-01) | ✓ VERIFIED | `codex/adapter.py:132-142` populates `agent_result.artifacts` via `replace()` with `_artifact_entries()` when `result.artifact_refs` is non-empty. `provider_model/adapter.py:131-141` same pattern. `test_submit_run_populates_agent_result_artifacts` passes for both adapters — asserts `len(run.result.artifacts) == 2` with correct `uri` values. |
| 3 | Artifact metadata enforces the output boundary — backend noise (model names, API error traces, function call internals) is filtered from artifact metadata fields via an allowlist (ARTIFACT-02) | ✓ VERIFIED | `output_boundary.py:155-211` defines `filter_artifact_metadata()` with `_ALLOWED_ARTIFACT_METADATA_KEYS` frozenset (sha256, size_bytes, content_ref, kind, name, mime_type, source, source_refs, template_ref, features, created_at). Both adapters import and apply it in `_artifact_records()` and `_artifact_entries()`. 11 `FilterArtifactMetadataTests` pass. `test_artifact_metadata_filters_model_names` passes for both adapters — asserts `model`, `api_error`, `function_call` keys are stripped. |
| 4 | Codex adapter populates `AgentResult.artifacts` and `_artifacts[run_id]` store from existing `CodexExecResult.artifact_refs` | ✓ VERIFIED | `codex/adapter.py:143` sets `self._artifacts[run_id] = _artifact_records(run_id, result.artifact_refs, result.metadata)`. `codex/adapter.py:136-139` populates `AgentResult.artifacts` from `result.artifact_refs`. `CodexExecResult.artifact_refs` field exists at `adapter.py:46`. Tests use `FakeCodexExecRunnerWithArtifacts` that returns `artifact_refs` with 2 refs. |
| 5 | Provider_model adapter populates artifacts from provider response file outputs | ✓ VERIFIED | `provider_model/adapter.py:142` sets `self._artifacts[run_id] = _artifact_records(run_id, result.artifact_refs, result.metadata)`. `openai_runner.py:163` calls `_extract_file_refs(response)` to extract file refs from the `files` field in the provider response. `openai_runner.py:213-241` `_extract_file_refs()` function handles `uri`/`url`/`id` keys. 4 `ParseOpenAIResponseArtifactTests` pass. |
| 6 | `collect_artifacts()` calls `_require_run()` — raises `KeyError` for unknown run IDs | ✓ VERIFIED | `codex/adapter.py:246` calls `self._require_run(run_id)` before returning. `provider_model/adapter.py:245` same. `test_collect_artifacts_raises_key_error_for_unknown_run` passes for both adapters. |
| 7 | `artifact_return_support=True` in both manifests | ✓ VERIFIED | `codex/manifest.py:50` sets `artifact_return_support=True`. `provider_model/manifest.py:54` sets `artifact_return_support=True`. `test_codex_manifest_artifact_return_support_is_true` and `test_provider_model_manifest_artifact_return_support_is_true` pass. Updated `test_manifest_does_not_overclaim_unsupported_capabilities` asserts `assertTrue(capabilities.artifact_return_support)` for both. |
| 8 | No frozen contract surfaces modified (BackendAdapter 9 methods, AdapterCapabilitySet 14 fields, ArtifactRecord fields, RunEventType enum) | ✓ VERIFIED | `test_contract_freeze` (2 tests) and `test_contract_count_freeze` (5 tests) pass — schema baseline hash and method/field counts unchanged. `test_codex_adapter_exposes_exactly_9_backend_adapter_methods` and `test_provider_model_adapter_exposes_exactly_9_backend_adapter_methods` pass. |
| 9 | `dependencies = []` invariant preserved — no new external imports at module top level; V2 gate suite remains green | ✓ VERIFIED | Codex `adapter.py` top-level imports are stdlib + `platform_contract` + `platform_runtime` + relative only. `filter_artifact_metadata` imported from `platform_runtime.output_boundary` (existing package, not external). Provider_model same. `scripts/run_v2_gates.py` exits 0; 17 `OK`/`PASS` gate results. |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` | `collect_artifacts()` with `_require_run()` + `_artifact_records`/`_artifact_entries` helpers + `AgentResult.artifacts` population | ✓ VERIFIED | lines 18-19 (import), 132-143 (submit_run artifact population), 246-248 (collect_artifacts), 306-349 (helpers) |
| `packages/backends/codex/src/inkstatute_backends_codex/manifest.py` | `artifact_return_support=True` | ✓ VERIFIED | line 50 |
| `packages/backends/codex/tests/test_collect_artifacts.py` | 8 tests for collect_artifacts + metadata filtering | ✓ VERIFIED | 8 tests pass |
| `packages/backends/codex/tests/test_adapter.py` | Updated manifest test for `artifact_return_support=True` | ✓ VERIFIED | line 104 asserts `assertTrue` |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` | `collect_artifacts()` with `_require_run()` + helpers + `AgentResult.artifacts` population | ✓ VERIFIED | lines 18-19 (import), 131-142 (submit_run), 245-247 (collect_artifacts), 307-350 (helpers) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py` | `artifact_return_support=True` | ✓ VERIFIED | line 54 |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` | `_extract_file_refs()` + `artifact_refs` in `ProviderModelExecResult` | ✓ VERIFIED | lines 163 (call), 213-241 (function) |
| `packages/backends/provider_model/tests/test_collect_artifacts.py` | 12 tests for collect_artifacts + file extraction + metadata filtering | ✓ VERIFIED | 12 tests pass |
| `packages/backends/provider_model/tests/test_adapter.py` | Updated manifest test for `artifact_return_support=True` | ✓ VERIFIED | line 104 asserts `assertTrue` |
| `packages/platform-runtime/src/platform_runtime/output_boundary.py` | `filter_artifact_metadata()` + `_ALLOWED_ARTIFACT_METADATA_KEYS` allowlist | ✓ VERIFIED | lines 155-211 |
| `packages/platform-runtime/tests/test_output_boundary.py` | 11 `FilterArtifactMetadataTests` | ✓ VERIFIED | 11 tests pass |
| `packages/contract-test-suite/tests/test_codex_backend_contract.py` | `test_codex_manifest_artifact_return_support_is_true` | ✓ VERIFIED | 8 tests pass |
| `packages/contract-test-suite/tests/test_provider_model_backend_contract.py` | `test_provider_model_manifest_artifact_return_support_is_true` | ✓ VERIFIED | 9 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `CodexExecResult.artifact_refs` | `ArtifactRecord` list | `_artifact_records()` in `submit_run` | ✓ VERIFIED | `adapter.py:143` stores records, `collect_artifacts()` returns them |
| `CodexExecResult.artifact_refs` | `AgentResult.artifacts` | `_artifact_entries()` in `submit_run` | ✓ VERIFIED | `adapter.py:136-139` populates via `replace()` |
| `ProviderModelExecResult.artifact_refs` | `ArtifactRecord` list | `_artifact_records()` in `submit_run` | ✓ VERIFIED | `adapter.py:142` stores records |
| OpenAI response `files` field | `ProviderModelExecResult.artifact_refs` | `_extract_file_refs()` in `parse_openai_response` | ✓ VERIFIED | `openai_runner.py:163` calls extractor |
| Runner metadata | Filtered artifact metadata | `filter_artifact_metadata()` in `_artifact_records`/`_artifact_entries` | ✓ VERIFIED | Both adapters import and apply the filter |

### Test Results

| Test Suite | Tests | Pass | Fail | Notes |
| ---------- | ----- | ---- | ---- | ----- |
| Codex package tests | 50 | 50 | 0 | All pass including 8 new collect_artifacts tests |
| Provider_model package tests | 61 | 61 | 0 | All pass including 12 new collect_artifacts tests |
| Platform-runtime output boundary | 34 | 33 | 1 | 1 pre-existing failure (`gateway` source check) |
| Codex backend contract | 8 | 8 | 0 | All pass including new artifact_return_support test |
| Provider_model backend contract | 9 | 9 | 0 | All pass including new artifact_return_support test |
| Contract freeze | 5 | 5 | 0 | Schema hash and count freeze unchanged |
| V2 gate suite | 17 | 17 | 0 | All OK/PASS |

### Anti-Patterns

| Anti-Pattern | Status | Details |
| ------------ | ------ | ------- |
| Inline binary content in artifact records | ✓ NOT PRESENT | All artifact records use `uri_ref` for content references; metadata contains only `source` and filtered safe keys |
| Backend noise in artifact metadata | ✓ NOT PRESENT | `filter_artifact_metadata()` strips model names, API error traces, function call internals via allowlist |
| Frozen contract surface modified | ✓ NOT PRESENT | Contract freeze tests pass; BackendAdapter 9 methods, AdapterCapabilitySet 14 fields unchanged |
| External SDK imports at module top level | ✓ NOT PRESENT | `dependencies = []` invariant preserved; `filter_artifact_metadata` imported from existing `platform_runtime` package |
| `collect_artifacts()` returns empty list | ✓ NOT PRESENT | Both adapters populate `_artifacts[run_id]` from `result.artifact_refs` in `submit_run` |
| `artifact_return_support=False` in manifest | ✓ NOT PRESENT | Both manifests declare `artifact_return_support=True` |
