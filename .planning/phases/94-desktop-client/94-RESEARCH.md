---
phase: 94
slug: desktop-client
researched_at: 2026-08-08
researcher: auto
status: complete
---

# Phase 94 Research — Desktop Client

## 1. lawyer-desktop Tauri Structure

### tauri.conf.json (51 lines)

**File**: `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/tauri.conf.json`

| Config key | Value | Notes |
|------------|-------|-------|
| `productName` | `墨律` | Chinese product name |
| `version` | `0.1.0` | |
| `identifier` | `com.sorawatcher.inkstatute` | |
| `build.beforeDevCommand` | `bun run dev` | Vite dev server on port 1420 |
| `build.devUrl` | `http://127.0.0.1:1420` | |
| `build.beforeBuildCommand` | `bun run build` | `tsc -b && vite build` |
| `build.frontendDist` | `../dist` | Vite output directory |
| `app.withGlobalTauri` | `true` | Tauri API on `window.__TAURI__` |
| `app.windows[0]` | `1280×800`, min `960×600` | Single window |
| `app.windows[0].decorations` | `false` | Custom TitleBar (no OS chrome) |
| `app.windows[0].dragDropEnabled` | `true` | OS drag-drop events |
| `app.security.csp` | `default-src 'self'; ...` | Allows fonts.googleapis.com, connect to https + localhost |
| `bundle.active` | `true` | |
| `bundle.targets` | `all` | All platform targets |
| `bundle.createUpdaterArtifacts` | `true` | Auto-update artifacts |
| `bundle.resources` | `resources/law-library/**/*` | Bundled law library corpus |
| `plugins.updater.endpoints` | `http://127.0.0.1:8787/api/app/latest/...` | Update server (placeholder) |
| `plugins.updater.pubkey` | `dW5zZXQtcmVwbGFjZS13aXRoLXNpZ25lci1wdWJrZXk=` | Placeholder — must be replaced with real signing key |

### Cargo.toml (56 lines)

**File**: `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/Cargo.toml`

**Tauri plugins (7):**

| Plugin | Version | Purpose | Keep in Phase 94? |
|--------|---------|---------|-------------------|
| `tauri-plugin-opener` | 2 | Open URLs/files in OS default app | Yes (desktop convenience) |
| `tauri-plugin-sql` | 2 (sqlite) | SQLite for main DB | Yes (offline cache) |
| `tauri-plugin-dialog` | 2 | File open/save dialogs | Yes (FileAdapter) |
| `tauri-plugin-fs` | 2 | File system access | Yes (file reading) |
| `tauri-plugin-updater` | 2 | Auto-update | Yes (desktop-only) |
| `tauri-plugin-process` | 2 | Process management (relaunch after update) | Yes (desktop-only) |
| `tauri-plugin-mcp-bridge` | 0.11.2 | MCP bridge (debug only) | **Remove** (MCP is server-side) |

**Other notable dependencies:**

| Crate | Purpose | Keep in Phase 94? |
|-------|---------|-------------------|
| `sqlx` (sqlite, tokio) | SQLite async pool | Yes (offline cache + FTS5) |
| `docx-rs` | DOCX text extraction + generation | Yes (workspace parser, docx export) |
| `pdf-extract` | PDF text extraction | Yes (workspace parser) |
| `walkdir` | Recursive directory scanner | Yes (workspace scanner) |
| `sha2` | File hashing for incremental index | Yes (workspace scanner) |
| `encoding_rs` | GB18030 encoding for Chinese files | Yes (workspace parser) |
| `reqwest` | HTTP client (LLM provider calls) | **Remove** (LLM is server-side) |
| `aes-gcm` | API key encryption | **Remove** (no local API keys) |
| `scraper` | HTML parsing | **Remove** (law library monitor) |
| `tauri-plugin-mcp-bridge` | MCP JSON-RPC bridge | **Remove** |

### src-tauri/src/ Directory Structure (63 .rs files)

```
src-tauri/src/
├── lib.rs                    # Entry: plugin registration, setup, command handler list
├── main.rs                   # Minimal main (calls lib::run())
├── bin/probe_llm_tools.rs    # Dev tool for LLM tool probing
├── commands/                 # Tauri command handlers (7 modules)
│   ├── mod.rs
│   ├── chat.rs               # send_message, classify, conversations, messages (2000 lines)
│   ├── chat_tools.rs         # Tool building, execution, streaming helpers
│   ├── settings.rs           # Provider/skills/MCP/files/law-library settings (380 lines)
│   ├── files.rs              # File reading, directory listing, drag-drop, sandbox (347 lines)
│   ├── documents.rs          # DOCX generation, legal document parsing (88 lines)
│   ├── workspace.rs          # FTS5 workspace bind/index/search (237 lines)
│   ├── skillopt.rs           # Skill optimization commands (426 lines)
│   ├── sync.rs               # Sync settings/outbox (73 lines)
│   └── trace.rs              # Agent trace event emission
├── citations/                # Citation extraction + verification
├── db/                       # SQLite: models, queries, migrations
├── documents/                # DOCX generation + legal document types
├── law_library/              # Bundled law library: copy, index, monitor
├── llm/                      # LLM engine, OpenAI-compat provider, tool_leak, types
├── mcp/                      # MCP client/manager (JSON-RPC stdio)
├── security/                 # Path sandbox, key store (AES-GCM), eval sandbox
├── skill_opt/                # Skill optimization: judge, optimizer, proposals, runner, score
├── skills/                   # Skill registry, loader, router, agent_classifier
├── sync/                     # Sync client, outbox, settings, skills_update, worker
└── workspace/                # FTS5 workspace index: scanner, parser, chunker, index_store, manager
```

**Modules to REMOVE in Phase 94 (agent logic → server-side):**
- `citations/` — citation audit is server-side (Phase 102)
- `llm/` — LLM provider calls are server-side
- `mcp/` — MCP client is server-side
- `skill_opt/` — skill optimization is server-side/admin
- `skills/` — skill loading/routing is server-side
- `sync/` — feedback goes directly to Gateway, no sync outbox
- `commands/chat.rs` — agent loop is server-side
- `commands/chat_tools.rs` — tool execution is server-side
- `commands/skillopt.rs` — skill opt is server-side
- `commands/sync.rs` — sync is removed
- `commands/trace.rs` — trace events come via SSE
- `law_library/monitor.rs` — regulation monitor is server-side

