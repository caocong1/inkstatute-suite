---
phase: 101
slug: agent-core-tools
status: draft
created: 2026-08-11
skip_discuss: false
---

# Phase 101 — Agent Core Tools

## Phase Goal

自研核心具备完成真实法律任务所需的工具，包括墨律最难也最值钱的产出——带 Word 原生修订的合同审查稿

## Requirements

- **CORE-02**: 工具层——澄清提问、法规检索、文件读取、文档生成、MCP client；工具结果回注与多轮工具编排
- **CORE-03**: Word 原生修订 docx 产出能力，直接复用 `lawfirm-profile/scripts/contract_review_trackchanges.py`（41,185 字节）的能力，不重写

## Success Criteria

1. 工具层实现并可被 turn loop 调用：澄清提问（映射 `elicitation.requested`）、法规检索、文件读取、文档生成、MCP client（复用 `packages/mcp-registry`）
2. 工具结果正确回注 turn loop，多轮工具编排可用；工具失败不导致整轮崩溃而是产出 `error` 事件并可恢复
3. Word 原生修订 docx 产出成功：直接复用 `lawfirm-profile/scripts/contract_review_trackchanges.py`（41,185 字节）的能力，**不重写**；产出的 docx 在 Word 中显示为原生修订标记
4. 产物以 `artifact.created` 事件发出，`kind` 正确区分 `docx` 与 `trackchanges_docx`，并可经 Gateway `/v1/artifacts/{id}` 下载
5. MCP 工具（`law-database`、`wenshu`）可被发现与调用，调用摘要进入 `tool_call.*` 事件与 `ExecutionTrace.tool_calls`
6. 工具权限遵守 Phase 90 的安全默认——不存在未经审批的 shell / 代码执行路径

## Human Gate

- **HG-4 修订稿质量**: Word 原生修订 docx 须由律师确认可直接用于对外谈判 —— 不得由自动化声称通过

## Depends On

- Phase 100 (COMPLETE) — agent core skeleton: turn loop, EventEmitter, model layer, context assembler, FixtureProvider
- Phase 88 (COMPLETE) — unified event vocabulary: `elicitation.requested`, `artifact.created`, `tool_call.*` payloads
- Phase 90 (COMPLETE) — ACP event bridge: `_DANGEROUS_PERMISSION_KINDS = {"terminal", "execute_code"}` security defaults
- Phase 96 (COMPLETE) — skill index (for skill-required scripts metadata)
- Phase 97 (COMPLETE) — skill materializer (body injector pattern)

## Codebase Scout Findings

### 1. Phase 100 Turn Loop — The Tool Executor Seam

**Location:** `packages/agent-core/src/inkstatute_agent_core/turn_loop.py` (369 lines)

The turn loop from Phase 100 already has the tool execution seam built in:

```python
ToolExecutor = Callable[[str, str, dict], Awaitable[ToolResult]]
# (tool_call_id, tool_name, arguments) -> ToolResult

@dataclass(frozen=True, slots=True)
class ToolResult:
    content: str
    error: ErrorInfo | None = None
    metadata: JsonObject = field(default_factory=dict)
```

The `run_turn()` function accepts a `tool_executor: ToolExecutor | None` parameter. When `None`, it produces fixture results (`"[fixture tool result]"`). Phase 101 must provide **real tool implementations** that implement this callable interface.

**Key observations from turn_loop.py:**
- Tool calls are accumulated from `ToolCallDelta` stream deltas (line 158-159)
- Each tool call emits `tool_call.started` → `tool_call.delta` → `tool_call.completed` (lines 192-267)
- Tool results are appended to `current_messages` as `{"role": "tool", "tool_call_id": ..., "content": ...}` (lines 245-249)
- Error recovery: tool exceptions caught → `tool_call.completed` with `status="error"` → error appended as tool result → loop continues (lines 268-288)
- The `tool_executor` receives parsed `args_dict` (JSON-parsed from `tc_delta.arguments`) (lines 207-210)

**What Phase 101 must build:**
- A `ToolRegistry` that maps tool names to callable handlers
- A `ToolExecutor` implementation that dispatches to the registry
- Individual tool implementations: clarification, regulation search, file reading, document generation, MCP client
- Tool definitions in OpenAI function-calling format (for `tools` parameter in `ChatRequest`)

