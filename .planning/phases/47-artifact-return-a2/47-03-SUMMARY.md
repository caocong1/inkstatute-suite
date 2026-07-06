# Plan 47-03 Summary: Output Boundary Artifact Metadata Allowlist + Contract Test Updates

## Objective

Add `filter_artifact_metadata()` to `output_boundary.py` that enforces an allowlist on artifact metadata fields, stripping backend noise (model names, API error traces, function call internals). Apply this filter in both Codex and provider_model adapters when building artifact records. Update contract tests to verify artifact return support and ref-based schema.

## Tasks Completed

### Task 1: Add filter_artifact_metadata() to output_boundary.py

**Files modified:**
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` — Added `_ALLOWED_ARTIFACT_METADATA_KEYS` frozenset (sha256, size_bytes, content_ref, kind, name, mime_type, source, source_refs, template_ref, features, created_at). Added `filter_artifact_metadata()` function that filters metadata to allowed keys only, with recursive dict/list sanitization and URL/token stripping. Added `_sanitize_artifact_value()` and `_sanitize_artifact_text()` helpers. Added `Any` to typing imports. Exported `filter_artifact_metadata` in `__all__`.
- `packages/platform-runtime/tests/test_output_boundary.py` — 11 new `FilterArtifactMetadataTests`: allows safe keys, strips model names, strips API error traces, strips function call internals, strips unknown keys, sanitizes URLs in allowed values, recursive dict filter, case-insensitive keys, empty metadata returns empty, preserves non-string non-dict values.

**Commit:** `f0201be` — `feat(47-03): output boundary artifact metadata allowlist + contract test updates`

### Task 2: Apply filter_artifact_metadata() in Codex and provider_model adapters

**Files modified:**
- `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` — Imported `filter_artifact_metadata` from `platform_runtime.output_boundary`. Updated `_artifact_records()` and `_artifact_entries()` to apply `filter_artifact_metadata()` on the metadata dict, passing through safe keys (sha256, size_bytes, content_ref, mime_type) from runner metadata.
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` — Same pattern as Codex, with `"source": "provider_model"`.
- `packages/backends/codex/tests/test_collect_artifacts.py` — Added `test_artifact_metadata_filters_model_names` test verifying backend noise (model, api_error, function_call) is stripped from artifact metadata.
- `packages/backends/provider_model/tests/test_collect_artifacts.py` — Added `test_artifact_metadata_filters_model_names` test.

**Commit:** `f0201be` — `feat(47-03): output boundary artifact metadata allowlist + contract test updates`

### Task 3: Update contract tests to verify artifact return support

**Files modified:**
- `packages/contract-test-suite/tests/test_codex_backend_contract.py` — Added `test_codex_manifest_artifact_return_support_is_true` test.
- `packages/contract-test-suite/tests/test_provider_model_backend_contract.py` — Added `test_provider_model_manifest_artifact_return_support_is_true` test.

**Commit:** `f0201be` — `feat(47-03): output boundary artifact metadata allowlist + contract test updates`

## Deviations

- **[Pre-existing test failure]** `test_runtime_source_does_not_embed_concrete_leak_examples` (forbidden='gateway') in `test_output_boundary.py` is a pre-existing failure unrelated to Phase 47. Verified by stashing changes and running the test — it fails identically without our changes. The failure is caused by the word "gateway" appearing in other platform-runtime source files (e.g., `fakes.py` references), not by our new code.

## Test Results

- **Platform-runtime output boundary tests:** 34 tests run, 11 new `FilterArtifactMetadataTests` pass, 1 pre-existing failure (gateway source check)
- **Codex package tests:** 50 tests pass (including metadata filtering test)
- **Provider_model package tests:** 61 tests pass (including metadata filtering test)
- **Codex backend contract tests:** 8 tests pass (including artifact_return_support test)
- **Provider_model backend contract tests:** 9 tests pass (including artifact_return_support test)
- **Contract freeze tests:** 5 tests pass (schema hash and count freeze unchanged)
- **V2 gate suite:** 17 gates pass (all OK/PASS)

## FROZEN Contract Surfaces Verified

- BackendAdapter: 9 methods (unchanged)
- AdapterCapabilitySet: 14 fields (unchanged)
- ArtifactRecord: fields unchanged
- AgentResult.artifacts: list[Artifact] field unchanged
- No frozen contract surfaces modified

## Key Design Decisions

1. **Allowlist-based filtering** — `filter_artifact_metadata()` uses a frozenset of allowed keys (case-insensitive), dropping any key not in the set. This is more robust than regex-based filtering of values.
2. **Recursive sanitization** — Dict values are recursively filtered (only allowed keys preserved), list values are recursively sanitized, string values have URLs and token-like patterns stripped.
3. **Applied at artifact construction** — Both adapters apply `filter_artifact_metadata()` when building `ArtifactRecord` and `Artifact` entries, ensuring backend noise never enters the artifact metadata.
4. **Safe keys passed through from runner metadata** — Only `sha256`, `size_bytes`, `content_ref`, `mime_type` are passed from runner metadata to the filter; all other runner metadata keys are dropped.