**Modules to KEEP in Phase 94 (desktop-specific):**
- `commands/files.rs` — local file reading, directory listing, drag-drop classification, sandbox
- `commands/workspace.rs` — FTS5 workspace bind/index/search
- `commands/documents.rs` — DOCX generation (local export), legal document parsing (DocumentParser)
- `commands/settings.rs` — reduced: only law library status + file dirs (provider/skills/MCP removed)
- `workspace/` — FTS5 index pipeline (scanner, parser, chunker, index_store, manager)
- `db/` — SQLite for offline cache (conversations, messages, documents)
- `security/path_sandbox.rs` — local file access sandbox
- `documents/` — DOCX generation + legal document types (for local export/parse)
- `law_library/` — bundled law library (local FTS5 index, minus monitor)

### lib.rs Setup (545 lines)

**Plugin registration (lines 164-177):**
```rust
let builder = tauri::Builder::default()
    .plugin(tauri_plugin_opener::init())
    .plugin(tauri_plugin_fs::init())
    .plugin(tauri_plugin_dialog::init())
    .plugin(tauri_plugin_updater::Builder::new().build())
    .plugin(tauri_plugin_process::init())
    .plugin(tauri_plugin_sql::Builder::new()
        .add_migrations("sqlite:lawyer-desktop.db", db::get_migrations())
        .build());
```

**Setup phase (lines 183-483):**
1. Create app data dir → `app_data_dir/lawyer-desktop.db`
2. SQLite pool (max 5 connections) + migrations (001_init, metadata, skill_opt, sync)
3. Workspace app data dir set for FTS5 indexes
4. KeyStore (AES-GCM) for API key encryption → **remove**
5. Path sandbox from `allowed_file_dirs` DB setting
6. Restore active LLM provider → **remove**
7. Restore fast LLM provider → **remove**
8. Skills root resolution + sync auto-update → **remove**
9. Background feedback sync worker → **remove**
10. Periodic skill update check (every 6h) → **remove**
11. Law library: copy bundled corpus + FTS5 index → **keep** (desktop enhancement)
12. MCP server auto-start from `.mcp.json` → **remove**
13. SkillOpt sleep cycle → **remove**

**Command handler registration (lines 484-542):** 57 commands registered via `generate_handler![]`.

---

## 2. invoke() Call Inventory — All 57 Calls Categorized

**File**: `/home/sorawatcher/workspace/lawyer-desktop/src/services/api.ts` (696 lines)

All 57 `invoke()` calls are in `src/services/api.ts`. Categorized by Phase 94 disposition:

### Category A: → Gateway HTTP/SSE (agent/session/message — 10 calls)

| # | invoke() command | Gateway replacement | Notes |
|---|------------------|---------------------|-------|
| 1 | `send_message` | `POST /v1/runs` + `GET /v1/runs/{id}/events` (SSE) | Core: create run, stream events |
| 2 | `create_conversation` | `POST /v1/sessions` | Create session |
| 3 | `get_conversations` | `GET /v1/sessions` (list) | List sessions for tenant |
| 4 | `get_messages` | `GET /v1/sessions/{id}/runs` | List runs for session |
| 5 | `delete_conversation` | `DELETE /v1/sessions/{id}` | Delete session |
| 6 | `update_conversation_title` | `PATCH /v1/sessions/{id}` | Update session title |
| 7 | `classify_agent_mode` | **REMOVED** | Classification is server-side in agent core |
| 8 | `update_message_metadata` | **REMOVED** | Metadata managed via events server-side |
| 9 | `generate_followup_prompts` | **REMOVED** | Agent generates suggestions via events |
| 10 | `set_active_conversation` | **REMOVED** | Session management is server-side |

### Category B: → Gateway HTTP (feedback — 3 calls)

| # | invoke() command | Gateway replacement | Notes |
|---|------------------|---------------------|-------|
| 11 | `submit_message_feedback` | `POST /v1/feedback` | Direct Gateway call |
| 12 | `get_message_feedback` | `GET /v1/feedback` | Per-conversation feedback |
| 13 | `list_all_feedback` | `GET /v1/feedback` | Admin — may be removed from desktop |

### Category C: → Gateway HTTP (skills — 1 call)

| # | invoke() command | Gateway replacement | Notes |
|---|------------------|---------------------|-------|
| 14 | `list_skills` | `GET /v1/skills` | Feature-flagged endpoint |

### Category D: → Gateway/Adapter (documents — 2 calls)

| # | invoke() command | Replacement | Notes |
|---|------------------|-------------|-------|
| 15 | `parse_legal_document` | `DocumentParser` adapter (client-side) | Parse LLM JSON into preview model |
| 16 | `generate_docx` | `GET /v1/artifacts/{id}` (download) | Artifact download replaces local generation |

### Category E: REMOVED — Provider/LLM config (8 calls)

| # | invoke() command | Reason |
|---|------------------|--------|
| 17 | `get_provider_presets` | Provider is server-side |
| 18 | `setup_provider` | Provider is server-side |
| 19 | `test_provider` | Provider is server-side |
| 20 | `get_active_provider` | Provider is server-side |
| 21 | `get_fast_model_presets` | Provider is server-side |
| 22 | `get_fast_provider` | Provider is server-side |
| 23 | `setup_fast_provider` | Provider is server-side |
| 24 | `test_fast_provider` | Provider is server-side |

### Category F: REMOVED — Skills management (3 calls)

| # | invoke() command | Reason |
|---|------------------|--------|
| 25 | `get_skills_root` | Skills are server-side |
| 26 | `set_skills_root` | Skills are server-side |
| 27 | `reload_skills` | Skills are server-side |

### Category G: REMOVED — MCP (1 call)

| # | invoke() command | Reason |
|---|------------------|--------|
| 28 | `get_mcp_health` | MCP is server-side |

### Category H: Desktop-specific — Law library (2 calls)

| # | invoke() command | Notes |
|---|------------------|-------|
| 29 | `get_law_library_status` | Local bundled law library FTS5 index |
| 30 | `reindex_law_library` | Local FTS5 reindex |

### Category I: REMOVED — SkillOpt/Eval (12 calls)

| # | invoke() command | Reason |
|---|------------------|--------|
| 31 | `get_skillopt_settings` | Skill optimization is server-side/admin |
| 32 | `set_skillopt_settings` | Server-side/admin |
| 33 | `list_eval_cases` | Server-side/admin |
| 34 | `set_eval_case_active` | Server-side/admin |
| 35 | `run_eval_case` | Server-side/admin |
| 36 | `list_eval_runs` | Server-side/admin |
| 37 | `list_proposals` | Server-side/admin |
| 38 | `adopt_proposal` | Server-side/admin |
| 39 | `reject_proposal` | Server-side/admin |
| 40 | `run_skill_refinement` | Server-side/admin |
| 41 | `mine_eval_cases` | Server-side/admin |
| 42 | `get_skillopt_overview` | Server-side/admin |

