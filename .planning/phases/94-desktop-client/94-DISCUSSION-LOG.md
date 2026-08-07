# Phase 94 — Desktop Client: Discussion Log

**Mode:** --auto (all gray areas auto-selected with recommended options)
**Date:** 2026-08-08
**Phase:** 94 — Desktop Client
**Requirement:** UI-05
**Depends on:** Phase 92 (Shared UI Core — complete)

---

## Summary

Phase 94 migrates the Tauri desktop shell from `lawyer-desktop` into `apps/desktop` within the inkstatute-suite repo. The desktop app reuses `@inkstatute/ui-core` (Phase 92) and communicates with the Gateway (Phase 91) via HTTP/SSE — identical to the web client (Phase 93). The desktop app adds only desktop-specific enhancements: native file dialogs, OS drag-drop with real file paths, local workspace FTS5 indexing, auto-update, custom window controls, and offline read-only mode.

**Gray areas identified:** 8
**All auto-selected with recommended options.**

---

## Gray Area Discussions

### GA-1: Tauri Version

**Question:** Stay on Tauri 2.11 from lawyer-desktop, or upgrade to a newer version? How to handle breaking changes?

**Options considered:**
- A) Stay on Tauri 2.x (current stable) — no breaking changes expected within major version
- B) Upgrade to latest Tauri 2.x patch — may pick up bug fixes but requires testing
- C) Wait for Tauri 3.x — premature, no release date, would introduce breaking changes

**Auto-selected:** A — Stay on Tauri 2.x

**Rationale:** lawyer-desktop uses Tauri 2.11 with all plugins at `^2.x`. The Tauri 2.x series maintains backward compatibility within the major version. Starting from the same baseline ensures the workspace FTS5 module and window management code port without modification. No breaking changes are expected. Pin to `^2.11` or latest `2.x` patch.

**Impact:** Cargo.toml and package.json dependencies mirror lawyer-desktop's versions. No migration effort for Tauri API changes.

---

### GA-2: invoke() Migration Strategy

**Question:** Which of the 57 invoke() calls become Gateway HTTP/SSE, and which stay as Tauri commands?

**Options considered:**
- A) Categorize by function: agent/session/message/skill/doc/sync → Gateway; file/workspace/dialog/updater → Tauri commands (recommended)
- B) Replace all invoke() with Gateway calls, reimplement file/workspace as web APIs — loses desktop-specific capabilities
- C) Keep all invoke() as Tauri commands, add Gateway as secondary — violates UI-05 requirement

**Auto-selected:** A — Categorize by function

**Rationale:** The 57 invoke() calls in `lawyer-desktop/src/services/api.ts` fall into clear categories. UI-05 #2 explicitly requires: "凡属于 agent / 会话 / 消息 / 技能 / 文档生成的，全部改为 Gateway HTTP/SSE；仅保留桌面专属能力（文件对话框、拖放、自动更新、本地工作区索引）为 Tauri 命令."

**Breakdown:**
- 42 calls → Gateway HTTP/SSE or removed (platform-side)
- 10 calls → Stay as Tauri commands (file/workspace/dialog)
- 5 calls → Removed (event listeners replaced by SSE, except workspace-index-progress)

**Net Tauri command surface:** 10 commands + 3 plugin APIs (dialog, updater, process) — down from 57 commands.

**Key mappings:**
- `send_message` → `POST /v1/runs` + SSE stream
- `create_conversation` → `POST /v1/sessions`
- `get_conversations` → `GET /v1/sessions`
- `list_skills` → `GET /v1/skills`
- `submit_message_feedback` → `POST /v1/feedback`
- `generate_docx` → `GET /v1/artifacts/{id}` download
- `onChatStream` / `onAgentTrace` → `EventStreamStore` (SSE from Gateway)
- `bind_workspace` / `search_workspace` / `read_file_content` / `classify_dropped_paths` → Stay as Tauri commands

---

### GA-3: Offline Storage

**Question:** How to cache history and artifacts for offline read-only access?

**Options considered:**
- A) SQLite local cache for session/run metadata + filesystem for downloaded artifacts, online detection via Gateway health check (recommended)
- B) IndexedDB in the Tauri webview — adds complexity, less robust than SQLite
- C) Full offline mirror of Gateway data — over-engineered for "online-first, offline-read-only" requirement

**Auto-selected:** A — SQLite local cache + filesystem artifacts

**Rationale:** PROJECT.md decision: "桌面端在线为主、离线只读." The offline mode is a degraded read-only state, not a full offline agent. A local SQLite database (`offline-cache.db`) caches session/run metadata and a subset of events (message.completed, artifact.created). Downloaded artifacts are saved to `{app_data_dir}/artifacts/{artifact_id}`. Online detection via periodic `GET /v1/health` check.