### 2. EventEmitter — Missing emit_artifact_created and emit_elicitation_requested

**Location:** `packages/agent-core/src/inkstatute_agent_core/event_emitter.py` (329 lines)

Current emit methods (9 total):
- `emit_message_delta()`, `emit_message_completed()`, `emit_thought_delta()`
- `emit_tool_call_started()`, `emit_tool_call_delta()`, `emit_tool_call_completed()`
- `emit_phase_changed()`, `emit_run_state_changed()`, `emit_error()`

**Missing for Phase 101:**
- `emit_artifact_created()` — needs `ArtifactCreatedPayload` (from `unified_events.py` line 127)
- `emit_elicitation_requested()` — needs `ElicitationRequestedPayload` (from `unified_events.py` line 108)
- `emit_citation_recorded()` — needs `CitationRecordedPayload` (from `unified_events.py` line 138) — deferred to Phase 102

The `_emit()` internal method (line ~170) handles seq numbering, occurred_at, and RunEvent construction. New emit methods follow the same pattern: construct payload dataclass → call `_emit(RunEventType.X, payload)`.

### 3. contract_review_trackchanges.py — The Word Native Track Changes Script

**Location:** `/home/sorawatcher/workspace/lawfirm-profile/scripts/contract_review_trackchanges.py` (714 lines, 41,185 bytes)
**Second copy:** `/home/sorawatcher/workspace/lawfirm-profile/skills/legal-contract-copilot/scripts/contract_review_trackchanges.py` (17,098 bytes — smaller version)

**Dependencies:** `lxml` + stdlib (`zipfile`, `shutil`, `os`, `re`, `copy`, `datetime`, `io`). No subprocess, no COM, no Word.exe, no platform-specific code. Pure Python + lxml, runs on Linux.

**Architecture:**
```python
class TrackChangesBuilder:
    def __init__(self, docx_path):
        # Unzip docx → self.files dict {name: bytes}
        # Parse word/document.xml → self.doc_tree (lxml etree)
        # Track changes counters: _next_id=1000, _comment_id=0
        # Parse word/settings.xml → self.settings_tree

    def process(self):
        # For each REVIEW_ITEM:
        #   1. _find_paragraph_by_text(find_text)
        #   2. _add_comment_to_paragraph(p, comment, comment_id)
        #   3. _replace_text_in_paragraph(p, old_text, new_text, date)
        # Returns results list [(id, level, status, comment_preview)]

    def save(self, output_path):
        # Update document.xml, content types, rels, comments.xml
        # Re-zip → output docx
```

**Track changes mechanism (OOXML):**
- Insertions: `<w:ins w:id="..." w:author="乙方律师审查" w:date="...">` wrapping new runs
- Deletions: `<w:del w:id="..." w:author="乙方律师审查" w:date="...">` wrapping runs with `<w:delText>` (converted from `<w:t>`)
- Comments: `word/comments.xml` with `<w:comment>` elements; paragraphs get `<w:commentRangeStart>`, `<w:commentRangeEnd>`, `<w:commentReference>`
- Content types: adds `Override` for `comments.xml`
- Relationships: adds `Relationship` targeting `comments.xml`
- Styles: ensures `CommentReference` style exists

**REVIEW_ITEMS:** 25 hardcoded review items (P0/P1/P2 priority) for a specific technology development contract. Each item has: `id`, `find_text`, `old_text`, `new_text`, `comment`, `level`.

**Reuse strategy (CORE-03 "不重写"):**
The script must be reused, not rewritten. The `TrackChangesBuilder` class is the reusable core:
- `__init__(docx_path)` — accepts any docx path (not hardcoded)
- `process()` — processes REVIEW_ITEMS (currently hardcoded, needs to be parameterized)
- `save(output_path)` — writes the modified docx

**What needs adaptation:**
1. **REVIEW_ITEMS must be injectable** — currently a module-level constant. The agent core's document generation tool must pass review items from the LLM's output, not use the hardcoded ones.
2. **The `main()` function** has hardcoded input/output paths — this is just a demo entry point, not the reusable API.
3. **The `process()` method** iterates over `REVIEW_ITEMS` — needs to accept a `review_items` parameter.

