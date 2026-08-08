---
phase: 106-acp-fs-handler
plan: 02
status: complete
requirements: [FS-01, FS-02, FS-04]
---

# Plan 02: Client Capabilities + Inbound Request Routing + fs Handler - Summary

## What Was Built
- **ACPClient client_capabilities**: `ACPClient.__init__` now accepts an optional `client_capabilities: dict | None = None` parameter. When provided, `initialize()` includes `clientCapabilities` in the request params. When `None` (default), the key is absent — Gateway backward compatibility is preserved with zero behavior change.
- **Request handler registration**: `ACPClient.register_request_handler(method, handler)` stores sync handlers in a `_request_handlers` dict. `ACPClient.handle_inbound_request(msg)` dispatches inbound JSON-RPC requests (messages with both `id` and `method`) to registered handlers, sending the handler's return value as the JSON-RPC `result` response.
- **Unregistered handler safety**: When no handler is registered for an inbound request method, a JSON-RPC error with code `-32601` (method not found) is sent — the client does NOT raise or crash.
- **StdioACPTransport inbound request buffering**: `receive()` now buffers inbound requests (messages with both `id` and `method`) into a new `_request_buffer` list, separate from responses and notifications. Added `receive_inbound_request()` method. `receive_notification()` also routes inbound requests to the request buffer instead of treating them as notifications.
- **ACPBackendConfig.client_capabilities**: New optional field defaulting to `None`. `ACPBackendAdapter` passes `config.client_capabilities` to `ACPClient` in both `bootstrap_check` and `submit_run`.
- **FSReadHandler**: Concrete handler combining `FSSandbox` (5-layer path validation + size cap) with `ReferenceSanitizer` (delimiter wrapping + injection detection). Returns `{"content": sanitized_content}` on success, `{"error": {"code": -32602, "message": ...}}` on sandbox violations or missing path param.
- **create_fs_read_handler convenience function**: Builds a ready-to-use `FSReadHandler` with defaults from `fs_sandbox.py` constants.
- **__init__.py re-exports**: All 10 new symbols (`FSSandbox`, `FSSandboxConfig`, `FSSandboxError`, `DEFAULT_ALLOWED_EXTENSIONS`, `DEFAULT_MAX_FILE_SIZE`, `ReferenceSanitizer`, `SanitizationResult`, `INJECTION_PATTERNS`, `FSReadHandler`, `create_fs_read_handler`) are re-exported from the package root.

## Tasks Completed
- [x] Task 1: ACPClient client_capabilities + request handler registration + backward compat
- [x] Task 2: FSReadHandler + __init__ re-exports + handler integration tests

## Verification Results
- **Task 1 verify** (`test_client_capabilities.py`): 8/8 tests passed
  - Test 1: clientCapabilities sent when configured ✓
  - Test 2: clientCapabilities NOT sent when None ✓
  - Test 3: default ACPClient has _client_capabilities == None ✓
  - Test 4: ACPBackendConfig default client_capabilities == None ✓
  - Test 5: request handler dispatch ✓
  - Test 6: unregistered handler returns -32601 error ✓
  - Test 7: ACPBackendConfig accepts client_capabilities ✓
  - Test 8: adapter passes client_capabilities to ACPClient ✓
- **Task 1 backward compat** (`test_acp_client.py`): 8/8 existing tests still pass
- **Task 2 verify** (`test_fs_handler.py`): 10/10 tests passed
  - Test 1: handler reads valid file ✓
  - Test 2: handler rejects traversal (-32602) ✓
  - Test 3: handler rejects symlink (-32602) ✓
  - Test 4: handler rejects bad extension (-32602) ✓
  - Test 5: handler rejects oversized (-32602) ✓
  - Test 6: sanitized content has BEGIN/END delimiters ✓
  - Test 7: injection content still delivered with delimiters ✓
  - Test 8: full integration ACPClient + handler + mock transport ✓
  - Test 9: missing path param returns -32602 ✓
  - Extra: create_fs_read_handler builds ready handler ✓
- **Full acp-client test suite**: 107/107 tests passed
- **V2 gates**: 341/342 passed (1 pre-existing failure in `packages/channels/qqbot/tests/test_wakeup_recall.py` — unrelated to this phase, confirmed failing on prior commit)

## Artifacts Produced
- `ACPClient.__init__` parameter `client_capabilities: dict | None = None` — client.py
- `ACPClient.register_request_handler(method, handler)` method — client.py
- `ACPClient.handle_inbound_request(msg)` method — client.py
- `ACPClient._request_handlers` dict attribute — client.py
- `ACPClient._client_capabilities` attribute — client.py
- `StdioACPTransport._request_buffer` list attribute — client.py
- `StdioACPTransport.receive_inbound_request()` method — client.py
- `StdioACPTransport.receive()` updated to buffer inbound requests — client.py
- `StdioACPTransport.receive_notification()` updated to route inbound requests to request buffer — client.py
- `ACPBackendConfig.client_capabilities` field (default None) — adapter.py
- `ACPBackendAdapter` passes `config.client_capabilities` to ACPClient in `bootstrap_check` and `submit_run` — adapter.py
- `FSReadHandler` class — packages/acp-client/src/inkstatute_acp_client/fs_handler.py
- `create_fs_read_handler` function — fs_handler.py
- `ClientCapabilitiesTests` test class — packages/acp-client/tests/test_client_capabilities.py
- `BackwardCompatTests` test class — packages/acp-client/tests/test_client_capabilities.py
- `FSHandlerDispatchTests` test class — packages/acp-client/tests/test_fs_handler.py
- `FSHandlerIntegrationTests` test class — packages/acp-client/tests/test_fs_handler.py
- Updated `__all__` in packages/acp-client/src/inkstatute_acp_client/__init__.py (10 new symbols)

## Notes
- The `receive()` method now drains `_response_buffer` first (responses buffered by `receive_notification()`), then reads new lines. This ensures no responses are lost when `receive_notification()` encounters a response while polling.
- The `handle_inbound_request` method calls the handler synchronously (handlers are sync per the plan spec). The handler's return value is sent as the JSON-RPC `result`.
- The pre-existing V2 gate failure (`test_recall01_c2c_over_window_wakeup_omits_msg_id_on_wire`) is in the QQ bot channel package and is unrelated to this phase. It was confirmed failing on the commit prior to Task 1.
- Gateway backward compatibility is preserved: when `client_capabilities` is `None` (the default), no `clientCapabilities` key appears in the initialize request, so the Gateway path has zero behavior change.
