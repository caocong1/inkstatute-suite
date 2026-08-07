---
phase: 89
slug: acp-backend-client
status: complete
created: 2026-08-07
---

# Phase 89 — Technical Research

## 1. BackendAdapter Protocol Analysis

The 9-method Protocol is defined in `packages/platform-runtime/src/platform_runtime/protocols.py` (lines 222-239):

| Method | Sync/Async | Returns | Purpose |
|--------|-----------|---------|---------|
| `backend_id()` | sync | `str` | Unique backend identifier |
| `capabilities()` | sync | `AdapterCapabilitySet` | Declared capabilities |
| `bootstrap_check()` | async | `BootstrapStatus` | Health/version check |
| `submit_run(req)` | async | `RunHandle` | Start a run |
| `get_run(run_id)` | async | `Run` | Get run state |
| `stream_events(run_id)` | async | `AsyncIterator[RunEvent]` | Stream events |
| `cancel_run(run_id)` | async | `Run` | Cancel a run |
| `submit_approval(run_id, approval)` | async | `Run` | Submit approval response |
| `collect_artifacts(run_id)` | async | `list[ArtifactRecord]` | Collect artifacts |

## 2. Current Backend Patterns

### Hermes Backend (packages/backends/hermes/)
- 423 lines, in-memory run state (`self._runs: dict[str, Run]`)
- Injected runner pattern (`HermesOneShotRunner`)
- Metadata sanitization to block sensitive fields
- `bootstrap_check` returns capability metadata
- **No streaming support** — this is the defect ACP client fixes (AGENTS.md #7: "Tool rounds must stream")

### Codex Backend (packages/backends/codex/)
- 413 lines adapter + 455 lines exec_runner
- Subprocess-based with JSONL parsing
- Streaming support via `StreamingCodexExecRunner`
- Timeout handling, transport abstraction for testability
- **This is the pattern to follow** for subprocess lifecycle

### Common Patterns to Reuse
- In-memory `_runs: dict[str, Run]` for state management
- Metadata sanitization (block sensitive fields)
- `BootstrapStatus` with capability metadata
- Transport abstraction for testability

## 3. ACP Protocol Mapping

### ACP session/update → Unified Events (from Phase 88)

| ACP Variant | Unified Event | Bot Degradation |
|---|---|---|
| session/new response | session.started | silent |
| agent_message_chunk | message.delta | buffer |
| agent_message (v2) | message.completed | deliver |
| agent_thought_chunk | thought.delta | discard |
| tool_call_update | tool_call.started/delta/completed | fold |
| plan/plan_update | plan.updated | first-then-silent |
| _meta extension | phase.changed | same as plan |
| elicitation/create | elicitation.requested | deliver as card |
| session/request_permission | permission.requested | deliver as approval card |
| Artifact content block | artifact.created | deliver as file |
| _meta extension | citation.recorded | attach to final |
| status update | run.state_changed | on-failure deliver |
| JSON-RPC error | error | deliver business prompt |

### ACP SDK Details
- PyPI `agent-client-protocol` 0.12.0 available (Python 3.10-3.14)
- ACP v1 stable, v2 draft with breaking changes
- Must use `use_unstable_protocol=True` for elicitation support
- Hermes ACP verified: `hermes acp --check` → OK (v0.19.0)
- HERMES_HOME must be explicitly set (active_profile sticky file not respected by ACP subprocess)

## 4. Subprocess Lifecycle Design

### Per-Session Mode (the only implemented mode)
```
Session Start → spawn ACP subprocess (stdio) → initialize → negotiate capabilities
  → session/new → prompt → stream session/update → ... → session/close
  → subprocess terminate → cleanup
```

### Lifecycle Controls
- **Session-end recovery:** `session/close` → terminate subprocess → wait → kill if timeout
- **Timeout recovery:** watchdog timer → terminate → restart if run still active
- **Crash restart:** detect subprocess exit → if run active, restart with `session/load` (if supported) or fail run
- **No process leaks:** `atexit` handler + context manager + orphan detection tests

### Orphan Detection Test
- Spawn subprocess, record PID
- Close session
- Assert PID no longer exists after cleanup timeout
- Run with multiple sessions, assert all PIDs cleaned

## 5. Capability Negotiation

### ACP initialize → AdapterCapabilitySet
ACP `initialize` response includes `capabilities` object. Map to `AdapterCapabilitySet`:
- `streaming` → ACP supports `session/update` streaming
- `elicitation` → ACP supports `elicitation/create` (requires `use_unstable_protocol=True`)
- `permissions` → ACP supports `session/request_permission`
- `artifacts` → ACP supports artifact content blocks
- `citations` → ACP supports `_meta` citation extension

### Explicit Rejection (not silent degradation)
If required capabilities are missing:
- Raise `CapabilityMismatchError` with details
- Do NOT proceed with degraded behavior
- Log the rejection reason

## 6. Fixture Agent Design

### In-Repo Echo Agent
Create `packages/acp-client/tests/fixtures/echo_agent.py`:
- Minimal ACP server implementation (stdio JSON-RPC)
- Responds to `initialize`, `session/new`, `session/prompt`, `session/update`, `session/cancel`, `session/close`
- Echoes prompt back as `agent_message_chunk` → `agent_message`
- Supports configurable capabilities (for testing rejection)
- No external dependencies (pure Python stdio)

### Test Strategy
- All tests use the echo agent fixture — no network, no external agent
- Test capability negotiation with configurable echo agent
- Test subprocess lifecycle with echo agent
- Test event mapping with echo agent producing known ACP events

## 7. Gate Registration

Add to `scripts/run_v2_gates.py` `_gates()` function:
```python
acp_client_src = repo_root / "packages" / "acp-client" / "src"
Gate(
    "acp-client",
    (py, "-m", "unittest", "discover", "-s", "packages/acp-client/tests"),
    (acp_client_src, platform_src, contract_src, platform_runtime_src),
),
```
Also add to compileall parameters and gate-coverage meta-test allowlist.

## 8. Validation Architecture

### Test Layers
1. **Unit tests** — ACP event mapping, capability negotiation logic (pure functions, no subprocess)
2. **Integration tests** — echo agent fixture, subprocess lifecycle, full BackendAdapter Protocol
3. **Gate** — `acp-client` gate in run_v2_gates.py

### Test Commands
- `python -m pytest packages/acp-client/tests/ -x` — full test suite
- `python scripts/run_v2_gates.py` — all 28+1 gates green

## 9. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| ACP SDK version 0.12.0 compatibility | Pin version in pyproject.toml, test with echo agent |
| Elicitation is UNSTABLE in ACP | Use `use_unstable_protocol=True`, implement `_meta` fallback |
| Subprocess leaks | Context manager + atexit + orphan detection tests |
| Permission auto-approve (Buzz failure) | Explicitly reject terminal/execute_code, never auto-allow |
| Hermes profile loading | Explicitly set HERMES_HOME env var |
| ACP v2 breaking changes | Lock v1 at initialize, flag off v2 features |

## 10. File Inventory

### New Files to Create
- `packages/acp-client/pyproject.toml` — package config with agent-client-protocol dependency
- `packages/acp-client/src/inkstatute_acp_client/__init__.py` — package exports
- `packages/acp-client/src/inkstatute_acp_client/client.py` — ACP client (stdio transport, initialize, session management)
- `packages/acp-client/src/inkstatute_acp_client/adapter.py` — BackendAdapter 9-method implementation
- `packages/acp-client/src/inkstatute_acp_client/lifecycle.py` — subprocess lifecycle management
- `packages/acp-client/src/inkstatute_acp_client/capability_negotiation.py` — capability mapping + rejection
- `packages/acp-client/src/inkstatute_acp_client/event_mapping.py` — ACP session/update → unified events
- `packages/acp-client/src/inkstatute_acp_client/process_mode.py` — backend_process_mode enum
- `packages/acp-client/tests/fixtures/echo_agent.py` — in-repo fixture ACP agent
- `packages/acp-client/tests/test_acp_client.py` — client tests
- `packages/acp-client/tests/test_adapter.py` — BackendAdapter Protocol tests
- `packages/acp-client/tests/test_lifecycle.py` — subprocess lifecycle + orphan detection tests
- `packages/acp-client/tests/test_capability_negotiation.py` — capability negotiation + rejection tests
- `packages/acp-client/tests/test_event_mapping.py` — ACP → unified event mapping tests

### Files to Modify
- `scripts/run_v2_gates.py` — add acp-client gate
- `packages/platform-contract/src/platform_contract/agent_adapter.py` — add backend_process_mode enum (if not present)

### Files to Reference (not modify)
- `packages/platform-runtime/src/platform_runtime/protocols.py` — BackendAdapter Protocol
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` — current Hermes pattern
- `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py` — subprocess pattern
- `packages/platform-contract/src/platform_contract/unified_events.py` — Phase 88 events
