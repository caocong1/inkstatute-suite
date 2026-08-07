---
phase: 94
slug: desktop-client
plan_count: TBD
subsystem: apps/desktop
tags: [tauri, solidjs, desktop, offline, fts5, auto-update, window-controls, gateway]
requires:
  - phase: 92
    reason: packages/ui-core — shared SolidJS components, event reducer, event stream store, adapter interfaces, themes
  - phase: 91
    reason: services/gateway — HTTP+SSE endpoints, auth middleware, session management, Last-Event-ID replay
provides:
  - apps/desktop — Tauri 2 desktop app (Windows + macOS), using ui-core, communicating via Gateway HTTP/SSE
  - Desktop adapter implementations (FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter, DocumentParser, WindowAdapter)
  - Local workspace FTS5 index (preserved from lawyer-desktop, scan → parse → chunk → per-root SQLite FTS5)
  - Offline read-only mode (cached history + downloaded artifacts, "需要联网" prompt for new tasks)
  - Auto-update mechanism via Tauri updater plugin
  - Custom TitleBar with window controls (minimize/maximize/close/drag) via WindowAdapter
affects:
  - lawyer-desktop — migration source (Tauri shell + workspace FTS5 + window management extracted, not modified in place)
  - apps/web — shares adapter pattern; desktop adapters are parallel implementations of the same interfaces
  - packages/ui-core — WindowAdapter interface already defined; desktop provides concrete implementation
key-files:
  - apps/desktop/package.json
  - apps/desktop/src-tauri/tauri.conf.json
  - apps/desktop/src-tauri/Cargo.toml
  - apps/desktop/src-tauri/src/lib.rs
  - apps/desktop/src-tauri/src/commands/workspace.rs
  - apps/desktop/src-tauri/src/commands/files.rs
  - apps/desktop/src-tauri/src/commands/desktop.rs
  - apps/desktop/src-tauri/src/workspace/mod.rs
  - apps/desktop/src-tauri/src/workspace/index_store.rs
  - apps/desktop/src-tauri/migrations/001_workspace_index.sql
  - apps/desktop/src/main.tsx
  - apps/desktop/src/App.tsx
  - apps/desktop/src/adapters/desktopAdapters.ts
  - apps/desktop/src/adapters/desktopFileAdapter.ts
  - apps/desktop/src/adapters/desktopDropAdapter.ts
  - apps/desktop/src/adapters/desktopAppInfoAdapter.ts
  - apps/desktop/src/adapters/desktopWorkspaceAdapter.ts
  - apps/desktop/src/adapters/desktopDocumentParser.ts
  - apps/desktop/src/adapters/desktopWindowAdapter.ts
  - apps/desktop/src/contexts/AuthContext.tsx
  - apps/desktop/src/contexts/ConversationContext.tsx
  - apps/desktop/src/config/gateway.ts
  - apps/desktop/src/stores/offlineCache.ts
  - apps/desktop/vite.config.ts
  - apps/desktop/tsconfig.json
  - package.json (root — add apps/desktop to workspaces)
  - scripts/run_v2_gates.py (add desktop gate if needed)
key-decisions:
  - "Tauri version: stay on Tauri 2.x (lawyer-desktop uses 2.11), no breaking changes expected"
  - "invoke() migration: 57 calls categorized — ~42 become Gateway HTTP/SSE, ~15 stay as Tauri commands (desktop-specific)"
  - "Offline storage: SQLite local cache for history + artifact metadata, file-system for downloaded artifacts"
  - "FTS5 index: preserved as Tauri command, scan → parse → chunk → per-root SQLite FTS5, results as attachment refs"
  - "Auto-update: Tauri updater plugin retained, endpoint configurable, dev pubkey placeholder"
  - "Window management: WindowAdapter wraps Tauri getCurrentWindow(), TitleBar uses it for minimize/maximize/close/drag"
  - "Build pipeline: tauri build for Windows (NSIS/MSI) + macOS (DMG), CI matrix optional for V3"
  - "Desktop adapters: parallel implementations of ui-core adapter interfaces, using Tauri APIs"
patterns-established:
  - "Desktop adapter pattern — concrete Tauri-backed implementations of ui-core adapter interfaces"
  - "Gateway-only communication — no agent logic in desktop, all via HTTP/SSE to Gateway"
  - "Offline read-only — SQLite cache + filesystem artifacts, online detection via fetch health check"
  - "FTS5 as desktop enhancement — local workspace index preserved, search results as context refs to Gateway"
  - "Tauri command surface — minimal: workspace FTS5 + file dialog + drag-drop classification + auto-update"
requirements-targeted:
  - UI-05
coverage:
  requirements: 1
  success_criteria: 6
duration: TBD
completed: false
status: context-gathered
created: 2026-08-08
---

# Phase 94 — Desktop Client

<domain>

## What This Phase Delivers

A desktop application (`apps/desktop`) that reuses the same `@inkstatute/ui-core` components and the same Gateway HTTP/SSE backend as the web client (Phase 93), wrapped in a Tauri 2 shell migrated from `lawyer-desktop`. The desktop app no longer contains any agent logic, LLM provider calls, skill loading, or MCP client — all of those capabilities come from the platform via the Gateway.

**Core principle (UI-05):** The desktop app is a thin Tauri shell around the same UI core and the same Gateway. It adds only desktop-specific enhancements: native file dialogs, OS drag-drop with real file paths, local workspace FTS5 indexing, auto-update, custom window controls, and offline read-only mode.

**Requirements targeted:**
- **UI-05**: 桌面客户端交付——复用 `lawyer-desktop` 的 Tauri 外壳，57 个 `invoke()` 改指 Gateway HTTP/SSE，保留本地工作区索引，离线只读历史与已生成文书

**Success Criteria (must all be TRUE):**
1. `apps/desktop` exists, migrated from `lawyer-desktop`'s Tauri shell, using `packages/ui-core`, Windows and macOS can build
2. Of the original 57 `invoke()` call sites, all agent/session/message/skill/document-generation calls are replaced by Gateway HTTP/SSE; only desktop-specific capabilities (file dialog, drag-drop, auto-update, local workspace index) remain as Tauri commands
3. Desktop app no longer contains agent loop, LLM provider calls, skill loading, or MCP client — these capabilities all come from the platform
4. Offline state: app can start, view history sessions and downloaded artifacts, and shows a clear "需要联网" prompt when attempting a new task (not silent failure)
5. Local workspace FTS5 index preserved as desktop-specific enhancement, search results can be attached as context refs to the platform
6. Desktop and web on the same task produce consistent results (same events, same clarification cards, same artifacts)

