# Phase 94-02 Summary: Wave 2 — Workspace SSE, Offline Cache, FTS5 Search

**Date:** 2026-08-09
**Phase:** 94 (Desktop Client)
**Plan:** 94-02 (Wave 2 — Workspace SSE wiring, offline SQLite cache, FTS5 workspace search panel)
**Status:** ✅ Complete
**Commits:** `4bef097` → `3e9874c` → `4fe5928` → `5087120` → `d8da4e4`

## What Was Built

Wave 2 of the desktop client wires the `WorkspacePage` to live Gateway SSE streaming, implements an offline SQLite cache for read-only history, and ports the complete FTS5 workspace search index from `lawyer-desktop`. This proves three critical success criteria: (1) the desktop app sends tasks to Gateway and sees streaming replies via SSE, (2) offline mode shows cached history with a clear "需要联网" prompt, and (3) the FTS5 workspace index works as a desktop-specific enhancement with search results attachable as references.

### Task 94-02-01: SSE Wiring (commit `4bef097`)

**Files Created:**
- `apps/desktop/src/hooks/useEventStream.ts` — SSE event stream hook (adapted from web)
- `apps/desktop/src/lib/runBuilder.ts` — builds `POST /v1/runs` request body
- `apps/desktop/src/lib/upload.ts` — file upload to Gateway `POST /v1/uploads`
- `apps/desktop/src/contexts/SessionContext.tsx` — SessionProvider + useSession() with sendMessage, submitClarification, submitFeedback, cancelRun

**Files Updated:**
- `apps/desktop/src/pages/WorkspacePage.tsx` — replaced tracer with full ChatPanel + DocPreview + CitationPanel wiring, Tauri drag-drop → context refs, SSE indicators
- `apps/desktop/tests/workspace-sse.test.tsx` — 4 test cases (ChatPanel rendering, sendMessage → SSE, artifact download, drag-drop)

### Task 94-02-02: Offline SQLite Cache (commit `3e9874c`)

**Files Created:**
- `apps/desktop/src-tauri/migrations/002_offline_cache.sql` — cached_sessions, cached_runs, cached_events, cached_artifacts tables
- `apps/desktop/src-tauri/src/commands/offline_cache.rs` — 9 Tauri commands for cache CRUD
- `apps/desktop/src/contexts/ConnectionContext.tsx` — ConnectionProvider with Gateway health probe + heartbeat (30s online, 10s offline)
- `apps/desktop/src/components/OfflineBanner.tsx` — offline banner with "需要联网" prompt
- `apps/desktop/src/lib/offlineCache.ts` — TypeScript wrappers for all 9 cache commands
- `apps/desktop/tests/offline-cache.test.tsx` — 6 test cases (connection states, banner visibility, cache wrapper)

**Files Updated:**
- `apps/desktop/src-tauri/Cargo.toml` — added tauri-plugin-sql, sqlx (sqlite + runtime-tokio)
- `apps/desktop/src-tauri/src/lib.rs` — registered tauri_plugin_sql + 9 cache commands
- `apps/desktop/src-tauri/src/commands/mod.rs` — added offline_cache module
- `apps/desktop/src-tauri/capabilities/default.json` — SQL permissions
- `apps/desktop/src/contexts/ConversationContext.tsx` — online/offline conversation loading
- `apps/desktop/src/App.tsx` — ConnectionProvider + OfflineBanner
- `apps/desktop/src/pages/WorkspacePage.tsx` — offline composer disable hint
- `apps/desktop/src/desktop-shell.css` — offline banner + workspace layout styles
- `apps/desktop/tests/test_desktop.py` — updated gate tests (sqlx allowed, 9 cache commands, ConnectionProvider/OfflineBanner assertions)

### Task 94-02-03: FTS5 Workspace Index Port (commit `4fe5928`)

