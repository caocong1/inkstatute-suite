---
phase: 101
slug: agent-core-tools
status: draft
created: 2026-08-11
mode: auto
---

# Phase 101 Discussion Log — Agent Core Tools

**Mode:** --auto (all gray areas auto-selected with recommended options)
**Requirements:** CORE-02, CORE-03
**Depends on:** Phase 100 (COMPLETE)

---

## Gray Areas Identified: 11

All 11 gray areas were identified during codebase scouting and auto-selected with the recommended option.

---

### Gray Area 1: Tool Layer Architecture

**Question:** How to define and register tools in the agent core?

**Options:**
- A) ToolRegistry class mapping tool names to callable handlers; dispatching ToolExecutor that looks up the registry
- B) Hardcoded if/else dispatch on tool_name in a single function
- C) Plugin-based architecture with entry points

**Auto-Selected:** A — ToolRegistry + dispatching ToolExecutor

**Rationale:** The turn loop's `ToolExecutor` is `Callable[[str, str, dict], Awaitable[ToolResult]]`. A `ToolRegistry` with `dict[str, ToolHandler]` is the simplest design that composes without modifying the turn loop. Tool definitions (OpenAI format) are generated from the registry. Option B doesn't scale; Option C is over-engineered for 5 tools.

---

### Gray Area 2: Clarification Tool (ask_user → elicitation.requested)

**Question:** How does the clarification tool map to the `elicitation.requested` unified event?

**Options:**
- A) Tool emits `elicitation.requested` via EventEmitter and returns a ToolResult with `metadata={"terminate_turn": True}` to signal the turn loop to stop
- B) Tool returns the questions as ToolResult.content and the turn loop detects "ask_user" specially
- C) Turn loop is modified to check tool_name == "ask_user" before continuing

**Auto-Selected:** A — Emit event + terminate_turn metadata flag

**Rationale:** Matches the Rust original's `finish_ask_user_turn()` behavior: the turn terminates immediately. Option A is the cleanest because it doesn't require the turn loop to know specific tool names — it checks a generic `terminate_turn` metadata flag. The tool handler has access to the EventEmitter to emit the `elicitation.requested` event. Requires a small turn loop enhancement: check `result.metadata.get("terminate_turn")` after tool execution and break.

---

### Gray Area 3: Regulation Search Tool (法规检索)

**Question:** How to implement the regulation search tool?

**Options:**
- A) MCP client that spawns the `law-database` Node.js connector as a subprocess and calls `tools/call`
- B) Direct HTTP client to flk.npc.gov.cn API in Python
- C) Reuse Hermes's existing MCP integration via ACP

**Auto-Selected:** A — MCP client calling law-database connector

**Rationale:** The `law-database` connector already implements `search_laws`, `get_law_detail`, `search_cases` against flk.npc.gov.cn with caching, provenance, and degraded error handling. It's standard MCP (JSON-RPC 2.0 over stdio). V3-SELECTION V1 confirmed: "标准 MCP client 可直连，无需适配." Reusing the connector avoids duplicating the API integration logic. Fixture mode (`LAW_DB_FIXTURES=1`) enables testing without network. Option B duplicates existing work; Option C introduces ACP dependency for a local tool.

---

### Gray Area 4: File Reading Tool

**Question:** How to read files safely in the agent core?

**Options:**
- A) Read-only file reading tool with path sandboxing (only within configured workspace/uploads directories)
- B) Unrestricted file reading (agent has full filesystem access)
- C) File reading via MCP `fs/*` protocol

**Auto-Selected:** A — Read-only with path sandboxing

**Rationale:** Phase 90 security defaults require no unapproved shell/code execution. The file reading tool must be read-only, sandboxed to configured directories, with no path traversal (`..` normalization), no symlink following outside the sandbox, and no shell execution. Binary files (docx, pdf) return metadata only. Option B violates security defaults; Option C introduces ACP `fs/*` which is explicitly not declared in Phase 103's capability list.

---

### Gray Area 5: Document Generation Tool (Word Track Changes)