</domain>

<prior_decisions>

## Decisions Carried Forward from Earlier Phases

### From Phase 92 — Shared UI Core (COMPLETE)
- **`packages/ui-core` exists** with all chat-related components: ChatPanel, ClarificationCard, DraftingProgressSteps, MessageFeedback, DocDraftingLoader, WorkflowProgressSteps, CitationPanel, DocPreview, MentionComposer, MentionMenu, Icons, TitleBar, HomePage, ConversationDrawer, AgentTracePanel
- **Event reducer** (`event-reducer.ts`): Pure function `(state, event) → state` processing all 13 event types into `RenderState`
- **EventStreamStore** (`stores/eventStream.ts`): SSE consumer with SolidJS signals, Last-Event-ID reconnection, exponential backoff (1s→30s max)
- **Adapter interfaces** (`adapters/index.ts`): `FileAdapter`, `DropAdapter`, `AppInfoAdapter`, `WorkspaceAdapter`, `DocumentParser`, `WindowAdapter` — injected via `AdapterContext` SolidJS context. `WindowAdapter` is optional (web omits it; desktop provides it)
- **Theme system**: `molv-tokens.css` + `molv-base.css`, `data-theme="a|b|c"`, `useTheme()` store with localStorage persistence
- **Build**: Vite library mode, `@inkstatute/ui-core` package, `workspace:*` protocol, dual ESM/CJS output
- **PlatformApiClient** expanded with all Gateway endpoints: `createSession`, `createRun`, `streamRun`, `submitElicitation`, `submitApproval`, `getArtifact`, `upload`, `submitFeedback`, `listSkills`, `cancelRun`
- **ui-core has zero `@tauri-apps/*` dependencies** — all platform-specific operations go through adapter interfaces

### From Phase 93 — Web Client (COMPLETE)
- **`apps/web` exists** with SPA routing (@solidjs/router), three routes (login, home, workspace)
- **Web adapter implementations**: `webFileAdapter` (hidden `<input type="file">`), `webDropAdapter` (DataTransferItemList → file names), `webAppInfoAdapter` (package.json version), `webWorkspaceAdapter` (returns empty — no local FS), `webDocumentParser` (client-side parse using ui-core utils)
- **Auth flow**: Login page POSTs to Gateway `/v1/auth/login`, session cookie HttpOnly, `AuthContext` wraps app
- **ConversationContext**: Global conversation list via Gateway `GET /v1/sessions`, `createConversation()` calls `POST /v1/sessions`
- **Gateway config**: `VITE_GATEWAY_URL` env var, Vite dev proxy `/v1` → Gateway, `PlatformApiClient` constructed with `baseUrl`
- **Responsive layout**: CSS media queries at 768px breakpoint, drawer navigation on mobile
- **E2E tests**: Playwright with fixture Gateway mock server, 10 test scenarios
- **Root workspace**: `apps/web` added to root `package.json` workspaces array
- **Settings panel deferred**: `SettingsPanel` (963 lines) and `SkillRefinementPanel` (390 lines) from lawyer-desktop are desktop-admin-specific, deferred to Phase 94

### From Phase 91 — Unified Gateway (COMPLETE)
- **12 Gateway endpoints**: `/v1/sessions` (POST/GET), `/v1/sessions/{id}/runs` (GET), `/v1/runs` (POST), `/v1/runs/{id}` (GET/DELETE), `/v1/runs/{id}/events` (SSE), `/v1/runs/{id}/elicitation` (POST), `/v1/runs/{id}/approvals` (POST), `/v1/artifacts/{id}` (GET), `/v1/uploads` (POST), `/v1/feedback` (POST), `/v1/skills` (GET)
- **Auth**: `GatewayAuth` with `resolve_identity()` — Bearer token first, session cookie fallback; `rbac_enabled=False` uses static_token fallback
- **SSE**: `GatewaySseStream` with output boundary enforcement, `Last-Event-ID` replay, in-memory event buffer per `run_id`
- **Login endpoint**: `POST /v1/auth/login` added in Phase 93 (unauthenticated, creates session + cookie)

### From PROJECT.md — Binding Architecture Decisions
- **lawyer-desktop 拆解而非整体迁入**: UI → `packages/ui-core` (done in Phase 92); Tauri shell → `apps/desktop` (this phase); agent logic → Python `packages/agent-core` (Phase 100-103); SQLite CRUD not migrated (platform has persistence)
- **桌面端在线为主、离线只读**: Desktop is online-first; offline mode is read-only (view history + downloaded artifacts). No local agent runtime.
- **移动原生 App 推 V4**: This milestone ships desktop + mobile browser only. Tauri mobile is V4.
- **工具轮必须流式**: lawyer-desktop's non-streaming tool round is a defect to fix, not an asset to port. Desktop gets streaming via Gateway SSE.

### From lawyer-desktop Source (migration inputs)
- **Tauri 2.11** + SolidJS + Vite 8 + bun
- **57 `invoke()` calls** in `src/services/api.ts` — all agent/session/message/skill/document/sync operations
- **Workspace FTS5 index**: `src-tauri/src/workspace/` — scan → parse → chunk → per-root SQLite FTS5 with trigram tokenizer, bm25 ranking, LIKE fallback for short terms
- **FTS5 migration**: `migrations/002_workspace_index.sql` — `workspace_roots`, `workspace_files`, `workspace_chunks`, `workspace_chunks_fts` (external content table, trigram tokenize)
- **Window management**: `TitleBar.tsx` uses `getCurrentWindow()` for minimize/maximize/close/drag, macOS traffic lights vs Windows controls, `data-tauri-drag-region` for window dragging
- **Auto-update**: `@tauri-apps/plugin-updater` + `@tauri-apps/plugin-process`, `checkForAppUpdate()` / `installAppUpdate()` in `api.ts`, `AppUpdateBanner.tsx` component
- **File dialog**: `@tauri-apps/plugin-dialog` `open()` / `save()` in ChatPanel, HomePage, SettingsPanel, DocPreview
- **Drag-drop**: `getCurrentWebview().onDragDropEvent()` in ChatPanel + HomePage, `classify_dropped_paths` invoke for file vs directory classification
- **Tauri config**: `decorations: false` (custom titlebar), `dragDropEnabled: true`, CSP with `connect-src` for Gateway URL
- **Cargo.toml dependencies**: tauri 2, tauri-plugin-{opener,fs,dialog,updater,process,sql}, sqlx (sqlite), reqwest, tokio, pdf-extract, docx-rs, walkdir, encoding_rs

</prior_decisions>

