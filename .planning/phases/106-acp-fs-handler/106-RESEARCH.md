---
phase: 106
slug: acp-fs-handler
status: complete
created: 2026-08-08
---

# Phase 106 — Technical Research

## 1. ACP Protocol fs Extension

ACP v1 defines `clientCapabilities.fs.readTextFile` as a boolean in the `initialize` request params. The client MUST advertise this capability for agents to use it.

**`fs/read_text_file` request format (inbound from agent):**
```json
{
  "id": "req-xxx",
  "method": "fs/read_text_file",
  "params": {
    "sessionId": "session-xxx",
    "path": "/absolute/path/to/file.md"
  }
}
```

**Response format (outbound to agent):**
```json
{
  "id": "req-xxx",
  "result": {
    "content": "file contents as text"
  }
}
```

**Error response:**
```json
{
  "id": "req-xxx",
  "error": {
    "code": -32602,
    "message": "Path outside allowed root"
  }
}
```

## 2. Current acp-client Architecture

**Key files:**
- `packages/acp-client/src/inkstatute_acp_client/client.py` — Main `ACPClient` class
- `packages/acp-client/src/inkstatute_acp_client/adapter.py` — `ACPBackendAdapter`, `ACPBackendConfig`
- `packages/acp-client/src/inkstatute_acp_client/transport.py` — `StdioACPTransport`

**Current state:**
- `ACPClient.initialize()` (line 237-261) sends `protocolVersion: 1` and `clientInfo` — does NOT send `clientCapabilities`
- `StdioACPTransport.receive()` (line 104-119) handles responses (has `id`, no `method`) and notifications (has `method`, no `id`)
- Inbound requests from agent (has both `id` and `method`) are NOT handled
- No request handler registration mechanism exists
- `ACPBackendConfig` (line 63-95) has no `client_capabilities` field

**Required changes:**
1. Add optional `client_capabilities: dict | None = None` to `ACPClient.__init__()` and `initialize()`
2. When provided, include `clientCapabilities` in initialize request
3. Add request handler registration: `register_request_handler(method, handler_fn)`
4. Modify `receive()` to dispatch inbound requests to registered handlers
5. When no handler registered for a method, return JSON-RPC error (not crash)

## 3. Path Sandboxing Design

**Existing utility:** `PathSandbox` in `packages/agent-core/src/inkstatute_agent_core/tools/path_sandbox.py` provides 3 of 5 protections:
- Rejects `..` components (line 68-70)
- Canonicalizes via `Path.resolve()` (line 73)
- Prefix-check against allowed roots (line 76-78)

**Missing protections to add (create `FSSandbox` in `packages/acp-client/src/inkstatute_acp_client/fs_sandbox.py`):**

1. **resolve normalization** — `Path.resolve()` to canonicalize, reject any path with `..` components before resolve
2. **prefix-check root directory constraint** — `resolved_path.is_relative_to(allowed_root)` or `str(resolved).startswith(str(root))`
3. **symlink rejection** — `os.path.islink(path)` or `path.lstat()` to detect symlinks at any component; reject if any component is a symlink
4. **extension allowlist** — `path.suffix.lower() in ALLOWED_EXTENSIONS`; recommended: `.txt`, `.md`, `.json`, `.yaml`, `.yml`, `.csv`, `.html`, `.xml`, `.log`, `.py`, `.js`, `.ts` (text-based formats only; NOT `.exe`, `.sh`, `.bat`, `.docx`, `.pdf` binary formats for v1)
5. **size cap** — `path.stat().st_size <= MAX_FILE_SIZE`; recommended: 1 MB (1_048_576 bytes) for v1

**FSSandbox class design:**
```python
@dataclass(frozen=True, slots=True)
class FSSandboxConfig:
    allowed_root: Path
    allowed_extensions: frozenset[str]
    max_file_size: int  # bytes

class FSSandbox:
    def __init__(self, config: FSSandboxConfig): ...
    def validate_path(self, path: str | Path) -> Path:  # returns resolved path or raises FSSandboxError
    def read_text_file(self, path: str | Path) -> str:  # validates + reads
```

## 4. Prompt Injection Sanitization

**Existing utility:** `sanitize_assistant_content()` in `packages/agent-core/src/inkstatute_agent_core/tool_leak.py` (line 116-203) — removes tool-call markup. NOT suitable for reference files.

**Required: Create `ReferenceSanitizer` in `packages/acp-client/src/inkstatute_acp_client/sanitizer.py`**

**Three-layer sanitization:**

1. **Delimiter wrapping** — Wrap file content in unforgeable delimiters:
   ```
   <reference_file path="/path/to/file.md">
   --- BEGIN REFERENCE CONTENT ---
   {file_content}
   --- END REFERENCE CONTENT ---
   </reference_file>
   ```

2. **Pattern detection** — Scan content for known injection patterns:
   - "ignore previous instructions"
   - "ignore all previous"
   - "you are now"
   - "new role:"
   - "forget everything above"
   - "system:" (role-play injection)
   - "</system>" (tag injection)
   - "<reference_file" (delimiter forgery attempt)

3. **Detection logging** — When patterns detected, log at WARNING level:
   ```python
   logger.warning("prompt_injection_detected", extra={
       "path": str(path),
       "pattern": matched_pattern,
       "line_number": line,
   })
   ```

**Sanitized output:** Content is always delivered (with delimiters), but detection is logged. The agent sees the delimiters and knows the content is untrusted reference data.

## 5. Gateway Backward Compatibility

**Gateway path:** `services/gateway/src/` uses `ACPBackendAdapter` which creates `ACPClient` with `RequiredCapabilities(streaming=True)` default.

**Current state:** No `client_capabilities` parameter exists anywhere in the codebase.