**Question:** How to generate documents with Word native track changes?

**Options:**
- A) Import `TrackChangesBuilder` from `contract_review_trackchanges.py`, parameterize `REVIEW_ITEMS`, call `process()` + `save()`
- B) Rewrite the track changes logic in a new Python module
- C) Call the script via subprocess

**Auto-Selected:** A — Import and parameterize (CORE-03 says "不重写")

**Rationale:** CORE-03 explicitly requires "直接复用 `lawfirm-profile/scripts/contract_review_trackchanges.py` 的能力，不重写." The `TrackChangesBuilder` class is well-structured: `__init__(docx_path)`, `process()`, `save(output_path)`. The only adaptation needed is making `REVIEW_ITEMS` injectable (currently a module-level constant). Option B violates the requirement; Option C adds unnecessary subprocess overhead when the script is pure Python + lxml. The `lxml` dependency is lazy-imported (matching provider_model's lazy SDK import pattern).

---

### Gray Area 6: MCP Client Integration

**Question:** How to reuse `packages/mcp-registry` for MCP tool discovery and invocation?

**Options:**
- A) Build a new `McpClient` in `agent-core/tools/mcp_client.py` that implements JSON-RPC 2.0 over stdio; reuse mcp-registry for catalog lookup
- B) Extend `packages/mcp-registry` with a client module
- C) Use a third-party MCP client library

**Auto-Selected:** A — New McpClient in agent-core

**Rationale:** `packages/mcp-registry` provides the catalog (`McpRegistryPort`, `InMemoryMcpRegistry`, `McpServerRecord`) but not the client protocol. The MCP client (subprocess spawning, JSON-RPC handshake, tool discovery, tool invocation, lifecycle management) is agent-core-specific. Building it in `agent-core/tools/mcp_client.py` keeps the concern local. Option B would change the mcp-registry package's scope (currently read-only catalog); Option C adds an external dependency when the protocol is simple (line-delimited JSON over stdio).

---

### Gray Area 7: Artifact Creation (artifact.created event)

**Question:** How to emit `artifact.created` events for generated documents?

**Options:**
- A) Add `emit_artifact_created()` to EventEmitter; document generation tool constructs `Artifact` dataclass and emits the event
- B) Turn loop detects document generation tool results and emits artifact events
- C) Gateway constructs artifact events from tool call metadata

**Auto-Selected:** A — EventEmitter + tool constructs Artifact

**Rationale:** The EventEmitter is the single point for event construction. Adding `emit_artifact_created(artifact: Artifact)` follows the existing pattern (9 emit methods). The document generation tool has the artifact metadata (kind, name, uri) and constructs the `Artifact` dataclass. The event flows through the normal event stream; the Gateway's existing event consumer registers it in `GatewayArtifactStore`. Option B couples the turn loop to specific tools; Option C loses event-stream consistency.

---

### Gray Area 8: Artifact Storage

**Question:** How to store and serve generated docx files?

**Options:**
- A) Write docx to a configured output directory; `Artifact.uri` points to the file path; Gateway serves `uri_ref` (reference-only)
- B) Store docx content in the event stream (base64 encoded)
- C) Upload to remote storage (S3, etc.) immediately

**Auto-Selected:** A — Local file path with uri_ref

**Rationale:** AGENTS.md: "Contract logs prefer raw_payload_ref" and "Never commit customer documents." The Gateway's artifact response is already reference-only (`uri_ref`, not raw content). Writing to a local output directory is the simplest approach for Phase 101. The `Artifact.uri` is a file path or `file://` URI. Remote storage is V4 scope (SCALE). Option B violates reference-first and bloats events; Option C is out of scope for single-firm deployment.

---

### Gray Area 9: Tool Permissions (Phase 90 Security Defaults)

**Question:** How to enforce Phase 90's security defaults in the tool layer?

**Options:**
- A) No tool has terminal/execute_code paths; MCP subprocess is controlled (configured connector path); file reading is sandboxed; all tools are read-only or write-to-output-dir only
- B) Add a permission check layer that mirrors ACP `request_permission` for each tool
- C) Require explicit user approval for every tool call

