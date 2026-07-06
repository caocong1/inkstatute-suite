# Phase 55: Multi-Agent Runtime Adapter (B5) — Research

**Researched:** 2026-07-06
**Status:** Complete

## Phase Goal

Operator can configure a Multi-Agent Runtime Adapter as a composite `BackendAdapter` delegating by `solution.backend_id`, supporting sequential/parallel/supervisor orchestration with `max_handoffs=5`, cycle detection, and shared state scoped to `parent_run_id` with copy-on-write isolation.

## Dependencies

- **Phase 54 (Model Provider Gateway)** — complete. Provides the composite `BackendAdapter` pattern reference (`ModelProviderGateway`).
- **Phase 50 (MCP Registry)** — complete. Provides MCP tool resolution context.

## Key Codebase Findings

### 1. BackendAdapter Protocol (frozen, 9 methods)

**File:** `packages/platform-runtime/src/platform_runtime/protocols.py:222-239`

The `BackendAdapter` Protocol defines 9 methods:
1. `backend_id() -> str`
2. `capabilities() -> AdapterCapabilitySet`
3. `bootstrap_check() -> BootstrapStatus`
4. `submit_run(req: RunRequest) -> RunHandle`
5. `get_run(run_id: str) -> Run`
6. `stream_events(run_id: str) -> AsyncIterator[RunEvent]`
7. `cancel_run(run_id: str) -> Run`
8. `submit_approval(run_id: str, approval: Approval) -> Run`
9. `collect_artifacts(run_id: str) -> list[ArtifactRecord]`

**Constraint:** Do NOT modify this Protocol. The MultiAgentRuntimeAdapter must implement it via structural subtyping (no explicit inheritance), exactly as `ModelProviderGateway` does.

### 2. ModelProviderGateway — Composite Adapter Pattern Reference

**File:** `packages/model-gateway/src/inkstatute_model_gateway/gateway.py`

Key patterns to replicate:
- **Structural subtyping:** `class ModelProviderGateway:` — no explicit `BackendAdapter` inheritance.
- **Sub-adapters injected as `dict[str, Any]`** keyed by `backend_id`. The gateway does NOT import provider_model packages directly — preserves `dependencies = []`.
- **`config.enabled` defaults to `False`** — when disabled, `submit_run` delegates directly to the matching sub-adapter (pass-through).
- **Run-to-adapter mapping:** `self._run_to_adapter: dict[str, str]` maps `run_id -> backend_id` for routing `get_run`/`stream_events`/`cancel_run`/`submit_approval`/`collect_artifacts`.
- **Capability merging:** `_merge_capabilities()` OR's booleans, unions lists, takes first non-None for strings.
- **`bootstrap_check`** aggregates all sub-adapter statuses.
- **Clock injection:** `_SystemClock` with `now()` returning UTC ISO timestamp.

### 3. Config Pattern

**File:** `packages/model-gateway/src/inkstatute_model_gateway/config.py`

`ModelProviderGatewayConfig` is a frozen dataclass with `slots=True`:
- `gateway_id: str = "model-provider-gateway"`
- `enabled: bool = False`
- Additional config fields with `field(default_factory=...)`
- `metadata: JsonObject = field(default_factory=dict)`

### 4. Feature Flag

**File:** `packages/platform-runtime/src/platform_runtime/feature_flags.py:31`

`multi_agent_enabled: bool = False` already exists in `RuntimeFeatureFlags` (M3 flags). This is the default-off flag for the multi-agent runtime lane.

### 5. RunRequest / SolutionBinding

**File:** `packages/platform-runtime/src/platform_runtime/protocols.py:98-116`

`RunRequest` contains:
- `turn: AgentTurn`
- `solution: SolutionBinding` — has `backend_id: BackendId | None`
- `tenant_id`, `workspace_id`, `session_id`, `metadata`

The `solution.backend_id` is the routing key for sub-adapter delegation.

Note: `platform_contract.events.SolutionBinding` (line 96-101) has `backend_id: str` (non-optional), while `platform_runtime.protocols.SolutionBinding` (line 98-104) has `backend_id: BackendId | None`. The gateway handles `None` by raising `KeyError`.

### 6. Run / RunHandle / RunEvent

**File:** `packages/platform-runtime/src/platform_runtime/protocols.py:119-145`

- `RunHandle`: `run_id`, `backend_run_id`, `status`, `metadata`
- `Run`: `run_id`, `status`, `turn_id`, `solution_id`, `result`, `metadata`
- `RunEvent`: `event_id`, `run_id`, `event_type`, `occurred_at`, `seq`, `payload`, `metadata`

### 7. AsyncTaskState

**File:** `packages/platform-contract/src/platform_contract/enums.py:6-14`

Terminal states: `SUCCEEDED`, `FAILED`, `CANCELLED`. Non-terminal: `QUEUED`, `RUNNING`, `WAITING_FOR_USER`.

### 8. FakeBackendAdapter — Test Pattern