**Approach: Import, don't copy.** The agent-core's document generation tool imports `TrackChangesBuilder` from the lawfirm-profile script location (or a vendored copy). The tool:
1. Receives review items from the LLM (as tool call arguments)
2. Constructs `TrackChangesBuilder(input_docx_path)`
3. Overrides/injects the review items
4. Calls `process()` and `save(output_path)`
5. Returns the output path as the tool result

**lxml dependency:** `packages/agent-core/pyproject.toml` currently has `dependencies = []`. Adding `lxml` is the first external dependency. Alternatively, the document generation tool can lazy-import lxml (matching the provider_model pattern of lazy SDK imports).

### 4. MCP Connector Architecture — law-database and wenshu

**Location:** `/home/sorawatcher/workspace/ai-for-china-legal/connectors/`

**6 connectors** (2 implemented, 4 config-only):
| Connector | Status | Tools |
|-----------|--------|-------|
| `law-database` | ✅ Implemented (`index.js`) | `search_laws`, `get_law_detail`, `search_cases` (3 tools) |
| `wenshu` | ✅ Implemented (`index.js`) | `search_cases`, `get_case_detail`, `case_statistics` (3 tools) |
| `gsxt` | Config only | — |
| `patent` | Config only | — |
| `trademark` | Config only | — |
| `wechat-notify` | Config only | — |

**Protocol:** Standard MCP (JSON-RPC 2.0 over stdio, `protocolVersion: "2024-11-05"`). Methods: `initialize`, `notifications/initialized`, `tools/list`, `tools/call`. Node.js implementation, zero npm dependencies.

**Tool discovery:** `tools/list` returns `[{name, description, inputSchema}]` — standard MCP tool schema format. The `inputSchema` uses JSON Schema with `type: "object"`, `properties`, `required`.

**Tool call:** `tools/call` with `{name, arguments}` → returns `{content: [{type: "text", text}], isError: false}`. "No results" is a normal text result, not an error.

**V3-SELECTION V1 conclusion:** "标准 MCP client 可直连，无需适配" — Phase 101 needs a standard MCP client that spawns the Node.js connector as a subprocess and communicates over stdio.

**packages/mcp-registry:** Currently provides `McpRegistryPort` (read-only Protocol), `InMemoryMcpRegistry`, `McpServerRecord`, `McpServerPage`. This is a **registry/catalog** — it stores MCP server descriptors and tool schemas, but does **not** implement the MCP client protocol (stdio JSON-RPC). Phase 101 must build the actual MCP client that connects to connectors.

### 5. Elicitation Contract — How Clarification Maps to elicitation.requested

**Location:** `packages/platform-contract/src/platform_contract/elicitation.py` (189 lines)

**Payload dataclass** (`unified_events.py` line 108):
```python
@dataclass(frozen=True, slots=True)
class ElicitationRequestedPayload:
    interrupt_id: str
    intro: str
    questions: list[ElicitationQuestion]
    resume_state_ref: str | None = None
    expires_at: str | None = None
    metadata: JsonObject = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class ElicitationQuestion:
    id: str
    question: str
    allow_multiple: bool = False
    options: list[ElicitationOption] = field(default_factory=list)
```

**ASK-USER-PROTOCOL.md constraints** (enforced by `validate_question_count()`):
- 2-4 questions per elicitation
- Each question: single-select (`allow_multiple=False` + options), multi-select (`allow_multiple=True` + options), or free-text (no options)
- Answers are collected and re-injected as a hidden user message: `"以下是补充信息…"`

**Conversion functions:**
- `elicitation_to_run_interrupt()` — converts payload to V2 `RunInterrupt` (for persistence)
- `run_interrupt_to_elicitation()` — converts back (for replay)
- `format_answer_display()` — formats answers for display

**Clarification tool design:**
The `ask_user` / clarification tool is special — it **terminates the current turn** (matching Rust `finish_ask_user_turn()`). When the LLM calls the clarification tool:
1. The tool constructs `ElicitationRequestedPayload` from the tool call arguments
2. The tool emits `elicitation.requested` event (via EventEmitter)
3. The turn loop stops (does not continue to next round)
4. The run enters `WAITING_FOR_USER` state
5. When the user answers, a new turn starts with the answers injected as context

