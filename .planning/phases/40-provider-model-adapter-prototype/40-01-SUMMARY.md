---
phase: 40
plan: 40-01
title: "Provider Model Adapter Package Structure, Manifest, and Capability Probe"
wave: 1
status: complete
requirements:
  - ADAPTER-02
---

# Plan 40-01 — Summary

## Tasks Completed

| Task ID | Description | Commit |
|---------|-------------|--------|
| 40-01-01 | Provider_model adapter package skeleton: pyproject.toml, README.md, config.py, manifest.py, adapter.py (all 9 BackendAdapter methods), probe.py, __init__.py, tests/__init__.py, tests/test_adapter.py | `11be197` |
| 40-01-02 | Capability probe tests: test_probe.py verifying 14-field AdapterCapabilitySet, no API calls, no top-level openai import, SDK-unavailable handling, manifest validation | `e0619a9` |

## Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| `tests/test_adapter.py` | 11 | PASS |
| `tests/test_probe.py` | 5 | PASS |
| **Total** | **16** | **16 passed, 0 failed** |

Quick command:
```
PYTHONPATH=packages/backends/provider_model/src:packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest packages/backends/provider_model/tests/ -q
```

## Files Created

| File | Purpose |
|------|---------|
| `packages/backends/provider_model/pyproject.toml` | Package definition (`inkstatute-backends-provider-model`, dependencies=[], requires-python>=3.11) |
| `packages/backends/provider_model/README.md` | Package readme (prototype, production_ready=false, no_channel_io=true, invocation_mode=direct_llm) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` | Public re-exports |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/config.py` | `ProviderModelBackendConfig` frozen dataclass |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py` | `build_provider_model_manifest()` + `provider_model_prototype_capabilities()` (14 fields) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/probe.py` | `ProviderModelCapabilityProbe` with injectable transport, importlib-based SDK check |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` | `ProviderModelBackendAdapter` (9 BackendAdapter methods) + `ProviderModelRunner` Protocol + `ProviderModelExecResult` |
| `packages/backends/provider_model/tests/__init__.py` | Test package init (empty) |
| `packages/backends/provider_model/tests/test_adapter.py` | 11 adapter/manifest tests |
| `packages/backends/provider_model/tests/test_probe.py` | 5 capability probe tests |

## Acceptance Criteria Verification

- [x] `pyproject.toml` exists with `name = "inkstatute-backends-provider-model"`, `dependencies = []`, `requires-python = ">=3.11"`.
- [x] `build_provider_model_manifest()` passes `validate_agent_backend_manifest` with zero issues.
- [x] `build_provider_model_manifest().mode == AgentBackendMode.PROVIDER_MODEL`.
- [x] `build_provider_model_manifest().metadata["production_ready"] is False`.
- [x] `build_provider_model_manifest().capabilities.no_channel_io is True`.
- [x] `build_provider_model_manifest().capabilities.invocation_mode == "direct_llm"`.
- [x] `provider_model_prototype_capabilities()` returns an `AdapterCapabilitySet` with exactly 14 fields.
- [x] `ProviderModelBackendAdapter` exposes exactly 9 callable BackendAdapter methods.
- [x] `select_agent_backend({"agent_backend": {"mode": "provider_model"}}, [build_provider_model_manifest()])` returns `live_acceptance_allowed=False`, `contract_compatible=True`.
- [x] `submit_run` without a runner raises `RuntimeError("provider_model runner not configured")`.
- [x] Package imports cleanly without the `openai` SDK installed (no top-level `openai` import).
- [x] `ProviderModelCapabilityProbe(FakeTransport()).probe()` returns `ok=True`, `sdk_available=True`, 14-field capabilities.
- [x] Probe source does not contain `"chat.completions"` or `"create("`.
- [x] Probe source does not contain top-level `import openai`.
- [x] `ProviderModelCapabilityProbe(FakeTransport(available=False)).probe()` returns `ok=False` with issue `code="openai_sdk_unavailable"`.
- [x] Probe report capabilities equal `provider_model_prototype_capabilities()` and validate in the manifest.

## Deviations

None. All tasks executed as specified in the plan. The adapter mirrors the Codex adapter pattern with provider_model-specific naming, `invocation_mode="direct_llm"`, `completion_id` instead of `thread_id`, and `model_name` in bootstrap metadata.

## EXECUTION COMPLETE