### Category J: REMOVED — Sync (5 calls)

| # | invoke() command | Reason |
|---|------------------|--------|
| 43 | `get_sync_settings` | Feedback goes directly to Gateway |
| 44 | `set_sync_settings` | No sync outbox needed |
| 45 | `get_sync_status_cmd` | No sync outbox |
| 46 | `flush_feedback_outbox` | No sync outbox |
| 47 | `test_sync_connection` | No sync server |

### Category K: Desktop-specific Tauri commands (10 calls)

| # | invoke() command | Adapter/Usage | Notes |
|---|------------------|---------------|-------|
| 48 | `read_file_content` | `WorkspaceAdapter` / file tools | Local file reading with path sandbox |
| 49 | `list_directory` | `WorkspaceAdapter` | Local directory listing with sandbox |
| 50 | `prepare_attachment` | File attachment prep | Read file, generate preview |
| 51 | `classify_dropped_paths` | `DropAdapter` | Classify OS drag-drop paths (file vs dir) |
| 52 | `grant_path_access` | Sandbox management | Grant one-time directory access |
| 53 | `get_allowed_file_dirs` | Sandbox config | List allowed directories |
| 54 | `set_allowed_file_dirs` | Sandbox config | Set allowed directories |
| 55 | `bind_workspace` | FTS5 workspace index | Bind + index directory |
| 56 | `get_workspace_index_status` | FTS5 status | Check index status |
| 57 | `search_workspace` | FTS5 search | Full-text search workspace |

### Summary

| Disposition | Count | Percentage |
|-------------|-------|------------|
| → Gateway HTTP/SSE | 16 | 28% |
| REMOVED (server-side) | 29 | 51% |
| Desktop-specific Tauri commands | 12 | 21% |
| **Total** | **57** | 100% |

### Non-invoke Tauri API Calls (also need migration)

| API call | Source | Adapter replacement |
|----------|--------|---------------------|
| `getVersion()` | `@tauri-apps/api/app` | `AppInfoAdapter.getVersion()` |
| `check()` (updater) | `@tauri-apps/plugin-updater` | `AppInfoAdapter.checkForUpdate()` |
| `downloadAndInstall()` + `relaunch()` | `@tauri-apps/plugin-updater` + `@tauri-apps/plugin-process` | `AppInfoAdapter.installUpdate()` |
| `getCurrentWindow()` | `@tauri-apps/api/window` | `WindowAdapter` (minimize/maximize/close/isMaximized/onResized/startDragging) |
| `getCurrentWebview().onDragDropEvent()` | `@tauri-apps/api/webview` | Tauri-specific drag-drop → stays as Tauri event listener |
| `listen()` (6 event listeners) | `@tauri-apps/api/event` | See below |

### Tauri Event Listeners (6 total)

| Event listener | Payload | Phase 94 disposition |
|----------------|---------|----------------------|
| `onChatStream` | `StreamChunk` | **REMOVED** — replaced by SSE `streamRun()` |
| `onAgentTrace` | `AgentTraceEvent` | **REMOVED** — trace events come via SSE as `tool_call.*` / `thought.delta` |
| `onWorkspaceIndexProgress` | `WorkspaceIndexProgress` | **KEEP** — desktop-specific FTS5 indexing progress |
| `onLawUpdateAlert` | `LawUpdateAlert` | **REMOVED** — regulation monitor is server-side |
| `onSkillsUpdated` | `{ version: string }` | **REMOVED** — skills are server-side |
| `onSkillOptProgress` | `SkillOptProgressEvent` | **REMOVED** — skill opt is server-side |

---

## 3. FTS5 Workspace Index

### Architecture

The workspace index is a **per-root SQLite FTS5 database** that enables full-text search over local case-materials directories. It is a desktop-specific enhancement — search results can be attached as context references (`ContextRefPayload`) when sending messages to the Gateway.

**Index DB path**: `{app_data_dir}/workspaces/{root_hash}/index.db`

Where `root_hash = SHA-256(canonicalized_root_path)` — one FTS5 DB per indexed directory.

### Pipeline: scan → parse → chunk → FTS5 index

```
bind_workspace(path)
  → grant_directory_access (sandbox + DB)
  → spawn bind_and_index(root, on_progress)
      → scan_root(root, max_file_size=50MB)
          → walkdir (skip .git, node_modules, target, etc.)
          → filter by ALLOW_EXTS (txt, md, json, yaml, pdf, docx, rs, ts, py, ...)
          → compute SHA-256 + mtime for each file
      → for each scanned file:
          → check incremental: skip if mtime + sha256 unchanged
          → parse_file(path, ext)
              → PDF: pdf_extract::extract_text
              → DOCX: docx-rs paragraph + table text extraction
              → Text: read with UTF-8 → GB18030 fallback
          → chunk_markdown(relative_path, markdown)
              → split by # headings (heading_path tracked)
              → subdivide long sections (3500 chars, 500 overlap)
          → upsert_file_and_chunks (delete old chunks, insert new)
      → delete removed files from index
      → set_root_status("ready", file_count, chunk_count)
      → emit "workspace-index-progress" events via Tauri
```

### FTS5 Schema (migrations/002_workspace_index.sql)

```sql
CREATE VIRTUAL TABLE workspace_chunks_fts USING fts5(
  content, heading_path, relative_path,
  content='workspace_chunks',
  content_rowid='rowid',
  tokenize='trigram'   -- trigram tokenizer for CJK
);
```

**External content table pattern** with 3 triggers (`AFTER INSERT/DELETE/UPDATE`) keeping FTS in sync with `workspace_chunks`.

### Search Implementation (index_store.rs, lines 266-338)

1. **FTS5 trigram search**: `escape_fts_query()` splits on whitespace, filters terms ≥3 chars, OR-joins quoted phrases. Uses `bm25(workspace_chunks_fts)` for ranking.
2. **LIKE fallback**: If FTS query is empty (all terms <3 chars) or returns no hits, falls back to `content LIKE %term%` on each whitespace-separated term.
3. **Result**: `Vec<ChunkHit>` with `chunk_id`, `relative_path`, `text`, `score`.

### Incremental Indexing (manager.rs)

