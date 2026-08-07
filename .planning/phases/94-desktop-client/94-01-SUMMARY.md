# Phase 94-01 Summary: Desktop Client Tracer

**Date:** 2026-08-08
**Phase:** 94 (Desktop Client)
**Plan:** 94-01 (Tracer: scaffold + Tauri shell + adapters + app shell)
**Status:** ✅ Complete
**Commits:** `fc7ba75` → `4f6902b` → `5d64a4e` → `6aee962` → `7d3484d` → `005afbf`

## What Was Built

A complete `apps/desktop` application scaffold with Tauri 2 shell, 6 Tauri-backed adapters, Gateway-connected contexts, and a signal-based app shell rendering TitleBar + ConversationDrawer. This is a tracer slice proving the desktop app builds, compiles, and passes all gates.

### Files Created (28 files)

**Scaffold:**
- `apps/desktop/package.json` — @inkstatute/desktop with workspace:* deps, Tauri plugins, no @solidjs/router
- `apps/desktop/tsconfig.json` — strict, solid-js, no baseUrl (TS 7.0.2 compat)
- `apps/desktop/vite.config.ts` — Vite + solid, port 1420, safari16 build target
- `apps/desktop/index.html` — root HTML
- `apps/desktop/src/main.tsx` — entry, renders App with theme CSS
- `apps/desktop/src/desktop-shell.css` — fixed-window layout, no responsive media queries
- `apps/desktop/src/shims/debug.ts` — solid-markdown peer dep shim
- `apps/desktop/src/shims/extend.ts` — solid-markdown peer dep shim

**Tauri 2 Shell (src-tauri/):**
- `tauri.conf.json` — Tauri 2 config, decorations:false, dragDropEnabled, CSP
- `Cargo.toml` — tauri 2 + plugins (fs, dialog, updater, process, opener), NO excluded deps
- `build.rs` — tauri_build
- `src/main.rs` — entry point
- `src/lib.rs` — plugin registration + 7 invoke_handler commands
- `src/commands/files.rs` — 7 desktop-only commands (read_file_content, list_directory, prepare_attachment, classify_dropped_paths, grant_path_access, get_allowed_file_dirs, set_allowed_file_dirs)
- `src/security/path_sandbox.rs` — PathSandbox with allowlist validation, parent-dir traversal rejection
- `capabilities/default.json` — Tauri 2 capabilities for main window
- `icons/` — placeholder RGBA PNG/ICO/ICNS icons

**Desktop Adapters (src/adapters/):**
- `desktopFileAdapter.ts` — Tauri native file dialog (open/save)
- `desktopDropAdapter.ts` — Tauri drag-drop path classification + classifyTauriPaths()
- `desktopAppInfoAdapter.ts` — Tauri app version + auto-update
- `desktopWorkspaceAdapter.ts` — workspace file listing (tracer: empty, FTS5 deferred to 94-02)
- `desktopDocumentParser.ts` — legal document parsing via ui-core utilities
- `desktopWindowAdapter.ts` — Tauri native window controls (minimize/maximize/close/drag)
- `desktopAdapters.ts` — barrel assembling AdapterContextValue with `window` defined

**Contexts (src/contexts/):**
- `AuthContext.tsx` — session management, login/logout, Gateway probe on mount
- `ConversationContext.tsx` — conversation list, createConversation, refreshConversations

**Config:**
- `src/config/gateway.ts` — PlatformApiClient with baseUrl http://127.0.0.1:8000

**Pages:**
- `src/pages/HomePage.tsx` — ui-core HomePage + recent conversations + Tauri drag-drop wiring
- `src/pages/WorkspacePage.tsx` — tracer placeholder for ChatPanel (Plan 94-02)

**App Shell:**
- `src/App.tsx` — AuthProvider → AdapterContext → ConversationProvider → signal-based screen switching (home/workspace), TitleBar + ConversationDrawer, NO router

**Tests:**
- `tests/test_desktop.py` — 20 Python gate tests (scaffold, adapters, contexts, Tauri shell, no agent logic, no excluded deps, 7 commands)
- `tests/scaffold.test.ts` — 4 vitest tests (package.json structure)
- `tests/adapters.test.ts` — 12 vitest tests (all 6 adapters with Tauri mocks)
- `tests/auth-context.test.tsx` — 3 vitest tests (auth logic)
- `tests/tracer.test.tsx` — 5 vitest tests (full slice integration)
- `tests/setup.ts` — vitest setup
- `tests/__init__.py` — Python package init

**Gate System:**
- `scripts/run_v2_gates.py` — added `desktop` gate (additive, no existing gate modified)
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — gate count 33→34

## Key Architectural Decisions

1. **No @solidjs/router** — Signal-based screen switching (`createSignal<"home" | "workspace">`), matching lawyer-desktop architecture
2. **WindowAdapter IS provided** — KEY difference from web (web omits `window`, desktop provides Tauri-backed implementation)
3. **7 desktop-only Tauri commands** — All file/path operations; zero agent logic (no send_message, create_conversation, classify_agent_mode, etc.)
4. **No excluded Cargo deps** — No tauri-plugin-mcp-bridge, reqwest, aes-gcm, sqlx, pdf-extract, docx-rs
5. **Gateway cross-origin** — Desktop uses http://127.0.0.1:8000 directly (no Vite dev proxy, unlike web)
6. **Dynamic Tauri imports** — All `@tauri-apps/*` imports are dynamic to avoid breaking vitest/jsdom

## Verification Results

- **tsc --noEmit**: ✅ Pass (0 errors)
- **vitest run**: ✅ 24 tests pass (4 scaffold + 12 adapters + 3 auth + 5 tracer)
- **Python gate tests**: ✅ 20 tests pass
- **cargo check**: ✅ Pass (0 errors, 0 warnings)
- **vite build**: ✅ Pass (280 modules, 306ms)
- **Full gate suite (34 gates)**: ✅ All green
- **Gate count**: 33 → 34 (added `desktop` gate, additive only)

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| apps/desktop exists with Tauri 2 shell, ui-core, no router | ✅ |
| 7 desktop-only Tauri commands (file/path), zero agent logic | ✅ |
| No excluded Cargo deps (mcp-bridge, reqwest, aes-gcm, sqlx, etc.) | ✅ |
| 6 Tauri-backed adapters including WindowAdapter | ✅ |
| Gateway config with PlatformApiClient (cross-origin) | ✅ |
| AuthContext + ConversationContext | ✅ |
| App.tsx with signal-based screen switching, TitleBar, ConversationDrawer | ✅ |
| HomePage + WorkspacePage tracer | ✅ |
| Tauri drag-drop wiring (onDragDropEvent) | ✅ |
| desktop gate registered in run_v2_gates.py | ✅ |
| tsc compiles, vitest passes, cargo check passes, vite build passes | ✅ |
| All 34 gates green | ✅ |

## What's Next (Plan 94-02+)

- **94-02**: ChatPanel + SSE event stream wiring (full workspace page)
- **94-03**: Offline read-only mode (history + downloaded artifacts)
- **94-04**: FTS5 workspace index + attachment引用
- **94-05**: Full integration test + cross-platform build verification
