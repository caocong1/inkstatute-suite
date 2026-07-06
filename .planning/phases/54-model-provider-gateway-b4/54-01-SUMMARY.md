# Plan 54-01 Summary: ModelProviderGateway Composite BackendAdapter

## Objective

Create the `packages/model-gateway/` package with `ModelProviderGateway` — a composite `BackendAdapter` that wraps multiple `provider_model` sub-adapters in a `dict[str, BackendAdapter]` keyed by `backend_id`. The gateway implements all 9 frozen `BackendAdapter` Protocol methods, delegating `submit_run` by `solution.backend_id` and routing `get_run`/`stream_events`/`cancel_run`/`submit_approval`/`collect_artifacts` via an internal `run_id → backend_id` mapping. When `model_gateway_enabled` is `False` (default), the gateway is transparent — pass-through to the matching sub-adapter.

## Tasks Completed

### Task 1: Create package layout, pyproject.toml, config, and ModelProviderGateway composite adapter

**Files created:**
- `packages/model-gateway/pyproject.toml` — `dependencies = []`, `requires-python = ">=3.11"`, `package-dir = { "" = "src" }`
- `packages/model-gateway/src/inkstatute_model_gateway/config.py` — `ModelProviderGatewayConfig` frozen dataclass with `gateway_id`, `enabled` (default `False`), `fallback_chain`, `metadata`
- `packages/model-gateway/src/inkstatute_model_gateway/gateway.py` — `ModelProviderGateway` class implementing all 9 `BackendAdapter` Protocol methods via structural subtyping. Key features:
  - `backend_id()` returns `config.gateway_id` (default `"model-provider-gateway"`)
  - `capabilities()` merges sub-adapter capabilities (OR booleans, union lists)
  - `bootstrap_check()` aggregates sub-adapter bootstrap statuses
  - `submit_run()` delegates by `solution.backend_id`, records `run_id → backend_id` mapping
  - `get_run()`, `stream_events()`, `cancel_run()`, `submit_approval()`, `collect_artifacts()` route via `_run_to_adapter` mapping
  - `_merge_capabilities()` helper merges AdapterCapabilitySet from multiple sub-adapters
- `packages/model-gateway/src/inkstatute_model_gateway/__init__.py` — exports `ModelProviderGateway`, `ModelProviderGatewayConfig`
- `packages/model-gateway/tests/__init__.py` — empty
- `packages/model-gateway/tests/test_gateway.py` — 18 tests covering backend_id, capabilities merging, bootstrap aggregation, submit_run delegation, routing for all 9 methods, disabled pass-through, and clean import

**Commit:** `4e45adb` — `feat(54-01): ModelProviderGateway composite BackendAdapter with sub-adapter delegation`

## Test Results

- **model-gateway tests:** 18 tests pass
  - `python3 -m unittest discover -s packages/model-gateway/tests -v` — OK

## FROZEN Contract Surfaces Verified

- BackendAdapter: 9 methods (unchanged — gateway implements via structural subtyping, no inheritance)
- AdapterCapabilitySet: 14 fields (unchanged — gateway merges, does not modify)
- `dependencies = []` invariant preserved — no external SDK imports at module top level

## Key Design Decisions

1. **Structural subtyping** — `ModelProviderGateway` does not explicitly inherit from `BackendAdapter` Protocol; it implements the 9 methods directly, matching the pattern used by `ProviderModelBackendAdapter` and `FakeBackendAdapter`.
2. **Run ID mapping** — `_run_to_adapter: dict[str, str]` maps `run_id → backend_id` to route `get_run`/`stream_events`/`cancel_run`/`submit_approval`/`collect_artifacts` to the correct sub-adapter.
3. **Capability merging** — Boolean fields are OR'd (True if any sub-adapter has True), list fields are unioned (deduplicated, order preserved), string fields take the first non-None value.
4. **Pass-through when disabled** — When `config.enabled` is `False`, `submit_run` delegates directly to the matching sub-adapter with no gateway logic.