**Files Created (ported verbatim from lawyer-desktop):**
- `apps/desktop/src-tauri/src/workspace/mod.rs` — module structure
- `apps/desktop/src-tauri/src/workspace/scanner.rs` — walkdir traversal, SHA-256 hashing, ignore dirs, allow extensions (222 lines)
- `apps/desktop/src-tauri/src/workspace/parser.rs` — PDF (pdf-extract), DOCX (docx-rs), text (encoding_rs GB18030 fallback) extraction (256 lines)
- `apps/desktop/src-tauri/src/workspace/chunker.rs` — markdown heading-aware chunking, 3500 char chunks with 500 overlap (190 lines)
- `apps/desktop/src-tauri/src/workspace/index_store.rs` — SQLite FTS5 store with trigram tokenizer, bm25 ranking, LIKE fallback (577 lines)
- `apps/desktop/src-tauri/src/workspace/manager.rs` — bind_and_index orchestrator, incremental indexing, parser version tracking (480 lines)
- `apps/desktop/src-tauri/src/commands/workspace.rs` — 3 Tauri commands: bind_workspace, get_workspace_index_status, search_workspace
- `apps/desktop/src-tauri/migrations/003_workspace_index.sql` — FTS5 schema with external content table + triggers

**Files Updated:**
- `apps/desktop/src-tauri/Cargo.toml` — added pdf-extract, docx-rs
- `apps/desktop/src-tauri/src/lib.rs` — added mod workspace, set_app_data_dir, 3 workspace commands
- `apps/desktop/src-tauri/src/commands/mod.rs` — added workspace module
- `apps/desktop/tests/test_desktop.py` — pdf-extract/docx-rs allowed, 3 workspace commands, FTS5 file existence test

### Task 94-02-04: FTS5SearchPanel + Workspace Adapter (commit `5087120`)

**Files Created:**
- `apps/desktop/src/components/FTS5SearchPanel.tsx` — search panel with debounced 300ms input, result rows with score/snippet, "作为附件引用" attach button, reindex button, index status display
- `apps/desktop/tests/fts5-search.test.tsx` — 6 test cases (rendering, debounced search, attach callback, reindex, adapter FTS5 integration)

**Files Updated:**
- `apps/desktop/src/adapters/desktopWorkspaceAdapter.ts` — replaced tracer `return []` with real FTS5 search_workspace invoke + list_directory fallback, workspacePath signal
- `apps/desktop/src/pages/WorkspacePage.tsx` — FTS5 search toggle button + overlay panel, onAttachRef → addContextRef
- `apps/desktop/src/desktop-shell.css` — FTS5 panel styles (fts-panel, fts-input, fts-result, fts-attach, fts-index-status, fts-reindex, ws-fts-toggle, ws-fts-overlay)

### Task 94-02-05: Wave 2 Verification (commit `d8da4e4`)

**Files Created:**
- `apps/desktop/tests/wave2-integration.test.tsx` — 7 integration test cases (online SSE streaming, offline composer disable, cached sessions, cached artifacts, FTS5 attach, online→offline transition, offline→online transition)

**Files Updated:**
- `apps/desktop/src/contexts/ConnectionContext.tsx` — exported ConnectionContext for test access

## Key Architectural Decisions

1. **SSE wiring reuses web pattern** — SessionContext + useEventStream + EventStreamStore from ui-core, adapted for signal-based conversation ID (no router params)
2. **Two separate SQLite databases** — `offline-cache.db` for session/run/event metadata, per-root `index.db` for FTS5 workspace index (keeps concerns isolated)
3. **FTS5 index is a verbatim port** — scanner/parser/chunker/index_store/manager ported from lawyer-desktop with all test cases as golden fixtures
4. **ConnectionContext is the online/offline source** — minimal signal ("checking" | "online" | "offline"), probes Gateway on launch, heartbeat re-probes
5. **Offline mode is read-only** — no data written locally that conflicts with Gateway on reconnection; composer disabled with "需要联网才能发送新任务"
6. **FTS5 search results attachable as context refs** — "作为附件引用" button creates ContextRefPayload with kind="file", added to pending refs in composer
7. **Dynamic Tauri imports** — All `@tauri-apps/*` imports remain dynamic to avoid breaking vitest/jsdom
8. **Gate test evolved** — sqlx, pdf-extract, docx-rs removed from excluded deps; command count test now covers 7 file + 9 cache + 3 workspace commands

