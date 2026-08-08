# Summary: Plan 101-02 — File Reading + MCP Client + Regulation Search

**Phase**: 101 (agent-core-tools)
**Plan**: 101-02
**Wave**: 2 (depends on 101-01; runs in parallel with 101-03)
**Requirements**: CORE-02 (partial — file reading tool, regulation search via MCP, MCP client)
**Status**: COMPLETE
**Date**: 2026-08-11

## What Was Built

### 1. PathSandbox (Task 101-02-01)
- **`packages/agent-core/src/inkstatute_agent_core/tools/path_sandbox.py`** — `PathSandbox` class that validates file paths against an allowlist of root directories. Python port of the Rust `PathSandbox` from `lawyer-desktop/src-tauri/src/security/path_sandbox.rs`.
  - `__init__(allowed_roots)` — stores canonicalized (resolved) root paths
  - `validate(path)` — rejects `..` components (path traversal), canonicalizes via `Path.resolve()`, checks canonical path is within at least one allowed root, raises `PermissionError` if outside
  - `is_allowed(path)` — returns True/False without raising
- **`packages/agent-core/tests/test_path_sandbox.py`** — 19 tests covering: file inside root, outside roots rejected, `..` traversal rejected, symlink resolution (within root and escape), nested subdirectory, absolute path, relative path, multiple roots, root itself, canonicalized roots, nonexistent file, empty roots, string paths.

### 2. file_read Tool (Task 101-02-02)
- **`packages/agent-core/src/inkstatute_agent_core/tools/file_read.py`** — File reading tool handler with path sandboxing, read-only access, max 50000 char limit, binary file rejection, and encoding resilience (UTF-8 with latin-1 fallback).
  - `create_file_read_tool(sandbox)` — factory that captures a `PathSandbox` and returns a `ToolHandler`
  - `FILE_READ_TOOL_DEFINITION` — OpenAI function-calling format with `name="read_file"`
  - Binary detection: null bytes in first 8KB → rejected with error `ToolResult`
  - Truncation: files exceeding `max_chars` get `"...[truncated]"` appended
  - No shell execution, no write access (read-only)
- **`packages/agent-core/tests/test_file_read_tool.py`** — 15 tests covering: valid text read, UTF-8 encoding, latin-1 fallback, nested subdirectory, truncation at custom and default max_chars, binary rejection, path traversal rejection, outside-root rejection, missing file, missing path argument, tool definition format, no write access, factory returns callable.
- **`packages/agent-core/tests/fixtures/sample_text.txt`** — Test fixture file
- **`packages/agent-core/tests/fixtures/sample_subdir/nested.txt`** — Nested test fixture

### 3. MCP Client (Task 101-02-03)
- **`packages/agent-core/src/inkstatute_agent_core/tools/mcp_client.py`** — `McpClient` class implementing JSON-RPC 2.0 over stdio for communicating with Node.js MCP connector subprocesses.
  - `__init__(connector_path, env, timeout=40.0)` — configured connector path (controlled subprocess, not user-supplied)
  - `start()` — spawns `node <connector_path>` subprocess, performs `initialize` handshake (protocol version "2024-11-05"), sends `notifications/initialized`
  - `list_tools()` — calls `tools/list`, returns tool descriptors
  - `call_tool(name, arguments)` — calls `tools/call`, returns text content, raises `McpError` on `isError=true`
  - `close()` — terminates subprocess, cleans up
  - `__aenter__` / `__aexit__` — async context manager support
  - Auto-incrementing request ID counter, `asyncio.Queue` for response matching, background reader task
  - `MCP_PROTOCOL_VERSION = "2024-11-05"`
- **Schema conversion utilities:**
  - `mcp_input_schema_to_openai_parameters(input_schema)` — direct passthrough (both are JSON Schema)
  - `mcp_tool_to_openai_definition(tool)` — wraps MCP tool in `{"type": "function", "function": {...}}` format
- **`packages/agent-core/tests/test_mcp_client.py`** — 19 tests using fake subprocess (no real Node.js): handshake, list_tools, call_tool success, isError handling, JSON-RPC error, auto-incrementing IDs, close terminates, async context manager, connector path configured, default timeout 40s, custom timeout, env passed, arguments passed, empty content, schema conversion (5 tests).