**Solution:**
- Add optional `client_capabilities: dict | None = None` to `ACPClient.__init__()` and `ACPBackendConfig`
- When `None`, don't include `clientCapabilities` in initialize request (backward compatible — Gateway path unchanged)
- When provided, include it in the request (arena-service will pass it in Phase 109)
- Gateway's `ACPBackendAdapter` does NOT pass `client_capabilities` → fs capability not advertised → agents don't send `fs/read_text_file` → zero behavior change

**Verification:** All 34 existing gates must remain green. Run `python scripts/run_v2_gates.py` before and after changes.

## 6. Gate Integration

**Add GATE-04 to `scripts/run_v2_gates.py`:**

```python
Gate(
    "fs-sandbox-escape",
    (py, "-m", "unittest", "discover", "-s", "packages/acp-client/tests", "-k", "FSSandbox"),
    (acp_client_src,),
),
```

Or create a dedicated test file `packages/acp-client/tests/test_fs_sandbox_escape.py` and gate:
```python
Gate(
    "fs-sandbox-escape",
    (py, "-m", "unittest", "packages.acp_client.tests.test_fs_sandbox_escape"),
    (acp_client_src,),
),
```

**Update gate count baseline:** `packages/contract-test-suite/tests/test_gate_coverage.py` — update expected gate count from 34 to 35+.

## 7. Existing Patterns

- **PathSandbox** (agent-core): Proven path validation — reuse the `..` rejection + resolve + prefix-check pattern
- **file_read tool** (agent-core): File reading with sandbox, binary detection, size limits — reference for size cap implementation
- **capability_negotiation**: Pattern for optional capabilities in ACP initialize
- **EventBridge**: Request ID correlation pattern — adapt for inbound request handling
- **Frozen slotted dataclasses**: Used throughout platform-contract — follow for config types

## 8. Test Strategy

**5 attack vectors (each must have a dedicated test):**

1. **Path traversal** — `../../etc/passwd` → reject because `..` component
2. **Symlink escape** — Create symlink inside root pointing outside root → reject because symlink detected
3. **Absolute path outside root** — `/etc/passwd` → reject because resolved path not under allowed root
4. **Non-allowlist extension** — `malware.exe` → reject because `.exe` not in allowed extensions
5. **Oversized file** — Create file > 1MB → reject because size > max_file_size

**Additional tests:**
- Valid file reads succeed (positive cases)
- Handler registration and dispatch
- Unregistered handler returns error (not crash)
- clientCapabilities not sent when not configured (backward compat)
- clientCapabilities sent when configured
- Sanitizer delimiter wrapping
- Sanitizer pattern detection + logging
- Sanitizer delimiter forgery attempt detection

**Test fixtures:**
- Use `tempfile.TemporaryDirectory()` for isolated test roots
- Create real symlinks with `os.symlink()`
- Create oversized files with `os.truncate()` or writing bytes

## Key Files to Modify

1. `packages/acp-client/src/inkstatute_acp_client/client.py` — Add client_capabilities + request handler registration
2. `packages/acp-client/src/inkstatute_acp_client/adapter.py` — Add client_capabilities to config
3. `packages/acp-client/src/inkstatute_acp_client/transport.py` — Handle inbound requests
4. `packages/acp-client/src/inkstatute_acp_client/fs_sandbox.py` — NEW: FSSandbox with 5 protections
5. `packages/acp-client/src/inkstatute_acp_client/fs_handler.py` — NEW: fs/read_text_file handler + sanitizer
6. `packages/acp-client/src/inkstatute_acp_client/sanitizer.py` — NEW: ReferenceSanitizer
7. `packages/acp-client/src/inkstatute_acp_client/__init__.py` — Re-exports
8. `packages/acp-client/tests/test_fs_sandbox.py` — NEW: Sandbox escape tests (5 vectors)
9. `packages/acp-client/tests/test_fs_handler.py` — NEW: Handler integration tests
10. `packages/acp-client/tests/test_client_capabilities.py` — NEW: Capability negotiation tests
11. `scripts/run_v2_gates.py` — Add GATE-04 gate
12. `packages/contract-test-suite/tests/test_gate_coverage.py` — Update gate count baseline

## Patterns to Follow

- Frozen slotted dataclasses for config types (platform-contract pattern)
- `PathSandbox` pattern for path validation (agent-core)
- JSON-RPC error codes: -32601 (method not found), -32602 (invalid params)
- `@runtime_checkable` Protocol for handler interface (platform-runtime pattern)
- unittest (not pytest) for all tests
- `tempfile.TemporaryDirectory()` for test isolation

## Anti-Patterns to Avoid

- Do NOT resolve symlinks before checking (must reject symlinks, not follow them)
- Do NOT use string prefix matching for path containment (use `Path.is_relative_to()` or resolved path comparison)
- Do NOT auto-approve any fs request (all requests must pass full 5-layer validation)
- Do NOT log file contents (log only path, pattern, line number — privacy)
- Do NOT break Gateway backward compatibility (no `client_capabilities` = no fs capability)
- Do NOT use `os.path.realpath()` for symlink check (it follows symlinks — use `os.path.islink()` or `Path.lstat()`)

## Open Questions

None — all design decisions are clear from existing patterns and ACP spec.

## Assumptions

- ACP v1 `fs/read_text_file` is the only fs method needed for v1 (no `fs/write`, `fs/list`, etc.)
- Size cap of 1 MB is sufficient for reference files (legal documents, configs, source files)
- Extension allowlist covers text-based formats only; binary formats (`.docx`, `.pdf`) deferred to future phase
- Gateway path does not need fs capability (only Arena service does, in Phase 109)
- Symlink rejection applies to all path components, not just the final component