## Verification Results

- **tsc --noEmit**: ✅ Pass (0 errors)
- **vitest run**: ✅ 47 tests pass (8 test files: scaffold, adapters, auth, tracer, workspace-sse, offline-cache, fts5-search, wave2-integration)
- **Python gate tests**: ✅ 22 tests pass (desktop gate)
- **cargo check**: ✅ Pass (0 errors, 2 warnings for unused re-exports)
- **vite build**: ✅ Pass (283KB main bundle, 533ms)
- **Full gate suite (34 gates)**: ✅ All green
- **No agent invoke() calls**: ✅ Zero results for `invoke.*(send_message|create_conversation|classify_agent_mode)`

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| useEventStream.ts with state(), isStreaming(), error(), reconnect() | ✅ |
| runBuilder.ts with buildRunBody() | ✅ |
| upload.ts with uploadFile() | ✅ |
| SessionContext.tsx with SessionProvider, useSession, sendMessage, etc. | ✅ |
| WorkspacePage wires ChatPanel, DocPreview, CitationPanel | ✅ |
| No @solidjs/router in src/ | ✅ |
| workspace-sse.test.tsx with 4 test cases | ✅ |
| Cargo.toml includes tauri-plugin-sql and sqlx | ✅ |
| 002_offline_cache.sql with 4 tables | ✅ |
| offline_cache.rs with 9 Tauri commands | ✅ |
| ConnectionContext.tsx with health probe + heartbeat | ✅ |
| OfflineBanner.tsx with offline banner text | ✅ |
| offlineCache.ts with wrappers for 9 commands | ✅ |
| ConversationContext loads from cache when offline | ✅ |
| App.tsx wraps with ConnectionProvider + OfflineBanner | ✅ |
| offline-cache.test.tsx with 6 test cases | ✅ |
| Cargo.toml includes pdf-extract and docx-rs | ✅ |
| 003_workspace_index.sql with FTS5 trigram + triggers | ✅ |
| workspace/scanner.rs, parser.rs, chunker.rs, index_store.rs, manager.rs | ✅ |
| commands/workspace.rs with 3 Tauri commands | ✅ |
| desktopWorkspaceAdapter.ts calls search_workspace (no longer empty) | ✅ |
| No law_library in src-tauri/src/ | ✅ |
| cargo check exits 0 | ✅ |
| FTS5SearchPanel.tsx with search, results, attach, reindex | ✅ |
| desktop-shell.css with FTS5 panel styles using var(--*) | ✅ |
| WorkspacePage wires drag-drop to context refs + FTS5 toggle | ✅ |
| fts5-search.test.tsx with 6 test cases | ✅ |
| wave2-integration.test.tsx with 7 test cases | ✅ |
| npx vitest run exits 0 | ✅ |
| npx tsc --noEmit exits 0 | ✅ |
| npx vite build succeeds | ✅ |
| python scripts/run_v2_gates.py exits 0 | ✅ |
| No agent invoke() calls in src/ | ✅ |

## Self-Check: PASSED

- [x] All 5 tasks executed and committed (5 commits)
- [x] All acceptance_criteria PASS
- [x] SSE streaming wired (SessionContext + useEventStream + ChatPanel)
- [x] Offline cache implemented (9 Tauri commands + ConnectionContext + OfflineBanner)
- [x] FTS5 workspace index ported (scanner/parser/chunker/index_store/manager + 3 commands)
- [x] FTS5SearchPanel component with search + attach + reindex
- [x] 47 vitest tests pass (8 test files)
- [x] 22 Python gate tests pass
- [x] cargo check passes
- [x] vite build succeeds
- [x] 34 gates green
- [x] Zero agent invoke() calls
