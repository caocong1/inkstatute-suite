---
phase: 39
plan: 39-03
title: "V2 Gate Integration and Contract Freeze Verification"
wave: 3
requirements:
  - ADAPTER-01
status: complete
commits:
  - aad0c5b
---

# Plan 39-03 — Summary

## Tasks Completed

### Task 39-03-01 — codex-backend V2 gate + contract test suite + gate count assertion (commit aad0c5b)

Wired the `packages/backends/codex/` package into the V2 gate suite:

- **`scripts/run_v2_gates.py`** — three changes:
  1. Added `codex_backend_src` variable (`repo_root / "packages" / "backends" / "codex" / "src"`) after `router_service_src`.
  2. Added a new `codex-backend` gate after `router-service` and before `feedback-service`, running `python -m unittest discover -s packages/backends/codex/tests` with PYTHONPATH `(codex_backend_src, platform_src, platform_runtime_src, wecom_src)`.
  3. Added `codex_backend_src` to the `contract-test-suite` gate's PYTHONPATH tuple (appended at end).
  4. Added `"packages/backends/codex/src"` to the `compileall` gate's path list (after `"packages/router-service/src"`).

- **`packages/contract-test-suite/tests/test_codex_backend_contract.py`** — new cross-package contract test file with 7 tests in `CodexBackendContractTests`:
  - `test_real_codex_manifest_validates_clean` — `validate_agent_backend_manifest(build_codex_manifest()) == []`
  - `test_real_codex_manifest_selects_as_contract_compatible_not_live` — `select_agent_backend` returns `mode="codex"`, `contract_compatible=True`, `live_acceptance_allowed=False`
  - `test_real_codex_manifest_production_ready_is_false` — `manifest.metadata["production_ready"] is False`
  - `test_real_codex_manifest_no_channel_io_is_true` — `manifest.capabilities.no_channel_io is True`
  - `test_codex_capabilities_field_count_matches_freeze_baseline` — `len(fields(AdapterCapabilitySet)) == 14` and `len(fields(codex_prototype_capabilities())) == 14`
  - `test_codex_adapter_exposes_exactly_9_backend_adapter_methods` — `CodexBackendAdapter` has all 9 BackendAdapter Protocol methods callable
  - `test_codex_adapter_mode_matches_enum` — `build_codex_manifest().mode == AgentBackendMode.CODEX`

- **`packages/contract-test-suite/tests/test_audit_v2_requirements.py`** — updated gate count assertion from 11 to 12 and added `codex-backend` to the `assertIn` check in `TestAuditGateList.test_v2_gates_includes_traceability_gate`.

### Task 39-03-02 — SAFETY-02 contract freeze verification (no commit — verification only)

Verified that the existing SAFETY-02 contract-count freeze tests remain green with no contract drift introduced by Phase 39:

- **`test_contract_count_freeze.py`** — all 3 tests pass:
  - `test_backend_adapter_method_count_unchanged` → `BACKEND_ADAPTER_METHOD_COUNT == 9`
  - `test_adapter_capability_set_field_count_unchanged` → `ADAPTER_CAPABILITY_SET_FIELD_COUNT == 14`
  - `test_channel_adapter_method_count_unchanged` → `CHANNEL_ADAPTER_METHOD_COUNT == 6`

- **Contract drift check**: `git diff` confirms no files in `packages/platform-contract/src/` or `packages/platform-runtime/src/protocols.py` were modified by Phase 39. The `BackendAdapter` Protocol still has exactly 9 methods, `ChannelAdapter` still has 6 methods, and `AdapterCapabilitySet` still has 14 fields.

- **Full V2 gate suite**: `python scripts/run_v2_gates.py` exits with code 0 — all 12 gates pass.

## Test Results

| Gate | Tests | Passed | Failed |
|------|-------|--------|--------|
| platform-contract | 21 | 21 | 0 |
| wecom-service | 72 | 72 | 0 |
| hermes-contract-layer | 35 | 35 | 0 |
| conversation-read-view | 24 | 24 | 0 |
| skill-registry | 35 | 35 | 0 |
| router-service | 33 | 33 | 0 |
| codex-backend (NEW) | 32 | 32 | 0 |
| feedback-service | 31 | 31 | 0 |
| phase7-privacy-boundary | 13 | 13 | 0 |
| contract-test-suite | 307 | 307 | 0 |
| v2-acceptance-traceability | — | PASS | 0 |
| compileall | — | PASS | 0 |
| **Total** | **603+** | **603+** | **0** |