### 4. Regulation Search Tool (Task 101-02-04)
- **`packages/agent-core/src/inkstatute_agent_core/tools/regulation_search.py`** — Regulation search tool that calls `search_laws` on the `law-database` MCP connector.
  - `create_regulation_search_tool(mcp_client)` — factory that captures an `McpClient`, calls `search_laws` via MCP, returns results as `ToolResult.content`
  - `create_fixture_regulation_search_tool(fixture_responses)` — fixture mode handler returning canned responses by keyword (no MCP subprocess or network needed)
  - `REGULATION_SEARCH_TOOL_DEFINITION` — OpenAI format with `name="search_laws"`, parameters: `keyword`, `law_type`, `issuing_authority`, `status`
  - Argument mapping: `law_type` → `lawType`, `issuing_authority` → `issuingAuthority` (snake_case to camelCase)
  - MCP errors caught and returned as error `ToolResult` (not exceptions)
- **`packages/agent-core/tests/fixtures/mcp_law_fixtures.py`** — Canned law-database responses for 4 keywords (合同法, 民法典, 公司法, 劳动法)
- **`packages/agent-core/tests/test_regulation_search_tool.py`** — 20 tests covering: argument mapping (6 tests), successful search, all arguments, empty results, MCP error handling, connection error handling, missing keyword, tool definition format, fixture mode (7 tests: canned response, different keywords, unknown keyword, no MCP call, missing keyword, with arguments, empty responses).

### 5. Builtin Registry Factory (Task 101-02-05)
- **`packages/agent-core/src/inkstatute_agent_core/tools/builtin_registry.py`** — `create_builtin_registry()` factory that composes all Phase 101 tools into a single `ToolRegistry`.
  - Registers `read_file` (via `create_file_read_tool(PathSandbox(sandbox_roots))`)
  - Registers `search_laws` (via `create_regulation_search_tool(mcp_client)` or fixture mode if no connector path)
  - Registers `ask_user` (via `create_clarification_tool(emitter)`) — only if emitter is provided
  - When `mcp_connector_path=None`, uses fixture mode (canned responses)
- **`packages/agent-core/tests/test_builtin_registry.py`** — 9 tests covering: all tools registered, without emitter (no ask_user), returns ToolRegistry, tool definitions format, tool definition names, fixture mode fallback, fixture mode default empty, file_read works through registry, MCP connector path creates MCP handler.

### 6. tools/__init__.py Updated
- **`packages/agent-core/src/inkstatute_agent_core/tools/__init__.py`** — Updated to re-export all 101-02 tools: `PathSandbox`, `create_file_read_tool`, `FILE_READ_TOOL_DEFINITION`, `McpClient`, `McpError`, `mcp_input_schema_to_openai_parameters`, `mcp_tool_to_openai_definition`, `create_regulation_search_tool`, `create_fixture_regulation_search_tool`, `REGULATION_SEARCH_TOOL_DEFINITION`, `create_builtin_registry`.

### 7. All 38 Gates Green (Task 101-02-06)
- `python scripts/run_v2_gates.py` exits 0, all 38 gates green
- agent-core gate: 487 tests (405 original + 82 new), all PASS
- No regressions in any pre-existing gate

## Commits

| Hash | Description |
|------|-------------|
| `47a416a` | feat(101-02): PathSandbox — path sandboxing for file reading security |
| `dd2c72a` | feat(101-02): file_read tool — read-only, path-sandboxed, max 50000 chars |
| `04c9819` | feat(101-02): McpClient — JSON-RPC 2.0 over stdio, MCP-to-OpenAI schema conversion |
| `3a3f9e6` | feat(101-02): regulation_search tool — MCP law-database + fixture mode |
| `8cdb150` | feat(101-02): builtin_registry factory — composes all Phase 101 tools |
| `7b0f62c` | fix(101-02): fix fixture import paths for unittest discover compatibility |
| `a6dcca0` | feat(101-02): update tools/__init__.py re-exports for 101-02 tools |