- **Skip unchanged**: `is_unchanged(existing_mtime, existing_sha256, scanned)` — skip re-parse if both match.
- **Delete removed**: `find_removed_paths()` compares DB paths vs scan result.
- **Parser version**: `PRAGMA user_version` tracks parser version (currently 2). Version mismatch → full re-index. Status reported as `"stale"`.

### Files Indexed

**Allowed extensions** (scanner.rs, 30 extensions):
`txt, md, markdown, json, yaml, yml, toml, xml, html, htm, csv, log, rs, ts, tsx, js, jsx, py, go, java, c, cpp, h, hpp, cs, rb, php, sql, sh, bash, ps1, pdf, docx`

**Ignored directories**: `.git, .svn, .hg, node_modules, venv, .venv, dist, build, __pycache__, target, .cargo, .idea, .vscode, .cursor, coverage, .next, .nuxt`

**Max file size**: 50 MB (configurable, `DEFAULT_MAX_FILE_SIZE`)

### How Results Are Used

1. User binds a workspace directory via `bind_workspace(path)` — often triggered by drag-dropping a folder.
2. FTS5 index builds in background, emitting `workspace-index-progress` Tauri events.
3. ChatPanel shows index progress on the context-ref chip: `索引中 ${processed}/${total}` → `已索引 ${fileCount} 文件`.
4. `search_workspace(path, query, k)` returns chunks — these can be attached as `ContextRefPayload` (kind: `"directory"`) when sending messages.
5. The Gateway receives context refs as part of the run request; the server-side agent reads workspace files via the attachment mechanism.

### Phase 94 Disposition

**KEEP as desktop-specific Tauri commands.** The FTS5 workspace index is explicitly called out in UI-05 success criterion #5: "本地工作区 FTS5 索引作为桌面专属增强保留，其检索结果可作为附件引用提交给平台."

The Rust modules to keep:
- `workspace/scanner.rs` (222 lines) — directory scanner
- `workspace/parser.rs` (256 lines) — file parser (PDF, DOCX, text)
- `workspace/chunker.rs` (190 lines) — Markdown chunker
- `workspace/index_store.rs` (577 lines) — SQLite FTS5 store
- `workspace/manager.rs` (480 lines) — index orchestrator
- `commands/workspace.rs` (237 lines) — Tauri commands

---

## 4. Auto-Update Mechanism

### Configuration (tauri.conf.json)

```json
"plugins": {
  "updater": {
    "endpoints": [
      "http://127.0.0.1:8787/api/app/latest/{{target}}/{{arch}}/{{current_version}}"
    ],
    "pubkey": "dW5zZXQtcmVwbGFjZS13aXRoLXNpZ25lci1wdWJrZXk="
  }
}
```

- **Endpoint**: Placeholder `http://127.0.0.1:8787` — must be replaced with real update server URL.
- **Pubkey**: Placeholder base64 — must be replaced with real signing public key.
- **`bundle.createUpdaterArtifacts`**: `true` — Tauri generates update artifacts (`.msi` for Windows, `.app.tar.gz` for macOS) alongside regular bundles.

### Frontend Implementation (api.ts, lines 674-696)

```typescript
export async function checkForAppUpdate(): Promise<AppUpdateInfo> {
  const { check } = await import("@tauri-apps/plugin-updater");
  const update = await check();
  if (!update) return { available: false };
  return { available: true, version: update.version, body: update.body };
}

export async function installAppUpdate(): Promise<void> {
  const { check } = await import("@tauri-apps/plugin-updater");
  const { relaunch } = await import("@tauri-apps/plugin-process");
  const update = await check();
  if (!update) return;
  await update.downloadAndInstall();
  await relaunch();
}
```

### UI Component (AppUpdateBanner.tsx, 52 lines)

- `onMount`: calls `checkForAppUpdate()` — if update available, shows banner.
- Banner: "发现新版本 {version} — {body}" + "下载并安装" button.
- Button click: calls `installAppUpdate()` → downloads, installs, relaunches.
- Error handling: shows error string in banner.

### Phase 94 Mapping

The auto-update mechanism maps to the `AppInfoAdapter` interface in ui-core:

```typescript
export interface AppInfoAdapter {
  getVersion(): Promise<string>;
  checkForUpdate?(): Promise<UpdateInfo | null>;
  installUpdate?(): Promise<void>;
}
```

**Desktop implementation**: Uses `@tauri-apps/plugin-updater` + `@tauri-apps/plugin-process` directly — these are optional methods that only the desktop adapter implements. The web adapter returns `null` for `checkForUpdate()`.

The `AppUpdateBanner` component was deferred from Phase 92 to Phase 94. It needs to be ported into the desktop app (not into ui-core, since it depends on Tauri updater plugin).

---

## 5. File Dialog & Drag-Drop

### File Dialog (plugin-dialog)

**Usage in lawyer-desktop:**

| Component | Dialog call | Purpose |
|-----------|-------------|---------|
| ChatPanel.tsx (line 306) | `open({ multiple: false, directory: kind === "directory" })` | Pick file or folder as context ref |
| HomePage.tsx (line 2) | `open` imported (same pattern) | Pick file/folder from home screen |
| SettingsPanel.tsx (line 2) | `open` imported | Pick skills root directory |
| DocPreview.tsx | `save()` | Save DOCX export to path |

**Phase 94 mapping**: File dialog maps to `FileAdapter` interface:

```typescript
export interface FileAdapter {
  open(options?: {
    multiple?: boolean;
    filters?: { name: string; extensions: string[] }[];
  }): Promise<string | string[] | null>;
  save(options: {
    defaultPath?: string;
    filters?: { name: string; extensions: string[] }[];
  }): Promise<string | null>;
}
```

**Desktop implementation**: Wraps `@tauri-apps/plugin-dialog` `open()` and `save()`. Returns real file system paths (unlike web which only returns file names).

### Drag-Drop (Tauri webview event)

**Configuration**: `tauri.conf.json` → `app.windows[0].dragDropEnabled: true`

**Usage in ChatPanel.tsx (lines 264-284):**
```typescript
void getCurrentWebview()
  .onDragDropEvent((event) => {
    const payload = event.payload;
    if (payload.type === "enter" || payload.type === "over") {
      if (!props.sending()) setDragActive(true);
    } else if (payload.type === "drop") {
      setDragActive(false);
      void handleDroppedPaths(payload.paths);
    } else {
      setDragActive(false);  // "leave"
    }
  })
```

**Usage in HomePage.tsx (lines 70-80):** Same pattern — `getCurrentWebview().onDragDropEvent()`.