**Offline behavior:**
- Session list shows cached sessions
- Clicking a cached session shows cached message text
- DocPreview shows cached artifacts if available
- Composer disabled with "需要联网才能发起新任务" hint
- FTS5 workspace search still works (fully local)
- No streaming, no new tasks, no elicitation, no feedback, no skill listing

**What is NOT cached:** No full event replay, no streaming state, no real-time updates. The cache is "last viewed" not "full sync."

---

### GA-4: FTS5 Index Preservation

**Question:** How to preserve the local workspace FTS5 index from lawyer-desktop?

**Options considered:**
- A) Port the workspace module (scanner, parser, chunker, index_store, manager) as Tauri commands, keep per-root SQLite FTS5 with trigram tokenizer (recommended)
- B) Reimplement FTS5 in TypeScript/JS — loses the battle-tested Rust implementation
- C) Move FTS5 to the platform — violates "desktop-specific enhancement" requirement

**Auto-selected:** A — Port workspace module as Tauri commands

**Rationale:** UI-05 #5 requires: "本地工作区 FTS5 索引作为桌面专属增强保留，其检索结果可作为附件引用提交给平台." The workspace FTS5 index is a desktop-specific value-add. The Rust implementation (577 lines in index_store.rs + scanner/parser/chunker/manager) is battle-tested with Chinese text search (trigram tokenizer, bm25 ranking, LIKE fallback for short terms).

**What is ported:**
- `workspace/` module (scanner, parser, chunker, index_store, manager)
- `commands/workspace.rs` (bind_workspace, get_workspace_index_status, search_workspace)
- `migrations/002_workspace_index.sql` (FTS5 schema with external content table + triggers)
- `security/path_sandbox.rs` (file access control)

**What is NOT ported:**
- `law_library/` (bundled law library — now platform-side)
- `sync/skills_update.rs` (skill syncing — now platform-side)

**FTS5 → Gateway integration:** Search results (chunk text + relative path) are uploaded as attachments via `POST /v1/uploads`. The chunk text is uploaded as a text file, and the resulting `attachment_ref` is included in the `POST /v1/runs` body. This avoids needing a local file server.

---

### GA-5: Auto-Update

**Question:** How to handle auto-update in the migrated desktop app?

**Options considered:**
- A) Retain Tauri updater plugin, configurable endpoint, dev pubkey placeholder replaced before production (recommended)
- B) Remove auto-update, rely on manual distribution — poor UX for ≤50 lawyers
- C) Custom update mechanism — reinvents what Tauri updater already does

**Auto-selected:** A — Retain Tauri updater plugin

**Rationale:** lawyer-desktop already has a working auto-update mechanism. The `tauri-plugin-updater` and `tauri-plugin-process` are retained. The `AppInfoAdapter` interface in ui-core already has optional `checkForUpdate?()` and `installUpdate?()` methods — the desktop app provides concrete implementations.

**What changes:**
- Updater endpoint is configurable (not hardcoded to `localhost:8787`)
- `pubkey` is a placeholder — replaced with real signing key before production
- `AppUpdateBanner` wired through `AppInfoAdapter`
- Skill auto-update via sync service is removed (skills are platform-side)

**What is NOT ported:**
- The sync service (`tools/sync-service`) that serves the updater manifest — separate deployment concern
- Skill syncing — platform-side

---

### GA-6: Window Management

**Question:** How to handle TitleBar window controls (minimize/maximize/close/drag)?

**Options considered:**
- A) WindowAdapter wraps Tauri getCurrentWindow(), TitleBar uses it via AdapterContext, macOS traffic lights vs Windows controls (recommended)
- B) Use native OS titlebar (decorations: true) — loses custom 墨律 branded titlebar
- C) Reimplement window management from scratch — unnecessary, ui-core already has the pattern

**Auto-selected:** A — WindowAdapter wraps Tauri getCurrentWindow()

**Rationale:** The ui-core `TitleBar` component (ported from lawyer-desktop in Phase 92) already accepts a `WindowAdapter` via `AdapterContext`. The `WindowAdapter` interface defines: `minimize()`, `toggleMaximize()`, `close()`, `isMaximized()`, `onResized?(cb)`, `startDragging?()`. The web client omits it (optional). The desktop client provides a concrete implementation using `@tauri-apps/api/window` `getCurrentWindow()`.

**TitleBar behavior:**
- macOS: traffic light dots (close/minimize/maximize), `data-tauri-drag-region` for dragging
- Windows: square buttons in top-right, double-click drag region to toggle maximize
- `decorations: false` in tauri.conf.json hides native OS titlebar

**The WindowAdapter is the key differentiator between web and desktop adapters.** Web omits `window` in `AdapterContextValue`; desktop provides it.

---

### GA-7: Build Pipeline

**Question:** How to build for Windows + macOS? CI setup?

