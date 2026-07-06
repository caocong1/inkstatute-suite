# Phase 54: Model Provider Gateway (B4) - Research

**Researched:** 2026-07-06
**Status:** Complete
**Depends on:** Phase 48 (Multi-Provider Runners), Phase 53 (Hybrid Routing)

## 1. Phase Goal

Operator can configure a Model Provider Gateway (`packages/model-gateway/`) as a composite `BackendAdapter` wrapping multiple `provider_model` sub-adapters, with per-tenant/provider rate limiting (RPM/TPM/concurrency), fallback chains with circuit breakers and tried-provider tracking, and per-tenant/matter cost tracking with budget ceilings.

## 2. Key Codebase Findings

### 2.1 BackendAdapter Protocol (frozen, 9 methods)

**File:** `packages/platform-runtime/src/platform_runtime/protocols.py:222-239`

The `BackendAdapter` Protocol defines exactly 9 methods:
1. `backend_id() -> str`
2. `capabilities() -> AdapterCapabilitySet`
3. `bootstrap_check() -> BootstrapStatus`
4. `submit_run(req: RunRequest) -> RunHandle`
5. `get_run(run_id: str) -> Run`
6. `stream_events(run_id: str) -> AsyncIterator[RunEvent]`
7. `cancel_run(run_id: str) -> Run`
8. `submit_approval(run_id: str, approval: Approval) -> Run`
9. `collect_artifacts(run_id: str) -> list[ArtifactRecord]`

**Constraint:** Must NOT modify this Protocol. The composite gateway implements all 9 methods by delegating to sub-adapters.

### 2.2 ProviderModelBackendAdapter (sub-adapter pattern)

**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py`

- `ProviderModelBackendAdapter` is a concrete adapter with `backend_id`, `capabilities`, `bootstrap_check`, `submit_run`, `get_run`, `stream_events`, `cancel_run`, `submit_approval`, `collect_artifacts`.
- `__init__` accepts `config: ProviderModelBackendConfig`, `runner: ProviderModelRunner`, `streaming_runner: StreamingProviderModelRunner`, `clock`.
- `submit_run` delegates to `runner.invoke(req)` returning `ProviderModelExecResult`, then builds a `Run` and `RunHandle`.
- Internal state: `_runs: dict[str, Run]`, `_artifacts: dict[str, list[ArtifactRecord]]`, `_run_requests: dict[str, RunRequest]`, `_next_run: int`.
- Run IDs are namespaced: `f"provider-model-run-{value:03d}"`.

### 2.3 Provider Runners (Phase 48)

Three runners implement `ProviderModelRunner` Protocol (`async def invoke(req: RunRequest) -> ProviderModelExecResult`):
- **OpenAIClientRunner** (`openai_runner.py`) — lazy SDK import via `importlib.import_module("openai")` inside `invoke`.
- **AnthropicRunner** (`anthropic_runner.py`) — lazy SDK import via `importlib.import_module("anthropic")` inside `invoke`.
- **OllamaRunner** (`ollama_runner.py`) — lazy stdlib `urllib.request` import inside `invoke`.

All return `ProviderModelExecResult` with `status`, `result: AgentResult`, `completion_id`, `artifact_refs`, `raw_payload_ref`, `metadata` (including `provider_usage` with token counts).

### 2.4 Error Normalization (Phase 48)

**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/error_normalization.py`

`normalize_provider_error(exc, stage, *, provider)` maps provider exceptions to `ErrorInfo` with codes:
- `provider_model_rate_limit` (429 / RateLimitError) — retryable=True
- `provider_model_auth_error` (401/403 / AuthenticationError) — retryable=False
- `provider_model_connection_error` (Connection/Timeout) — retryable=True
- `provider_model_api_error` (5xx / APIStatusError) — retryable=None
- `provider_model_unknown_error` — retryable=None

### 2.5 Feature Flags

**File:** `packages/platform-runtime/src/platform_runtime/feature_flags.py:30`

`model_gateway_enabled: bool = False` already exists in `RuntimeFeatureFlags` (M3 flags). It defaults to `False`. The `require_enabled(flag_name)` method raises `RuntimeFeatureDisabledError` if the flag is off.

### 2.6 RunRequest and SolutionBinding

**File:** `packages/platform-runtime/src/platform_runtime/protocols.py:107-116`

`RunRequest` has:
- `turn: AgentTurn`
- `solution: SolutionBinding` — has `backend_id: BackendId | None`, `solution_id`, `version`, `config_ref`, `metadata`
- `tenant_id: str | None`
- `workspace_id: str | None`
- `metadata: JsonObject`

The gateway delegates by `solution.backend_id` — if it matches a registered sub-adapter's `backend_id`, that adapter handles the run. Otherwise, fallback chain order is used.

### 2.7 ProviderModelExecResult and Token Usage

**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py:45-54`

`ProviderModelExecResult` has `metadata` which includes `provider_usage` (dict with `input_tokens`, `output_tokens`, `prompt_tokens`, `completion_tokens`, `total_tokens`). This is the source for cost tracking.

### 2.8 Package Layout Convention

Existing packages follow:
```
packages/<name>/
  pyproject.toml          # dependencies = [], requires-python = ">=3.11"
  src/
    <package_name>/
      __init__.py
      <modules>.py
  tests/
    __init__.py           # (some packages have it, some don't)
    test_*.py