**Path classification** (ChatPanel.tsx lines 324-342):
```typescript
async function handleDroppedPaths(paths: string[]) {
  const kinds = await classifyDroppedPaths(cleaned);  // Tauri command
  for (const item of kinds) {
    if (!item.exists) continue;
    const kind = item.is_dir ? "directory" : "file";
    addContextRef({ alias: pathToAlias(item.path, kind), path: item.path, kind });
  }
}
```

**Phase 94 mapping**: Drag-drop is Tauri-specific. The `DropAdapter` interface in ui-core accepts `DataTransferItemList` (browser API), but in Tauri the drag-drop event provides raw OS paths directly.

**Desktop adapter strategy**: The desktop `DropAdapter` implementation will need to handle Tauri's `onDragDropEvent` separately from the browser `DataTransferItemList` interface. Two options:
1. **Extend DropAdapter** to accept `string[]` paths (Tauri-specific overload)
2. **Keep Tauri drag-drop in the desktop app shell** (not via adapter) — the desktop app registers `onDragDropEvent` listeners and calls `classifyDroppedPaths` Tauri command directly, then feeds results into the same `addContextRef` flow.

Option 2 is cleaner — the ui-core `DropAdapter` is for browser `DataTransferItemList`; Tauri drag-drop is handled at the app shell level.

---

## 6. Window Management (TitleBar)

### TitleBar.tsx (226 lines)

**Custom window chrome**: `tauri.conf.json` sets `decorations: false` — the app renders its own title bar.

**Platform detection:**
```typescript
function isMacOS() {
  return /mac/i.test(navigator.platform) || /mac/i.test(navigator.userAgent);
}
```

**Window actions** (lines 28-35):
```typescript
async function runWindowAction(action: (win: ReturnType<typeof getCurrentWindow>) => Promise<void>) {
  if (!isTauri()) return;
  try {
    await action(getCurrentWindow());
  } catch (error) {
    console.error("[TitleBar] window action failed:", error);
  }
}
```

**Controls:**
- **Minimize**: `win.minimize()`
- **Maximize/Restore**: `win.toggleMaximize()` — tracks `isMaximized` signal via `win.onResized()`
- **Close**: `win.close()`
- **Drag**: `win.startDragging()` (macOS only — uses `data-tauri-drag-region` attribute)
- **Double-click title bar**: `win.toggleMaximize()` (non-macOS)

**macOS vs Windows layout:**
- **macOS**: Traffic light dots (close/minimize/maximize) on left, drag region in center
- **Windows**: Window controls on right, double-click title bar to maximize

**Phase 94 mapping**: TitleBar was ported to ui-core in Phase 92. It uses `WindowAdapter` interface:

```typescript
export interface WindowAdapter {
  minimize(): Promise<void>;
  toggleMaximize(): Promise<void>;
  close(): Promise<void>;
  isMaximized(): Promise<boolean>;
  onResized?(cb: () => void): Promise<() => void>;
  startDragging?(): Promise<void>;
}
```

**Desktop implementation**: Wraps `@tauri-apps/api/window` `getCurrentWindow()` methods. This is the only adapter that is **required** for desktop (optional for web — `AdapterContextValue.window` is optional).

---

## 7. Offline Storage

### Main SQLite Database

**Path**: `{app_data_dir}/lawyer-desktop.db`

**Schema** (migrations/001_init.sql):

| Table | Purpose | Phase 94 disposition |
|-------|---------|----------------------|
| `conversations` | id, title, created_at, updated_at, settings_json | **Offline cache** — sync with Gateway sessions |
| `messages` | id, conversation_id, role, content, attachments_json, tool_calls_json, created_at | **Offline cache** — sync with Gateway run events |
| `documents` | id, conversation_id, title, document_json, version, created_at, updated_at | **Offline cache** — downloaded artifacts |
| `llm_providers` | id, name, display_name, api_base_url, api_key, model_name, is_active, config_json | **REMOVED** — provider is server-side |
| `app_settings` | key-value settings | **Keep** — for desktop-specific settings (Gateway URL, allowed_file_dirs) |

**Additional schema** (applied via `ensure_*` functions in queries.rs):
- `message_metadata` — metadata JSON per message (workflow state, feedback)
- `skill_opt_*` tables — skill optimization (REMOVED)
- `sync_*` tables — sync outbox (REMOVED)

### Per-Root FTS5 Index Databases

**Path**: `{app_data_dir}/workspaces/{root_hash}/index.db`

Each indexed workspace directory gets its own SQLite FTS5 database with:
- `workspace_roots` — root binding metadata
- `workspace_files` — indexed file records (path, size, mtime, sha256)
- `workspace_chunks` — text chunks (content, heading_path, ordinal)
- `workspace_chunks_fts` — FTS5 virtual table (trigram tokenizer)

### Bundled Law Library

**Path**: `resources/law-library/**/*` (bundled in app resources)

On startup, `law_library::ensure_library()` copies the bundled corpus into app data and creates an FTS5 index. This provides offline law regulation search without server connectivity.

### Offline Behavior (UI-05 Success Criterion #4)

> "离线状态下应用可启动，能查看历史会话与已下载的产物文件，发起新任务时给出明确的'需要联网'提示而非静默失败"

**Implementation strategy:**
1. **On startup**: Load conversations and messages from local SQLite cache.
2. **Online**: Sync with Gateway — create sessions, send runs, stream events. Cache results locally.
3. **Offline**: App starts, shows cached conversations and downloaded artifacts. New task attempt → show "需要联网" prompt.
4. **Gateway health check**: Ping Gateway on startup. If unreachable, enter offline mode.

---

## 8. ui-core Adapter Interfaces — Desktop Implementation Mapping

### 6 Adapter Interfaces (packages/ui-core/src/adapters/index.ts, 120 lines)

| Interface | Web Implementation (Phase 93) | Desktop Implementation (Phase 94) |
|-----------|-------------------------------|-----------------------------------|
| `FileAdapter` | `<input type="file">` / `<a download>` | `@tauri-apps/plugin-dialog` open/save — returns real paths |
| `DropAdapter` | `DataTransferItemList` → file names | Tauri `onDragDropEvent` → `classifyDroppedPaths` command |
| `AppInfoAdapter` | Hardcoded version, no update check | `getVersion()` + `@tauri-apps/plugin-updater` check/install |
| `WorkspaceAdapter` | Returns empty array (no local FS) | `list_directory` Tauri command — real local file listing |
| `DocumentParser` | Client-side parse using ui-core utils | `parse_legal_document` Tauri command (or client-side) |
| `WindowAdapter` | **Not provided** (optional) | `getCurrentWindow()` — minimize/maximize/close/drag |

