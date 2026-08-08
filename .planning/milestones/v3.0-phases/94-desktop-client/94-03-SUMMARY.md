# Phase 94-03 Summary: Wave 2 — invoke() Migration Verification, SettingsPanel, AppUpdateBanner, Auto-Update Wiring

**Date:** 2026-08-09
**Phase:** 94 (Desktop Client)
**Plan:** 94-03 (Wave 2 — invoke() migration verification, SettingsPanel, AppUpdateBanner, auto-update wiring)
**Status:** ✅ Complete
**Commits:** `dfaed30` → `dfdc787` → `503c7f3` → `948efca`

## What Was Built

Wave 2 completion of the desktop client verifies the invoke() migration is structurally complete (42 agent calls → Gateway HTTP/SSE, 0 remaining), implements the reduced desktop SettingsPanel with 4 tabs (workspace, auto-update, file access, about), ports the AppUpdateBanner with 5 states and download progress bar, and audits the Tauri command surface (21 desktop-only commands, zero agent logic).

### Task 94-03-01: invoke() Migration Verification (commit `dfaed30`)

**Files Created:**
- `apps/desktop/tests/invoke-migration.test.ts` — Static analysis test with 5 test cases:
  - `no agent invoke() calls in frontend source — only desktop-specific allowlist`: Scans all .ts/.tsx files for `invoke("...")` calls, asserts every call is in the 21-command desktop allowlist
  - `no removed invoke() commands present`: Asserts 46 removed agent/session/message/skill/document/sync commands do NOT appear
  - `Gateway HTTP equivalents are wired`: Asserts `gateway.createRun`, `gateway.createSession`, `gateway.listSessions`, `gateway.submitElicitation`, `gateway.submitFeedback`, `gateway.getArtifact`, `gateway.cancelRun` are all present
  - `SSE event stream is used (not Tauri events)`: Asserts `createEventStream`/`useEventStream` is used, and removed Tauri event listeners (`chat-stream`, `agent-trace`, `law-update-alert`, `skills-updated`, `skillopt-progress`) are absent
  - `only desktop-specific Tauri event listeners remain`: Asserts the only `listen()` calls are for `workspace-index-progress`

### Task 94-03-02: Reduced SettingsPanel (commit `dfdc787`)

**Files Created:**
- `apps/desktop/src/components/SettingsPanel.tsx` — Modal overlay with 4 tabs:
  - 工作区 (Workspace): workspace path selector, FTS5 index status, reindex button
  - 自动更新 (Auto-Update): update channel radio (stable/beta), auto-check toggle, version display, Gateway URL, manual check button
  - 文件访问 (File Access): allowed directories list with add/remove, native directory picker
  - 关于 (About): brand seal, brand name, version/build/platform info, legal disclaimer
  - `role="dialog"`, `aria-modal="true"`, `aria-label="设置"`, close on Escape + overlay click
- `apps/desktop/src-tauri/src/commands/desktop.rs` — 2 Tauri commands:
  - `get_app_setting(key)`: Read from `{app_data_dir}/app_settings.json`
  - `set_app_setting(key, value)`: Write to `{app_data_dir}/app_settings.json`
  - Uses `Mutex<AppSettings>` for thread-safe concurrent access
- `apps/desktop/tests/settings-panel.test.tsx` — 7 test cases:
  - Renders 4 tabs, closes on Escape, closes on overlay click, workspace tab shows index status, file access tab lists allowed dirs, about tab shows version + disclaimer, no provider/skills/MCP/sync tabs

**Files Updated:**
- `apps/desktop/src/desktop-shell.css` — Added settings panel styles (`.settings-overlay`, `.settings-panel`, `.settings-header`, `.close-btn`, `.settings-tabs`, `.tab`, `.settings-content`, `.form-group`, `.btn-primary`, `.btn-secondary`, `.toggle-switch`, `.settings-divider`, `.test-result`, workspace/auto-update/file-access/about tab styles) — all using `var(--*)` tokens
- `apps/desktop/src/App.tsx` — Wired `<SettingsPanel open={settingsOpen()} onClose={...} />` replacing the deferred placeholder
- `apps/desktop/src-tauri/src/commands/mod.rs` — Added `pub mod desktop;`
- `apps/desktop/src-tauri/src/lib.rs` — Added `AppSettings` state management + `get_app_setting`, `set_app_setting` to `generate_handler![]`
- `apps/desktop/tests/invoke-migration.test.ts` — Added `get_app_setting`, `set_app_setting` to desktop allowlist
- `apps/desktop/tsconfig.json` — Added `"node"` to types array (for `node:fs`/`node:path` in tests)
- `apps/desktop/package.json` — Added `@types/node` devDependency