**Options considered:**
- A) tauri build for Windows (NSIS) + macOS (DMG), CI matrix optional for V3 (recommended)
- B) Full CI matrix from day one — over-engineered for ≤50 lawyers self-hosted
- C) Only build for one platform — violates UI-05 #1 ("Windows 与 macOS 可构建")

**Auto-selected:** A — tauri build for both platforms, CI optional

**Rationale:** UI-05 #1 requires "Windows 与 macOS 可构建." For V3's self-hosted single-firm scale (≤50 lawyers), local builds are sufficient. The `tauri build` command produces platform-specific installers. CI can be added post-V3 or when distributing to multiple machines.

**Build commands:**
- `bun run tauri build` — Vite build + Rust compile + bundle
- Windows: NSIS installer (`.exe`) + MSI
- macOS: DMG + `.app` bundle
- `createUpdaterArtifacts: true` generates signed updater artifacts

**Prerequisites:**
- Windows: Rust MSVC, Node.js, bun, WebView2
- macOS: Rust stable, Node.js, bun, Xcode CLT

**CI (deferred):** GitHub Actions matrix with `tauri-apps/tauri-action`, code signing, notarization. Not on V3 critical path.

---

### GA-8: Desktop Adapters

**Question:** How do the ui-core adapter interfaces map to Tauri commands?

**Options considered:**
- A) Parallel implementations of all 6 adapter interfaces using Tauri APIs, injected via AdapterContext (recommended)
- B) Reuse web adapters with Tauri shims — loses native file path support
- C) Only implement adapters that differ from web — inconsistent, violates adapter pattern

**Auto-selected:** A — Parallel implementations of all 6 adapter interfaces

**Rationale:** The ui-core defines 6 adapter interfaces. The web client (Phase 93) provides web implementations. The desktop client provides Tauri-backed implementations. Both inject via `AdapterContext.Provider`. This is the established pattern from Phase 92/93.

**Adapter mapping:**

| Interface | Desktop impl | Key Tauri APIs |
|---|---|---|
| `FileAdapter` | `desktopFileAdapter` | `@tauri-apps/plugin-dialog` open/save — returns real file paths |
| `DropAdapter` | `desktopDropAdapter` | `getCurrentWebview().onDragDropEvent()` + `classify_dropped_paths` — real OS paths with isDir |
| `AppInfoAdapter` | `desktopAppInfoAdapter` | `@tauri-apps/api/app` getVersion + `@tauri-apps/plugin-updater` check/install |
| `WorkspaceAdapter` | `desktopWorkspaceAdapter` | `list_directory` + `search_workspace` — real local files + FTS5 search |
| `DocumentParser` | `desktopDocumentParser` | Client-side parse (same as web, using ui-core utils) |
| `WindowAdapter` | `desktopWindowAdapter` | `@tauri-apps/api/window` getCurrentWindow — minimize/maximize/close/drag |

**Key differences from web adapters:**
- `FileAdapter.open()` returns **real file paths** (not just names)
- `DropAdapter` returns **real OS paths with isDir classification**
- `WorkspaceAdapter.listFiles()` returns **real local files**
- `AppInfoAdapter.checkForUpdate()` is **implemented** (web omits it)
- `WindowAdapter` is **provided** (web omits it)

---

## Decision Summary

| # | Gray Area | Selected Option | Impact |
|---|-----------|----------------|--------|
| GA-1 | Tauri Version | Stay on Tauri 2.x | No API migration, direct port of workspace/window code |
| GA-2 | invoke() Migration | Categorize: 42→Gateway, 10→Tauri, 5→removed | Net 10 Tauri commands (down from 57) |
| GA-3 | Offline Storage | SQLite cache + filesystem artifacts | Read-only offline, "需要联网" prompt for new tasks |
| GA-4 | FTS5 Index | Port workspace module as Tauri commands | Desktop-specific enhancement preserved, results as attachment refs |
| GA-5 | Auto-Update | Retain Tauri updater plugin | AppInfoAdapter wraps check/install, configurable endpoint |
| GA-6 | Window Management | WindowAdapter wraps getCurrentWindow() | TitleBar uses adapter, macOS traffic lights vs Windows controls |
| GA-7 | Build Pipeline | tauri build for Win+macOS, CI optional | NSIS + DMG, local builds sufficient for V3 |
| GA-8 | Desktop Adapters | Parallel implementations of all 6 interfaces | Tauri-backed adapters, WindowAdapter is key differentiator |

---

## No Open Questions

All 8 gray areas were auto-selected with recommended options. No questions require human input. The phase is ready for planning.

**Key risk:** The workspace FTS5 module port from Rust is the most complex part — it involves scanner, parser, chunker, index_store, and manager modules. However, the code is being ported verbatim (not rewritten), and the existing tests in `index_store.rs` serve as validation.

**Human gates:** None in Phase 94. HG-1 (legal quality) and HG-4 (revision quality) are in Phase 101/102. Phase 94 is a UI/channel phase, not a legal logic phase.