<decisions>

## Auto-Selected Decisions for Gray Areas

[--auto] Selected all gray areas: Tauri Version, invoke() Migration Strategy, Offline Storage, FTS5 Index Preservation, Auto-Update, Window Management, Build Pipeline, Desktop Adapters.

### 1. Tauri Version

[auto] [Tauri Version] — Q: "Stay on Tauri 2.11 from lawyer-desktop, or upgrade to a newer version?" → Selected: "Stay on Tauri 2.x (current latest stable), no breaking changes expected" (recommended default)

**Rationale:** lawyer-desktop uses Tauri 2.11 with `@tauri-apps/api ^2.11.0`, `@tauri-apps/cli ^2.11.2`, and all plugins at `^2.x`. The Tauri 2.x series maintains backward compatibility within the major version. The desktop client for Phase 94 starts from the same Tauri 2.x baseline.

**What changes from lawyer-desktop:**
- Package name: `lawyer-desktop` → `inkstatute-desktop` (or `@inkstatute/desktop`)
- `tauri.conf.json` `productName` stays "墨律", `identifier` stays `com.sorawatcher.inkstatute`
- Frontend changes from lawyer-desktop's own components to `@inkstatute/ui-core` imports
- CSP `connect-src` must include the Gateway URL (configurable, not just localhost)
- The `beforeDevCommand` and `beforeBuildCommand` point to the new `apps/desktop` Vite config

**What stays the same:**
- Tauri plugin set: `tauri-plugin-dialog`, `tauri-plugin-fs`, `tauri-plugin-updater`, `tauri-plugin-process`
- `tauri-plugin-sql` is retained for the workspace FTS5 index (separate from the main app SQLite)
- `tauri-plugin-opener` for opening external links
- `decorations: false` + custom TitleBar pattern
- `dragDropEnabled: true` for OS file drag-drop

**What is removed:**
- `tauri-plugin-mcp-bridge` — MCP is now platform-side, not desktop-side
- All agent logic modules: `llm/`, `skills/`, `mcp/`, `skill_opt/`, `citations/`, `law_library/`, `sync/`, `documents/` (except workspace FTS5)
- All agent-related Tauri commands (see invoke() migration below)
- `tauri-plugin-sql` for the main app database (`lawyer-desktop.db`) — the platform has its own persistence. The `tauri-plugin-sql` is retained ONLY for the workspace FTS5 index database.

### 2. invoke() Migration Strategy

[auto] [invoke() Migration] — Q: "Which of the 57 invoke() calls become Gateway HTTP/SSE, and which stay as Tauri commands?" → Selected: "Categorize by function: agent/session/message/skill/doc/sync → Gateway; file/workspace/dialog/updater → Tauri commands" (recommended default)