### Task 94-03-03: AppUpdateBanner (commit `503c7f3`)

**Files Created:**
- `apps/desktop/src/components/AppUpdateBanner.tsx` — 5-state auto-update banner:
  - `idle`: banner hidden (no update available)
  - `available`: `✨ 发现新版本 {version}` + "下载并安装" button + × dismiss
  - `downloading`: "下载中…" + progress bar (4px height, `--accent` fill) + percentage
  - `error`: `⚠ 下载失败：{error}` + retry-enabled "下载并安装" button
  - `restart-prompt`: `✓ 更新已就绪 — 重启应用以完成安装` + "立即重启" button
  - `dismissed`: banner hidden, update deferred
  - `role="status"`, `aria-live="polite"`
  - Uses `desktopAppInfoAdapter` (not direct Tauri imports) — keeps it testable
- `apps/desktop/tests/app-update.test.tsx` — 6 test cases:
  - Hidden when no update, shows available state, dismiss hides, download triggers installUpdate, shows error on failure, shows restart prompt after success

**Files Updated:**
- `apps/desktop/src/adapters/desktopAppInfoAdapter.ts` — Enhanced `installUpdate` with progress callback (`InstallProgressCallback`), separated `relaunchApp()` as standalone export (banner calls it for restart prompt, not inside installUpdate)
- `apps/desktop/src/desktop-shell.css` — Added AppUpdateBanner styles (`.app-update-banner`, `.app-update-version`, `.app-update-install-btn`, `.app-update-dismiss`, `.app-update-progress`, `.app-update-progress-bar`, `.app-update-progress-fill`, `.app-update-progress-pct`, `.app-update-error`, `.app-update-restart`) — all using `var(--*)` tokens
- `apps/desktop/src/App.tsx` — Added `<AppUpdateBanner />` below TitleBar, above OfflineBanner

### Task 94-03-04: Command Surface Audit (commit `948efca`)

**Files Created:**
- `apps/desktop/tests/command-surface.test.ts` — 6 test cases:
  - `Tauri command surface is minimal (≤ 21 commands)`: Parses `generate_handler![]` in lib.rs, asserts exactly 21 commands (7 file + 3 workspace + 9 offline cache + 2 settings)
  - `no agent logic modules in Rust source`: Asserts `llm/`, `skills/`, `mcp/`, `skill_opt/`, `sync/`, `citations/`, `law_library/`, `documents/` directories do NOT exist in `src-tauri/src/`
  - `no LLM provider code in Rust`: Asserts `reqwest` and `aes-gcm` are NOT in Cargo.toml
  - `no MCP bridge plugin`: Asserts `tauri-plugin-mcp-bridge` is NOT in Cargo.toml
  - `desktop and web share same Gateway client`: Both import `PlatformApiClient` from `@inkstatute/platform-sdk-ts`
  - `desktop and web share same ui-core`: Both depend on `@inkstatute/ui-core` with `workspace:*`

## Key Architectural Decisions

1. **invoke() migration was structural from 94-01** — The Tauri shell was created with only desktop-specific commands from the start. No agent commands were ever registered. 94-03 verifies this with static analysis tests.
2. **SettingsPanel has 4 tabs, not 6** — Removed LLM provider, skills-root, MCP-health, and sync configuration sections (now platform-side). Added workspace (FTS5) and auto-update sections.
3. **AppUpdateBanner uses adapter, not direct Tauri imports** — The banner imports `desktopAppInfoAdapter` and `relaunchApp` from the adapter module, not `@tauri-apps/plugin-updater` or `@tauri-apps/plugin-process` directly. This keeps the component testable.
4. **installUpdate separated from relaunch** — `installUpdate()` downloads and installs but does NOT call `relaunch()`. The banner shows a restart prompt, and the user clicks "立即重启" to call `relaunchApp()` separately.
5. **App settings use JSON file, not SQLite** — Desktop-specific app settings (update channel, auto-check flag) are stored in `{app_data_dir}/app_settings.json`. The offline-cache SQLite DB is for session data only.
6. **21 Tauri commands total** — 7 file + 3 workspace + 9 offline cache + 2 settings = 21. All desktop-specific, zero agent logic.

