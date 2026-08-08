---
phase: 89-acp-backend-client
plan: 01
subsystem: backend
title: ACP Client Core — Stdio Transport, Initialize Negotiation, Event Mapping, Echo Agent Fixture
tags: [acp, stdio, client, protocol-v1, capability-negotiation, event-mapping, echo-agent]
requires: []
provides:
  - packages/acp-client — Python ACP v1 client package with stdio transport
  - ACPClient — initialize, new_session, prompt, stream_updates, cancel, close_session, shutdown
  - StdioACPTransport — asyncio.subprocess-based stdio transport implementing ACPTransport Protocol
  - capability_negotiation.py — negotiate(), CapabilityMismatchError, RequiredCapabilities, CapabilityNegotiationResult
  - event_mapping.py — map_acp_update_to_run_event() covering all 13 ACP variant types
  - echo_agent.py — standalone stdio JSON-RPC echo agent fixture for CI (stdlib only)
  - 32 unit/integration tests (9 capability negotiation + 15 event mapping + 8 ACP client)
  - acp-client gate registered in scripts/run_v2_gates.py (gate #29)
affects: [89-02, 89-03, 89-04]
key-files:
  - packages/acp-client/pyproject.toml
  - packages/acp-client/src/inkstatute_acp_client/__init__.py
  - packages/acp-client/src/inkstatute_acp_client/client.py
  - packages/acp-client/src/inkstatute_acp_client/capability_negotiation.py
  - packages/acp-client/src/inkstatute_acp_client/event_mapping.py
  - packages/acp-client/tests/fixtures/echo_agent.py
  - packages/acp-client/tests/test_capability_negotiation.py
  - packages/acp-client/tests/test_event_mapping.py
  - packages/acp-client/tests/test_acp_client.py
  - scripts/run_v2_gates.py
  - packages/contract-test-suite/tests/test_audit_v2_requirements.py
key-decisions:
  - "ACP v1 lock: negotiate() rejects protocolVersion != 1 with CapabilityMismatchError"
  - "No silent degradation: all missing required capabilities collected before raising"
  - "Permission requests never auto-approved: permission.requested payload has NO auto_approve or default_decision"
  - "Echo agent fixture uses stdlib only (sys, json, uuid, os) — no external deps for CI"
  - "PyPI agent-client-protocol installs as module 'acp' (not agent_client_protocol) — deviation noted"
  - "Gate registered in Plan 01 (not Plan 04) to satisfy gate-coverage meta-test immediately"
patterns-established:
  - "ACPTransport Protocol abstraction for testability (like Codex SubprocessTransport)"
  - "Incrementing JSON-RPC ids starting at 1, all messages include jsonrpc 2.0"
  - "stream_updates as async generator yielding RunEvent via event_mapping"
  - "Capability mismatch closes transport and re-raises (no resource leak)"
  - "Echo agent capabilities configurable via ECHO_AGENT_CAPABILITIES env var"
requirements-completed: [ACP-01]
coverage:
  tests: 32
  test_files: 3
  gates: 29
  gate_status: all-green
duration: ~45min
completed: "2026-08-07"
status: complete
---

# Plan 89-01 Summary: ACP Client Core

## What Was Built

Created the `packages/acp-client` package — a Python ACP v1 client that drives any ACP-speaking agent as a backend over stdio. This is the tracer slice for Phase 89; every subsequent plan (89-02 adapter, 89-03 lifecycle, 89-04 second backend) builds on this client core.

### Package Structure

```
packages/acp-client/
├── pyproject.toml                          # agent-client-protocol>=0.12,<0.13
├── src/inkstatute_acp_client/
│   ├── __init__.py                         # Public API exports (9 names)
│   ├── client.py                           # ACPClient, StdioACPTransport, ACPTransport
│   ├── capability_negotiation.py           # negotiate(), CapabilityMismatchError, etc.
│   └── event_mapping.py                    # map_acp_update_to_run_event() — 13 mappings
└── tests/
    ├── fixtures/echo_agent.py              # Standalone stdio JSON-RPC echo agent
    ├── test_capability_negotiation.py      # 9 tests
    ├── test_event_mapping.py               # 15 tests
    └── test_acp_client.py                  # 8 integration tests
```

### Key Components

1. **StdioACPTransport** — Spawns ACP agent subprocess via `asyncio.create_subprocess_exec`, sends newline-delimited JSON-RPC on stdin, reads responses/notifications from stdout. Tracks PID, terminates then kills on close.

2. **ACPClient** — High-level client with `initialize()` (locks v1, negotiates capabilities), `new_session()`, `prompt()`, `stream_updates()` (async generator yielding `RunEvent`), `cancel()`, `close_session()`, `shutdown()`.

3. **capability_negotiation.py** — Maps ACP `initialize` response capabilities to `AdapterCapabilitySet`. Rejects `protocolVersion != 1` and any missing required capability via `CapabilityMismatchError`. Never silently degrades — collects ALL missing caps before raising.

4. **event_mapping.py** — Maps all 13 ACP `session/update` variant types to Phase 88 unified event types: `agent_message_chunk`→`message.delta`, `agent_message`→`message.completed`, `agent_thought_chunk`→`thought.delta`, `tool_call_update`→`tool_call.started/delta/completed`, `plan`/`plan_update`→`plan.updated`, `elicitation`→`elicitation.requested`, `session/request_permission`→`permission.requested` (NO auto_approve), artifact→`artifact.created`, `_meta.citation`→`citation.recorded`, `status`→`run.state_changed`, JSON-RPC error→`error`.

5. **echo_agent.py** — Standalone Python script (stdlib only: `sys`, `json`, `uuid`, `os`) that responds to `initialize`, `session/new`, `session/prompt`, `session/cancel`, `session/close`. Capabilities configurable via `ECHO_AGENT_CAPABILITIES` env var.

### Gate Registration

Added `acp-client` gate (#29) to `scripts/run_v2_gates.py` with PYTHONPATH including `acp_client_src`, `platform_src`, and `platform_runtime_src`. Also added `packages/acp-client/src` to the compileall gate. Updated gate count assertion from 28 to 29.

## Deviations

1. **SDK import name:** The plan specified `python -c "import agent_client_protocol"` as an acceptance criterion. The PyPI package `agent-client-protocol` 0.12.0 installs the module as `acp`, not `agent_client_protocol`. Verified with `python -c "import acp"`. This is a factual property of the SDK, not a design choice. The `pyproject.toml` dependency is correctly `agent-client-protocol>=0.12,<0.13`.

2. **Gate registration in Plan 01 (not Plan 04):** The plan's binding constraint #4 stated "gate added in Plan 04". However, the gate-coverage meta-test enforces that every `packages/*/src` directory is covered by a gate (AGENTS.md coding rule). Adding the gate in Plan 01 prevents the 28 existing gates from going red. The gate was registered here with the same pattern that Plan 04 would have used.

## Self-Check: PASSED

- [x] All 6 tasks executed and committed
- [x] All acceptance_criteria verified PASS
- [x] packages/acp-client package created with pyproject.toml
- [x] ACP client with stdio transport, initialize, session management
- [x] Capability negotiation with explicit rejection (no silent degradation)
- [x] Event mapping (13 ACP session/update variants → unified events)
- [x] Echo agent fixture for CI (stdlib only, no network/external agents)
- [x] Unit tests pass (32 tests: 9 + 15 + 8)
- [x] Existing 28 gates still green (now 29 gates with acp-client gate added)
- [x] `python -m pytest packages/acp-client/tests/ -x` passes
- [x] `python scripts/run_v2_gates.py` passes (all 29 gates green)
- [x] `python -m compileall packages/acp-client/src` exits 0
- [x] Protocol v1 locked at initialize — negotiate rejects protocolVersion != 1
- [x] Permission request payload has NO auto_approve or default_decision

## Commit Hashes

| Task | Commit | Description |
|------|--------|-------------|
| 89-01-01 | 6f2f4ac | Scaffold package, pin SDK, echo agent fixture |
| 89-01-02 | 808c94c | Capability negotiation with explicit rejection |
| 89-01-03 | ad2bf31 | Event mapping — ACP session/update → unified RunEvent |
| 89-01-04 | db6fe0a | ACP stdio client with initialize, session lifecycle, streaming |
| 89-01-05 | 0a3d43a | Unit tests for capability negotiation, event mapping, ACP client |
| 89-01-06 | 145ebd4 | Update __init__.py with public API exports |
| gate | d08889a | Register acp-client gate and update gate count to 29 |