### AdapterContextValue

```typescript
export interface AdapterContextValue {
  file: FileAdapter;
  drop: DropAdapter;
  appInfo: AppInfoAdapter;
  workspace: WorkspaceAdapter;
  documentParser: DocumentParser;
  window?: WindowAdapter;  // Required for desktop, omitted for web
}
```

### Desktop Adapter Implementation Plan

```
apps/desktop/src/adapters/
├── desktopAdapters.ts          # Barrel: assembles AdapterContextValue
├── desktopFileAdapter.ts       # Wraps @tauri-apps/plugin-dialog
├── desktopDropAdapter.ts       # Wraps Tauri onDragDropEvent + classifyDroppedPaths
├── desktopAppInfoAdapter.ts    # Wraps getVersion + plugin-updater
├── desktopWorkspaceAdapter.ts  # Wraps list_directory Tauri command
├── desktopDocumentParser.ts    # Wraps parse_legal_document Tauri command
└── desktopWindowAdapter.ts     # Wraps getCurrentWindow() from @tauri-apps/api/window
```

### Key Difference: DropAdapter

The web `DropAdapter` accepts `DataTransferItemList` (browser drag-drop API). Tauri's drag-drop provides raw OS paths via `onDragDropEvent`, not `DataTransferItemList`.

**Strategy**: The desktop app shell registers `onDragDropEvent` listeners (not via `DropAdapter`) and calls `classifyDroppedPaths` Tauri command directly. The `DropAdapter` interface is used for browser-compatible drag-drop (if any). The Tauri-specific drag-drop flow feeds into the same `addContextRef` mechanism.

Alternatively, extend `DropAdapter` with an optional `classifyTauriPaths?(paths: string[]): Promise<DroppedPath[]>` method — but this leaks Tauri specifics into ui-core. Better to keep Tauri drag-drop in the app shell.

---

## 9. Build Pipeline

### Current lawyer-desktop Build

```bash
# Development (Vite + Rust)
bun run tauri dev    # Starts Vite on :1420 + Rust compilation + Tauri window

# Frontend only
bun run dev          # Vite dev server on :1420

# Production build
bun run tauri build  # tsc -b && vite build → Tauri bundle (MSI/DMG/AppImage)
```

**Tauri CLI wrapper**: `scripts/tauri-with-rust-path.cjs` — puts `%USERPROFILE%\.cargo\bin` first on PATH (Windows-specific, prefers rustup MSVC over Chocolatey GNU rust).

### Phase 94 Build Requirements (UI-05 Success Criterion #1)

> "`apps/desktop` 存在，由 `lawyer-desktop` 的 Tauri 外壳迁入，使用 `packages/ui-core`，Windows 与 macOS 可构建"

### Build Configuration

| Aspect | Value |
|--------|-------|
| Package manager | Bun (workspace protocol) |
| Frontend build | Vite 8 + vite-plugin-solid |
| Backend build | Cargo (Tauri 2) |
| Frontend dist | `dist/` (Vite output) |
| Bundle targets | `all` (MSI + DMG + AppImage) |
| Updater artifacts | `createUpdaterArtifacts: true` |
| Bundled resources | `resources/law-library/**/*` |

### Vite Configuration (from apps/web pattern)

```typescript
// vite.config.ts
import { defineConfig } from "vitest/config";
import solid from "vite-plugin-solid";
import path from "node:path";

export default defineConfig({
  plugins: [solid()],
  resolve: {
    alias: {
      debug: path.resolve(__dirname, "src/shims/debug.ts"),  // solid-markdown shim
    },
  },
  // Tauri dev server uses port 1420
  server: { port: 1420 },
  build: { outDir: "dist" },
  test: { environment: "jsdom" },
});
```

### package.json (desktop app)

```json
{
  "name": "@inkstatute/desktop",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "tauri": "tauri",
    "tauri:dev": "tauri dev",
    "tauri:build": "tauri build",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@inkstatute/ui-core": "workspace:*",
    "@inkstatute/platform-sdk-ts": "workspace:*",
    "@tauri-apps/api": "^2.11.0",
    "@tauri-apps/plugin-dialog": "^2.7.1",
    "@tauri-apps/plugin-fs": "^2.5.1",
    "@tauri-apps/plugin-updater": "^2.9.0",
    "@tauri-apps/plugin-process": "^2.3.1",
    "@tauri-apps/plugin-opener": "^2.5.4",
    "solid-js": "^1.9.0",
    "solid-markdown": "^2.1.0",
    "remark-gfm": "^4.0.0",
    "highlight.js": "^11.0.0"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.11.2",
    "typescript": "^5.7.0",
    "vite": "^8.0.0",
    "vite-plugin-solid": "^2.11.0",
    "vitest": "^3.0.0"
  }
}
```