## Files Created
- `packages/agent-core/src/inkstatute_agent_core/tools/path_sandbox.py`
- `packages/agent-core/src/inkstatute_agent_core/tools/file_read.py`
- `packages/agent-core/src/inkstatute_agent_core/tools/mcp_client.py`
- `packages/agent-core/src/inkstatute_agent_core/tools/regulation_search.py`
- `packages/agent-core/src/inkstatute_agent_core/tools/builtin_registry.py`
- `packages/agent-core/tests/test_path_sandbox.py`
- `packages/agent-core/tests/test_file_read_tool.py`
- `packages/agent-core/tests/test_mcp_client.py`
- `packages/agent-core/tests/test_regulation_search_tool.py`
- `packages/agent-core/tests/test_builtin_registry.py`
- `packages/agent-core/tests/fixtures/sample_text.txt`
- `packages/agent-core/tests/fixtures/sample_subdir/nested.txt`
- `packages/agent-core/tests/fixtures/mcp_law_fixtures.py`

## Files Modified
- `packages/agent-core/src/inkstatute_agent_core/tools/__init__.py` (re-exports for 101-02 tools)

## Test Counts
- test_path_sandbox.py: 19 tests
- test_file_read_tool.py: 15 tests
- test_mcp_client.py: 19 tests
- test_regulation_search_tool.py: 20 tests
- test_builtin_registry.py: 9 tests
- **Total new tests: 82**
- **Total agent-core tests: 487** (405 original + 82 new)

## Design Decisions

### PathSandbox: Reject `..` Before Canonicalization
The Rust original checks for `ParentDir` components before canonicalization. This prevents symlink-based path traversal escapes where a symlink within the root points outside, and the path is constructed with `..` to reach the symlink. The Python port checks `Path(path).parts` for `".."` before calling `Path.resolve()`.

### MCP Client: Configured Subprocess (Not User-Supplied)
The `McpClient` constructor takes a `connector_path` that is configured at construction time — not user-supplied. This is a **controlled subprocess** (specific Node.js script with stdio JSON-RPC), not arbitrary shell execution. This matches the Phase 90 security defaults: no tool in Phase 101 has a `terminal` or `execute_code` permission path.

### Fixture Mode for Testing
The regulation search tool supports fixture mode via `create_fixture_regulation_search_tool(fixture_responses)`, which returns canned responses by keyword without requiring a real MCP subprocess or network. This enables testing without Node.js, matching the law-database connector's own `LAW_DB_FIXTURES=1` fixture mode. The `builtin_registry` factory automatically uses fixture mode when `mcp_connector_path=None`.

### MCP-to-OpenAI Schema Conversion: Direct Passthrough
MCP `inputSchema` and OpenAI `parameters` both use JSON Schema `{"type": "object", "properties": ..., "required": ...}`. The conversion is a direct passthrough (field rename: `inputSchema` → `parameters`), wrapped in `{"type": "function", "function": {...}}` for OpenAI format. This is the simplest possible conversion — no schema transformation needed.

### Argument Mapping: snake_case to camelCase
The regulation search tool uses Python snake_case (`law_type`, `issuing_authority`) while the MCP connector uses JavaScript camelCase (`lawType`, `issuingAuthority`). The `_map_arguments()` function handles this conversion, keeping the tool interface Pythonic while matching the connector's expected parameter names.

### MCP Client Tests: Fake Subprocess
The MCP client tests use a `FakeProcess` class that simulates the Node.js MCP connector's line-delimited JSON-RPC protocol. This allows testing the protocol logic, request/response matching, error handling, and schema conversion without requiring Node.js to be installed. The fake process captures stdin writes and yields pre-loaded stdout lines.

## Self-Check: PASSED

- [x] All tasks executed and committed (6/6)
- [x] All acceptance_criteria PASS
- [x] PathSandbox created (path_sandbox.py — reject `..`, canonicalize, allowlist roots)
- [x] file_read tool created (file_read.py — read-only, sandboxed, max 50000 chars, no shell)
- [x] McpClient created (mcp_client.py — JSON-RPC 2.0 over stdio, asyncio subprocess)
- [x] regulation_search tool created (regulation_search.py — via MCP + fixture mode)
- [x] builtin_registry factory created (builtin_registry.py — composes all tools)
- [x] All 38 gates green (487 agent-core tests, 0 regressions)
- [x] SUMMARY.md with Self-Check: PASSED
