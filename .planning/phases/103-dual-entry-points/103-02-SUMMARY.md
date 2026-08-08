---
phase: 103
plan: 02
title: ACP Server Entry Point
status: complete
created: 2026-08-08
---

# Plan 103-02 Summary: ACP Server Entry Point

## Objective

Implement `inkstatute-agent acp` — a CLI entry point that speaks ACP v1 over stdio, allowing the agent-core to be driven by any standard ACP client. This proves the self-built core has no architectural privilege: it can be used in-process OR as an ACP subprocess, just like Hermes.

## Files Created/Modified

### Created
1. **`packages/agent-core/src/inkstatute_agent_core/acp_server.py`** — ACP server protocol handler
   - `ACPServer` class: reads JSON-RPC 2.0 from stdin, responds over stdout
   - Protocol methods: `initialize`, `session/new`, `session/prompt`, `session/cancel`, `session/close`
   - `map_run_event_to_acp_update()`: reverse event mapping (RunEvent → ACP session/update)
   - `map_run_event_to_acp_request()`: elicitation/permission request forwarding
   - `run_check()`: bootstrap check for `--check` flag
   - `default_provider_factory()`: creates model provider from env vars
   - `SessionState`: in-memory session tracking dataclass

2. **`packages/agent-core/src/inkstatute_agent_core/__main__.py`** — CLI entry point
   - `argparse`-based CLI with `acp` subcommand
   - `inkstatute-agent acp` → start ACP server
   - `inkstatute-agent acp --check` → bootstrap check, exit 0/1
   - `inkstatute-agent --version` → print version

3. **`packages/agent-core/tests/test_acp_server.py`** — 35 tests covering:
   - initialize protocol response (7 tests)
   - session/new (1 test)
   - session/prompt streaming (3 tests)
   - session/cancel and session/close (2 tests)
   - unknown method handling (1 test)
   - --check flag (2 tests)
   - reverse event mapping (10 tests)
   - elicitation/permission mapping (4 tests)
   - full ACP round-trip with FixtureProvider (1 test)
   - ACPClient integration via subprocess (1 test, skipped when acp-client not on PYTHONPATH)
   - CLI entry point (3 tests)

### Modified
4. **`packages/agent-core/pyproject.toml`** — added `[project.scripts]` section:
   ```toml
   [project.scripts]
   inkstatute-agent = "inkstatute_agent_core.__main__:main"
   ```

## Key Implementation Details

### ACP Server Architecture
- Uses `asyncio` with `asyncio.to_thread()` for blocking stdin reads
- Main loop: read line → parse JSON-RPC → dispatch to handler → write response
- `session/prompt` runs `run_turn()` async generator, maps each RunEvent to ACP notification
- Injectable stdin/stdout for testability (TextIO streams)

### Capabilities Declared
```python
AGENT_CAPABILITIES = {
    "streaming": True,
    "elicitation": True,
    "permissions": True,
}
```
Does NOT declare `fs/*` or `terminal/*` (AGENTS.md safety rule).

### Reverse Event Mapping (RunEvent → ACP session/update)
| RunEvent Type | ACP Update Type |
|---|---|
| `message.delta` | `agent_message_chunk` |
| `message.completed` | `agent_message` |
| `thought.delta` | `agent_thought_chunk` |
| `tool_call.started` | `tool_call_update` (status=started) |
| `tool_call.delta` | `tool_call_update` (content) |
| `tool_call.completed` | `tool_call_update` (status=completed) |
| `plan.updated` | `plan` |
| `phase.changed` | `plan` (folded) |
| `error` | `error` |
| `run.state_changed` | (not forwarded — internal) |

### Elicitation and Permission Agent-Side
- `elicitation.requested` → `elicitation/create` JSON-RPC request to client
- `permission.requested` → `session/request_permission` JSON-RPC request to client
- Dangerous permissions (`terminal`, `execute_code`) are NEVER auto-approved — no `auto_approve` or `default_decision` fields in the request

### --check Flag
- Tries to create a model provider from `default_provider_factory()`
- Success: prints "InkStatute ACP check OK", exit 0
- Failure: prints error to stderr, exit 1
- Matches `hermes acp --check` pattern

### Integration Test
- Uses `ACPClient` from `packages/acp-client/` to drive the agent-core ACP server via subprocess
- Spawns `python -c` with inline script that creates `ACPServer` with a `FixtureProvider`
- Verifies: initialize → session/new → session/prompt → message.completed
- Gracefully skips when `inkstatute_acp_client` is not importable (V2 gate compatibility)

## Verification Results

### New Tests
- **35 tests** in `test_acp_server.py` — all pass
- Test command: `PYTHONPATH=packages/agent-core/src:packages/agent-core/tests:packages/platform-contract/src:packages/platform-runtime/src:packages/model-gateway/src:packages/acp-client/src python -m pytest packages/agent-core/tests/test_acp_server.py -q`

### Full Agent-Core Suite
- **843 tests passed** (785 original + 35 new + 23 from 103-01)
- No regressions

### V2 Gates
- All 35 gates pass (exit code 0)
- agent-core gate: `OK (skipped=1)` — the 1 skip is the integration test (graceful skip when acp-client not on PYTHONPATH)

## Success Criteria Met

- [x] `inkstatute-agent acp` starts and responds to initialize with protocolVersion 1
- [x] ACP server declares streaming, elicitation, permissions but NOT fs/* or terminal/*
- [x] session/prompt emits agent_message_chunk and agent_message notifications
- [x] `inkstatute-agent acp --check` works (exit 0 when OK, exit 1 when provider unavailable)
- [x] Reverse event mapping converts RunEvent types to ACP session/update types
- [x] ACP server can be driven by standard ACPClient (integration test)
- [x] All 35 new tests pass
- [x] Full test suite remains green (843 passed)
- [x] V2 gates remain green (35 gates OK)
- [x] No new pip dependencies (stdlib only: asyncio, json, sys, argparse, os, uuid, io)
- [x] ACP server shares the same `run_turn()` implementation as the in-process adapter
- [x] Elicitation requests forwarded as `elicitation/create`
- [x] Permission requests forwarded as `session/request_permission`
- [x] Dangerous permissions (terminal, execute_code) never auto-approved
