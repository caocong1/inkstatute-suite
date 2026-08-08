---
phase: 103
plan: 01
title: In-Process BackendAdapter
status: complete
created: 2026-08-08
---

# Plan 103-01 Summary: In-Process BackendAdapter

## Objective

Implement `InProcessAgentCoreAdapter` — a `BackendAdapter` Protocol implementation that wraps the agent-core's `run_turn()` for direct in-process use by the Gateway. No IPC, no subprocess, full observability.

## Files Created

### 1. `packages/agent-core/src/inkstatute_agent_core/backend_config.py`
`AgentCoreBackendConfig` frozen dataclass with:
- `config: AgentCoreConfig` — turn loop config (max_turns, temperature, silence threshold, etc.)
- `provider_factory: Callable[[], LlmProvider]` — factory for model provider (called once per `submit_run` for independent concurrent run state)
- `tool_executor_factory: Callable[[], ToolExecutor] | None` — optional factory for tool executor
- `backend_id: str = "inkstatute"` — unique backend identifier

### 2. `packages/agent-core/src/inkstatute_agent_core/backend_adapter.py`
`InProcessAgentCoreAdapter` implementing all 9 `BackendAdapter` Protocol methods:

1. **`backend_id()`** → returns `"inkstatute"` from config
2. **`capabilities()`** → returns `AdapterCapabilitySet` with `stream_event_support=True`, `cancel_support=True`, `approval_support=True`, `session_memory_support=True`. No `fs/*` or `terminal/*` capabilities.
3. **`bootstrap_check()`** → calls `provider_factory()` to verify the model provider is available. Returns `BootstrapStatus(ok=True, ...)` on success, `BootstrapStatus(ok=False, ...)` with issues on failure.
4. **`submit_run(req: RunRequest) -> RunHandle`** → extracts user prompt from `req.turn`, creates `EventEmitter` + `LlmProvider` from config, starts `run_turn()` as a background `asyncio.Task`, buffers events in an `asyncio.Queue`, returns `RunHandle` with `RUNNING` status.
5. **`get_run(run_id) -> Run`** → returns current `Run` state from internal dict; raises `KeyError` for unknown run_id.
6. **`stream_events(run_id) -> AsyncIterator[RunEvent]`** → yields events from the per-run `asyncio.Queue` until the `_STREAM_DONE` sentinel signals completion.
7. **`cancel_run(run_id) -> Run`** → cancels the background `asyncio.Task`, emits `run.state_changed` to `"cancelled"`, pushes sentinel, updates run status to `CANCELLED`.
8. **`submit_approval(run_id, approval) -> Run`** → rejects auto-approval of `terminal` and `execute_code` permissions (sets `WAITING_FOR_USER`, records rejection in metadata). Safe permissions are accepted and stored for the turn loop.
9. **`collect_artifacts(run_id) -> list[ArtifactRecord]`** → returns artifacts collected from `artifact.created` events during the background task.

Key design decisions:
- **Event buffering**: `asyncio.Queue` per run. Background `run_turn()` task pushes events; `stream_events()` pulls. `_STREAM_DONE` sentinel signals completion.
- **Approval safety**: `_DANGEROUS_PERMISSION_KINDS = frozenset({"terminal", "execute_code"})` — same pattern as `ACPBackendAdapter`.
- **No architectural privilege**: the self-built core follows the same `BackendAdapter` contract as Hermes. Swapping `backend_id` requires zero channel/UI changes.
- **Concurrent runs**: each `submit_run` calls `provider_factory()` for a fresh provider instance, ensuring independent event streams.

### 3. `packages/agent-core/tests/test_backend_adapter.py`
23 tests covering all 9 BackendAdapter methods:

| # | Test | Description |
|---|------|-------------|
| 1 | `test_backend_id_returns_inkstatute` | `backend_id()` returns `"inkstatute"` |
| 2 | `test_capabilities_declares_streaming_cancel_approval` | capabilities declares streaming, cancel, approval, session memory |
| 3 | `test_capabilities_does_not_declare_fs_or_terminal` | no `fs/*` or `terminal/*` capabilities |
| 4 | `test_bootstrap_check_success` | `bootstrap_check()` returns `ok=True` when provider available |
| 5 | `test_bootstrap_check_failure_when_provider_unavailable` | `bootstrap_check()` returns `ok=False` when provider factory raises |
| 6 | `test_submit_run_returns_handle_with_running_status` | `submit_run()` returns `RunHandle` with `RUNNING` status |
| 7 | `test_get_run_after_submit` | `get_run()` returns correct run state after submit |
| 8 | `test_get_run_unknown_raises_keyerror` | `get_run()` raises `KeyError` for unknown run_id |
| 9 | `test_stream_events_yields_message_delta` | stream yields `message.delta` events |
| 10 | `test_stream_events_yields_message_completed` | stream yields `message.completed` event |
| 11 | `test_stream_events_yields_thought_delta` | stream yields `thought.delta` events |
| 12 | `test_stream_events_yields_tool_call_events` | stream yields `tool_call.started` and `tool_call.completed` |
| 13 | `test_stream_events_completes_with_terminal_state` | stream completes with `SUCCEEDED` status |
| 14 | `test_cancel_run_emits_state_changed` | `cancel_run()` emits `run.state_changed` to `cancelled` |
| 15 | `test_cancel_run_unknown_raises_keyerror` | `cancel_run()` raises `KeyError` for unknown run_id |
| 16 | `test_submit_approval_rejects_terminal` | `submit_approval()` rejects `terminal` auto-approval |
| 17 | `test_submit_approval_rejects_execute_code` | `submit_approval()` rejects `execute_code` auto-approval |
| 18 | `test_submit_approval_accepts_safe_permission` | `submit_approval()` accepts safe permission kinds |
| 19 | `test_collect_artifacts_empty_when_no_artifacts` | `collect_artifacts()` returns empty list when no artifacts |
| 20 | `test_collect_artifacts_returns_artifact_records` | `collect_artifacts()` returns `ArtifactRecord` list |
| 21 | `test_submit_run_with_fixture_provider_no_external_calls` | no external LLM calls — `FixtureProvider` used |
| 22 | `test_event_seq_is_monotonic` | event seq numbers are strictly monotonically increasing |
| 23 | `test_concurrent_runs_have_independent_event_streams` | two concurrent runs have independent event streams |

## Verification Results

- **New tests**: 23 passed (0.70s)
- **Full agent-core suite**: 808 passed (785 existing + 23 new)
- **V2 gates**: All gates green (exit code 0)
  - agent-core gate: 843 tests, OK (skipped=1)
  - All other gates: OK
- **No new pip dependencies**: only stdlib + existing project packages
- **No external LLM calls in tests**: `FixtureProvider` used throughout

## must_haves Verification

- ✅ InProcessAgentCoreAdapter implements all 9 BackendAdapter methods
- ✅ backend_id() returns 'inkstatute'
- ✅ capabilities() declares streaming, cancel, approval support but NOT fs/* or terminal/*
- ✅ bootstrap_check() returns BootstrapStatus with ok=True when provider is available
- ✅ submit_run() starts run_turn() as background task and returns RunHandle with RUNNING status
- ✅ stream_events() yields RunEvent objects in seq order until terminal state
- ✅ cancel_run() cancels the background task and emits run.state_changed to cancelled
- ✅ submit_approval() rejects auto-approval of terminal and execute_code permissions
- ✅ collect_artifacts() returns ArtifactRecord list from artifact.created events
- ✅ No external LLM calls in tests — FixtureProvider used throughout

## Key Links

- `backend_adapter.py` imports `run_turn` from `turn_loop.py`
- `backend_adapter.py` imports `EventEmitter` from `event_emitter.py`
- `backend_adapter.py` imports `AdapterCapabilitySet` from `platform_contract.agent_adapter`
- `backend_adapter.py` imports `BootstrapStatus, Run, RunEvent, RunHandle, RunRequest, Approval, ArtifactRecord` from `platform_runtime.protocols`
- `backend_config.py` imports `AgentCoreConfig` from `config.py`
- `backend_config.py` imports `LlmProvider` from `model.provider`
- `backend_config.py` imports `ToolExecutor` from `turn_loop.py`