**File:** `packages/platform-runtime/src/platform_runtime/fakes.py:56-255`

In-memory adapter with deterministic lifecycle. `submit_run` stores runs in `self.runs[run_id]`, events in `self.events[run_id]`. Used in model-gateway tests as sub-adapters.

### 9. Package Layout

**File:** `packages/model-gateway/pyproject.toml`

```
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "inkstatute-model-gateway"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools]
package-dir = { "" = "src" }

[tool.setuptools.packages.find]
where = ["src"]
```

Package structure:
```
packages/model-gateway/
  pyproject.toml
  src/inkstatute_model_gateway/
    __init__.py
    config.py
    gateway.py
    circuit_breaker.py
    rate_limiter.py
    cost_tracker.py
  tests/
    __init__.py
    test_gateway.py
    test_circuit_breaker.py
    ...
```

### 10. V2 Gates Script

**File:** `scripts/run_v2_gates.py`

Each gate is a `Gate(name, command, pythonpath)`. The `model-gateway` gate (line 122-126) runs unittest discovery with `PYTHONPATH=(model_gateway_src, platform_src, platform_runtime_src)`. The `compileall` gate (line 192-224) lists all src directories to byte-compile.

A new gate for `multi-agent-adapter` must be added, and `packages/multi-agent-adapter/src` must be added to `compileall`.

## Design Decisions

### D1: Structural Subtyping (no explicit Protocol inheritance)
Follow `ModelProviderGateway` pattern — `class MultiAgentRuntimeAdapter:` with no explicit `BackendAdapter` inheritance. This preserves the frozen Protocol invariant.

### D2: `multi_agent_enabled` defaults to False
When disabled, `submit_run` is transparent pass-through to the sub-adapter matching `solution.backend_id` — identical to `ModelProviderGateway._submit_run_passthrough`.

### D3: Orchestration Modes
Three modes configured via `MultiAgentOrchestrationConfig.mode`:
- **sequential**: Entry agent runs, checks result for `handoff_to` metadata, chains to next agent. Handoff chain tracked with visited-set for cycle detection.
- **parallel**: Fan-out to multiple agents concurrently using `asyncio.gather` with `asyncio.Semaphore` bounding concurrency. Fan-in merges results.
- **supervisor**: Supervisor agent runs first, may delegate to worker agents via `delegate_to` metadata. Workers run, results flow back.

### D4: max_handoffs=5
Enforced as a counter in the orchestration loop. Each handoff increments the counter. When `handoff_count >= max_handoffs`, the next handoff raises `MultiAgentHandoffLimitError`.

### D5: Cycle Detection
A `visited: set[str]` tracks agent_ids in the handoff chain. Before dispatching to a handoff target, check if the target is already in `visited`. If so, raise `MultiAgentCycleError` with a clear message showing the cycle.

### D6: Copy-on-Write Shared State
`SharedStateStore` maintains:
- `_shared: dict[parent_run_id, dict]` — the shared state
- `_copies: dict[parent_run_id, dict[agent_id, dict]]` — per-agent COW copies

When an agent reads, it gets a snapshot of the shared state. When an agent writes, a COW copy is created for that agent — the shared state is NOT mutated. In sequential mode, after an agent completes, its COW copy is committed to shared state for the next agent. In parallel mode, each agent gets the same snapshot and writes are isolated.

### D7: Parent Run Tracking
`_ParentRunRecord` tracks:
- `parent_run_id` — the multi-agent run ID
- `sub_run_ids` — ordered list of sub-run IDs
- `sub_run_to_agent` — maps sub_run_id to agent_id
- `handoff_chain` — ordered list of agent_ids (for cycle detection)
- `shared_state_key` — the parent_run_id key for SharedStateStore
- `final_run` — the final aggregated Run
- `status` — overall orchestration status

### D8: `dependencies = []` Invariant
The package imports only stdlib + `platform_contract` + `platform_runtime`. No imports of codex, provider_model, or other backend packages at module top level. Sub-adapters are injected as `dict[str, Any]`.

### D9: Run ID Namespacing
Parent run IDs are prefixed with `ma-` (multi-agent) to distinguish from sub-run IDs. The `_run_to_adapter` map routes both parent and sub run IDs to the correct adapter (parent → self, sub → sub-adapter).

## Requirements Traceability

| Requirement | Success Criterion | Design Decision |
| --- | --- | --- |
| MULTIAGENT-01 | Composite BackendAdapter delegating by `solution.backend_id` | D1, D2, D9 |
| MULTIAGENT-01 | Sequential/parallel/supervisor orchestration | D3 |
| MULTIAGENT-01 | `max_handoffs=5` enforced | D4 |
| MULTIAGENT-01 | Cycle detection | D5 |
| MULTIAGENT-02 | Shared state scoped to `parent_run_id` with COW isolation | D6 |
| MULTIAGENT-02 | `multi_agent_enabled` defaults to False, transparent pass-through | D2 |
