# Plan 55-01 Summary: Multi-Agent Runtime Adapter

## Objective

Create a new `packages/multi-agent-adapter/` package implementing `MultiAgentRuntimeAdapter` — a composite `BackendAdapter` that wraps multiple sub-adapters and orchestrates them in sequential, parallel, or supervisor patterns. The adapter delegates by `solution.backend_id`, enforces `max_handoffs=5` with cycle detection, and maintains copy-on-write shared state scoped to `parent_run_id`. When `multi_agent_enabled` is `False` (default), the adapter is transparent pass-through.

## Tasks Completed

### Task 1: Package scaffold, config, errors, and SharedStateStore

**Files created:**
- `packages/multi-agent-adapter/pyproject.toml` — Package layout matching model-gateway with `name="inkstatute-multi-agent-adapter"`, `dependencies=[]`, src layout.
- `packages/multi-agent-adapter/src/inkstatute_multi_agent_adapter/config.py` — `MultiAgentOrchestrationMode` StrEnum (SEQUENTIAL, PARALLEL, SUPERVISOR), `MultiAgentOrchestrationConfig` frozen dataclass (mode, entry_agent_id, supervisor_agent_id, max_handoffs=5, parallel_concurrency=4, agent_set, metadata), `MultiAgentRuntimeAdapterConfig` frozen dataclass (adapter_id="multi-agent-runtime", enabled=False, orchestration, metadata).
- `packages/multi-agent-adapter/src/inkstatute_multi_agent_adapter/errors.py` — `MultiAgentError` base, `MultiAgentHandoffLimitError`, `MultiAgentCycleError`, `MultiAgentRoutingError`.
- `packages/multi-agent-adapter/src/inkstatute_multi_agent_adapter/shared_state.py` — `SharedStateStore` with copy-on-write isolation: `init()`, `snapshot()`, `write()`, `write_all()`, `commit()`, `agent_state()`, `has_cow_copy()`, `dispose()`. Uses `copy.deepcopy` for all isolation.
- `packages/multi-agent-adapter/src/inkstatute_multi_agent_adapter/__init__.py` — Exports all public symbols.
- `packages/multi-agent-adapter/tests/__init__.py` — Empty test package init.
- `packages/multi-agent-adapter/tests/test_shared_state.py` — 10 tests: snapshot isolation, COW write, commit, cross-agent non-mutation, dispose, deep copy isolation.

**Commit:** `1dffedf` — `feat(55-01): MultiAgentRuntimeAdapter composite adapter...`

### Task 2: MultiAgentRuntimeAdapter — BackendAdapter Protocol implementation with orchestration

**Files created:**
- `packages/multi-agent-adapter/src/inkstatute_multi_agent_adapter/adapter.py` — `MultiAgentRuntimeAdapter` class implementing all 9 BackendAdapter methods via structural subtyping (no explicit Protocol inheritance). Key components:
  - `_ParentRunRecord` dataclass tracking parent_run_id, sub_run_ids, sub_run_to_agent, handoff_chain, shared_state_key, final_run, status, events, artifacts.
  - `_submit_run_passthrough`: transparent delegation when `enabled=False`.
  - `_submit_run_enabled`: generates `ma-` prefixed parent_run_id, inits SharedStateStore, dispatches to orchestration mode.
  - `_orchestrate_sequential`: entry agent → check `handoff_to` metadata → chain with visited-set cycle detection and max_handoffs counter; COW shared state committed between agents.
  - `_orchestrate_parallel`: `asyncio.gather` with `asyncio.Semaphore(parallel_concurrency)` fan-out; each agent gets same snapshot; COW writes isolated (no commit).
  - `_orchestrate_supervisor`: supervisor runs first → `delegate_to` metadata dispatches to workers (parallel) → results flow back; supervisor's COW state committed before workers.
  - `get_run`/`stream_events`/`cancel_run`/`collect_artifacts`: parent run_id → aggregated results; sub run_id → delegate to sub-adapter.
  - `_merge_capabilities`: reuses gateway pattern (OR booleans, union lists, first non-None strings).
  - Shared state flows through `RunRequest.metadata["shared_state"]` (injected) and `Run.metadata["shared_state_update"]` (extracted).
- `packages/multi-agent-adapter/src/inkstatute_multi_agent_adapter/__init__.py` — Updated to export `MultiAgentRuntimeAdapter`.
- `packages/multi-agent-adapter/tests/test_adapter.py` — 18 tests: backend_id, capabilities merge, bootstrap_check, pass-through mode (8 tests), enabled mode routing (5 tests), unknown run/agent error handling.
- `packages/multi-agent-adapter/tests/test_orchestration.py` — 20 tests: sequential handoff chain (4), max_handoffs limit (2), cycle detection (2), parallel fan-out/fan-in (4), supervisor delegation (4), COW shared state isolation (3), error handling (1).

