# Phase 101 Research — Agent Core Tools

**Phase:** 101 — Agent Core Tools
**Created:** 2026-08-11
**Status:** Complete
**Requirements:** CORE-02, CORE-03

---

## 1. contract_review_trackchanges.py — The Word Native Track Changes Script

### 1.1 Location & Size

**Primary copy:** `/home/sorawatcher/workspace/lawfirm-profile/scripts/contract_review_trackchanges.py` — 715 lines, 41,185 bytes.
**Second copy:** `/home/sorawatcher/workspace/lawfirm-profile/skills/legal-contract-copilot/scripts/contract_review_trackchanges.py` — 17,098 bytes (smaller variant).

### 1.2 Dependencies

- **`lxml`** (`from lxml import etree`) — the only external dependency; used for OOXML XML manipulation.
- **stdlib:** `zipfile`, `shutil`, `os`, `re`, `copy`, `datetime`, `io`.
- **No subprocess, no COM, no Word.exe, no platform-specific code.** Pure Python + lxml, runs on Linux.

### 1.3 Architecture — TrackChangesBuilder Class

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

### 1.4 Track Changes Mechanism (OOXML)

The script generates native Word track changes by manipulating the OOXML XML directly:

| Operation | OOXML Element | Method |
|-----------|---------------|--------|
| **Insertion** | `<w:ins w:id="..." w:author="乙方律师审查" w:date="...">` wrapping new `<w:r>` runs | `_create_ins_element()` (line 318) |
| **Deletion** | `<w:del w:id="..." w:author="乙方律师审查" w:date="...">` wrapping runs with `<w:delText>` (converted from `<w:t>`) | `_create_del_element()` (line 331) |
| **Comment** | `word/comments.xml` with `<w:comment>` elements; paragraphs get `<w:commentRangeStart>`, `<w:commentRangeEnd>`, `<w:commentReference>` | `_add_comment_to_paragraph()` (line 351) |

**Supporting methods for save():**
- `_build_comments_xml()` (line 526) — builds the `word/comments.xml` part
- `_update_content_types()` (line 549) — adds `Override` for `comments.xml` in `[Content_Types].xml`
- `_update_rels()` (line 568) — adds `Relationship` targeting `comments.xml` in `word/_rels/document.xml.rels`
- `_ensure_comment_style()` (line 596) — ensures `CommentReference` style exists in `word/styles.xml`

### 1.5 Input Format — REVIEW_ITEMS

The review items are currently a **module-level constant** (`REVIEW_ITEMS`, line 36, 25 items). Each item is a dict:

```python
{
    "id": 1,                          # unique int
    "find_text": "根据《中华人民共和国",  # text to find in paragraph (for locating)
    "old_text": "根据《中华人民共和国合同法》的规定",  # text to replace
    "new_text": "根据《中华人民共和国民法典》的规定",  # replacement text (None = comment only)
    "comment": "【P0 法律引用已废止】...",  # comment text to attach
    "level": "P0",                     # P0/P1/P2 priority
}
```

The 25 hardcoded items cover a specific technology development contract (技术开发委托合同) reviewed from 乙方 (Party B)立场. Items span P0 (must fix: 11 items), P1 (negotiate: 12 items), P2 (optimize: 2 items).

### 1.6 Output Format

