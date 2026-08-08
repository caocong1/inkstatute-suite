---
phase: 90
status: complete
researched_at: 2026-08-07T16:00:00Z
---

# Phase 90 Research — ACP Event Bridge & Output Boundary

## §1 Reverse Mapping — Exact ACP Methods for User Responses

**Key Finding:** ACP v1 does NOT use separate methods for user responses. Instead, responses are JSON-RPC responses to the original request IDs.

### Elicitation Answers
There is NO `elicitation/answer` method. The response to `elicitation/create` is a JSON-RPC response with the original request `id`:
```json
{
  "jsonrpc": "2.0",
  "id": "<original_elicitation_create_id>",
  "result": {
    "action": "accept" | "decline" | "cancel",
    "content": { "user_provided_data": "..." }
  }
}
```

### Permission Decisions
There is NO separate method. The response to `session/request_permission` is a JSON-RPC response:
```json
{
  "jsonrpc": "2.0",
  "id": "<original_request_permission_id>",
  "result": {
    "outcome": {
      "outcome": "selected" | "cancelled",
      "optionId": "<selected_option_id>"
    }
  }
}
```

### Cancellation
ACP client already has `cancel(session_id)` at `client.py:339-343` which sends `session/cancel`.

### What ACP Client Already Supports
The ACP client (`client.py`) has methods for `initialize`, `new_session`, `prompt`, `cancel`, `close_session` but does NOT have methods for sending user responses to elicitation/permission requests. The bridge must construct JSON-RPC responses directly via the transport's `send()` method.

## §2 Output Boundary Rules — ACP-Specific Blocked Content Categories

### Requirements
The requirements list these blocked categories: meta, gateway, system, update, command, help, available_commands_update, terminal.

### Mapping to ACP
These are NOT separate ACP notification types. They are content patterns that appear in:
- `session/update` notifications (in the `content` field of `agent_message_chunk` or `agent_thought_chunk`)
- `_meta` fields of tool call updates
- Debug/diagnostic notifications from the ACP agent

### Existing Rules in output_boundary.py
- **Already blocks:** `admin_notice`, `stack trace`, `traceback`, `token=`, secret patterns, internal paths, provider leaks, debug traces
- **Already rewrites:** backend lifecycle notices, tool progress, approval requests, debug traces, rate limit notices, context window notices
- **Already blocks operator commands:** `/[a-z][a-z0-9_-]*` pattern

### New Rules Needed
- Add ACP-specific patterns for: `meta:`, `gateway:`, `system:`, `update:`, `command:`, `help:`, `available_commands_update`, `terminal` content
- Add to `_HARD_BLOCK_RULES` in `output_boundary.py` or as ACP-specific pre-filtering in the bridge's `output_filter.py`
- Default-deny policy for unknown ACP notification types (explicit allowlist for known types)

## §3 Bidirectional Roundtrip Testing — Test Strategy

### Test Fixtures Needed
- ACP notification fixtures for each variant: `agent_message_chunk`, `agent_message`, `agent_thought_chunk`, `tool_call_update` (all statuses), `plan`, `plan_update`, `elicitation`, `status`, artifact content blocks, citation in `_meta`
- User response fixtures: elicitation responses (accept/decline/cancel with content), permission responses (selected/cancelled with optionId)
- Backend noise fixtures: meta, gateway, system, update, command, help, available_commands_update, terminal content

### Roundtrip Test Approach
1. Start with ACP notification fixture
2. Apply forward mapping (`map_acp_update_to_run_event`) → unified event
3. Apply reverse mapping (`map_unified_to_acp`) → ACP response/notification
4. Verify semantic equivalence:
   - For elicitation: interrupt_id, questions, intro, resume_state_ref must match
   - For permission: permission_id, tool_call_id, description, kind must match
   - For tool calls: tool_call_id, tool_name, status, content must match
   - For messages: message_id, content must match

### Test Location
`packages/acp-event-bridge/tests/test_bridge.py`

## §4 Secrets & Privacy Scanning — Patterns and Test Approach

### Existing Secret Patterns in output_boundary.py
- `secret_like`: `(?:access|refresh|api|client|encoding)[_-]?(?:token|key|secret)`, `(?:token|secret|key)\s*[:=]`
- `internal_path`: `(?:^|\s)(?:/[^ \n\t]+){2,}`, `[a-z]:\\[^ \n\t]+`
- `debug_trace`: `admin_notice|stack trace|traceback|delivery debug|runtime detail`
- `provider_leak`: `model[:\s]|provider[:\s]|api[_-]?key|quota|token[_\s-]?usage`
- `api_error`: `api key invalid|quota exceeded|rate limit retry|insufficient quota`
- `function_trace`: `function call|tool output|token usage report|function_call_result`