**Rationale:** The 57 `invoke()` calls in `lawyer-desktop/src/services/api.ts` fall into clear categories. The success criterion (UI-05 #2) requires that "凡属于 agent / 会话 / 消息 / 技能 / 文档生成的，全部改为 Gateway HTTP/SSE；仅保留桌面专属能力（文件对话框、拖放、自动更新、本地工作区索引）为 Tauri 命令."

**Category A — Migrate to Gateway HTTP/SSE (42 calls):**

| invoke() command | Gateway replacement | Notes |
|---|---|---|
| `send_message` | `POST /v1/runs` + SSE `GET /v1/runs/{id}/events` | Core chat → Gateway run + SSE stream |
| `classify_agent_mode` | Removed — classification is platform-side | Agent logic not in desktop |
| `create_conversation` | `POST /v1/sessions` | Session = conversation |
| `get_conversations` | `GET /v1/sessions` | Session list |
| `get_messages` | `GET /v1/sessions/{id}/runs` + event replay | Messages come from event stream |
| `update_message_metadata` | Removed — metadata is platform-side | |
| `generate_followup_prompts` | Removed — platform generates suggestions | |
| `delete_conversation` | `DELETE /v1/sessions/{id}` (if available) or `DELETE /v1/runs/{id}` | |
| `get_active_provider` | Removed — provider is platform-side | |
| `get_fast_model_presets` | Removed — platform-side | |
| `get_fast_provider` | Removed — platform-side | |
| `setup_fast_provider` | Removed — platform-side | |
| `test_fast_provider` | Removed — platform-side | |
| `set_active_conversation` | Removed — session management is Gateway-side | |
| `update_conversation_title` | `PATCH /v1/sessions/{id}` (if available) | |
| `get_provider_presets` | Removed — platform-side | |
| `setup_provider` | Removed — platform-side | |
| `test_provider` | Removed — platform-side | |
| `get_skills_root` | Removed — skills are platform-side | |
| `set_skills_root` | Removed — skills are platform-side | |
| `reload_skills` | Removed — skills are platform-side | |
| `list_skills` | `GET /v1/skills` | Gateway skills endpoint |
| `get_mcp_health` | Removed — MCP is platform-side | |
| `get_law_library_status` | Removed — law library is platform-side | |
| `reindex_law_library` | Removed — platform-side | |
| `parse_legal_document` | Client-side parse via `DocumentParser` adapter | Uses ui-core's `markdownToLegalDocument` |
| `generate_docx` | `GET /v1/artifacts/{id}` download | Doc generation is platform-side; desktop downloads |
| `get_skillopt_settings` | Removed — skill optimization is platform-side | |
| `set_skillopt_settings` | Removed — platform-side | |
| `submit_message_feedback` | `POST /v1/feedback` | Gateway feedback endpoint |
| `get_message_feedback` | Removed — feedback is platform-side | |
| `list_all_feedback` | Removed — platform-side | |
| `list_eval_cases` | Removed — eval is platform-side | |
| `set_eval_case_active` | Removed — platform-side | |
| `run_eval_case` | Removed — platform-side | |
| `list_eval_runs` | Removed — platform-side | |
| `list_proposals` | Removed — platform-side | |
| `adopt_proposal` | Removed — platform-side | |
| `reject_proposal` | Removed — platform-side | |
| `run_skill_refinement` | Removed — platform-side | |
| `mine_eval_cases` | Removed — platform-side | |
| `get_skillopt_overview` | Removed — platform-side | |
| `get_sync_settings` | Removed — sync is platform-side | |
| `set_sync_settings` | Removed — platform-side | |
| `get_sync_status_cmd` | Removed — platform-side | |
| `flush_feedback_outbox` | Removed — platform-side | |
| `test_sync_connection` | Removed — platform-side | |

**Category B — Keep as Tauri commands (15 calls, desktop-specific):**

| invoke() command | Purpose | Tauri command in apps/desktop |
|---|---|---|
| `read_file_content` | Read local file for attachment/context ref | `read_file_content` |
| `list_directory` | List directory for workspace file browser | `list_directory` |
| `prepare_attachment` | Prepare local file as attachment for Gateway upload | `prepare_attachment` |
| `classify_dropped_paths` | Classify OS-dropped paths as file vs directory | `classify_dropped_paths` |
| `grant_path_access` | Grant sandbox read access to a path | `grant_path_access` |
| `get_allowed_file_dirs` | Get allowed directory list for sandbox | `get_allowed_file_dirs` |
| `set_allowed_file_dirs` | Set allowed directory list | `set_allowed_file_dirs` |
| `bind_workspace` | Bind + start FTS5 indexing for a directory | `bind_workspace` |
| `get_workspace_index_status` | Check FTS5 index status | `get_workspace_index_status` |
| `search_workspace` | FTS5 search on local workspace | `search_workspace` |
| `getVersion` (via `@tauri-apps/api/app`) | Get app version | Via `AppInfoAdapter` |
| `checkForAppUpdate` (via `@tauri-apps/plugin-updater`) | Check for app updates | Via `AppInfoAdapter` |
| `installAppUpdate` (via `@tauri-apps/plugin-updater`) | Install update + relaunch | Via `AppInfoAdapter` |
| `onChatStream` (Tauri event listener) | Replaced by SSE `EventStreamStore` | Removed — use Gateway SSE |
| `onAgentTrace` (Tauri event listener) | Replaced by SSE events | Removed — use Gateway SSE |

**Category C — Tauri event listeners (removed, replaced by SSE):**

| Event listener | Replacement |
|---|---|
| `onChatStream` (`listen("chat-stream")`) | `EventStreamStore` from ui-core (SSE) |
| `onAgentTrace` (`listen("agent-trace")`) | `EventStreamStore` (tool_call events) |
| `onWorkspaceIndexProgress` (`listen("workspace-index-progress")`) | Retained as Tauri event (desktop-specific) |
| `onLawUpdateAlert` (`listen("law-update-alert")`) | Removed — law monitoring is platform-side |
| `onSkillOptProgress` (`listen("skillopt-progress")`) | Removed — skill optimization is platform-side |
| `onSkillsUpdated` (`listen("skills-updated")`) | Removed — skills are platform-side |

**Net Tauri command surface in apps/desktop:**
- `read_file_content`, `list_directory`, `prepare_attachment`, `classify_dropped_paths`
- `grant_path_access`, `get_allowed_file_dirs`, `set_allowed_file_dirs`
- `bind_workspace`, `get_workspace_index_status`, `search_workspace`
- Tauri event: `workspace-index-progress` (emitted during FTS5 indexing)
- Tauri plugins: dialog (open/save), updater (check/install), process (relaunch), fs (file access), opener (external links)

This is 10 Tauri commands + 3 plugin APIs — a dramatic reduction from lawyer-desktop's 57 commands.

### 3. Offline Storage

[auto] [Offline Storage] — Q: "How to cache history and artifacts for offline read-only access?" → Selected: "SQLite local cache for session/run metadata + filesystem for downloaded artifacts, online detection via Gateway health check" (recommended default)

**Rationale:** The success criterion (UI-05 #4) requires: "离线状态下应用可启动，能查看历史会话与已下载的产物文件，发起新任务时给出明确的'需要联网'提示而非静默失败." The desktop app is online-first (PROJECT.md decision: "桌面端在线为主、离线只读"), so offline is a degraded read-only mode, not a full offline agent.

**Offline architecture:**

1. **Online detection**: On app startup and periodically (every 30s), the desktop app calls `GET /v1/health` (or any lightweight Gateway endpoint). If it fails, the app enters offline mode. A banner/indicator shows "离线模式 — 仅可查看历史".

2. **Session history cache**: A local SQLite database (`apps/desktop` app data dir, separate from the FTS5 workspace index) caches:
   - `cached_sessions`: `session_id`, `tenant_id`, `title`, `created_at`, `updated_at`, `last_viewed_at`
   - `cached_runs`: `run_id`, `session_id`, `status`, `created_at`, `completed_at`
   - `cached_events`: `event_id`, `run_id`, `seq`, `event_type`, `payload_json`, `occurred_at` — a subset of events sufficient to reconstruct message history (message.completed, artifact.created, elicitation.requested)
   - This cache is populated incrementally as the user views sessions online. It is NOT a full sync — it's a "last viewed" cache.

3. **Artifact cache**: Downloaded artifacts (via `GET /v1/artifacts/{id}`) are saved to `{app_data_dir}/artifacts/{artifact_id}`. The file path and metadata are recorded in `cached_artifacts` table. When offline, the user can open previously downloaded artifacts from the local filesystem.

4. **Offline UI behavior**:
   - Session list shows cached sessions (may be stale)
   - Clicking a cached session shows cached messages (text only, no re-streaming)
   - DocPreview shows cached artifacts if available, or a "未缓存" placeholder
   - Composer is disabled with a "需要联网才能发起新任务" hint
   - FTS5 workspace search still works (it's fully local)
   - Theme switching still works (local)

5. **What is NOT cached offline**:
   - No streaming (requires SSE connection)
   - No new task submission (requires Gateway)
   - No elicitation/clarification submission (requires Gateway)
   - No feedback submission (requires Gateway)
   - No skill listing (requires Gateway)

**SQLite implementation**: Use `tauri-plugin-sql` (already a dependency for FTS5) with a separate database file (`offline-cache.db`). Migrations are embedded. The cache is write-on-view (updated when online) and read-only when offline.

### 4. FTS5 Index Preservation

[auto] [FTS5 Index] — Q: "How to preserve the local workspace FTS5 index from lawyer-desktop?" → Selected: "Port the workspace module (scanner, parser, chunker, index_store, manager) as Tauri commands, keep per-root SQLite FTS5 with trigram tokenizer" (recommended default)

**Rationale:** The success criterion (UI-05 #5) requires: "本地工作区 FTS5 索引作为桌面专属增强保留，其检索结果可作为附件引用提交给平台." The workspace FTS5 index is a desktop-specific enhancement that adds value over the web client — it allows lawyers to search local case materials and attach relevant chunks as context references to the platform.

**What is ported from lawyer-desktop:**
- `src-tauri/src/workspace/mod.rs` — module structure
- `src-tauri/src/workspace/scanner.rs` — file scanning (walkdir, hash, metadata)
- `src-tauri/src/workspace/parser.rs` — text/PDF extraction (pdf-extract, encoding_rs)
- `src-tauri/src/workspace/chunker.rs` — markdown-aware chunking
- `src-tauri/src/workspace/index_store.rs` — SQLite FTS5 with trigram tokenizer, bm25 ranking, LIKE fallback
- `src-tauri/src/workspace/manager.rs` — bind_and_index, search, get_status orchestration
- `src-tauri/migrations/002_workspace_index.sql` — schema (workspace_roots, workspace_files, workspace_chunks, workspace_chunks_fts with external content table + triggers)
- `src-tauri/src/commands/workspace.rs` — Tauri commands: `bind_workspace`, `get_workspace_index_status`, `search_workspace`

**What is NOT ported:**
- `law_library/` — the bundled law library index. Law library is now platform-side. The FTS5 workspace index is for user's local case materials only.
- `sync/skills_update.rs` — skill syncing is platform-side

**FTS5 search → Gateway integration:**
1. User searches local workspace via `search_workspace` Tauri command
2. Results show as a local search panel with chunk text + relative path
3. User selects chunks to attach as context references
4. Context refs are sent to Gateway as part of `POST /v1/runs` body (as `context_refs` or attachment refs)
5. The platform reads the referenced file content via a separate `read_file_content` Tauri command call (if the desktop app provides a local file server) OR the desktop app uploads the chunk text as an attachment via `POST /v1/uploads`

**Implementation choice**: The desktop app uploads selected FTS5 chunks as attachments via `POST /v1/uploads` (the chunk text is uploaded as a text file). This avoids needing a local file server and keeps the Gateway's attachment handling uniform. The `prepare_attachment` Tauri command reads the local file and prepares it for upload.

**Index DB path**: `{app_data_dir}/workspaces/{root_hash}/index.db` — same as lawyer-desktop.

### 5. Auto-Update

[auto] [Auto-Update] — Q: "How to handle auto-update in the migrated desktop app?" → Selected: "Retain Tauri updater plugin, configurable endpoint via tauri.conf.json, dev pubkey placeholder replaced before production" (recommended default)

**Rationale:** lawyer-desktop already has a working auto-update mechanism using `@tauri-apps/plugin-updater` and `@tauri-apps/plugin-process`. The `tauri.conf.json` has an `updater` config with `endpoints` and `pubkey`. The `api.ts` has `checkForAppUpdate()` and `installAppUpdate()` functions. The `AppUpdateBanner.tsx` component shows update notifications.

**What is ported:**
- `tauri-plugin-updater` and `tauri-plugin-process` in Cargo.toml
- `updater` config in `tauri.conf.json` (endpoint + pubkey)
- `AppInfoAdapter` implementation wraps `checkForUpdate()` and `installUpdate()` (via `@tauri-apps/plugin-updater`)
- `AppUpdateBanner` component (from ui-core or reimplemented in desktop app)

**What changes:**
- Updater endpoint is configurable via environment variable or build-time config (not hardcoded to `localhost:8787`)
- The `pubkey` in `tauri.conf.json` is a placeholder (`dW5zZXQtcmVwbGFjZS13aXRoLXNpZ25lci1wdWJrZXk=`) — must be replaced with a real signing key before production builds. This is a pre-production step, not a code change.
- `createUpdaterArtifacts: true` in bundle config is retained
- The `AppUpdateBanner` is wired through `AppInfoAdapter.checkForUpdate()` — the ui-core `AppInfoAdapter` interface already has optional `checkForUpdate?()` and `installUpdate?()` methods

**What is NOT ported:**
- The sync service (`tools/sync-service`) that serves the updater manifest — this is a separate deployment concern, not part of the desktop app code
- Skill auto-update via sync service — skills are now platform-side

### 6. Window Management

[auto] [Window Management] — Q: "How to handle TitleBar window controls (minimize/maximize/close/drag)?" → Selected: "WindowAdapter wraps Tauri getCurrentWindow(), TitleBar uses it via AdapterContext, macOS traffic lights vs Windows controls" (recommended default)

**Rationale:** The ui-core `TitleBar` component (ported from lawyer-desktop in Phase 92) already accepts a `WindowAdapter` via `AdapterContext`. The `WindowAdapter` interface in `adapters/index.ts` defines: `minimize()`, `toggleMaximize()`, `close()`, `isMaximized()`, `onResized?(cb)`, `startDragging?()`. The web client omits it (optional in `AdapterContextValue`). The desktop client provides a concrete implementation.

**DesktopWindowAdapter implementation:**
```typescript
import { getCurrentWindow } from "@tauri-apps/api/window";
import type { WindowAdapter } from "@inkstatute/ui-core";

export const desktopWindowAdapter: WindowAdapter = {
  async minimize() { await getCurrentWindow().minimize(); },
  async toggleMaximize() { await getCurrentWindow().toggleMaximize(); },
  async close() { await getCurrentWindow().close(); },
  async isMaximized() { return await getCurrentWindow().isMaximized(); },
  async onResized(cb) {
    const win = getCurrentWindow();
    const unlisten = await win.onResized(() => cb());
    return unlisten;
  },
  async startDragging() { await getCurrentWindow().startDragging(); },
};
```

**TitleBar behavior:**
- The ui-core `TitleBar` component already handles macOS vs Windows detection (`isMacOS()`), traffic light dots vs Windows-style buttons, `data-tauri-drag-region` for window dragging, and double-click to toggle maximize.
- The `WindowAdapter` is injected via `AdapterContext.Provider` — the `TitleBar` calls `useAdapters().window` to access it.
- When `window` is undefined (web mode), the TitleBar hides window controls. When defined (desktop mode), it shows them.

**Tauri config**: `decorations: false` in `tauri.conf.json` ensures the native OS titlebar is hidden, and the custom `TitleBar` component provides the window controls.

### 7. Build Pipeline

[auto] [Build Pipeline] — Q: "How to build for Windows + macOS? CI setup?" → Selected: "tauri build for Windows (NSIS) + macOS (DMG), CI matrix optional for V3 (local build sufficient for ≤50 lawyers)" (recommended default)

**Rationale:** The success criterion (UI-05 #1) requires "Windows 与 macOS 可构建." For V3's self-hosted single-firm scale (≤50 lawyers), a full CI matrix for cross-platform builds is not on the critical path. The desktop app should be buildable on both platforms, but automated CI builds can be deferred.

**Build commands:**
- `bun run tauri build` — builds the frontend (Vite) + compiles Rust + bundles the app
- Windows: produces NSIS installer (`.exe`) and MSI installer
- macOS: produces DMG and app bundle (`.app`)
- `createUpdaterArtifacts: true` generates signed updater artifacts (`.sig` files) for the Tauri updater

**Prerequisites:**
- Windows: Rust (MSVC toolchain), Node.js, bun, WebView2 (pre-installed on Windows 10+)
- macOS: Rust (stable), Node.js, bun, Xcode Command Line Tools

**CI (deferred):**
- GitHub Actions matrix (`windows-latest`, `macos-latest`) with `tauri-apps/tauri-action`
- Signing: Windows code signing cert (optional for self-hosted), macOS notarization (required for distribution, optional for self-hosted)
- Updater manifest: `latest.json` served by a static endpoint (the sync service or a simple static server)
- For V3, local builds are sufficient. CI can be added post-V3 or when distributing to multiple machines.

**Vite config**: `apps/desktop/vite.config.ts` mirrors lawyer-desktop's config — `vite-plugin-solid`, port 1420 (or configurable), `debug` shim for `solid-markdown`.

### 8. Desktop Adapters

[auto] [Desktop Adapters] — Q: "How do the ui-core adapter interfaces map to Tauri commands?" → Selected: "Parallel implementations of all 6 adapter interfaces using Tauri APIs, injected via AdapterContext" (recommended default)

**Rationale:** The ui-core defines 6 adapter interfaces in `adapters/index.ts`. The web client (Phase 93) provides web implementations. The desktop client provides Tauri-backed implementations. Both inject via `AdapterContext.Provider`.

**Adapter implementations:**

| Interface | Desktop Implementation | Tauri APIs used |
|---|---|---|
| `FileAdapter` | `desktopFileAdapter` — uses `@tauri-apps/plugin-dialog` `open()` / `save()` with native file dialogs | `tauri-plugin-dialog` |
| `DropAdapter` | `desktopDropAdapter` — uses `getCurrentWebview().onDragDropEvent()` + `classify_dropped_paths` Tauri command for real file paths | `@tauri-apps/api/webview`, `invoke("classify_dropped_paths")` |
| `AppInfoAdapter` | `desktopAppInfoAdapter` — uses `@tauri-apps/api/app` `getVersion()` + `@tauri-apps/plugin-updater` `check()` / `downloadAndInstall()` + `@tauri-apps/plugin-process` `relaunch()` | `tauri-plugin-updater`, `tauri-plugin-process` |
| `WorkspaceAdapter` | `desktopWorkspaceAdapter` — uses `list_directory` Tauri command to list files in allowed dirs, `search_workspace` for FTS5 search results | `invoke("list_directory")`, `invoke("search_workspace")` |
| `DocumentParser` | `desktopDocumentParser` — client-side parse using ui-core's `markdownToLegalDocument` (same as web) | None (pure JS) |
| `WindowAdapter` | `desktopWindowAdapter` — uses `@tauri-apps/api/window` `getCurrentWindow()` for minimize/maximize/close/drag | `@tauri-apps/api/window` |

**Key difference from web adapters:**
- `FileAdapter.open()` returns **real file paths** (not just file names) — Tauri dialog exposes the full path
- `DropAdapter.classifyDroppedPaths()` returns **real file paths with isDir** — Tauri drag-drop exposes OS paths
- `WorkspaceAdapter.listFiles()` returns **real local files** — Tauri can list the filesystem
- `AppInfoAdapter.checkForUpdate()` is **implemented** (web omits it) — Tauri updater plugin
- `WindowAdapter` is **provided** (web omits it) — Tauri window management

**Drag-drop handling:**
The desktop app registers `getCurrentWebview().onDragDropEvent()` in `onMount` (same pattern as lawyer-desktop's ChatPanel and HomePage). When files are dropped:
1. The event payload contains `paths[]` (real OS paths)
2. `classify_dropped_paths` Tauri command classifies each as file vs directory
3. Classified paths are attached to the composer as attachments
4. For directories, `bind_workspace` can be called to start FTS5 indexing

**File attachment flow:**
1. User picks files via `FileAdapter.open()` (native dialog) or drag-drop
2. `prepare_attachment` Tauri command reads the file and returns metadata (name, size, type)
3. The file is uploaded to Gateway via `POST /v1/uploads` (the desktop app reads the file content and sends it as multipart form data)
4. Gateway returns `attachment_ref` which is included in the `POST /v1/runs` body

</decisions>

<canonical_refs>

## Canonical References for Downstream Agents

### ui-core (Phase 92, complete — the single chat UI source)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/index.ts` — All exports (components, stores, adapters, types, utils)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/adapters/index.ts` — Adapter interfaces (FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter, DocumentParser, WindowAdapter)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/stores/eventStream.ts` — EventStreamStore with SSE consumer + Last-Event-ID reconnection
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/event-reducer.ts` — Pure reducer for 13 event types → RenderState
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/TitleBar.tsx` — Top bar with window controls (uses WindowAdapter when available)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/ChatPanel.tsx` — Chat panel
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/HomePage.tsx` — Home page
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/DocPreview.tsx` — Document preview
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/ConversationDrawer.tsx` — Conversation list
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/themes/molv-tokens.css` — Theme tokens (3 themes)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/package.json` — Package config

### platform-sdk-ts (Phase 92, complete — Gateway client SDK)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/platform-sdk-ts/src/index.ts` — PlatformApiClient with all 12 Gateway endpoints
- `/home/sorawatcher/workspace/inkstatute-suite/packages/platform-sdk-ts/src/events.ts` — TS bindings for 13 event types

### apps/web (Phase 93, complete — reference for adapter pattern)
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/adapters/webAdapters.ts` — Web adapter barrel (pattern to mirror)
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/adapters/webFileAdapter.ts` — Web FileAdapter (reference implementation)
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/adapters/webDropAdapter.ts` — Web DropAdapter
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/adapters/webAppInfoAdapter.ts` — Web AppInfoAdapter
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/adapters/webWorkspaceAdapter.ts` — Web WorkspaceAdapter
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/adapters/webDocumentParser.ts` — Web DocumentParser
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/App.tsx` — App root with context providers + router
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/contexts/AuthContext.tsx` — Auth context (pattern to reuse)
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/contexts/ConversationContext.tsx` — Conversation context
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/config/gateway.ts` — Gateway config (PlatformApiClient instance)
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/pages/LoginPage.tsx` — Login page
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/pages/WorkspacePage.tsx` — Workspace page
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web/src/layouts/AppLayout.tsx` — App layout

### Gateway (Phase 91, complete — HTTP+SSE backend)
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/app.py` — All endpoint handlers
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/auth.py` — Auth middleware
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/sse.py` — SSE stream with output boundary
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/sessions.py` — Session management

### lawyer-desktop (migration source — Tauri shell + workspace FTS5)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/tauri.conf.json` — Tauri config (decorations, dragDrop, updater, CSP, bundle)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/Cargo.toml` — Rust dependencies (tauri 2, plugins, sqlx, pdf-extract, etc.)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/lib.rs` — Tauri app setup, plugin registration, command handler list
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/workspace/mod.rs` — Workspace module structure
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/workspace/index_store.rs` — FTS5 index store (577 lines, with tests)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/workspace/manager.rs` — Index orchestration (bind_and_index, search, get_status)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/workspace/scanner.rs` — File scanner (walkdir, hash)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/workspace/parser.rs` — Text/PDF extraction
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/workspace/chunker.rs` — Markdown chunking
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/commands/workspace.rs` — Tauri commands: bind_workspace, get_workspace_index_status, search_workspace
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/commands/files.rs` — File commands: read_file_content, list_directory, prepare_attachment, classify_dropped_paths, grant_path_access
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/migrations/002_workspace_index.sql` — FTS5 schema (workspace_roots, workspace_files, workspace_chunks, workspace_chunks_fts with trigram tokenizer + triggers)
- `/home/sorawatcher/workspace/lawyer-desktop/src/services/api.ts` — All 57 invoke() calls (696 lines, the migration source)
- `/home/sorawatcher/workspace/lawyer-desktop/src/components/layout/TitleBar.tsx` — TitleBar with window controls (226 lines, reference for WindowAdapter usage)
- `/home/sorawatcher/workspace/lawyer-desktop/src/components/layout/AppUpdateBanner.tsx` — Update banner component
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/security/path_sandbox.rs` — Path sandbox (for file access control)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/capabilities/default.json` — Tauri capabilities/permissions

### Project Decisions
- `/home/sorawatcher/workspace/inkstatute-suite/.planning/PROJECT.md` — Key Decisions (lawyer-desktop 拆解, 桌面端在线为主离线只读, 移动原生 App 推 V4)
- `/home/sorawatcher/workspace/inkstatute-suite/AGENTS.md` — Implementation Priorities #5: "extract before building apps/web or apps/desktop"
- `/home/sorawatcher/workspace/inkstatute-suite/.planning/REQUIREMENTS.md` — UI-05 requirement text
- `/home/sorawatcher/workspace/inkstatute-suite/.planning/ROADMAP.md` — Phase 94 success criteria

</canonical_refs>

<code_context>

## Reusable Assets and Patterns Found During Codebase Scouting

### lawyer-desktop Tauri Shell (migration source)

The `lawyer-desktop` project at `/home/sorawatcher/workspace/lawyer-desktop/` is a complete Tauri 2.11 + SolidJS app. The desktop client for Phase 94 migrates the Tauri shell (not the agent logic) into `apps/desktop` in the inkstatute-suite repo.

**Tauri config** (`tauri.conf.json`):
- `productName: "墨律"`, `identifier: "com.sorawatcher.inkstatute"`
- `decorations: false` — custom TitleBar, no native OS titlebar
- `dragDropEnabled: true` — OS file drag-drop
- `withGlobalTauri: true` — `window.__TAURI__` available
- CSP: `default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https: http://localhost:* http://127.0.0.1:* ws://localhost:*`
- Bundle: `targets: "all"`, `createUpdaterArtifacts: true`, icons for Windows + macOS
- Updater: endpoint + pubkey (placeholder)

**Cargo.toml dependencies** (to be selectively ported):
- Retained: `tauri 2`, `tauri-plugin-{opener,fs,dialog,updater,process,sql}`, `sqlx (sqlite)`, `serde`, `serde_json`, `tokio`, `uuid`, `chrono`, `anyhow`, `log`, `walkdir`, `encoding_rs`, `pdf-extract`, `sha2`, `regex`
- Removed: `docx-rs` (doc generation is platform-side), `reqwest` (no direct HTTP from Rust), `scraper`, `zip`, `aes-gcm`, `base64`, `rand`, `dotenvy`, `tauri-plugin-mcp-bridge`, `thiserror`, `env_logger`, `async-trait`, `futures`, `tokio-stream`, `serde_yaml`

**Rust modules to port** (workspace FTS5 + file commands only):
- `workspace/` (scanner, parser, chunker, index_store, manager) — FTS5 indexing pipeline
- `commands/workspace.rs` — 3 Tauri commands (bind_workspace, get_workspace_index_status, search_workspace)
- `commands/files.rs` — 5 Tauri commands (read_file_content, list_directory, prepare_attachment, classify_dropped_paths, grant_path_access) + path sandbox
- `security/path_sandbox.rs` — path access control
- `db/` — NOT ported (main app DB is platform-side); only workspace FTS5 DB is local

**Rust modules NOT ported** (agent logic, now platform-side):
- `llm/` — LLM provider (OpenAI-compatible streaming)
- `skills/` — skill registry, router, classifier
- `mcp/` — MCP client
- `skill_opt/` — skill optimization
- `citations/` — citation audit
- `law_library/` — bundled law library
- `sync/` — sync service client
- `documents/` — docx generation
- `commands/chat.rs` — chat commands (send_message, classify_agent_mode, etc.)
- `commands/settings.rs` — settings commands
- `commands/skillopt.rs` — skill optimization commands
- `commands/sync.rs` — sync commands
- `commands/documents.rs` — document generation commands
- `commands/trace.rs` — agent trace commands

### 57 invoke() Calls — Full Inventory

All 57 `invoke()` calls are in `/home/sorawatcher/workspace/lawyer-desktop/src/services/api.ts` (696 lines). They are categorized in the decisions section above. Key observations:

- **Chat/session/message**: 12 calls → Gateway HTTP/SSE
- **Provider/settings**: 12 calls → Removed (platform-side)
- **Skills/MCP**: 5 calls → 1 to Gateway (`list_skills`), 4 removed
- **Files/workspace**: 10 calls → Stay as Tauri commands (desktop-specific)
- **Documents**: 2 calls → 1 to Gateway download, 1 to client-side parse
- **SkillOpt/eval**: 12 calls → All removed (platform-side)
- **Sync**: 5 calls → All removed (platform-side)
- **Event listeners**: 6 `listen()` calls → 1 retained (workspace-index-progress), 5 removed (replaced by SSE)

### Workspace FTS5 Index — Implementation Details

The FTS5 index is a per-root SQLite database at `{app_data_dir}/workspaces/{root_hash}/index.db`. The schema (from `002_workspace_index.sql`):

- `workspace_roots`: one row per indexed directory (id, root_path, root_hash, status, file_count, chunk_count)
- `workspace_files`: indexed files (id, root_id, absolute_path, relative_path, size, mtime_secs, sha256, file_ext)
- `workspace_chunks`: text chunks (id, file_id, root_id, relative_path, heading_path, ordinal, content, sha256)
- `workspace_chunks_fts`: FTS5 virtual table with `tokenize='trigram'`, external content table pattern with INSERT/DELETE/UPDATE triggers

Search uses bm25 ranking with trigram tokenizer. Terms shorter than 3 chars fall back to LIKE search. Multi-keyword queries are OR-joined for bm25 ranking. The `escape_fts_query()` function builds FTS5 query strings.

The indexing pipeline: scan (walkdir) → parse (pdf-extract, encoding_rs) → chunk (markdown-aware) → upsert (SQLite + FTS5). Progress is emitted via Tauri event `workspace-index-progress`.

### Window Management — TitleBar Pattern

The `TitleBar.tsx` component (226 lines) in lawyer-desktop uses:
- `isTauri()` from `@tauri-apps/api/core` — runtime check for Tauri environment
- `getCurrentWindow()` from `@tauri-apps/api/window` — window handle
- `win.minimize()`, `win.toggleMaximize()`, `win.close()`, `win.isMaximized()`, `win.onResized()`, `win.startDragging()`
- macOS detection: `isMacOS()` checks `navigator.platform` / `navigator.userAgent`
- macOS: traffic light dots (close/minimize/maximize), `data-tauri-drag-region` for dragging
- Windows: square buttons in top-right, double-click drag region to toggle maximize

In ui-core (Phase 92), the TitleBar was ported to use `WindowAdapter` via `AdapterContext`. The desktop app provides the concrete `WindowAdapter` implementation.

### Auto-Update — Existing Pattern

lawyer-desktop's auto-update:
- `checkForAppUpdate()` in `api.ts`: dynamic import `@tauri-apps/plugin-updater`, calls `check()`, returns `{ available, version?, body? }`
- `installAppUpdate()` in `api.ts`: dynamic import `@tauri-apps/plugin-updater` + `@tauri-apps/plugin-process`, calls `update.downloadAndInstall()` + `relaunch()`
- `AppUpdateBanner.tsx`: component that calls `checkForAppUpdate()` on mount, shows banner if update available
- `tauri.conf.json` updater config: `endpoints` array + `pubkey` (base64-encoded signing public key)
- `createUpdaterArtifacts: true` in bundle config

In the desktop app, this maps to `AppInfoAdapter.checkForUpdate()` and `AppInfoAdapter.installUpdate()`.

### apps/web Adapter Pattern (reference for desktop)

The web client (Phase 93) established the adapter pattern:
1. Create individual adapter files in `src/adapters/` (one per interface)
2. Create a barrel file `src/adapters/webAdapters.ts` that assembles `AdapterContextValue`
3. Inject in `App.tsx` via `<AdapterContext.Provider value={webAdapters}>`
4. The `AdapterContextValue` type requires `file`, `drop`, `appInfo`, `workspace`, `documentParser`; `window` is optional

The desktop client mirrors this:
1. Create `src/adapters/desktopFileAdapter.ts`, `desktopDropAdapter.ts`, etc.
2. Create `src/adapters/desktopAdapters.ts` barrel
3. Include `window: desktopWindowAdapter` (the key difference from web)
4. Inject in `App.tsx`

### Gateway Communication Pattern

The desktop app communicates with the Gateway identically to the web client:
- `PlatformApiClient` from `@inkstatute/platform-sdk-ts` with `baseUrl` configurable
- SSE via `EventStreamStore` from `@inkstatute/ui-core`
- Auth via session cookie (Tauri's HTTP client sends cookies automatically) or Bearer token
- The Gateway URL is configurable via a settings panel or environment variable

**Key difference from web**: The desktop app does NOT use a Vite dev proxy. Instead, the Gateway URL is configured directly (e.g., `http://localhost:8000` for dev, or a remote URL for production). The Tauri CSP must include the Gateway URL in `connect-src`.

### Root Workspace Config

Current `package.json` workspaces (after Phase 93):
```json
{
  "workspaces": ["packages/platform-sdk-ts", "packages/ui-core", "apps/web"]
}
```
Phase 94 adds `"apps/desktop"` to this array.

</code_context>

<deferred>

## Deferred Ideas for Future Phases

1. **Settings panel** — The `SettingsPanel` (963 lines) from lawyer-desktop includes provider config, skills root, allowed dirs, MCP health, sync settings, skill optimization. Most of these are now platform-side. A minimal desktop settings panel (Gateway URL, theme, allowed directories, auto-update channel) can be included in Phase 94 or deferred. The full SettingsPanel is NOT ported as-is.

2. **SkillRefinementPanel** — 390 lines, skill optimization admin UI. This is platform-side now. Not ported to desktop.

3. **AgentTracePanel in production** — 799 lines, developer-only trace viewer. Available in ui-core but gated behind a dev flag. Not shown to end users.

4. **CI build matrix** — GitHub Actions matrix for Windows + macOS cross-platform builds. Deferred for V3 (local builds sufficient for ≤50 lawyers). Can be added post-V3.

5. **Code signing + notarization** — Windows code signing certificate and macOS notarization. Required for public distribution, optional for self-hosted single-firm. Pre-production step.

6. **Tauri mobile** — Tauri 2 mobile (Android/iOS) is V4 per PROJECT.md decision.

7. **Local file server** — A Tauri command that serves local files over HTTP so the Gateway can fetch them directly. Currently, the desktop app uploads files via `POST /v1/uploads`. A local file server could be more efficient for large files. Deferred.

8. **Workspace FTS5 → Gateway search integration** — Currently FTS5 results are uploaded as attachments. A more integrated approach would let the platform query the desktop's FTS5 index via a local API. Deferred — the attachment approach is simpler and sufficient.

9. **Offline event replay** — Full offline event replay from cached events (reconstruct streaming state). Currently, offline mode shows cached message text only. Full replay could provide a richer offline experience. Deferred.

10. **Multi-window support** — Tauri multi-window (e.g., pop-out document preview in a separate window). Not needed for V3. Single window is sufficient.

11. **System tray** — System tray icon with quick actions (new session, open recent). Deferred — not a V3 requirement.

12. **Global keyboard shortcuts** — Lawyer-desktop has some shortcuts (Ctrl+Shift+O for skill optimization panel). Desktop-specific shortcuts can be added but are not a V3 requirement.

</deferred>
