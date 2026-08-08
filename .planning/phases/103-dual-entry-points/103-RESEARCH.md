---
phase: 103
slug: dual-entry-points
status: planning
created: 2026-08-08
---

# Phase 103: Dual Entry Points — Research

## Goal

自研核心以一份实现提供两个入口，并在架构上与其他后端完全平等——换 `backend_id` 不需要改任何通道层或 UI 代码。

## Requirements

- CORE-10: 双入口（in-process BackendAdapter + `inkstatute-agent acp`）

## Success Criteria

1. in-process 入口：`backend_id="inkstatute"` 实现 `BackendAdapter` 9 方法，被 Gateway 直接调用，无 IPC 开销，完整可观测
2. ACP 入口：`inkstatute-agent acp` 可启动，`inkstatute-agent acp --check` 通过，能被标准 ACP 宿主（用本仓的 fixture ACP client 验证）连接并完成一轮对话
3. 两个入口共享同一份核心实现，无重复逻辑；有测试断言两条路径在同一输入下产生等价事件流
4. 后端可替换性验收通过：同一条律师任务分别用 `backend_id=hermes`（ACP）与 `backend_id=inkstatute`（in-process）跑通，通道层与 UI 代码零改动，事件流形状一致
5. ACP 入口正确声明能力（不声明 `fs/*` / `terminal/*`），并正确实现 `elicitation` 与 `request_permission` 的 agent 侧
6. 后端选择可经 `packages/operator-config` 配置，默认值可切换

## Integration Points

### BackendAdapter Protocol (9 methods)
Location: `packages/platform-runtime/src/platform_runtime/protocols.py:223-240`

```python
class BackendAdapter(Protocol):
    def backend_id(self) -> str: ...
    def capabilities(self) -> AdapterCapabilitySet: ...
    async def bootstrap_check(self) -> BootstrapStatus: ...
    async def submit_run(self, req: RunRequest) -> RunHandle: ...
    async def get_run(self, run_id: str) -> Run: ...
    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]: ...
    async def cancel_run(self, run_id: str) -> Run: ...
    async def submit_approval(self, run_id: str, approval: Approval) -> Run: ...
    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]: ...
```

### Reference Implementation: ACPBackendAdapter
Location: `packages/acp-client/src/inkstatute_acp_client/adapter.py`

Key patterns to follow:
- `ACPBackendConfig` frozen dataclass for configuration
- Per-session subprocess spawning in `submit_run()`
- Background event collection with asyncio tasks
- `_DANGEROUS_PERMISSION_KINDS` safety in `submit_approval()`
- `bootstrap_check()` returns `BootstrapStatus` with ok/issues

### Agent Core Turn Loop
Location: `packages/agent-core/src/inkstatute_agent_core/turn_loop.py`

`run_turn()` is an async generator yielding `RunEvent` objects. It takes:
- `messages`, `tools`, `provider` (LlmProvider), `emitter` (EventEmitter), `config` (AgentCoreConfig), `tool_executor`, `run_id`, `phase`

The in-process adapter needs to:
1. Create an EventEmitter
2. Create a model provider (from config)
3. Build messages from RunRequest
4. Start `run_turn()` as a background task
5. Buffer events for `stream_events()`

### ACP Server Protocol (from echo_agent.py fixture)
Location: `packages/acp-client/tests/fixtures/echo_agent.py`

The ACP server reads JSON-RPC 2.0 from stdin line-by-line:
- `initialize` → respond with protocolVersion, agentInfo, capabilities
- `session/new` → respond with sessionId
- `session/prompt` → emit `session/update` notifications, then respond
- `session/cancel` → respond
- `session/close` → respond

The ACP server needs to:
1. Map incoming ACP `session/prompt` to agent-core's `run_turn()`
2. Map `RunEvent` stream back to ACP `session/update` notifications
3. Handle `elicitation/create` and `session/request_permission` agent-side

### Event Mapping (ACP ↔ Unified Events)
Location: `packages/acp-client/src/inkstatute_acp_client/event_mapping.py`

ACP update types → RunEventType:
- `agent_message_chunk` → `message.delta`
- `agent_message` → `message.completed`
- `agent_thought_chunk` → `thought.delta`
- `plan` / `plan_update` → `plan.updated`

The ACP server needs the **reverse mapping**: RunEventType → ACP update types.

### Operator Config
Location: `packages/operator-config/src/inkstatute_operator_config/`

Currently has no backend selection schema. Need to add:
- `BackendSelectionDoc` schema for default backend_id configuration
- Resolver to read and apply backend selection

### Gateway Integration
Location: `services/gateway/src/gateway/app.py`

Gateway passes `backend_id` from `SolutionBinding` in `RunRequest` to the injected `RunRuntime`. The runtime has a single injected `BackendAdapter`. For dual-backend support, the runtime (or a factory) needs to select the adapter based on `backend_id`.

## Architectural Decisions

1. **One implementation, two entry points** — both the in-process adapter and the ACP server call the same `run_turn()` function. No logic duplication.
2. **No architectural privilege** — the self-built core is the default backend but follows the same `BackendAdapter` contract as Hermes.
3. **ACP v1 protocol** — the ACP server speaks protocol v1, same as the client expects.
4. **Safety** — the ACP server must NOT declare `fs/*` or `terminal/*` capabilities. Permission requests for dangerous kinds must be escalated, not auto-approved.

## Plan Structure

### Plan 103-01: In-Process BackendAdapter
- `InProcessAgentCoreAdapter` implementing all 9 BackendAdapter methods
- `AgentCoreBackendConfig` dataclass
- Model provider factory from config
- Event buffering with asyncio.Queue
- Tests: all 9 methods, event streaming, cancellation, approval safety

### Plan 103-02: ACP Server Entry Point
- `inkstatute-agent acp` CLI (`__main__.py`)
- ACP server protocol handler (initialize, session/new, session/prompt, session/cancel, session/close)
- Reverse event mapping (RunEvent → ACP session/update)
- `--check` flag for bootstrap verification
- Elicitation and permission request agent-side handling
- Tests: ACP protocol compliance, event mapping, --check, elicitation, permission

### Plan 103-03: Equivalence + Operator Config + Phase Completion
- Equivalence tests: same input → same event stream shape via both entry points
- Backend selection schema in operator-config
- Backend selection resolver
- Backend interchangeability test (hermes vs inkstatute, same task)
- Success criteria mapping tests
- Phase completion