This is different from other tools — most tools return a `ToolResult` and the loop continues. The clarification tool must signal the turn loop to stop.

### 6. Artifact Events and Gateway Storage

**ArtifactKind enum** (`enums.py` line 89):
```python
class ArtifactKind(StrEnum):
    DOCX = "docx"
    TRACKCHANGES_DOCX = "trackchanges_docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    JSON = "json"
    OTHER = "other"
```

**Artifact dataclass** (`events.py` line 61):
```python
@dataclass(frozen=True, slots=True)
class Artifact:
    artifact_id: str
    kind: ArtifactKind | str
    name: str
    uri: str
    mime_type: str | None = None
    template_ref: str | None = None
    features: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)
```

**ArtifactCreatedPayload** (`unified_events.py` line 127):
```python
@dataclass(frozen=True, slots=True)
class ArtifactCreatedPayload:
    artifact: Artifact
    metadata: JsonObject = field(default_factory=dict)
```

**Gateway artifact store** (`services/gateway/src/gateway/artifacts.py`):
- `GatewayArtifactStore` — in-memory store with tenant isolation
- `register_artifact(ArtifactMetadata)` — stores artifact
- `get_artifact(artifact_id, tenant_id=...)` — retrieves with tenant check (cross-tenant → 404)
- Response is **reference-only**: returns `uri_ref`, not raw content
- `ArtifactMetadata`: `artifact_id`, `kind`, `uri_ref`, `name`, `tenant_id`, `metadata`

**Artifact creation flow:**
1. Document generation tool produces a docx file → writes to a storage location
2. Tool constructs `Artifact(artifact_id=uuid, kind="trackchanges_docx", name=..., uri=...)` 
3. EventEmitter emits `artifact.created` with `ArtifactCreatedPayload`
4. Gateway's event consumer registers the artifact in `GatewayArtifactStore`
5. Client downloads via `GET /v1/artifacts/{artifact_id}` → gets `uri_ref`

**Artifact storage:** The Gateway currently uses in-memory store. For Phase 101, the agent-core's document generation tool writes the docx to a local file path (or temp dir) and the `uri` points to that location. The Gateway's `uri_ref` is reference-first — it doesn't store raw content.

### 7. Phase 90 Security Defaults — Permission Safety

**Location:** `packages/acp-client/src/inkstatute_acp_client/adapter.py` line 114

```python
_DANGEROUS_PERMISSION_KINDS: frozenset[str] = frozenset({"terminal", "execute_code"})
```