### ACP-Specific Patterns to Add
- `HERMES_HOME` paths: `/home/[^/]+/\.hermes`, `\.hermes[^/]`
- ACP subprocess env vars: `HERMES_HOME`, `ACP_.*`, `AGENT_.*` with secret patterns
- ACP-specific debug content: `acp:`, `agent-client-protocol:`, `session/update` debug fields

### Test Approach
- Create `packages/acp-event-bridge/tests/test_privacy_scan.py`
- Scan all bridge output events (both forward and reverse mapped)
- Assert no secret patterns match
- Assert all events use `raw_payload_ref` instead of full text
- Test with fixture events containing intentional secrets to verify they are blocked

## §5 Package Structure — Module Layout and Dependencies

### New Package
```
packages/acp-event-bridge/
├── pyproject.toml
├── src/inkstatute_acp_event_bridge/
│   ├── __init__.py
│   ├── bridge.py              # EventBridge class: forward + reverse mapping, output boundary integration
│   ├── reverse_mapping.py     # map_unified_to_acp() functions for user responses
│   ├── output_filter.py       # ACP-specific output boundary rules (blocked notification types)
│   └── privacy_scan.py        # Secrets scanning for bridge output events
└── tests/
    ├── __init__.py
    ├── test_bridge.py          # Bidirectional mapping tests
    ├── test_output_filter.py   # Output boundary enforcement tests
    ├── test_privacy_scan.py    # Secrets scanning tests
    └── fixtures/
        ├── acp_notifications.json
        ├── user_responses.json
        └── backend_noise.json
```

### Dependencies
- `acp-client` (for forward mapping reference and ACP client types)
- `platform-contract` (for RunEventType, unified events, protocols)
- `platform-runtime` (for output_boundary, protocols)
- No external dependencies — all are internal packages

## §6 ACP Protocol Details — Exact Method Names and Message Formats

### Elicitation Response Format
```json
{
  "jsonrpc": "2.0",
  "id": "<original_elicitation_create_id>",
  "result": {
    "action": "accept" | "decline" | "cancel",
    "content": { "user_provided_data": "..." }
  }
}
```

### Permission Response Format
```json
{
  "jsonrpc": "2.0",
  "id": "<original_request_permission_id>",
  "result": {
    "outcome": {
      "outcome": "selected" | "cancelled",
      "optionId": "<selected_option_id>"
    }
  }
}
```

### Cancellation
- Method: `session/cancel`
- Params: `{"sessionId": "<session_id>"}`
- Already implemented in `client.py:339-343`

### Source
ACP v1 specification at https://agentclientprotocol.com/protocol/v1/

## §7 Gate Registration — Exact Gate Entry to Add

### Location: scripts/run_v2_gates.py

Add path variable:
```python
acp_event_bridge_src = repo_root / "packages" / "acp-event-bridge" / "src"
```

Add gate entry:
```python
Gate(
    "acp-event-bridge",
    (py, "-m", "unittest", "discover", "-s", "packages/acp-event-bridge/tests"),
    (acp_event_bridge_src, acp_client_src, platform_src, platform_runtime_src),
),
```

Add to compileall gate:
```python
"packages/acp-event-bridge/src",
```

Add to gate-coverage-meta-test path list:
```python
"packages/acp-event-bridge/src",
```

## §8 Risk Assessment — Technical Risks and Mitigations

| # | Risk | Mitigation |
|---|------|------------|
| 1 | ACP v2 breaking changes to elicitation/permission response formats | Lock protocol v1 (already done), add version check in bridge |
| 2 | Lossy roundtrip mapping | Comprehensive roundtrip tests with golden fixtures, field-by-field equivalence |
| 3 | Permission auto-approval bypass | Double-layer enforcement (adapter + bridge), test assertions for no `allow_once`/`auto_approve` |
| 4 | Secret leakage in bridge events | Privacy scan tests, reference-first logging, audit all event payloads |
| 5 | New ACP notification types bypass boundary | Default-deny for unknown types, explicit allowlist for known types |
| 6 | JSON-RPC response ID correlation lost | Bridge maintains request_id → unified event mapping, uses original request ID in responses |