**Note**: `@tauri-apps/plugin-sql` and `@tauri-apps/plugin-mcp-bridge` are NOT needed in frontend deps (they're Rust-only plugins). `@tauri-apps/plugin-sql` is used via `tauri-plugin-sql` in Cargo.toml only.

### Root package.json Workspace Update

Current workspaces:
```json
"workspaces": [
  "packages/platform-sdk-ts",
  "packages/ui-core",
  "apps/web"
]
```

**Phase 94 adds `"apps/desktop"` to the workspaces array.**

### CI Considerations

| Platform | Build target | CI runner | Notes |
|----------|-------------|-----------|-------|
| Windows | `.msi` + updater artifact | `windows-latest` | Requires MSVC toolchain |
| macOS | `.dmg` + updater artifact | `macos-latest` | Universal binary (x86_64 + aarch64) |
| Linux | `.AppImage` (optional) | `ubuntu-latest` | Not required by UI-05 but `targets: "all"` generates it |

**Cross-compilation**: Tauri does not support cross-compilation. Each platform must be built on its native OS runner.

**Signing**: Auto-update requires code signing. The placeholder pubkey in `tauri.conf.json` must be replaced with a real signing key pair. The private key is injected via CI secrets (`TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`).

**Gate coverage**: `apps/desktop` is under `apps/`, not `packages/` or `services/`, so the `gate-coverage` meta-test does not strictly require it. However, a lightweight gate (typecheck + vitest) should be added for consistency, matching the `apps/web` pattern.

---

## 10. apps/web Patterns Reusable in Desktop

### Phase 93 Architecture (apps/web)

The web client (Phase 93) established patterns that the desktop client can directly reuse:

### Context Provider Hierarchy

```
AuthProvider → AdapterContext.Provider → ConversationProvider → Router/Pages
```

**Desktop equivalent:**
```
AuthProvider → AdapterContext.Provider → ConversationProvider → ScreenSwitcher
```

The desktop app does NOT use `@solidjs/router` — it uses signal-based screen switching (like lawyer-desktop's `createSignal<"home" | "workspace">("home")`). However, the auth and conversation contexts can be reused.

### AuthContext (apps/web/src/contexts/AuthContext.tsx, 127 lines)

- `login()` → `POST /v1/auth/login` with credentials
- `onMount` → probe session validity
- Stores `session_id`, `tenant_id`, `user_id` in signals
- HttpOnly cookie is the sole credential

**Desktop reuse**: AuthContext can be reused as-is. The desktop app also talks to the Gateway via HTTP, so the same login flow applies. The Gateway URL is configurable (not same-origin like web).

### ConversationContext (apps/web/src/contexts/ConversationContext.tsx, 123 lines)

- `createConversation()` → `gateway.createSession()`
- `refreshConversations()` → `gateway.listSessions()`
- Stores conversations in signal

**Desktop reuse**: Can be reused, but the desktop app also needs offline cache integration — load from local SQLite first, then sync with Gateway.

### SessionContext (apps/web/src/contexts/SessionContext.tsx, 136 lines)

- `sendMessage()` → `gateway.createRun()` → sets `runId`
- `submitClarification()` → `gateway.submitElicitation()`
- `submitFeedback()` → `gateway.submitFeedback()`
- `cancelRun()` → `gateway.cancelRun()`
- Uses `useEventStream(runId)` hook for SSE consumption

**Desktop reuse**: SessionContext can be reused as-is. The SSE event stream is the same whether the client is web or desktop.

### useEventStream Hook (apps/web/src/hooks/useEventStream.ts, 93 lines)

- Wraps `createEventStream()` from ui-core
- `createEffect(on(runId, ...))` — starts/stops stream when runId changes
- Provides `state()`, `isStreaming()`, `error()`, `reconnect()`

**Desktop reuse**: Can be reused as-is. The `createEventStream` store uses `PlatformApiClient.streamRun()` which works with any `baseUrl`.

### Gateway Configuration (apps/web/src/config/gateway.ts, 17 lines)

```typescript
const baseUrl = import.meta.env.VITE_GATEWAY_URL || "";
export const gateway = new PlatformApiClient({
  baseUrl,
  fetchImpl: typeof window !== "undefined" ? window.fetch.bind(window) : undefined,
});
```

**Desktop equivalent**:
```typescript
const baseUrl = import.meta.env.VITE_GATEWAY_URL || "http://127.0.0.1:8000";
export const gateway = new PlatformApiClient({
  baseUrl,
  fetchImpl: typeof window !== "undefined" ? window.fetch.bind(window) : undefined,
});
```

The desktop app needs a configurable Gateway URL (not same-origin). Default to `http://127.0.0.1:8000` for local development. The URL should be persisted in local settings (SQLite `app_settings` table).

### WorkspacePage (apps/web/src/pages/WorkspacePage.tsx, 203 lines)

The WorkspacePage wires together:
- `ChatPanel` (from ui-core) — driven by `session.state()`
- `DocPreview` (from ui-core) — driven by `session.state().artifacts`
- `CitationPanel` (from ui-core) — driven by `groupCitations(session.state().citations)`
- Mobile tab toggle (chat/doc/cite) — desktop doesn't need this (always side-by-side)

**Desktop reuse**: The same component wiring, minus the mobile tab toggle. The desktop layout is always side-by-side (fixed window, no responsive breakpoints needed).

### Web Adapters (6 files, ~140 lines total)

| Adapter | Web implementation | Desktop implementation |
|---------|---------------------|------------------------|
| `webFileAdapter.ts` (52 lines) | `<input type="file">` / `<a download>` | `@tauri-apps/plugin-dialog` |
| `webDropAdapter.ts` (25 lines) | `DataTransferItemList` | Tauri `onDragDropEvent` + `classifyDroppedPaths` |
| `webAppInfoAdapter.ts` (20 lines) | Hardcoded version, no update | `getVersion()` + updater plugin |
| `webWorkspaceAdapter.ts` (13 lines) | Returns empty array | `list_directory` Tauri command |
| `webDocumentParser.ts` | Client-side parse | `parse_legal_document` Tauri command |
| `webAdapters.ts` (27 lines) | Barrel export | Desktop barrel export |

### Key Pattern: App Shell

**Web (App.tsx, 41 lines):**
```tsx
<AuthProvider>
  <AdapterContext.Provider value={webAdapters}>
    <ConversationProvider>
      <Router>
        <Route path="/login" component={LoginPage} />
        <Route path="/" component={AppLayout}>
          <Route path="/" component={HomePage} />
          <Route path="/workspace/:conversationId" component={WorkspacePage} />
        </Route>
      </Router>
    </ConversationProvider>
  </AdapterContext.Provider>
</AuthProvider>
```

**Desktop equivalent:**
```tsx
<AuthProvider>
  <AdapterContext.Provider value={desktopAdapters}>
    <ConversationProvider>
      <TitleBar ... />          {/* With WindowAdapter */}
      <AppUpdateBanner />       {/* Desktop-only */}
      <Show when={screen() === "home"}><HomePage ... /></Show>
      <Show when={screen() === "workspace"}><WorkspacePage ... /></Show>
      <Show when={settingsOpen()}><SettingsPanel ... /></Show>
      <ConversationDrawer ... />
    </ConversationProvider>
  </AdapterContext.Provider>
</AuthProvider>
```

---

## 11. SettingsPanel — Desktop-Admin Component

### SettingsPanel.tsx (963 lines)

Deferred from Phase 92 to Phase 94. Contains 6 tabs:

| Tab | Purpose | Phase 94 disposition |
|-----|---------|----------------------|
| `provider` | LLM provider setup (presets, API key, base URL, model) | **REMOVED** — provider is server-side |
| `skills` | Skills root path, skill list, reload | **REMOVED** — skills are server-side |
| `sync` | Sync service URL, API key, feedback upload settings | **REMOVED** — feedback goes to Gateway directly |
| `files` | Allowed file directories, sandbox config | **KEEP** — desktop-specific path sandbox |
| `mcp` | MCP server health check | **REMOVED** — MCP is server-side |
| `about` | App version, law library status, reindex | **KEEP** — desktop-specific (version, law library) |

**Phase 94 reduced SettingsPanel**: Only `files` and `about` tabs remain. The `provider`, `skills`, `sync`, and `mcp` tabs are removed since those capabilities are now server-side.

The SettingsPanel uses `@tauri-apps/plugin-dialog` `open()` for directory picker — this maps to `FileAdapter.open()` in the adapter pattern.

---

## 12. law_library — Bundled Law Library

### Architecture (law_library/mod.rs, orchestrator.rs)

1. **Bundled corpus**: `src-tauri/resources/law-library/**/*` — packaged with the app via `bundle.resources` in `tauri.conf.json`.
2. **On startup**: `ensure_library(resource_candidates, data_dir)` copies the bundled corpus into app data dir.
3. **FTS5 index**: Creates a workspace-style FTS5 index over the law library files.
4. **Status**: `get_law_library_status()` returns `LibraryStatus` with law count, article count, index status, and law entries.
5. **Reindex**: `reindex_law_library()` rebuilds the FTS5 index.
6. **Regulation monitor**: `monitor::spawn_regulation_monitor()` — daily checks for online statute status changes. **REMOVED in Phase 94** (server-side capability).

### Phase 94 Disposition

**KEEP** the law library as a desktop-specific enhancement. The bundled law library provides offline regulation search. The `get_law_library_status` and `reindex_law_library` Tauri commands stay. The regulation monitor (`law_library/monitor.rs`) is removed.

---

## Summary & Recommendations

### Key Findings

1. **57 invoke() calls categorized**: 16 → Gateway HTTP/SSE, 29 REMOVED (server-side), 12 desktop-specific Tauri commands. The desktop app retains only ~21% of original Tauri commands.

2. **FTS5 workspace index is the key desktop enhancement** (UI-05 #5). The full pipeline (scanner → parser → chunker → index_store → manager) stays as Rust Tauri commands. Per-root SQLite FTS5 with trigram tokenizer for CJK, incremental indexing via SHA-256 + mtime, LIKE fallback for short terms.

3. **6 adapter interfaces map cleanly** to desktop: `FileAdapter` (dialog), `DropAdapter` (Tauri drag-drop), `AppInfoAdapter` (version + updater), `WorkspaceAdapter` (local FS listing), `DocumentParser` (legal doc parse), `WindowAdapter` (window controls — desktop-only).

4. **Auto-update uses Tauri plugin-updater** with placeholder endpoint/pubkey — must be configured with real update server and signing keys. `AppUpdateBanner` component (52 lines) is desktop-only, ported from lawyer-desktop.

5. **Offline storage via SQLite**: Main DB (`lawyer-desktop.db`) for conversation/message/document cache + app settings. Per-root FTS5 DBs for workspace indexes. Law library bundled in app resources.

6. **apps/web patterns are directly reusable**: AuthContext, ConversationContext, SessionContext, useEventStream hook, gateway config, WorkspacePage wiring — all transfer to desktop with minimal changes (mainly: signal-based screen switching instead of router, configurable Gateway URL, offline cache integration).

7. **SettingsPanel reduced from 6 tabs to 2**: Only `files` (sandbox config) and `about` (version, law library) remain. Provider/skills/sync/MCP tabs removed.

8. **Rust modules to remove**: `llm/`, `mcp/`, `skills/`, `skill_opt/`, `sync/`, `citations/`, `commands/chat.rs`, `commands/chat_tools.rs`, `commands/skillopt.rs`, `commands/sync.rs`, `commands/trace.rs`, `law_library/monitor.rs`. ~60% of Rust code is removed.

9. **Build pipeline**: Tauri 2 + Vite 8 + Bun. Windows (MSI) + macOS (DMG) builds required. No cross-compilation — native OS CI runners. Auto-update requires code signing.

10. **Root package.json** needs `"apps/desktop"` added to workspaces array.

### Risks

1. **Tauri updater signing**: The placeholder pubkey must be replaced with a real signing key pair. Without signing, auto-update won't work. CI needs `TAURI_SIGNING_PRIVATE_KEY` secret.

2. **DropAdapter interface mismatch**: ui-core's `DropAdapter` accepts `DataTransferItemList` (browser API). Tauri's `onDragDropEvent` provides raw OS paths. The desktop app must handle Tauri drag-drop at the app shell level, not via the `DropAdapter` interface.

3. **Offline cache sync strategy**: The desktop app needs a strategy for syncing local SQLite cache with Gateway sessions. When online, new sessions/runs are created on the Gateway and cached locally. When offline, only cached data is visible. Conflict resolution (e.g., session created on another device) needs consideration.

4. **Gateway URL configuration**: Unlike web (same-origin), the desktop app needs a configurable Gateway URL. This should be persisted in local settings and configurable via the SettingsPanel `about` tab.

5. **CSP for Gateway connectivity**: The current CSP in `tauri.conf.json` allows `connect-src 'self' https: http://localhost:* http://127.0.0.1:*`. For production Gateway connectivity, the CSP may need to be updated to allow the specific Gateway domain.

6. **Rust code reduction scope**: Removing ~60% of Rust code is a significant change. Must ensure no shared dependencies break (e.g., `db/queries.rs` has functions for both removed and kept modules). The `db/queries.rs` file (1,276 lines) needs selective pruning.

7. **`solid-markdown` debug shim**: Required in Vite config or build breaks. Must be carried into the desktop app's Vite config (same as web and ui-core).

### Recommendations for Planner

1. **Plan 1**: Scaffold `apps/desktop` — copy Tauri shell from lawyer-desktop, create package.json, vite.config.ts, tsconfig.json, tauri.conf.json, add to root workspaces, prune Rust modules (remove agent/LLM/MCP/skill_opt/sync).

2. **Plan 2**: Desktop adapters + Gateway config — implement 6 adapter interfaces (FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter, DocumentParser, WindowAdapter), Gateway config with configurable URL, AuthContext/ConversationContext/SessionContext reuse.

3. **Plan 3**: App shell + offline cache — TitleBar with WindowAdapter, AppUpdateBanner, HomePage, WorkspacePage, SettingsPanel (reduced: files + about tabs), SQLite offline cache for conversations/messages/documents, offline mode detection.

4. **Plan 4**: FTS5 workspace index + drag-drop + build verification — wire `bind_workspace`/`search_workspace` Tauri commands, drag-drop event handling, law library status/reindex, Windows + macOS build verification, gate setup.