**Rules (from AGENTS.md and Phase 90):**
- `terminal` / `execute_code` permission requests must be **explicitly denied** or escalated to user approval
- Server-side must **never** auto-approve (`allow_once` is forbidden — reference: Buzz's ACP bridge auto-allow accident)
- ACP `session/request_permission` for dangerous kinds → run set to `WAITING_FOR_USER` with issue

**Phase 101 tool permissions:**
The agent-core's tools must follow the same security defaults:
- **File reading tool**: Read-only, no shell execution, no write access. Path sandboxing (only within workspace/uploads).
- **Document generation tool**: Writes only to designated output directory. No shell execution.
- **Regulation search tool**: HTTP GET only (to flk.npc.gov.cn API). No shell execution.
- **MCP client**: Spawns Node.js subprocess for MCP connectors. This is a **controlled subprocess** (not arbitrary shell execution) — the connector path is configured, not user-supplied. The MCP client must not pass arbitrary commands.
- **Clarification tool**: No I/O, just constructs events. Safe.

No tool in Phase 101 should have a `terminal` or `execute_code` permission path. The MCP client's subprocess spawning is a controlled, configured operation (specific Node.js script with stdio JSON-RPC), not arbitrary shell execution.

### 8. Tool Definition Format — OpenAI Function Calling

**Location:** `packages/agent-core/src/inkstatute_agent_core/model/provider.py`

The `ChatRequest` dataclass (line 118) accepts `tools: list[dict] | None` — tool definitions in **OpenAI function-calling format**:

```python
{
    "type": "function",
    "function": {
        "name": "legal_search",
        "description": "检索法律法规...",
        "parameters": {
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    }
}
```

The MCP connector's `inputSchema` format (`{type: "object", properties: {...}, required: [...]}`) maps directly to the OpenAI `parameters` field. The MCP client must convert MCP tool schemas to OpenAI function-calling format.

**ToolCallDelta** (line 63): `tool_call_id: str`, `tool_name: str`, `arguments: str` (JSON string). The turn loop parses `arguments` with `json.loads()`.

### 9. packages/mcp-registry — What Exists vs What's Needed

**Exists:**
- `McpRegistryPort` (read-only Protocol): `list_servers`, `get_server`, `search`
- `InMemoryMcpRegistry`: in-memory catalog of MCP server descriptors
- `McpServerRecord`: mutable record with `tool_schemas: list[dict]`
- `schema_validator.py`: validates tool schemas at registration time
- `admin.py`: write operations (register, version, soft-delete)
- `cursor.py`: cursor pagination

**Does NOT exist (Phase 101 must build):**
- **MCP Client** — actual JSON-RPC 2.0 over stdio client that spawns connector subprocesses
- **Tool discovery** — calling `tools/list` on a live MCP server to get available tools
- **Tool invocation** — calling `tools/call` with arguments and parsing results
- **MCP-to-OpenAI schema conversion** — converting `inputSchema` to OpenAI `parameters` format
- **Subprocess lifecycle** — spawning, health check, timeout, cleanup of Node.js connector processes

The mcp-registry package provides the **catalog** (which connectors exist, their metadata, schemas). Phase 101 builds the **client** (how to connect to and call them). The client can live in `packages/agent-core/src/inkstatute_agent_core/tools/mcp_client.py` or as a new module in `packages/mcp-registry/`.

### 10. lawyer-desktop Rust Tool Implementations — Reference

**Location:** `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/`

The Rust original built these tools (`build_all_tools()` in `chat.rs` line 658):
- `select_skill` — skill selection (not needed in Phase 101 — skill routing is Phase 98/102)
- `ask_user` — clarification (maps to `elicitation.requested`)
- `search_workspace` — workspace FTS5 search (desktop-specific, not in agent core)
- `read_file_relative` — file reading (relative to workspace)
- `fetch_url` — URL fetching (not in Phase 101 scope — could be added later)
- `generate_docx` — document generation (maps to Word track-changes)

**Rust `ask_user` handling** (chat.rs): When `ask_user` tool is called, `finish_ask_user_turn()` terminates the turn immediately — emits a clarification card and saves a "waiting" message. The turn does NOT continue to the next round.

**Rust `generate_docx`**: Calls the Python `contract_review_trackchanges.py` script via subprocess (Tauri sidecar). In the Python agent core, this becomes a direct Python import — no subprocess needed.

## Key Decisions (Auto-Selected)

### 1. Tool Layer Architecture: ToolRegistry + dispatching ToolExecutor

[auto] Q: "How to define and register tools?" → Selected: "ToolRegistry class that maps tool names to callable handlers; a dispatching ToolExecutor that looks up the registry and calls the handler" (recommended)

**Rationale:** The turn loop's `ToolExecutor` is `Callable[[str, str, dict], Awaitable[ToolResult]]` — a simple callable. A `ToolRegistry` holds `dict[str, ToolHandler]` where `ToolHandler = Callable[[dict], Awaitable[ToolResult]]`. The dispatching executor extracts `tool_name` and `arguments`, looks up the handler, and calls it. This is the simplest design that composes with the existing turn loop without modifying it. Tool definitions (OpenAI format) are generated from the registry.

### 2. Clarification Tool: Emits elicitation.requested and signals turn termination

[auto] Q: "How to map clarification to elicitation.requested?" → Selected: "Clarification tool constructs ElicitationRequestedPayload, emits via EventEmitter, and returns a special ToolResult that signals the turn loop to stop (not continue to next round)" (recommended — matches Rust `finish_ask_user_turn()`)

**Rationale:** The clarification tool is special — it terminates the turn. Rather than modifying the turn loop's control flow, the tool returns a `ToolResult` with a special metadata flag (`metadata={"terminate_turn": True, "elicitation_id": ...}`). The turn loop checks this flag after tool execution and breaks out of the round loop. The `elicitation.requested` event is emitted by the tool handler itself (which has access to the EventEmitter). This requires a small enhancement to the turn loop: check `result.metadata.get("terminate_turn")` after each tool execution.

### 3. Regulation Search Tool: MCP client calling law-database connector

[auto] Q: "How to implement 法规检索?" → Selected: "MCP client that spawns the `law-database` Node.js connector as a subprocess and calls `tools/call` with `search_laws` tool" (recommended — reuses existing MCP connector)

**Rationale:** The `law-database` connector already implements `search_laws`, `get_law_detail`, `search_cases` against flk.npc.gov.cn. It's standard MCP (JSON-RPC 2.0 over stdio). Phase 101 builds a Python MCP client that spawns the Node.js process, performs `initialize` handshake, discovers tools via `tools/list`, and calls `tools/call`. The regulation search tool in the agent-core is a thin wrapper that calls the MCP client. Fixture mode (`LAW_DB_FIXTURES=1`) enables testing without network.

### 4. File Reading Tool: Read-only with path sandboxing

[auto] Q: "How to read files safely?" → Selected: "Read-only file reading tool with path sandboxing — only reads within configured workspace/uploads directories, no shell execution, no write access" (recommended — Phase 90 security defaults)

**Rationale:** The file reading tool accepts a file path (or attachment_ref), resolves it against a configured base directory, validates the resolved path is within the sandbox (no path traversal), reads the file as text (with encoding detection), and returns the content. Binary files (docx, pdf) are rejected or return metadata only. The tool has no shell execution, no write access, and no symlink following outside the sandbox.

### 5. Document Generation Tool: Import TrackChangesBuilder, parameterize review items

[auto] Q: "How to generate documents with Word track changes?" → Selected: "Import TrackChangesBuilder from contract_review_trackchanges.py, parameterize REVIEW_ITEMS (make them injectable), call process() + save()" (recommended — CORE-03 says '不重写')

**Rationale:** The script's `TrackChangesBuilder` class is the reusable core. Phase 101 adapts it by:
1. Making `REVIEW_ITEMS` injectable (pass as constructor arg or `process()` parameter)
2. The document generation tool receives review items from the LLM's tool call arguments
3. The tool constructs `TrackChangesBuilder(input_docx_path)`, injects review items, calls `process()` + `save(output_path)`
4. Returns the output path and artifact metadata
5. The agent-core emits `artifact.created` with `kind="trackchanges_docx"`

The script is imported from its location in `lawfirm-profile/scripts/` (or a vendored copy in the agent-core package). The `lxml` dependency is lazy-imported to keep the package importable without it.

### 6. MCP Client Integration: New McpClient in agent-core/tools/mcp_client.py

[auto] Q: "How to reuse mcp-registry?" → Selected: "Build a new McpClient in agent-core/tools/mcp_client.py that implements JSON-RPC 2.0 over stdio; reuse mcp-registry for catalog/descriptor lookup but build the actual client protocol in agent-core" (recommended)

**Rationale:** `packages/mcp-registry` provides the catalog (which servers exist, their schemas) but not the client protocol. The MCP client needs to: spawn subprocess, perform initialize handshake, list tools, call tools, handle responses, manage lifecycle. This is agent-core-specific functionality. The client imports `McpServerDescriptor` from platform-contract for server metadata but implements the JSON-RPC protocol itself. The mcp-registry's `McpServerRecord.tool_schemas` can pre-populate tool definitions without live discovery, but the client also supports live `tools/list` for dynamic discovery.

### 7. Artifact Creation: EventEmitter.emit_artifact_created() + Gateway registration

[auto] Q: "How to emit artifact.created events?" → Selected: "Add emit_artifact_created() to EventEmitter; document generation tool constructs Artifact dataclass and emits the event; Gateway's event consumer registers it in GatewayArtifactStore" (recommended)

**Rationale:** The EventEmitter needs a new `emit_artifact_created(artifact: Artifact)` method that constructs `ArtifactCreatedPayload` and emits via `RunEventType.ARTIFACT_CREATED_V3`. The document generation tool constructs the `Artifact` with `kind="trackchanges_docx"` (or `"docx"` for non-track-changes), `uri` pointing to the output file, and `name` from the tool arguments. The event flows through the normal event stream; the Gateway's event consumer (already existing) registers it in `GatewayArtifactStore` for `GET /v1/artifacts/{id}`.

### 8. Artifact Storage: Local file path with uri_ref

[auto] Q: "How to store and serve docx files?" → Selected: "Write docx to a configured output directory (default: temp dir or workspace/output); Artifact.uri points to the file path; Gateway serves uri_ref (reference-only, no raw content in events)" (recommended — reference-first principle)

**Rationale:** The document generation tool writes the docx to a configurable output directory. The `Artifact.uri` is a file path or `file://` URI. The Gateway's artifact response is reference-only (`uri_ref`), not raw content — matching AGENTS.md: "Contract logs prefer raw_payload_ref" and "Never commit customer documents." The actual file download is handled by the Gateway's artifact endpoint, which returns the `uri_ref` for the client to fetch. For Phase 101, a simple local file path suffices; remote storage (S3, etc.) is V4 scope.

### 9. Tool Permissions: No terminal/execute_code paths; MCP subprocess is controlled

[auto] Q: "How to enforce Phase 90 security defaults?" → Selected: "No tool has terminal or execute_code permission paths; MCP client subprocess spawning is a controlled operation (configured connector path, not arbitrary shell); file reading is sandboxed; all tools are read-only or write-to-output-dir only" (recommended)

**Rationale:** Phase 90's `_DANGEROUS_PERMISSION_KINDS = {"terminal", "execute_code"}` applies to ACP permission requests. The agent-core's tools don't request permissions — they execute directly. The security model is:
- File reading: sandboxed, read-only
- Document generation: writes only to output directory
- Regulation search: HTTP GET to known API
- MCP client: spawns configured Node.js connector (not arbitrary shell)
- Clarification: no I/O
No tool executes arbitrary shell commands or code. The MCP client's subprocess is a controlled, configured operation — the connector path comes from configuration, not user input.

### 10. Tool Result Injection: ToolResult.content appended to messages, turn loop continues

[auto] Q: "How to feed tool results back to turn loop?" → Selected: "ToolResult.content is appended as a tool result message by the existing turn loop mechanism; the turn loop already handles this (lines 245-249, 262-266); no changes needed to the injection mechanism" (recommended — existing design)

**Rationale:** The turn loop already appends tool results to `current_messages` as `{"role": "tool", "tool_call_id": ..., "content": result.content}`. The `ToolRegistry` handlers return `ToolResult(content=..., error=..., metadata=...)`. The dispatching executor passes these through. The only enhancement is checking `metadata.get("terminate_turn")` for the clarification tool (Decision 2). Error results are already handled (lines 268-288): error appended as tool result, loop continues.

### 11. Tool Definitions: Generated from registry in OpenAI format

[auto] Q: "How are tool definitions provided to the LLM?" → Selected: "ToolRegistry.get_tool_definitions() returns a list of OpenAI function-calling format dicts, generated from registered tools; MCP tools are converted from inputSchema to OpenAI parameters format" (recommended)

**Rationale:** The `ChatRequest.tools` field expects OpenAI function-calling format. The `ToolRegistry` stores tool metadata (name, description, parameters schema) alongside each handler. `get_tool_definitions()` produces the `tools` list. For MCP tools, the `inputSchema` (JSON Schema `{type: "object", properties, required}`) maps directly to OpenAI `parameters`. The turn loop passes these definitions to `ChatRequest(tools=registry.get_tool_definitions())`.

## Plan Estimate

**4 plans** (estimated):

1. **101-01**: Tool registry + tool definitions + dispatching executor + EventEmitter enhancements (emit_artifact_created, emit_elicitation_requested, terminate_turn metadata)
2. **101-02**: Clarification tool + file reading tool + regulation search tool (via MCP client)
3. **101-03**: Document generation tool (TrackChangesBuilder integration) + artifact.created emission + MCP client (law-database, wenshu)
4. **101-04**: E2E integration tests + phase completion (multi-tool orchestration, artifact download, MCP tool discovery, security verification)