```

### 2.9 V2 Gate Script

**File:** `scripts/run_v2_gates.py`

The gate script runs `unittest discover` per package with `PYTHONPATH` set to the package's `src/` directory plus dependencies. The `compileall` gate compiles all `src/` directories. The new `packages/model-gateway/src` must be added to the `compileall` gate. A new gate entry for `model-gateway` tests should be added.

### 2.10 RouterService Pattern (Phase 53)

**File:** `packages/router-service/src/inkstatute_router_service/service.py`

`RouterService` implements `RouterPort` via structural subtyping (no explicit inheritance). It uses `RouterStrategy` enum (RULE, SKILL, HYBRID) and produces `RouteDecision` records. The HYBRID strategy cascades Rule → Skill → Model with confidence thresholds and legal-risk forcing to Hermes.

## 3. Design Decisions

### 3.1 Composite BackendAdapter Pattern

`ModelProviderGateway` implements `BackendAdapter` (structural subtyping, no explicit inheritance to avoid import coupling). It wraps `dict[str, BackendAdapter]` sub-adapters keyed by `backend_id`.

- `submit_run`: delegates by `req.solution.backend_id` if it matches a sub-adapter; otherwise uses fallback chain order.
- `get_run`, `stream_events`, `cancel_run`, `submit_approval`, `collect_artifacts`: route by run_id prefix or internal mapping.
- `bootstrap_check`: aggregates sub-adapter bootstrap statuses.
- `capabilities`: merged from sub-adapters (union of capabilities).
- `backend_id`: returns `"model-provider-gateway"`.

### 3.2 Rate Limiting (RPM/TPM/Concurrency)

Pure-Python implementation using:
- `collections.deque` for sliding-window RPM/TPM tracking (timestamps of recent requests/tokens).
- `asyncio.Semaphore` for concurrency limits.
- `asyncio.Lock` for thread-safe updates.
- `asyncio.monotonic()` for time references.

Per-tenant per-provider limits configured via `RateLimitConfig(rpm, tpm, max_concurrency)`.

### 3.3 Circuit Breakers

Three states: CLOSED (normal), OPEN (tripped, rejecting), HALF_OPEN (probe request allowed).
- Trips after N consecutive failures (`failure_threshold`).
- Stays OPEN for `cooldown_seconds`, then transitions to HALF_OPEN.
- A successful request in HALF_OPEN closes the breaker; a failure re-opens it.

Per-provider circuit breaker state tracked in `CircuitBreaker` dataclass.

### 3.4 Fallback Chains

`fallback_chain: list[str]` — ordered list of `backend_id` values. When the primary provider fails (or circuit breaker is open), the gateway tries the next provider in the chain. `tried_providers` is tracked in run metadata as a list of `backend_id` strings.

### 3.5 Cost Tracking with Budget Ceilings

- `CostTracker` accumulates token usage per tenant per matter.
- `BudgetCeiling` per tenant per matter (or global per-tenant).
- When cumulative cost exceeds the ceiling, further requests are rejected with `ErrorInfo(code="model_gateway_budget_exceeded")`.
- Cost is estimated from `provider_usage` token counts × per-provider pricing rates.

### 3.6 Transparent Pass-Through When Disabled

When `model_gateway_enabled` is `False` (default), the gateway operates in pass-through mode:
- `submit_run` delegates directly to the sub-adapter matching `solution.backend_id` without rate limiting, circuit breaking, fallback, or cost tracking.
- This preserves backward compatibility — existing behavior is unchanged.

### 3.7 Dependencies Invariant

`dependencies = []` in `pyproject.toml`. No external SDK imports at module top level. The gateway only imports from `platform_contract`, `platform_runtime`, and stdlib. Sub-adapter instances are injected — the gateway does not import provider_model packages directly.

## 4. Risk Analysis

1. **Run ID namespacing**: The gateway must track which sub-adapter owns which run_id. Solution: maintain `_run_to_adapter: dict[str, str]` mapping run_id → backend_id.
2. **Concurrency safety**: Rate limiting and circuit breakers must be async-safe. Solution: `asyncio.Lock` for state mutations.
3. **Test isolation**: Tests must not require real provider SDKs. Solution: inject fake sub-adapters (using `FakeBackendAdapter` or custom fakes).
4. **V2 gate integration**: Must add `packages/model-gateway/src` to `compileall` gate and add a new test gate. Solution: edit `scripts/run_v2_gates.py`.

## 5. Plan Split

- **Plan 01**: Create `packages/model-gateway/` package with `ModelProviderGateway` composite `BackendAdapter`, sub-adapter delegation by `backend_id`, transparent pass-through when disabled, package layout + pyproject.toml + `__init__.py`.
- **Plan 02**: Rate limiting (RPM/TPM/concurrency) + circuit breakers (open/half-open/closed) + fallback chains with `tried_providers` tracking.
- **Plan 03**: Cost tracking with budget ceilings + integration tests + V2 gate integration.
