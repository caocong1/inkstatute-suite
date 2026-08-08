---
phase: 104
plan: 01
title: Retire Legacy Backends (hermes + codex)
status: complete
created: 2026-08-08
---

# Plan 104-01 Summary: Retire Legacy Backends

## Objective

Retire `packages/backends/hermes/` and `packages/backends/codex/` — their
functionality is fully replaced by `packages/acp-client/`. Remove the
`codex-backend` gate. Update all external references.

## What Was Done

### Deleted

- `packages/backends/hermes/` — entire directory (src + tests + fixtures + pyproject.toml)
- `packages/backends/codex/` — entire directory (src + tests + pyproject.toml)
- `packages/contract-test-suite/tests/test_codex_backend_contract.py` — contract tests for the retired codex backend
- `packages/contract-test-suite/tests/test_phase11_hermes_parity.py` — parity tests for the retired hermes backend

### Modified

#### `scripts/run_v2_gates.py`
- Removed `hermes_backend_src` and `codex_backend_src` path variables
- Removed the `codex-backend` gate definition
- Removed `hermes_backend_src` and `codex_backend_src` from the `contract-test-suite` gate PYTHONPATH
- Removed `packages/backends/codex/src` and `packages/backends/hermes/src` from the `compileall` gate path list
- Added `acp_client_src` to the `agent-core` gate PYTHONPATH (needed by the new Phase 104 test)

#### `packages/contract-test-suite/tests/test_audit_v2_requirements.py`
- Removed `self.assertIn("codex-backend", gate_names)` assertion (gate retired)
- Updated gate count assertion from 38 to 37

### Created

#### `packages/agent-core/tests/test_phase104_backend_retirement.py`
Seven tests verifying:
- `test_acp_adapter_has_hermes_compatibility_matrix` — HERMES_COMPATIBILITY_MATRIX exists with versions 0.17.0, 0.18.0, 0.19.0
- `test_acp_adapter_has_bootstrap_check` — ACPBackendAdapter.bootstrap_check() method exists
- `test_acp_adapter_has_capability_negotiation` — capability_negotiation module is importable
- `test_no_backends_hermes_directory_exists` — packages/backends/hermes/ is deleted
- `test_no_backends_codex_directory_exists` — packages/backends/codex/ is deleted
- `test_codex_backend_gate_removed` — codex-backend gate is not in run_v2_gates.py
- `test_no_imports_from_legacy_backends` — no Python files import from inkstatute_backends_hermes or inkstatute_backends_codex

## ACP Adapter Parity Verification

The `ACPBackendAdapter` in `packages/acp-client/src/inkstatute_acp_client/adapter.py` is a
functional superset of the legacy backend adapters:
- `HERMES_COMPATIBILITY_MATRIX` (line 50): maps Hermes 0.17.0, 0.18.0, 0.19.0 to supported ACP capabilities
- `bootstrap_check()` (line 186): async method returning BootstrapStatus with version + capability checking
- `capability_negotiation.py`: module for capability matching with RequiredCapabilities, CapabilityNegotiationResult, CapabilityMismatchError

## External References — Not Touched (Handled in 104-02)

The following files reference `hermes_contract_layer` (the **service**, not the
backend package) and are explicitly deferred to Plan 104-02:
- `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py`
- `packages/contract-test-suite/tests/test_phase55_wecom_service_loop.py`
- `packages/contract-test-suite/tests/test_phase5_wecom_loop.py`
- `scripts/audit_v2_requirements.py`

String references to `inkstatute_backends_hermes` in boundary-check forbidden
lists (e.g., `test_phase12_channel_client_surface.py`,
`test_web_chat_render.py`, `test_web_sse_channel.py`,
`test_wecom_channel_adapter.py`) are **not imports** — they verify that SDK
and renderer source code does not reference backend modules. These remain valid
architectural boundary checks and were left in place.

## Verification

- **Baseline gate suite**: all 38 gates passed (exit code 0)
- **Post-change gate suite**: all 37 gates passed (exit code 0)
- **Agent-core tests**: 891 passed, 5 skipped, 0 errors
- **New Phase 104 tests**: 7 passed, 3 subtests passed
- **Gate count**: 38 → 37 (codex-backend gate removed)
- **No broken imports**: verified by `test_no_imports_from_legacy_backends`

## Lines Retired

- `packages/backends/hermes/`: ~1,843 lines of production code + tests
- `packages/backends/codex/`: ~2,032 lines of production code + tests
- Total: ~3,875 lines retired