**Commit:** `1dffedf` — `feat(55-01): MultiAgentRuntimeAdapter composite adapter...`

### Task 3: V2 gate integration

**Files modified:**
- `scripts/run_v2_gates.py` — Added `multi_agent_src` path variable, new `multi-agent-adapter` gate (PYTHONPATH: multi_agent_src, platform_src, platform_runtime_src), added `packages/multi-agent-adapter/src` to compileall. Also added `services/admin-web-ui/src` and `services/lawyer-web-chat/src` to compileall for pre-existing Phase 57 service coverage.
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — Updated gate count from 23 to 24, added `multi-agent-adapter` to expected gate names.
- `services/admin-console-api/tests/test_contract_freeze.py` — Added `admin_web_ui_enabled` and `lawyer_web_chat_enabled` to expected feature flags set (pre-existing Phase 57 freeze test fix).

**Commit:** `11afa09` — `fix(55): update V2 gate count to 24, add multi-agent-adapter gate, fix pre-existing freeze test and service coverage`

## Deviations

- **[Pre-existing fix — non-blocking]** Updated `services/admin-console-api/tests/test_contract_freeze.py` to include `admin_web_ui_enabled` and `lawyer_web_chat_enabled` in the expected feature flags set. Phase 57 (commit `1757aaf`) added these flags to `RuntimeFeatureFlags` but did not update the freeze test, causing a pre-existing `admin-console-api` gate failure. This fix was necessary to make V2 gates green.
- **[Pre-existing fix — non-blocking]** Added `services/admin-web-ui/src` and `services/lawyer-web-chat/src` to the compileall gate. These directories exist on disk from Phase 57's incomplete work but were not covered by any gate, causing the `test_all_services_src_covered` meta-test to fail.
- **[Test helper duplication]** The `_ScriptedAdapter` test helper and `_make_request`/`_make_turn` helpers are duplicated in `test_orchestration.py` rather than imported from `test_adapter.py`, because `unittest discover` does not support cross-test-module imports via `from tests.test_adapter import ...` without the `tests` package being on PYTHONPATH.

## Test Results

- **Multi-agent-adapter package tests:** 48 tests pass
  - `python3 -m unittest discover -s packages/multi-agent-adapter/tests -v` — OK
  - 10 SharedStateStore tests + 18 adapter tests + 20 orchestration tests
- **V2 gate suite:** 24 gates, all green
  - `python3 scripts/run_v2_gates.py` — exits 0
  - New `multi-agent-adapter` gate: 48 tests pass
  - All 23 pre-existing gates remain green

## FROZEN Contract Surfaces Verified

- BackendAdapter: 9 methods (unchanged)
- AdapterCapabilitySet: 14 fields (unchanged)
- RuntimeFeatureFlags: 21 fields → 23 fields (2 added by Phase 57, not by Phase 55)
- `dependencies = []` invariant preserved — imports only stdlib + `platform_contract` + `platform_runtime`
- No frozen Protocol modified — `MultiAgentRuntimeAdapter` uses structural subtyping

## Key Design Decisions

1. **Structural subtyping** — `class MultiAgentRuntimeAdapter:` with no explicit `BackendAdapter` inheritance, matching `ModelProviderGateway` pattern.
2. **`multi_agent_enabled` defaults to False** — when disabled, `submit_run` is transparent pass-through to the sub-adapter matching `solution.backend_id`.
3. **Sequential orchestration** — entry agent runs, `handoff_to` metadata chains to next agent; visited-set for cycle detection; `handoff_count >= max_handoffs` raises `MultiAgentHandoffLimitError`.
4. **Parallel orchestration** — `asyncio.gather` with `asyncio.Semaphore(parallel_concurrency)`; each agent gets same snapshot; COW writes isolated (no commit).
5. **Supervisor orchestration** — supervisor runs first, `delegate_to` metadata dispatches to workers; supervisor's COW state committed before workers run.
6. **Copy-on-write shared state** — `SharedStateStore` uses `copy.deepcopy` for all reads/writes; writes create per-agent COW copies; `commit()` merges into shared state.
7. **Run ID namespacing** — parent run IDs prefixed with `ma-`; `_run_to_adapter` routes both parent and sub run IDs.
8. **Shared state transport** — state flows through `RunRequest.metadata["shared_state"]` (injected by adapter) and `Run.metadata["shared_state_update"]` (extracted by adapter), preserving the frozen BackendAdapter Protocol.