- V2 gate count: **12** (was 11 before Phase 39)
- `python scripts/run_v2_gates.py --list` outputs exactly 12 gate names including `codex-backend`
- SAFETY-02 freeze tests: 3/3 passed (9 methods, 14 fields, 6 channel methods — no drift)

## Files Modified/Created

| File | Action |
|------|--------|
| `scripts/run_v2_gates.py` | Modified — added `codex_backend_src` variable, `codex-backend` gate, `codex_backend_src` in contract-test-suite PYTHONPATH, `packages/backends/codex/src` in compileall paths |
| `packages/contract-test-suite/tests/test_codex_backend_contract.py` | Created — 7 cross-package contract tests |
| `packages/contract-test-suite/tests/test_audit_v2_requirements.py` | Modified — gate count assertion updated from 11 to 12, added `codex-backend` assertIn |

## Deviations from Plan

1. **`codex-backend` gate PYTHONPATH includes `wecom_src`**: The plan specified PYTHONPATH `(codex_backend_src, platform_src, platform_runtime_src)`, but `packages/backends/codex/tests/test_adapter.py` imports `wecom_service.agent_backend.select_agent_backend` (line 82). Without `wecom_src` in the PYTHONPATH, the codex-backend gate would fail with `ModuleNotFoundError: No module named 'wecom_service'`. The `wecom_src` path was added to the gate's PYTHONPATH to match the verification command used in the 39-01 summary. This is consistent with the key implementation details which state the PYTHONPATH "must include `services/wecom-service/src`".

2. **`test_audit_v2_requirements.py` modified (not in plan's `files_modified`)**: The plan's `files_modified` list only includes `scripts/run_v2_gates.py` and `packages/contract-test-suite/tests/test_codex_backend_contract.py`. However, `test_audit_v2_requirements.py` contains a gate count assertion (`assertEqual(len(gate_names), 11)`) that would fail after adding the 12th gate. This file was updated to assert `len(gate_names) == 12` and include `assertIn("codex-backend", gate_names)`. This change is necessary for the `contract-test-suite` gate to pass and is explicitly called for in the plan's key implementation details ("The gate count assertion must be updated from 11 to 12").

## Acceptance Criteria Verification

- [x] `python scripts/run_v2_gates.py --list` outputs exactly 12 gate names including `codex-backend`
- [x] `python scripts/run_v2_gates.py` exits with code 0 (all 12 gates pass)
- [x] The `codex-backend` gate runs `python -m unittest discover -s packages/backends/codex/tests` with PYTHONPATH including `codex_backend_src`, `platform_src`, `platform_runtime_src`, and `wecom_src`
- [x] The `contract-test-suite` gate PYTHONPATH includes `codex_backend_src` (so `import inkstatute_backends_codex` succeeds in contract tests)
- [x] The `compileall` gate includes `"packages/backends/codex/src"` in its path list
- [x] `packages/contract-test-suite/tests/test_codex_backend_contract.py` passes within the `contract-test-suite` gate
- [x] `validate_agent_backend_manifest(build_codex_manifest()) == []` (zero issues)
- [x] `select_agent_backend({"agent_backend": {"mode": "codex"}}, [build_codex_manifest()])` returns `live_acceptance_allowed=False`, `contract_compatible=True`
- [x] `build_codex_manifest().metadata["production_ready"]` is `False`
- [x] `build_codex_manifest().capabilities.no_channel_io` is `True`
- [x] `CodexBackendAdapter` has exactly 9 callable BackendAdapter methods
- [x] Gate count is 12 (was 11 before Phase 39)
- [x] SAFETY-02 contract-count freeze tests pass: 9 methods, 14 fields, 6 channel methods
- [x] No files in `packages/platform-contract/src/` were modified by Phase 39
- [x] No files in `packages/platform-runtime/src/protocols.py` were modified by Phase 39

## EXECUTION COMPLETE