A `.docx` file with:
- Native Word track changes (insertions and deletions visible in Word's Review pane)
- Comments attached to reviewed paragraphs
- Reviewer identity: `"乙方律师审查"` (author), `"乙审"` (initials)
- All changes dated with incrementing timestamps (7 minutes per item from base date)

### 1.7 Text Replacement Algorithm

`_replace_text_in_paragraph()` (line 379) handles the complex case of text spanning multiple XML runs:

1. Collect all `<w:r>` runs and their text boundaries
2. Find `old_text` position in concatenated full text
3. Classify each run as: entirely outside, entirely within, spanning start, spanning end, or containing the full replacement
4. For each case: preserve unaffected run text, wrap old text in `<w:del>`, wrap new text in `<w:ins>`
5. Rebuild the paragraph: remove old `<w:r>` children, insert new elements after `<w:pPr>`

### 1.8 Reuse Strategy (CORE-03 "不重写")

The `TrackChangesBuilder` class is the reusable core. **What needs adaptation:**

1. **REVIEW_ITEMS must be injectable** — currently a module-level constant. The `process()` method (line 620) iterates over `REVIEW_ITEMS` directly. It needs to accept a `review_items` parameter, or the items should be passed to `__init__`.
2. **The `main()` function** (line 682) has hardcoded input/output paths — this is just a demo entry point, not the reusable API.
3. **REVIEWER and REVIEWER_INITIALS** (lines 25-26) are hardcoded constants — could be parameterized for multi-party review.

**Approach: Import, don't copy.** The agent-core's document generation tool imports `TrackChangesBuilder` from the lawfirm-profile script location (or a vendored copy). The tool:
1. Receives review items from the LLM (as tool call arguments)
2. Constructs `TrackChangesBuilder(input_docx_path)`
3. Injects review items (via parameterized `process()` call)
4. Calls `process()` and `save(output_path)`
5. Returns the output path as the tool result

**lxml dependency:** `packages/agent-core/pyproject.toml` currently has `dependencies = []`. Adding `lxml` is the first external dependency. The document generation tool should **lazy-import lxml** (matching the provider_model pattern of lazy SDK imports via `importlib.import_module`), so the package remains importable without lxml installed.

---

## 2. packages/mcp-registry — MCP Client and Tool Discovery

### 2.1 File Inventory

**Location:** `packages/mcp-registry/src/inkstatute_mcp_registry/`

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 35 | Re-exports all public types |
| `registry.py` | 204 | `McpRegistryPort` (read-only Protocol), `McpServerPage`, `McpServerRecord`, `InMemoryMcpRegistry` |
| `admin.py` | 191 | `McpRegistryAdminPort` (write Protocol), `InMemoryMcpRegistryAdmin`, `McpServerRegistrationSpec` |
| `cursor.py` | 26 | `encode_cursor()`, `decode_cursor()` — base64-urlsafe pagination |
| `schema_validator.py` | 55 | `validate_tool_schema()`, `validate_tool_schemas()` — basic JSON Schema validation |

**Total: 511 lines across 5 files.** No external dependencies.

### 2.2 What mcp-registry Provides (Catalog)

The mcp-registry package is a **registry/catalog** — it stores MCP server descriptors and tool schemas, but does **not** implement the MCP client protocol (stdio JSON-RPC).

**`McpRegistryPort` (read-only Protocol):**
```python
class McpRegistryPort(Protocol):
    def list_servers(self, cursor: str | None = None, limit: int = 50) -> McpServerPage: ...
    def get_server(self, server_id: str) -> McpServerDescriptor | None: ...
    def search(self, query: str, cursor: str | None = None, limit: int = 50) -> McpServerPage: ...
```

**`McpServerRecord`** (internal mutable record):
- `server_id`, `name`, `transport`, `capability_refs`, `secret_refs`
- `tool_schemas: list[dict[str, Any]]` — JSON Schema tool definitions
- `active: bool`, `version: str`, `admission_status: str` — admin fields
- `to_descriptor()` → converts to frozen `McpServerDescriptor` (admin fields placed in `metadata`)

**`McpRegistryAdminPort` (write Protocol):**
- `register_server(spec)` — validates tool schemas, creates inactive record (admission_status="pending")
- `approve_server(server_id)` — sets active=True, admission_status="approved"
- `update_version(server_id, version, tool_schemas)` — semantic versioning
- `deactivate_server(server_id)` — soft-delete

**Key design principle:** Registration does NOT auto-execute — the `mcp` SDK is never invoked during registration. An admission review step is required before a connector is marked active.

### 2.3 What mcp-registry Does NOT Provide (Phase 101 Must Build)

| Gap | Description |
|-----|-------------|
| **MCP Client** | Actual JSON-RPC 2.0 over stdio client that spawns connector subprocesses |
| **Tool discovery** | Calling `tools/list` on a live MCP server to get available tools |
| **Tool invocation** | Calling `tools/call` with arguments and parsing results |
| **MCP-to-OpenAI schema conversion** | Converting `inputSchema` to OpenAI `parameters` format |
| **Subprocess lifecycle** | Spawning, health check, timeout, cleanup of Node.js connector processes |

The MCP client should live in `packages/agent-core/src/inkstatute_agent_core/tools/mcp_client.py`. It imports `McpServerDescriptor` from platform-contract for server metadata but implements the JSON-RPC protocol itself. The mcp-registry's `McpServerRecord.tool_schemas` can pre-populate tool definitions without live discovery, but the client also supports live `tools/list` for dynamic discovery.

---

## 3. MCP Connector Architecture — law-database and wenshu

### 3.1 Location

**Repository:** `/home/sorawatcher/workspace/ai-for-china-legal/connectors/`

### 3.2 Connector Inventory

| Connector | Status | Tools | Implementation |
|-----------|--------|-------|----------------|
| `law-database` | ✅ Implemented | `search_laws`, `get_law_detail`, `search_cases_by_law` (3 tools) | `index.js` (567 lines) |
| `wenshu` | ✅ Implemented | `search_cases`, `get_case_detail`, `get_case_statistics` (3 tools) | `index.js` (481 lines) |
| `gsxt` | Config only | — | `connector.json` only, no `index.js` |
| `patent` | Config only | — | `connector.json` only |
| `trademark` | Config only | — | `connector.json` only |
| `wechat-notify` | Config only | — | `connector.json` only |

### 3.3 Protocol — Standard MCP (JSON-RPC 2.0 over stdio)

**Shared RPC library:** `connectors/_lib/rpc.js` (117 lines)

Protocol contract (from `rpc.js`):
- One JSON object per line on stdin, exactly one JSON object per line on stdout
- NO banners / pretty-print on stdout; ALL logging goes to stderr
- `initialize` → `{protocolVersion: "2024-11-05", capabilities: {tools: {}}, serverInfo}`
- `notifications/initialized` → no response
- `tools/list` → `{tools: [{name, description, inputSchema}]}`
- `tools/call` → `{content: [{type: "text", text}], isError: false}` (isError true only for internal crashes; "no results" is a normal text result)
- Unknown method WITH id → error `{code: -32601, message: "method not found"}`
- Parse errors on a line: log to stderr, ignore the line

**Protocol version:** `"2024-11-05"` (MCP standard)
**Runtime:** Node.js 18+ built-ins only, zero npm dependencies. CommonJS (not ESM).

### 3.4 law-database Connector Details

**Data sources:**
- 国家法律法规数据库 (flk.npc.gov.cn) — REST API
- 国务院政策文件库 (www.gov.cn) — web scrape
- 最高人民法院司法解释 (www.court.gov.cn) — web scrape

**Tools:**
1. `search_laws` — keyword search with lawType, issuingAuthority, dateRange, status filters; returns hit blocks with provenance
2. `get_law_detail` — full text by law name or document number; includes article-level truncation, gold URL fallback (court.gov.cn), revision history
3. `search_cases_by_law` — finds cases citing a specific law from Supreme Court guiding/typical case lists

**Key features:**
- **Fixture mode:** `LAW_DB_FIXTURES=1` → reads canned responses from `./fixtures` directory (enables testing without network)
- **Caching:** `cache.withCache()` wraps each tool call with TTL-based caching (default 86400s)
- **Degradation:** When flk.npc.gov.cn is unreachable, returns honest degradation text with retry suggestions
- **Provenance blocks:** Each result includes structured provenance metadata (tier, channel, URL, method, validity)
- **Budget:** 40-second deadline per tool call

### 3.5 wenshu Connector Details

**Data source:** 中国裁判文书网 (wenshu.court.gov.cn) — REST API

**Tools:**
1. `search_cases` — keyword, causeOfAction, courtName, courtLevel, dateRange, caseType filters
2. `get_case_detail` — by case number (案号)
3. `get_case_statistics` — case trend statistics by causeOfAction, courtName, timeRange, groupBy

**Authentication:** `WENSHU_API_KEY` environment variable (Bearer token). If not configured, returns error message.

### 3.6 Tool Schema Format

MCP tools use standard JSON Schema for `inputSchema`:
```json
{
    "name": "search_laws",
    "description": "根据关键词、法规类型、发布机构等条件搜索法律法规",
    "inputSchema": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "搜索关键词"},
            "lawType": {"type": "string", "enum": [...], "description": "法规类型"},
            ...
        },
        "required": []
    }
}
```

This maps **directly** to OpenAI function-calling `parameters` field:
```json
{
    "type": "function",
    "function": {
        "name": "search_laws",
        "description": "根据关键词...",
        "parameters": {
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    }
}
```

The MCP-to-OpenAI conversion is a simple field rename: `inputSchema` → `parameters`, wrapped in `{"type": "function", "function": {...}}`.

### 3.7 V3-SELECTION Conclusion

From `.planning/research/V3-SELECTION.md` (V1 conclusion): "标准 MCP client 可直连，无需适配" — Phase 101 needs a standard MCP client that spawns the Node.js connector as a subprocess and communicates over stdio. No custom adapter needed.

---

## 4. Elicitation Protocol — Clarification Questions

### 4.1 Payload Dataclasses

**Location:** `packages/platform-contract/src/platform_contract/unified_events.py` (lines 93-114)

```python
@dataclass(frozen=True, slots=True)
class ElicitationOption:
    label: str
    value: str

@dataclass(frozen=True, slots=True)
class ElicitationQuestion:
    id: str
    question: str
    allow_multiple: bool = False
    options: list[ElicitationOption] = field(default_factory=list)

@dataclass(frozen=True, slots=True)
class ElicitationRequestedPayload:
    interrupt_id: str
    intro: str
    questions: list[ElicitationQuestion]
    resume_state_ref: str | None = None
    expires_at: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

### 4.2 ASK-USER-PROTOCOL Constraints

**Location:** `packages/platform-contract/src/platform_contract/elicitation.py` (189 lines)

- **2-4 questions** per elicitation (enforced by `validate_question_count()`, line 130)
- Each question type:
  - **Single-select:** `allow_multiple=False` + non-empty `options`
  - **Multi-select:** `allow_multiple=True` + non-empty `options`
  - **Free-text:** empty `options`
- `format_answer_display()` (line 146): formats answers as numbered list with question text and answer (multi-select values joined by `、`)

### 4.3 Conversion Functions

- `elicitation_to_run_interrupt(payload, run_id, session_id, created_id)` → V2 `RunInterrupt` (for persistence)
  - `prompt_ref` = `"elicitation://<interrupt_id>"` (reference-first)
  - `reason` = `"clarification"`
  - `status` = `WAITING_FOR_USER`
  - Full question structure stored in `metadata` for round-trip fidelity
- `run_interrupt_to_elicitation(interrupt)` → `ElicitationRequestedPayload` (reconstructs from metadata for replay)

### 4.4 How the Agent Core Emits Elicitation

The clarification tool (`ask_user`) is **special** — it terminates the current turn (matching Rust `finish_ask_user_turn()`). When the LLM calls the clarification tool:

1. The tool handler constructs `ElicitationRequestedPayload` from the tool call arguments
2. The tool handler emits `elicitation.requested` event (via EventEmitter — needs new `emit_elicitation_requested()` method)
3. The tool returns a `ToolResult` with `metadata={"terminate_turn": True, "elicitation_id": ...}`
4. The turn loop checks `result.metadata.get("terminate_turn")` after each tool execution and breaks out of the round loop
5. The run enters `WAITING_FOR_USER` state
6. When the user answers, a new turn starts with the answers injected as context (`"以下是补充信息…"`)

### 4.5 Rust Reference — ask_user Handling

**Location:** `lawyer-desktop/src-tauri/src/commands/chat_tools.rs` (lines 38-60, 296-323) and `chat.rs` (lines 1319-1342, 864-874, 905-915, 1041-1051)

Rust types:
```rust
struct AskUserOption { label, value, description }
struct AskUserQuestion { id, question, options, allow_multiple, allow_free_text }
struct AskUserRequest { id, intro, questions }
```

`parse_ask_user_args()` (line 296):
- Parses `AskUserRequest` from JSON args
- Removes empty questions
- Truncates to 4 questions max
- Auto-assigns `q1`, `q2`, etc. if `id` is empty
- Removes empty options
- Auto-fills `value` from `label` if empty
- If no options, adds a single `"由我补充"` (free-text fallback) option

`finish_ask_user_turn()` (line 1326):
- Emits `"clarifying"` stream status
- Saves a "waiting" message to SQLite
- Returns immediately — the turn does NOT continue to the next round

`ToolBatch` struct (line 1319):
```rust
struct ToolBatch {
    results: Vec<(String, String)>,
    ask_user: Option<AskUserRequest>,  // Some → terminate turn
    retrievals: Vec<(String, String)>,
}
```

When `batch.ask_user` is `Some(...)`, the turn immediately calls `finish_ask_user_turn()` and returns — no further tool execution or LLM calls in this turn.

### 4.6 EventEmitter Gap

**Location:** `packages/agent-core/src/inkstatute_agent_core/event_emitter.py` (329 lines)

Current emit methods (9 total): `emit_message_delta`, `emit_message_completed`, `emit_thought_delta`, `emit_tool_call_started`, `emit_tool_call_delta`, `emit_tool_call_completed`, `emit_phase_changed`, `emit_run_state_changed`, `emit_error`.

**Missing for Phase 101:**
- `emit_elicitation_requested(interrupt_id, intro, questions, ...)` — needs `ElicitationRequestedPayload`
- `emit_artifact_created(artifact, ...)` — needs `ArtifactCreatedPayload`
- `emit_permission_requested(permission_id, tool_call_id, description, kind, ...)` — needs `PermissionRequestedPayload` (may be needed if tools request permissions)

The `_emit()` internal method (line 124) handles seq numbering, occurred_at, and RunEvent construction. New emit methods follow the same pattern: construct payload dataclass → call `_emit(RunEventType.X, payload)`.

---

## 5. Artifact Events — artifact.created

### 5.1 ArtifactKind Enum

**Location:** `packages/platform-contract/src/platform_contract/enums.py` (line 89)

```python
class ArtifactKind(StrEnum):
    DOCX = "docx"
    PPTX = "pptx"
    TRACKCHANGES_DOCX = "trackchanges_docx"
    XLSX = "xlsx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    JSON = "json"
    OTHER = "other"
```

Phase 101 success criterion 4 requires `kind` to correctly distinguish `docx` from `trackchanges_docx`. The enum already has both values.

### 5.2 Artifact Dataclass

**Location:** `packages/platform-contract/src/platform_contract/events.py` (line 61)

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
    source_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```

### 5.3 ArtifactCreatedPayload

**Location:** `packages/platform-contract/src/platform_contract/unified_events.py` (line 127)

```python
@dataclass(frozen=True, slots=True)
class ArtifactCreatedPayload:
    artifact: Artifact
    metadata: JsonObject = field(default_factory=dict)
```

### 5.4 Artifact Creation Flow

1. Document generation tool produces a docx file → writes to a storage location (local file path or temp dir)
2. Tool constructs `Artifact(artifact_id=uuid, kind="trackchanges_docx", name=..., uri="file:///path/to/output.docx")`
3. EventEmitter emits `artifact.created` with `ArtifactCreatedPayload(artifact=artifact)` — needs new `emit_artifact_created()` method
4. Gateway's event consumer registers the artifact in `GatewayArtifactStore`
5. Client downloads via `GET /v1/artifacts/{artifact_id}` → gets `uri_ref` (reference-only, no raw content)

### 5.5 Bot Degradation for artifact.created

**Location:** `packages/platform-contract/src/platform_contract/bot_degradation.py` (line 70)

`artifact.created` is categorized as `DegradationCategory.DELIVER` — for bot channels, it is delivered as a file attachment. The degradation aggregator (line 203) appends artifact payloads to the `files` list.

### 5.6 Five-Phase Mapping

**Location:** `packages/platform-contract/src/platform_contract/five_phase.py` (line 88)

`artifact.created` maps to `FivePhase.REVIEW` — artifacts are produced and citations verified during the review phase.

---

## 6. Gateway Artifact Endpoint — /v1/artifacts/{id}

### 6.1 Location

**`services/gateway/src/gateway/artifacts.py`** (131 lines)

### 6.2 GatewayArtifactStore

In-memory artifact store with tenant isolation:

```python
@dataclass
class ArtifactMetadata:
    artifact_id: str
    kind: str
    uri_ref: str
    name: str | None = None
    tenant_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

class GatewayArtifactStore:
    def register_artifact(self, artifact: ArtifactMetadata) -> None: ...
    def get_artifact(self, artifact_id: str, *, tenant_id: str) -> ArtifactMetadata | None: ...
    def list_artifacts(self, run_id: str, *, tenant_id: str) -> list[ArtifactMetadata]: ...
```

**Tenant isolation:** Cross-tenant access returns `None` (invisible), not an error. The handler returns 404 for both not-found and cross-tenant denied — no existence leak.

### 6.3 Handler — handle_get_artifact_request()

```python
def handle_get_artifact_request(store, auth_ctx, artifact_id) -> JsonObject:
    artifact = store.get_artifact(artifact_id, tenant_id=auth_ctx.tenant_id)
    if artifact is None:
        return {"error": {"code": "not_found", "message": ...}, "status": 404}
    return {
        "artifact_id": artifact.artifact_id,
        "kind": artifact.kind,
        "uri_ref": artifact.uri_ref,
        "name": artifact.name,
        "tenant_id": artifact.tenant_id,
        "reference_only": True,
        "status": 200,
    }
```

**Reference-only:** The response does NOT include raw artifact content — only the `uri_ref` pointing to the storage location. This satisfies AGENTS.md: "Contract logs prefer raw_payload_ref" and "Never commit customer documents."

### 6.4 Route Registration

**Location:** `services/gateway/src/gateway/app.py` (line 619)

```python
# GET /v1/artifacts/{artifact_id}
if method == "GET" and len(parts) == 2 and parts[0] == "artifacts":
    return OPERATION_GET_ARTIFACT, {"artifact_id": parts[1]}
```

The handler is dispatched at line 266: `return await self._handle_get_artifact(ctx, path_params)`.

### 6.5 Storage Backend

The Gateway currently uses an **in-memory store** (`GatewayArtifactStore`). For Phase 101, the agent-core's document generation tool writes the docx to a local file path (or temp dir) and the `Artifact.uri` points to that location. The Gateway's `uri_ref` is reference-first — it doesn't store raw content. Remote storage (S3, etc.) is V4 scope.

### 6.6 OpenAPI Documentation

**Location:** `services/gateway/src/gateway/openapi.py` (line 113)

The endpoint is documented in the OpenAPI spec:
- Path: `/v1/artifacts/{artifact_id}`
- Method: GET
- Summary: "Download an artifact by id."
- Description: "Retrieve artifact metadata by artifact_id. Returns a uri_ref (not raw content). Cross-tenant access returns 404. Reference-only: no raw content is stored or returned."
- Response 200: `ArtifactResponse` schema with `artifact_id`, `kind`, `uri_ref`, `name`, `tenant_id`

---

## 7. Tool Layer from Phase 100 — ToolExecutor

### 7.1 Turn Loop Tool Execution Seam

**Location:** `packages/agent-core/src/inkstatute_agent_core/turn_loop.py` (369 lines)

The turn loop from Phase 100 already has the tool execution seam built in:

```python
# Type alias for the tool executor callable
ToolExecutor = Callable[[str, str, dict], Awaitable[ToolResult]]
# (tool_call_id, tool_name, arguments) -> ToolResult

@dataclass(frozen=True, slots=True)
class ToolResult:
    content: str
    error: ErrorInfo | None = None
    metadata: JsonObject = field(default_factory=dict)
```

The `run_turn()` function accepts a `tool_executor: ToolExecutor | None` parameter. When `None`, it produces fixture results (`"[fixture tool result]"`).

### 7.2 Tool Call Flow in the Turn Loop

1. **Tool call accumulation** (line 158-159): `ToolCallDelta` objects are accumulated from the stream
2. **Assistant message with tool calls** (line 183-187): built and appended to `current_messages`
3. **Per tool call execution** (line 190-288):
   - a. `emit_tool_call_started(tool_call_id, tool_name)` (line 192)
   - b. Heartbeat check during tool execution (line 198)
   - c. Execute tool: `result = await tool_executor(tool_call_id, tool_name, args_dict)` (line 212)
   - d. If `result.error is not None`: `emit_tool_call_completed(status="error", error=result.error)` + append error as tool result (line 218-233)
   - e. If succeeded: `emit_tool_call_delta(content="执行完成")` + `emit_tool_call_completed(status="succeeded", content=result.content)` + append tool result (line 234-250)
   - f. If exception: `emit_tool_call_completed(status="error", error=error_info)` + append error as tool result (line 268-288)
4. **Transition thought** (line 291): `emit_thought_delta("工具执行完成，正在整合结果...")`
5. **Continue to next round** (line 294)

### 7.3 Tool Result Injection

Tool results are appended to `current_messages` as:
```python
{"role": "tool", "tool_call_id": tool_call_id, "content": result.content}
```

Error results are prefixed with `"Error: "`:
```python
if is_error and not content.startswith("Error: "):
    content = f"Error: {content}"
```

The turn loop already handles this — **no changes needed to the injection mechanism**. The only enhancement for Phase 101 is checking `metadata.get("terminate_turn")` for the clarification tool.

### 7.4 Arguments Parsing

The turn loop parses tool call arguments from JSON string (line 207-210):
```python
try:
    args_dict = json.loads(tc_delta.arguments) if tc_delta.arguments else {}
except (json.JSONDecodeError, TypeError):
    args_dict = {}
```

### 7.5 What Phase 101 Must Build

- A **`ToolRegistry`** that maps tool names to callable handlers
- A **dispatching `ToolExecutor`** that looks up the registry and calls the handler
- Individual tool implementations: clarification, regulation search, file reading, document generation, MCP client
- Tool definitions in OpenAI function-calling format (for `tools` parameter in `ChatRequest`)
- EventEmitter enhancements: `emit_artifact_created()`, `emit_elicitation_requested()`
- Turn loop enhancement: check `result.metadata.get("terminate_turn")` after tool execution

### 7.6 Tool Definition Format

**Location:** `packages/agent-core/src/inkstatute_agent_core/model/provider.py`

The `ChatRequest` dataclass accepts `tools: list[dict] | None` — tool definitions in **OpenAI function-calling format**:

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

The `ToolRegistry` should store tool metadata (name, description, parameters schema) alongside each handler. `get_tool_definitions()` produces the `tools` list. For MCP tools, the `inputSchema` maps directly to OpenAI `parameters`.

---

## 8. File Reading Tool — Safe File Reading

### 8.1 Rust Reference — PathSandbox

**Location:** `lawyer-desktop/src-tauri/src/security/path_sandbox.rs` (153 lines)

The Rust original implements path sandboxing with:

```rust
pub struct PathSandbox {
    allowed_roots: Vec<PathBuf>,
}

impl PathSandbox {
    pub fn validate(&self, path: &str) -> Result<PathBuf> {
        // 1. Reject paths with ParentDir components (path traversal)
        if input.components().any(|c| matches!(c, Component::ParentDir)) {
            bail!("path traversal not allowed: {}", path);
        }
        // 2. Canonicalize the path (resolve symlinks)
        let canonical = std::fs::canonicalize(input)?;
        // 3. Check canonical path starts with an allowed root
        for root in &self.allowed_roots {
            let root_canon = std::fs::canonicalize(root)?;
            if canonical.starts_with(&root_canon) {
                return Ok(canonical);
            }
        }
        bail!("access denied: outside allowed directories");
    }
}
```

**Security constraints:**
1. **No `..` components** — rejected before canonicalization
2. **Canonicalization** — resolves symlinks to their real path
3. **Allowlist of roots** — canonical path must start with an allowed root
4. **Tests:** `allows_file_inside_root`, `rejects_path_outside_roots`, `rejects_parent_dir_traversal`

### 8.2 Rust Tool Definitions for File Reading

**Location:** `lawyer-desktop/src-tauri/src/skills/router.rs` (lines 238-309)

The Rust original defines workspace tools:
- `search_workspace` — FTS5 full-text search in indexed case directory
- `read_chunk` — read indexed chunk by chunk_id
- `read_file` — read file by relative path within workspace root (max 50000 chars)
- `list_files` — list indexed files with optional pattern filter
- `get_index_status` — query workspace index status

And a builtin tool:
- `read_user_file` — read user-uploaded or local file by absolute path (validated by PathSandbox)

### 8.3 Python Port Design

The Python file reading tool should:
1. Accept a file path (or attachment_ref) as argument
2. Resolve the path against a configured base directory (workspace/uploads)
3. **Reject `..` components** (path traversal prevention)
4. **Canonicalize** the path (resolve symlinks via `pathlib.Path.resolve()`)
5. **Validate** the canonical path is within an allowed root
6. Read the file as text (with encoding detection — try UTF-8, fall back to latin-1)
7. Binary files (docx, pdf) are rejected or return metadata only
8. Enforce a max character limit (default 50000, matching Rust)
9. No shell execution, no write access, no symlink following outside the sandbox

---

## 9. Document Generation — Connecting to TrackChangesBuilder

### 9.1 Invocation Strategy: Direct Python Import

The Rust original called `contract_review_trackchanges.py` via subprocess (Tauri sidecar). In the Python agent core, this becomes a **direct Python import** — no subprocess needed.

**Approach:**
```python
# Lazy import to keep package importable without lxml
import importlib
mod = importlib.import_module("contract_review_trackchanges")
TrackChangesBuilder = mod.TrackChangesBuilder

# Use it
builder = TrackChangesBuilder(input_docx_path)
results = builder.process(review_items=llm_generated_items)
builder.save(output_path)
```

### 9.2 Required Adaptation to TrackChangesBuilder

1. **`process()` method** (line 620) currently iterates `REVIEW_ITEMS` (module-level constant). Must accept a `review_items: list[dict]` parameter.
2. **REVIEWER/REVIEWER_INITIALS** (lines 25-26) are module-level constants. Could be parameterized via constructor or `process()` parameter.
3. The `main()` function (line 682) is a demo entry point — not used by the agent core.

### 9.3 Tool Interface

The document generation tool receives from the LLM:
- `input_docx_path` — path to the original contract docx
- `review_items` — list of review items (each with find_text, old_text, new_text, comment, level)
- `output_path` — where to write the revised docx
- `reviewer` (optional) — reviewer name for track changes attribution

The tool:
1. Validates paths (sandbox check for both input and output)
2. Lazy-imports `TrackChangesBuilder`
3. Constructs `TrackChangesBuilder(input_docx_path)`
4. Calls `process(review_items=review_items)` (adapted method)
5. Calls `save(output_path)`
6. Constructs `Artifact(artifact_id=uuid4(), kind="trackchanges_docx", name=..., uri="file://...")`
7. Emits `artifact.created` event
8. Returns `ToolResult(content=f"修订版已生成: {output_path}", metadata={"artifact_id": ..., "output_path": ...})`

### 9.4 lxml Dependency

`packages/agent-core/pyproject.toml` currently has `dependencies = []`. Options:
1. **Add `lxml` to dependencies** — simplest, but adds a build-time dependency (lxml requires libxml2/libxslt)
2. **Lazy-import lxml** (recommended) — matches the provider_model pattern. The document generation tool lazy-imports the track-changes module (which imports lxml). If lxml is not installed, the tool returns an error result (not a crash). The package remains importable without lxml.

---

## 10. Regulation Search — 法规检索

### 10.1 Existing Capabilities

**MCP connectors (production-ready):**
- `law-database` — 3 tools: `search_laws`, `get_law_detail`, `search_cases_by_law` (flk.npc.gov.cn)
- `wenshu` — 3 tools: `search_cases`, `get_case_detail`, `get_case_statistics` (wenshu.court.gov.cn)

**Rust original built-in tools** (router.rs lines 312-361):
- `legal_search` — aggregated search (concurrent local + online)
- `search_law` — local law library FTS5 search (offline-available)
- `get_law_article` — precise article retrieval from local law library

### 10.2 Phase 101 Approach

Per the context document Decision 3: "MCP client that spawns the `law-database` Node.js connector as a subprocess and calls `tools/call` with `search_laws` tool."

The regulation search tool in the agent-core is a **thin wrapper** that calls the MCP client. The MCP client:
1. Spawns the `law-database` Node.js connector as a subprocess (`node index.js`)
2. Performs `initialize` handshake (protocol version "2024-11-05")
3. Sends `notifications/initialized`
4. Discovers tools via `tools/list`
5. Calls `tools/call` with the appropriate tool name and arguments
6. Parses the response (`{content: [{type: "text", text}], isError: false}`)
7. Returns the text content as `ToolResult.content`

**Fixture mode:** `LAW_DB_FIXTURES=1` environment variable enables testing without network — the connector reads canned responses from `./fixtures` directory.

### 10.3 Retrieval Tool Identification

**Location:** `lawyer-desktop/src-tauri/src/skills/router.rs` (line 36)

```rust
pub fn is_retrieval_tool_name(name: &str) -> bool {
    matches!(name, "legal_search" | "search_law" | "get_law_article" | "fetch_url" | "search_workspace")
    || (name.starts_with("mcp__") && {
        let lower = name.to_lowercase();
        ["law", "legal", "fagui", "statute", "wenshu", "case", "judgment"]
            .iter().any(|kw| lower.contains(kw))
    })
}
```

This function identifies which tool calls count as "retrieval" for citation auditing (Phase 102). MCP tools with names containing `law`, `legal`, `fagui`, `statute`, `wenshu`, `case`, or `judgment` are retrieval tools. The Python port should preserve this logic.

---

## 11. Security Defaults from Phase 90

### 11.1 Dangerous Permission Kinds

**Location:** `packages/acp-client/src/inkstatute_acp_client/adapter.py` (line 114)

```python
_DANGEROUS_PERMISSION_KINDS: frozenset[str] = frozenset({"terminal", "execute_code"})
```

### 11.2 Rules (from AGENTS.md and Phase 90)

- `terminal` / `execute_code` permission requests must be **explicitly denied** or escalated to user approval
- Server-side must **never** auto-approve (`allow_once` is forbidden — reference: Buzz's ACP bridge auto-allow accident)
- ACP `session/request_permission` for dangerous kinds → run set to `WAITING_FOR_USER` with issue
- `submit_approval()` with `decision="approved"` and `kind in _DANGEROUS_PERMISSION_KINDS` → rejected, run stays `WAITING_FOR_USER`

### 11.3 Phase 101 Tool Permissions

The agent-core's tools must follow the same security defaults. **No tool in Phase 101 should have a `terminal` or `execute_code` permission path:**

| Tool | I/O | Security |
|------|-----|----------|
| **File reading** | Read-only | Path sandboxing (no `..`, canonicalize, allowlist roots); no shell, no write |
| **Document generation** | Write to output dir only | Path validation; no shell; writes only to designated output directory |
| **Regulation search** | HTTP GET to known API | No shell; only contacts flk.npc.gov.cn / wenshu.court.gov.cn |
| **MCP client** | Subprocess (Node.js) | **Controlled subprocess** — connector path is configured, not user-supplied; stdio JSON-RPC only; not arbitrary shell execution |
| **Clarification** | No I/O | Just constructs events. Safe. |

The MCP client's subprocess spawning is a **controlled, configured operation** (specific Node.js script with stdio JSON-RPC), not arbitrary shell execution. The connector path comes from configuration, not user input.

### 11.4 PermissionRequestedPayload (for reference)

**Location:** `packages/platform-contract/src/platform_contract/unified_events.py` (line 118)

```python
@dataclass(frozen=True, slots=True)
class PermissionRequestedPayload:
    permission_id: str
    tool_call_id: str
    description: str
    kind: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

The schema description states: "Must NEVER be auto-approved server-side." Phase 101 tools don't request permissions — they execute directly. But the payload exists for future use if a tool needs user approval for a sensitive operation.

---

## 12. lawyer-desktop Rust Tool Implementations — Full Reference

### 12.1 Tool Inventory

**Location:** `lawyer-desktop/src-tauri/src/commands/chat_tools.rs` (line 286)

```rust
pub async fn build_all_tools(mcp: &McpManager, mode: AgentMode, include_workspace: bool) -> Vec<ToolDefinition> {
    let mut tools = router::build_builtin_tool_definitions(mode, include_workspace);
    tools.extend(mcp.build_tool_definitions().await);
    tools
}
```

**Builtin tools** (router.rs `build_builtin_tool_definitions`, line 363):
- `read_user_file` — read user file by absolute path (PathSandbox validated)
- `fetch_url` — fetch URL content (max 20000 chars, 20s timeout)
- `generate_docx` — generate docx from title + content_markdown + output_path (PathSandbox validated)
- `select_skill` — activate a legal skill by name

**Workspace tools** (router.rs `build_workspace_tool_definitions`, line 238):
- `search_workspace` — FTS5 search in indexed case directory
- `read_chunk` — read indexed chunk by chunk_id
- `read_file` — read file by relative path within workspace root
- `list_files` — list indexed files
- `get_index_status` — query index status

**Law library tools** (router.rs `build_law_tool_definitions`, line 312):
- `legal_search` — aggregated search (concurrent local + online)
- `search_law` — local law library FTS5 search
- `get_law_article` — precise article retrieval from local library

**MCP tools** — dynamically discovered from `McpManager`, prefixed with `mcp__<server>__<tool>` (e.g., `mcp__law-database__search_laws`, `mcp__wenshu__search_cases`)

### 12.2 Phase 101 Scope vs Deferred

| Rust Tool | Phase 101? | Notes |
|-----------|-----------|-------|
| `ask_user` | ✅ Yes | Maps to `elicitation.requested`; clarification tool |
| `generate_docx` | ✅ Yes | Maps to TrackChangesBuilder; document generation tool |
| `read_user_file` / `read_file` | ✅ Yes | File reading tool with path sandboxing |
| `legal_search` / `search_law` / `get_law_article` | ✅ Yes (via MCP) | Regulation search tool via MCP client calling `law-database` |
| MCP tools (`law-database`, `wenshu`) | ✅ Yes | MCP client integration |
| `select_skill` | ❌ Phase 102 | Skill routing is Phase 98/102 |
| `search_workspace` | ❌ Desktop-specific | Workspace FTS5 is desktop-only, not in agent core |
| `fetch_url` | ❌ Later | URL fetching not in Phase 101 scope |

### 12.3 Rust generate_docx Implementation

**Location:** `lawyer-desktop/src-tauri/src/commands/chat_tools.rs` (line 385)

```rust
"generate_docx" => {
    let title = args.get("title")...;
    let content = args.get("content_markdown")...;
    let output_path = args.get("output_path")...;
    let validated = ctx.sandbox.validate(output_path)?;
    docx_gen::generate_docx(title, content, &validated)?;
    // Save document metadata to SQLite
    Ok(format!("DOCX 已生成: {}", validated.display()))
}
```

The Rust version uses `docx_gen::generate_docx()` (a basic Rust docx generator, 74 lines). Phase 101 replaces this with `TrackChangesBuilder` from the Python script — a much more capable implementation that produces Word-native track changes.

---

## 13. packages/agent-core Current State (from Phase 100)

### 13.1 File Inventory

**Location:** `packages/agent-core/src/inkstatute_agent_core/`

| File | Lines | Purpose | Phase |
|------|-------|---------|-------|
| `__init__.py` | 21 | Package docstring, `__version__` | 100 |
| `config.py` | 72 | `AgentCoreConfig` — max_turns, silence_threshold, temperature, etc. | 100-01 |
| `event_emitter.py` | 329 | `EventEmitter` — 9 emit methods, heartbeat, monotonic seq | 100-01 |
| `fixtures.py` | — | `FixtureProvider`, `TurnScript` — testing without external LLM | 100-02 |
| `context.py` | — | `AgentContextAssembler` — history trim + skill body injection | 100-03 |
| `turn_loop.py` | 369 | `run_turn()` async generator, `ToolResult`, `ToolExecutor` | 100-03 |
| `messages.py` | — | Message building helpers (tool results, assistant messages) | 100-03 |
| `model/provider.py` | — | `LlmProvider` Protocol, `StreamDelta` union, `ChatRequest` | 100-02 |
| `model/openai_runner.py` | — | `OpenAIStreamProvider` with tool call + reasoning | 100-02 |
| `model/anthropic_runner.py` | — | `AnthropicStreamProvider` with tool call + reasoning | 100-02 |
| `model/ollama_runner.py` | — | `OllamaStreamProvider` | 100-02 |
| `model/gateway_components.py` | — | `GatewayComponents` (circuit breaker, rate limiter, cost tracker) | 100-02 |
| `model/config.py` | — | `ProviderModelConfig` | 100-02 |
| `model/error_normalization.py` | — | `normalize_provider_error()`, `sanitize_error_message()` | 100-02 |
| `tools/__init__.py` | 9 | **Placeholder** — "Populated in Phase 101" | — |

### 13.2 Test Count

- **agent-core gate:** 340 tests, all PASS, 0 external calls
- **Full gate suite:** 38 gates, all green
- **No external dependencies:** `dependencies = []` in pyproject.toml

### 13.3 tools/ Sub-Package

**Location:** `packages/agent-core/src/inkstatute_agent_core/tools/__init__.py`

Currently a placeholder:
```python
"""Tool layer for the InkStatute agent core.

This sub-package will contain the tool registry, tool execution, and
MCP client integration.

Populated in Phase 101.
"""
```

Phase 101 will populate this with:
- `tools/registry.py` — `ToolRegistry`, `ToolHandler` type, dispatching executor
- `tools/clarification.py` — clarification (ask_user) tool
- `tools/file_reader.py` — file reading tool with path sandboxing
- `tools/regulation_search.py` — regulation search tool (via MCP client)
- `tools/document_generation.py` — document generation tool (TrackChangesBuilder)
- `tools/mcp_client.py` — MCP client (JSON-RPC 2.0 over stdio)

---

## 14. Key Findings Summary

### 14.1 What Can Be Reused Directly

| Component | Location | Reuse Mode |
|-----------|----------|------------|
| `TrackChangesBuilder` | `lawfirm-profile/scripts/contract_review_trackchanges.py` | Import (with `process()` parameterized) |
| `McpRegistryPort` / `InMemoryMcpRegistry` | `packages/mcp-registry/` | Import for catalog/descriptor lookup |
| `ElicitationRequestedPayload` / `ElicitationQuestion` / `ElicitationOption` | `packages/platform-contract/unified_events.py` | Import for clarification tool |
| `Artifact` / `ArtifactCreatedPayload` / `ArtifactKind` | `packages/platform-contract/` | Import for artifact events |
| `GatewayArtifactStore` / `handle_get_artifact_request` | `services/gateway/src/gateway/artifacts.py` | Already exists — agent-core emits events, Gateway registers |
| `ToolExecutor` / `ToolResult` | `packages/agent-core/turn_loop.py` | Already exists — Phase 101 provides real implementations |
| `EventEmitter._emit()` | `packages/agent-core/event_emitter.py` | Extend with new emit methods |
| MCP connectors (`law-database`, `wenshu`) | `ai-for-china-legal/connectors/` | Spawn as subprocess via MCP client |
| `PathSandbox` pattern | `lawyer-desktop/security/path_sandbox.rs` | Port to Python (pathlib-based) |

### 14.2 What Must Be Built New

| Component | Location | Description |
|-----------|----------|-------------|
| `ToolRegistry` | `agent-core/tools/registry.py` | Maps tool names to handlers; generates OpenAI tool definitions |
| Dispatching `ToolExecutor` | `agent-core/tools/registry.py` | Looks up registry, calls handler, returns `ToolResult` |
| Clarification tool | `agent-core/tools/clarification.py` | Constructs `ElicitationRequestedPayload`, emits event, signals turn termination |
| File reading tool | `agent-core/tools/file_reader.py` | Read-only with path sandboxing (Python port of PathSandbox) |
| Regulation search tool | `agent-core/tools/regulation_search.py` | Thin wrapper calling MCP client |
| Document generation tool | `agent-core/tools/document_generation.py` | Imports `TrackChangesBuilder`, parameterizes review items, emits `artifact.created` |
| MCP client | `agent-core/tools/mcp_client.py` | JSON-RPC 2.0 over stdio; spawn, initialize, tools/list, tools/call, lifecycle |
| `emit_elicitation_requested()` | `agent-core/event_emitter.py` | New EventEmitter method |
| `emit_artifact_created()` | `agent-core/event_emitter.py` | New EventEmitter method |
| Turn loop enhancement | `agent-core/turn_loop.py` | Check `result.metadata.get("terminate_turn")` after tool execution |

### 14.3 Key Risks

1. **lxml dependency** — First external dependency for agent-core. Lazy-import to keep package importable without it.
2. **MCP subprocess lifecycle** — Node.js connector processes must be properly cleaned up (timeout, crash, close). The ACP client's subprocess pattern (Phase 89) is a reference.
3. **TrackChangesBuilder adaptation** — The `process()` method must be parameterized to accept review items. This is a minimal change to the lawfirm-profile script (or a vendored copy), not a rewrite.
4. **Clarification tool turn termination** — The turn loop needs a small enhancement to check `metadata.get("terminate_turn")`. This must not break existing Phase 100 tests.
5. **HG-4 修订稿质量** — Human gate: the track-changes docx must be confirmed by a lawyer as usable for external negotiation. Cannot be auto-claimed as passed.

### 14.4 Dependencies on Prior Phases

| Phase | Dependency |
|-------|------------|
| Phase 100 | Turn loop, EventEmitter, ToolExecutor/ToolResult, FixtureProvider, model layer |
| Phase 88 | Unified event vocabulary (elicitation.requested, artifact.created, tool_call.*, payloads) |
| Phase 90 | Security defaults (`_DANGEROUS_PERMISSION_KINDS`, output boundary, permission safety) |
| Phase 96 | Skill index (for skill-required scripts metadata) |
| Phase 97 | Skill materializer (body injector pattern, context budget) |

---

## 15. Plan Estimate Alignment

The context document estimates **4 plans**:

1. **101-01**: Tool registry + tool definitions + dispatching executor + EventEmitter enhancements (emit_artifact_created, emit_elicitation_requested, terminate_turn metadata)
2. **101-02**: Clarification tool + file reading tool + regulation search tool (via MCP client)
3. **101-03**: Document generation tool (TrackChangesBuilder integration) + artifact.created emission + MCP client (law-database, wenshu)
4. **101-04**: E2E integration tests + phase completion (multi-tool orchestration, artifact download, MCP tool discovery, security verification)

This research confirms the estimate is appropriate. The work divides cleanly into:
- **101-01**: Infrastructure (registry, executor, EventEmitter) — no external dependencies
- **101-02**: Three tools that don't need lxml (clarification, file reading, regulation search via MCP)
- **101-03**: Document generation (needs lxml/TrackChangesBuilder) + full MCP client
- **101-04**: Integration tests covering all success criteria