**Auto-Selected:** A — No dangerous permission paths

**Rationale:** Phase 90's `_DANGEROUS_PERMISSION_KINDS = {"terminal", "execute_code"}` applies to ACP permission requests. The agent-core's tools don't request permissions — they execute directly. The security model is enforced by design: file reading is sandboxed, document generation writes only to output dir, regulation search is HTTP GET to known API, MCP client spawns configured connectors (not arbitrary shell), clarification has no I/O. No tool executes arbitrary shell or code. Option B adds unnecessary complexity for tools that are safe by design; Option C would make the agent unusable (every tool call needs approval).

---

### Gray Area 10: Tool Result Injection

**Question:** How to feed tool results back to the turn loop?

**Options:**
- A) ToolResult.content is appended as a tool result message by the existing turn loop mechanism; no changes needed
- B) Tool results are injected as a new system message
- C) Tool results modify the last user message

**Auto-Selected:** A — Existing turn loop mechanism

**Rationale:** The turn loop already appends tool results to `current_messages` as `{"role": "tool", "tool_call_id": ..., "content": result.content}` (lines 245-249, 262-266). Error results are handled (lines 268-288). The `ToolRegistry` handlers return `ToolResult(content=..., error=..., metadata=...)` which the dispatching executor passes through. The only enhancement is checking `metadata.get("terminate_turn")` for the clarification tool (Gray Area 2). Option B breaks the OpenAI tool-calling protocol; Option C is semantically wrong.

---

### Gray Area 11: Tool Definitions Format

**Question:** How are tool definitions provided to the LLM?

**Options:**
- A) `ToolRegistry.get_tool_definitions()` returns OpenAI function-calling format dicts; MCP tools converted from `inputSchema` to OpenAI `parameters`
- B) Hardcode tool definitions in the turn loop
- C) Use a separate tool definition file (YAML/JSON)

**Auto-Selected:** A — Generated from registry in OpenAI format

**Rationale:** The `ChatRequest.tools` field expects OpenAI function-calling format (`{type: "function", function: {name, description, parameters}}`). The `ToolRegistry` stores tool metadata alongside each handler. `get_tool_definitions()` produces the `tools` list. For MCP tools, the `inputSchema` (JSON Schema `{type: "object", properties, required}`) maps directly to OpenAI `parameters`. Option B doesn't scale; Option C adds a configuration burden without benefit.

---

## Summary

| # | Gray Area | Selected Option |
|---|-----------|-----------------|
| 1 | Tool layer architecture | ToolRegistry + dispatching ToolExecutor |
| 2 | Clarification tool | Emit elicitation.requested + terminate_turn metadata |
| 3 | Regulation search tool | MCP client calling law-database connector |
| 4 | File reading tool | Read-only with path sandboxing |
| 5 | Document generation tool | Import TrackChangesBuilder, parameterize review items |
| 6 | MCP client integration | New McpClient in agent-core/tools/mcp_client.py |
| 7 | Artifact creation | EventEmitter.emit_artifact_created() + tool constructs Artifact |
| 8 | Artifact storage | Local file path with uri_ref (reference-only) |
| 9 | Tool permissions | No terminal/execute_code paths; controlled MCP subprocess |
| 10 | Tool result injection | Existing turn loop mechanism (no changes) |
| 11 | Tool definitions format | Generated from registry in OpenAI format |

All decisions are consistent with:
- AGENTS.md binding architecture decisions (Python core, tool rounds stream, no auto-approve permissions)
- Phase 90 security defaults (`_DANGEROUS_PERMISSION_KINDS`)
- CORE-03 requirement ("不重写" the track changes script)
- Phase 100 turn loop design (ToolExecutor callable, ToolResult dataclass)
- Phase 88 unified events (ElicitationRequestedPayload, ArtifactCreatedPayload)
- Reference-first principle (artifact.uri, not raw content in events)
