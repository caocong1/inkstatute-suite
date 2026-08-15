# Plan 125-03 Summary: Settings Panel + Workspace Shell

**Date:** 2026-08-16
**Status:** ✅ Complete (Task 5 manual check deferred — requires real engine + API key)
**Wave:** 3
**Depends on:** 125-02

## What was done

### Task 1: Credential commands (Rust)

New `commands/credentials.rs` with 6 Tauri commands:

| Command | Behavior |
|---|---|
| `list_providers` | Returns 9 `ProviderInfo` (id, display_name, env_var, has_key) |
| `get_active_provider` | Reads active provider id from `app_settings.json` (default: deepseek) |
| `set_active_provider` | Validates and stores provider id in `app_settings.json` |
| `set_provider_key` | Stores key in OS credential store (never logged, never returned) |
| `clear_provider_key` | Deletes key from OS credential store |
| `test_provider` | Verifies key exists, returns Chinese user-facing text |

**Security constraints honored:**
- No `get_provider_key` command — keys are write-only
- `set_provider_key` input never logged, no `println!`/`dbg!`
- Active provider stores only id, never the key
- 2 Rust unit tests: `list_providers_returns_nine`, `no_get_provider_key_command`

### Task 2: SettingsPanel port

New `services/settings.ts` — wrappers for credential/file commands.

`SettingsPanel.tsx` rewritten as V5 port from lawyer-desktop:
- **4 tabs:** LLM 模型 / 法律技能 / 文件访问 / 关于
- **Sync and MCP tabs deleted** (v5.0 has no sync; MCP is DSH-managed)
- LLM tab: provider dropdown, key status badge ("已配置"/"未配置"), password input, test/clear buttons
- Skills tab: placeholder for Phase 126
- Files tab: allowed directory list (reuses `files.rs` commands)
- About tab: app version, engine status, DSH version
- `SettingsPanel.css` ported from lawyer-desktop (LF-normalized, byte-identical)
- All interactions via `services/settings.ts` — no direct `invoke()`

### Task 3: Workspace shell

New `Workspace.tsx` — V5 workspace shell:
- Left: ui-core `ChatPanel` (driven by `SessionContext` RenderState)
- Right: ui-core `DocPreview` (driven by RenderState artifacts)
- Draggable splitter with persisted `--chat-w` CSS variable (localStorage)
- Solo mode when no artifact/citation present
- Keyboard-accessible splitter: `role="separator"`, `tabindex="0"`, arrow keys
- `prefers-reduced-motion` aware

`WorkspacePage.tsx` simplified to wrap `Workspace` in `SessionProvider`.

### Task 4: App routing and startup

`App.tsx` rewritten:
- Three views: HomePage / Workspace / SettingsPanel (modal overlay)
- Engine startup on mount: `engineStart()` → success: HomePage; failure: Chinese error + retry
- Missing API key → auto-opens settings panel
- TitleBar + ConversationDrawer (sidebar, data from history plane)
- Three-theme support via ui-core `useTheme()`
- Engine startup/error states with Chinese messaging

### Task 5: Manual check

**Deferred** — requires `bunx tauri dev` with a real engine assembly and API key. The 6 manual checks will be performed during Phase 127 integration testing.

## Verification

| Check | Result |
|---|---|
| `packages/ui-core` tsc + vitest | 186 tests pass |
| `apps/desktop` tsc | 0 errors |
| `apps/desktop` vitest | 36 tests pass (7 settings + 4 transport + 3 fts5 + 22 others) |
| `apps/desktop/src-tauri` cargo check | green |
| `apps/desktop/src-tauri` cargo test | 85 tests pass (5 ignored) |
| V5 gates | 2 passed, 0 failed |
| `event-reducer.ts` untouched | PASS |
| All 11 ui-core components untouched | PASS |
| `SettingsPanel.css` byte-identical to lawyer-desktop (LF) | PASS |
| `molv-tokens.css` identical to lawyer-desktop (LF) | PASS |
| No `get_provider_key` in `credentials.rs` | PASS |
| No direct `invoke` in components (except file commands in SettingsPanel via services) | PASS |