## Verification Results

- **tsc --noEmit**: ✅ Pass (0 errors)
- **vitest run**: ✅ 71 tests pass (12 test files: scaffold, adapters, auth, tracer, invoke-migration, settings-panel, app-update, workspace-sse, offline-cache, fts5-search, wave2-integration, command-surface)
- **Python gate tests (desktop)**: ✅ 22 tests pass
- **Full gate suite (34 gates)**: ✅ All green
- **invoke() migration**: ✅ 0 agent calls remain (verified by static analysis)
- **Command surface**: ✅ 21 desktop-only commands, zero agent logic
- **No excluded Cargo deps**: ✅ No reqwest, aes-gcm, tauri-plugin-mcp-bridge

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| invoke-migration.test.ts exists with all 5 test cases passing | ✅ |
| npx vitest run exits 0 | ✅ |
| grep for removed invoke() commands returns zero results | ✅ |
| grep for removed Tauri event listeners returns zero results | ✅ |
| grep for Gateway HTTP equivalents returns results | ✅ |
| grep for createEventStream/useEventStream returns results | ✅ |
| Only desktop-specific invoke() calls in allowlist | ✅ |
| SettingsPanel.tsx exists with 4 tabs | ✅ |
| No provider/skills/MCP/sync tabs in SettingsPanel | ✅ |
| desktop-shell.css includes settings panel styles using var(--*) | ✅ |
| App.tsx renders SettingsPanel when settingsOpen() is true | ✅ |
| desktop.rs exists with get_app_setting, set_app_setting | ✅ |
| lib.rs includes get_app_setting, set_app_setting in generate_handler![] | ✅ |
| settings-panel.test.tsx exists with all 7 test cases passing | ✅ |
| tsc --noEmit exits 0 | ✅ |
| AppUpdateBanner.tsx exists with 5 states | ✅ |
| All state copy present (发现新版本, 下载并安装, 下载中, 下载失败, 更新已就绪, 立即重启) | ✅ |
| AppUpdateBanner styles in desktop-shell.css using var(--*) | ✅ |
| App.tsx renders AppUpdateBanner below TitleBar | ✅ |
| No direct @tauri-apps/plugin-* imports in AppUpdateBanner | ✅ |
| app-update.test.tsx exists with all 6 test cases passing | ✅ |
| command-surface.test.ts exists with all 6 test cases passing | ✅ |
| Total command count ≤ 21 | ✅ (exactly 21) |
| No agent modules in src-tauri/src/ | ✅ |
| No tauri-plugin-mcp-bridge in Cargo.toml | ✅ |
| No reqwest/aes-gcm in Cargo.toml | ✅ |
| Desktop and web share PlatformApiClient | ✅ |
| Desktop and web share @inkstatute/ui-core workspace:* | ✅ |
| python scripts/run_v2_gates.py exits 0 | ✅ |

## Self-Check: PASSED

- [x] All 4 tasks executed and committed (4 commits)
- [x] All acceptance_criteria PASS
- [x] invoke() migration verified (0 agent calls remain)
- [x] SettingsPanel ported (reduced 4 tabs)
- [x] AppUpdateBanner ported (5 states with progress bar)
- [x] Tauri command surface audited (21 commands, zero agent logic)
- [x] 71 vitest tests pass (12 test files)
- [x] 22 Python gate tests pass
- [x] tsc compiles (0 errors)
- [x] 34 gates green
- [x] No direct Tauri plugin imports in AppUpdateBanner (uses adapter)
- [x] Desktop and web share same Gateway client + ui-core
