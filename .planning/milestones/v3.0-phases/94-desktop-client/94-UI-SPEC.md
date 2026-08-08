---
phase: 94
slug: desktop-client
status: draft
created: 2026-08-08
inherits_from: 92-UI-SPEC.md
requirement: UI-05
---

# Phase 94 — UI Design Contract

> Desktop application shell and interaction contract for `apps/desktop`.
> This spec builds on the Phase 92 UI-SPEC (墨律 three-theme system, 17 components, adapter pattern).
> The desktop client is a **Tauri 2.11 shell** migrated from `lawyer-desktop`, using `@inkstatute/ui-core`
> for all chat/document/citation UI. The desktop app contains **zero chat UI code** — all rendering comes
> from ui-core. This spec covers the desktop shell, native window controls, offline mode, FTS5 local
> search, auto-update, and desktop-specific settings.
>
> **Key difference from web (Phase 93):** The desktop app provides a `WindowAdapter` (native window
> controls), a `WorkspaceAdapter` backed by local FTS5 (not Gateway HTTP), and desktop-only components
> (`AppUpdateBanner`, `SettingsPanel`, `FTS5SearchPanel`) that were deferred from Phase 92.

---

## Design System

### Inheritance from ui-core (Phase 92)

The desktop client inherits the complete 墨律 design system from `@inkstatute/ui-core`. No new themes, tokens, or component styles are created — the desktop app provides the **Tauri shell** (window management, native menus, offline detection, auto-update) and **desktop-specific adapter wiring** only.

| Property | Value | Source |
|----------|-------|--------|
| Component library | `@inkstatute/ui-core` — 17 components + 2 utils + 3 deferred (this phase) | Phase 92, `workspace:*` |
| Theme system | 墨律 three themes via `data-theme="a|b|c"` | `molv-tokens.css` + `molv-base.css` |
| Theme switcher | Pill toggle in TitleBar with 3 color dots | ui-core `TitleBar` component |
| Theme persistence | `localStorage["ml-theme"]`, values `"a"|"b"|"c"`, default `"a"` | ui-core `useTheme()` store |
| Font families | Noto Serif SC + Newsreader (serif), Noto Sans SC (sans), Spline Sans Mono (mono) | `molv-tokens.css` |
| Font loading | **Bundled locally** (no Google Fonts CDN) — Tauri embeds font files in app resources | Phase 94 specific |
| CSS strategy | CSS custom properties + `data-theme` attribute switching — no JS theme engine | Phase 92 §Design System |
| Icon library | Custom SVG icon set from ui-core `Icons.tsx` (30+ icons, stroke-based) | Phase 92 |
| Markdown | `solid-markdown` + `remark-gfm` (peer dependency, provided by desktop app) | Phase 92 |
| Syntax highlight | `highlight.js` (peer dependency, provided by desktop app) | Phase 92 |

### Theme Application in the Desktop App

The desktop app imports ui-core CSS as side-effect imports:

```typescript
// apps/desktop/src/index.tsx
import "@inkstatute/ui-core/themes";  // molv-tokens.css + molv-base.css
import "./desktop-shell.css";           // desktop-only layout + offline/update styles (this phase)
```

The `useTheme()` store from ui-core is used directly — no desktop-specific theme logic. On app mount, `useTheme()` reads `localStorage["ml-theme"]` and applies `document.documentElement.setAttribute("data-theme", variant)`. The `TitleBar` component renders the theme switcher pill.

**No desktop-specific theme tokens.** All CSS custom properties are defined in `molv-tokens.css`. The desktop app's `desktop-shell.css` only adds layout-specific CSS (offline banner, update banner, FTS5 search panel, native menu integration) — it references existing `var(--*)` tokens, never hardcodes colors.

### CSS Import Order

1. `molv-tokens.css` — `:root` + `[data-theme="a|b|c"]` custom properties (~80 tokens × 3 themes)
2. `molv-base.css` — base styles (app frame, titlebar, home, workspace, chat, doc, citation, toast)
3. Component CSS files — imported by ui-core components via `<style>` or CSS modules
4. `desktop-shell.css` — **desktop-only** styles (offline banner, update banner, FTS5 search, settings panel desktop overrides)

### Font Bundling (Desktop-Specific)

Unlike the web client (which loads fonts from Google CDN via `@import url(...)`), the desktop app bundles fonts locally for offline use:

- Font files placed in `apps/desktop/src-tauri/resources/fonts/`
- `@font-face` declarations in `desktop-shell.css` reference local paths (`src: url('./fonts/NotoSerifSC-Regular.otf')`)
- The `@import url(...)` Google Fonts line in `molv-tokens.css` is **suppressed** in the desktop build (via Vite env conditional or a desktop-specific CSS entry that overrides the import)
- This ensures the app renders correctly in offline mode without network font loading

---

## Desktop Layout

### Architecture Overview

The desktop app shell wraps the SolidJS app with context providers and a connection-state guard:

```
App.tsx
├── AdapterContext.Provider       (desktop adapter implementations — includes WindowAdapter)
├── ConnectionContext.Provider    (online/offline state, Gateway reachability)
└── <Show>                        (no router — single-window app with screen signal)
    ├── screen === "home"         → HomePage
    ├── screen === "workspace"    → WorkspacePage
    └── settingsOpen              → SettingsPanel (overlay)
```

**No router:** The desktop app does not use `@solidjs/router`. Navigation is managed via a `screen` signal (`"home" | "workspace"`) and a `currentConversationId` signal, matching the original `lawyer-desktop` architecture. This is intentional — desktop apps don't need URL-based routing.

**Connection guard:** A `ConnectionContext` probes Gateway reachability on app launch and on network change events (Tauri `plugin-network` or polling). When offline, the app enters read-only mode (see §Offline Mode UI).

### Desktop Layout (Fixed Window)

```
┌──────────────────────────────────────────────────────────────────┐
│ TitleBar (46px) — [● ● ●] brand · crumbs · theme switch · ⚙ ·   │
│                                              [—] [□] [×]         │  ← macOS: traffic lights left
│ AppUpdateBanner (conditional, 36px)                              │  ← shown when update available
├────────────┬─────────────────────────────────────────────────────┤
│            │                                                       │
│ Sidebar    │  Main Stage (flex: 1)                                 │
│ (280px)    │                                                       │
│            │  Home page:  centered, max-width 1040px               │
│ Conversation│  Workspace:  ChatPanel (500px) | Splitter | DocPreview│
│ Drawer     │               + CitationPanel (slide-in overlay)      │
│ (always    │                                                       │
│  open)     │                                                       │
│            │                                                       │
├────────────┴─────────────────────────────────────────────────────┤
│ (no footer)                                                       │
└──────────────────────────────────────────────────────────────────┘
```

**Desktop shell structure:**

```tsx
<div class="app">                          // position: fixed; inset: 0; flex column
  <TitleBar ... />                         // flex: 0 0 46px — includes window controls
  <Show when={updateAvailable()}>
    <AppUpdateBanner ... />                // flex: 0 0 auto — conditional
  </Show>
  <div class="stage">                      // flex: 1; min-height: 0; flex row
    <ConversationDrawer open={true} ... /> // sidebar: flex: 0 0 280px
    <div class="main-content">             // flex: 1; min-width: 0
      <Show when={screen() === "home"}>
        <HomePage ... />
      </Show>
      <Show when={screen() === "workspace"}>
        <WorkspacePage ... />
      </Show>
    </div>
  </div>
  <Show when={settingsOpen()}>
    <SettingsPanel ... />                  // overlay modal
  </Show>
</div>
```

### Differences from Web Client (Phase 93)

| Aspect | Web (Phase 93) | Desktop (Phase 94) |
|--------|----------------|---------------------|
| **Routing** | `@solidjs/router` with URL paths | Screen signal (`"home" \| "workspace"`), no router |
| **Window controls** | None — `WindowAdapter` not provided | Full — `WindowAdapter` provided (traffic lights / min/max/close) |
| **Login** | Login page at `/login` | No login page — session stored locally, auto-probe Gateway on launch |
| **Responsive** | 768px breakpoint (desktop + mobile) | No responsive — fixed window, desktop-only |
| **Font loading** | Google Fonts CDN (`@import url(...)`) | Bundled locally (offline-capable) |
| **ConversationDrawer** | Desktop: always open; Mobile: overlay | Always open (no mobile layout) |
| **Offline mode** | Not applicable (web requires network) | Read-only history + cached artifacts (see §Offline Mode UI) |
| **FTS5 search** | Not available (no local FS) | Local workspace FTS5 search panel (see §FTS5 Search UI) |
| **Auto-update** | Not applicable (web is always latest) | Tauri updater plugin (see §Auto-Update UI) |
| **Native menus** | Not applicable | Tauri native menu bar (see §Native Menus) |
| **Settings** | Not in Phase 93 scope | Desktop-specific SettingsPanel (see §Settings Panel) |
| **File operations** | Browser `<input type="file">` / download | Tauri `plugin-dialog` (native OS dialog) |

### Desktop Sidebar (ConversationDrawer)

- Width: `var(--sidebar-width, 280px)` — fixed left sidebar, always visible
- `position: relative` in the flex flow (not an overlay)
- Contains: conversation search, conversation list, new conversation button
- The ui-core `ConversationDrawer` component's `open` prop is `true` (always open on desktop)
- Border-right: `1px solid var(--line)` separates sidebar from main content
- **Offline behavior:** Conversation list is loaded from local SQLite cache (not Gateway). New conversation button is disabled with tooltip "需要联网才能发起新对话".

---

## TitleBar

### Purpose

Frameless window titlebar with native window controls, brand, breadcrumbs, theme switcher, and settings button. Uses the ui-core `TitleBar` component with `WindowAdapter` provided — this is the key difference from the web client where `WindowAdapter` is not provided.

### Window Controls

The desktop app provides a `WindowAdapter` implementation backed by Tauri's `@tauri-apps/api/window`:

```typescript
// apps/desktop/src/adapters/windowAdapter.ts
import { getCurrentWindow } from "@tauri-apps/api/window";

export const desktopWindowAdapter: WindowAdapter = {
  isTauri: () => true,
  minimize: () => getCurrentWindow().minimize(),
  toggleMaximize: () => getCurrentWindow().toggleMaximize(),
  close: () => getCurrentWindow().close(),
  startDragging: () => getCurrentWindow().startDragging(),
  isMaximized: () => getCurrentWindow().isMaximized(),
  onResized: (cb) => getCurrentWindow().onResized(cb),
};
```

### Platform-Specific Window Controls

#### macOS — Traffic Lights (Left Side)

```
┌──────────────────────────────────────────────────────────────────┐
│ [●close] [●minimize] [●maximize]  brand · crumbs · ● ● ●  ⚙     │
└──────────────────────────────────────────────────────────────────┘
```

- Three 12px round dots on the **left** side of the TitleBar
- Colors: close `#ff5f57`, minimize `#febc2e`, maximize `#28c840`
- `data-tauri-drag-region` on the crumbs area for native window dragging
- Double-click on drag region toggles maximize
- `onMouseDown` on non-drag area calls `startDragging()` for smooth drag

#### Windows — Caption Buttons (Right Side)

```
┌──────────────────────────────────────────────────────────────────┐
│  brand · crumbs · ● ● ●  ⚙                          [—] [□] [×] │
└──────────────────────────────────────────────────────────────────┘
```

- Three 46×46px buttons on the **right** side of the TitleBar
- SVG icons: minimize (horizontal line), maximize (square), restore (overlapping squares), close (X)
- Close button hover: `background: #e81123; color: #fff`
- Other buttons hover: `background: color-mix(in srgb, var(--ink) 8%, transparent)`
- Windows uses `-webkit-app-region: drag` on the TitleBar (OS-level drag, no IPC per frame)
- `.tb-no-drag` class on interactive elements (`-webkit-app-region: no-drag`)

### TitleBar Visual Contract

Inherited from Phase 92 §TitleBar (226 lines), with `WindowAdapter` active:

| Element | Style | Notes |
|---------|-------|-------|
| TitleBar container | `height: 46px; --titlebar-bg background; --titlebar-line bottom border` | `flex: 0 0 46px` |
| Traffic lights (macOS) | 3 dots, 12px round, 8px gap, left-aligned | `.tb-traffic` container |
| Window controls (Windows) | 3 buttons, 46×46px each, right-aligned | `.tb-win-ctrls` container |
| Brand seal | 26px round, `var(--seal-bg)`, `var(--seal-text)`, `--serif` 700 15px | `.seal` class |
| Brand name | `--serif` 700 15px, `.04em` spacing, `--ink` | `.brand-name` class |
| Brand small label | `--cite-font` 10px, `.16em` spacing, uppercase | `<small>` in brand-name |
| Crumbs | 12.5px `--ink-soft`, centered, 9px gap | `.tb-crumbs` — drag region |
| Theme switcher | Pill (`.theme-switch`), 999px radius, 3 color dots (18px, 5px gap) | Active dot: `--accent` border, `scale(1.05)` |
| Settings button | 30px square, 8px radius, `--muted` color, 17px SVG icon | `.tb-ibtn` — hover → `--accent-dim` bg |
| Conversation list button | 30px square, 8px radius, `--muted` color, grid icon | `.tb-conv-list` |

### TitleBar Props (Desktop)

```tsx
<TitleBar
  screen={screen()}                        // "home" | "workspace"
  onGoHome={() => setScreen("home")}
  onOpenConversations={() => { /* drawer always open on desktop */ }}
  onOpenSettings={() => setSettingsOpen(true)}
  windowAdapter={desktopWindowAdapter}     // ← provided (unlike web)
/>
```

---

## Offline Mode UI

### Purpose

The desktop app must function in offline mode — lawyers may work without internet. Offline mode provides read-only access to conversation history and cached artifacts. New tasks that require the Gateway are blocked with a clear prompt.

### Connection State Model

```typescript
type ConnectionState = "online" | "offline" | "checking";
```

- **`checking`**: App is probing Gateway reachability (on launch or network change)
- **`online`**: Gateway is reachable, full functionality available
- **`offline`**: Gateway is unreachable, read-only mode active

**Detection mechanism:**
- On app launch: `ConnectionContext` sends a lightweight `GET /v1/health` to Gateway
- On network change: Tauri network event listener triggers re-probe
- Periodic heartbeat: Every 30 seconds, probe Gateway (when in offline state, probe more frequently — every 10 seconds — to detect reconnection)
- On SSE disconnect: Mark as offline, attempt reconnection with backoff

### Offline Banner

When offline, a banner appears below the TitleBar (and below AppUpdateBanner if present):

```
┌──────────────────────────────────────────────────────────────────┐
│ ⚠ 当前处于离线模式 — 可查看历史对话与已下载文书，新任务需要联网    │
└──────────────────────────────────────────────────────────────────┘
```

**Visual contract:**
- Container: `.offline-banner` — `flex; align-items: center; gap: 10px; padding: 8px 16px`
- Background: `var(--doc-risk-bg)` (warning amber tint, matching risk note styling)
- Border-bottom: `1px solid var(--doc-risk-line)` (amber left-border color)
- Text: 13px `--doc-risk-ink` (amber-tinted text)
- Icon: warning triangle, 16px, `--amber` color
- `role="status"`, `aria-live="polite"`

### Offline Behavior by Area

| Area | Online Behavior | Offline Behavior |
|------|----------------|------------------|
| **Conversation list** | Loaded from Gateway `GET /v1/sessions` | Loaded from **local SQLite cache** (last-synced conversation metadata) |
| **Message history** | Loaded from Gateway `GET /v1/sessions/{id}/runs` | Loaded from **local SQLite cache** (persisted message events) |
| **Document preview** | Artifact downloaded from Gateway `GET /v1/artifacts/{id}` | **Cached artifacts** viewed from local filesystem (`~/.inkstatute/artifacts/`) |
| **Citation panel** | Citations from Gateway event stream | **Cached citations** from local SQLite (last-seen citation records) |
| **Composer** | Enabled, sends to Gateway `POST /v1/runs` | **Disabled** with "需要联网" hint |
| **New conversation** | Enabled, creates session via Gateway | **Disabled** with tooltip "需要联网才能发起新对话" |
| **File upload** | Enabled, uploads to Gateway `POST /v1/uploads` | **Disabled** — cannot upload without network |
| **Feedback submission** | Enabled, posts to Gateway `POST /v1/feedback` | **Queued locally** — submitted when connection restored (outbox pattern) |
| **FTS5 search** | Works (local index, no network needed) | **Works** (fully local, no Gateway dependency) |
| **Settings** | Full settings available | Settings available (auto-update check deferred) |
| **Theme switching** | Works (local) | Works (local) |

### Composer Offline State

When offline, the composer input is visually disabled with a hint:

```
┌──────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────┐  │
│  │  (disabled, dimmed)                            │  │
│  │  需要联网才能发送新任务                         │  │
│  └────────────────────────────────────────────────┘  │
│  (send button disabled, dimmed)                      │
└──────────────────────────────────────────────────────┘
```

**Visual contract:**
- Textarea: `opacity: 0.5; pointer-events: none`
- Placeholder text: `需要联网才能发送新任务`
- Send button: `opacity: 0.45; cursor: not-allowed` (same as disabled state from Phase 92)
- No drag-drop active state (attachments require network for upload)

### Reconnection UI

When transitioning from offline → online:
1. Offline banner fades out (`.3s opacity transition`)
2. Composer re-enables
3. New conversation button re-enables
4. Feedback outbox flushes automatically (queued feedback submissions sent to Gateway)
5. Toast: `已恢复连接` (bottom-center, `.25s` fade-in, auto-dismiss after 3s)

When transitioning from online → offline:
1. Offline banner slides in from top (`.3s` transition)
2. Composer disables with hint
3. If SSE was active, toast: `连接中断，正在重连…` (from Phase 92 copywriting)
4. SSE reconnection attempts continue in background

### Cached Artifact Viewing

Downloaded artifacts are cached locally for offline viewing:

- **Cache location:** `~/.inkstatute/artifacts/{artifact_id}/` (OS-specific app data directory)
- **Cache metadata:** Local SQLite table maps `artifact_id` → `local_path`, `conversation_id`, `downloaded_at`, `kind` (docx, trackchanges_docx, etc.)
- **Offline DocPreview:** When offline, `DocPreview` checks local cache first. If artifact is cached, it renders from local file. If not cached, shows empty state with message.
- **Cache indicator:** A small "已缓存" (cached) badge appears next to the version pill in DocPreview when viewing from local cache

**Cache badge visual:**
- 10.5px `--mono`, `--gold` text, `--accent-soft` bg, 6px radius, 3px×8px padding
- Similar to `.ver-pill` but with `--gold` color instead of `--accent`

---

## FTS5 Search UI

### Purpose

The desktop app retains `lawyer-desktop`'s local workspace FTS5 (SQLite Full-Text Search 5) index as a desktop-specific enhancement. Lawyers can search their local workspace files (contracts, case documents, legal references) and attach search results as references in their conversation with the agent.

### FTS5 Search Panel

A search panel accessible from the workspace, allowing full-text search across indexed local files:

```
┌──────────────────────────────────────────────────────┐
│  🔍 搜索工作区文件                                    │  ← search input
│  ┌──────────────────────────────────────────────────┐ │
│  │ 输入关键词…                                       │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  搜索结果 (5)                                         │  ← result count
│  ┌──────────────────────────────────────────────────┐ │
│  │ 📄 租赁合同_2026.docx                    0.92     │ │  ← result row
│  │ ...第四条 租金及支付方式...                        │ │  ← snippet with highlight
│  │ 📎 作为附件引用                                    │ │  ← attach button
│  ├──────────────────────────────────────────────────┤ │
│  │ 📄 案件分析_买卖纠纷.docx                0.87     │ │
│  │ ...第三条 交付义务...                              │ │
│  │ 📎 作为附件引用                                    │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  索引状态: 已索引 128 个文件 / 3,420 个条文块         │  ← index status
│  [重新索引]                                           │  ← reindex button
└──────────────────────────────────────────────────────┘
```

### FTS5 Search Panel Visual Contract

| Element | Style | Notes |
|---------|-------|-------|
| Panel container | `.fts-panel` — `--surface` bg, `--line` border, 12px radius, 16px padding | Slide-in from right or modal overlay |
| Search input | `.fts-input` — 100% width, 42px height, `--line` border, 10px radius, `--surface-2` bg, 14px | Focus → `--accent` border |
| Result count | `.fts-count` — 12.5px `--ink-soft`, 12px margin-top | Shows `搜索结果 ({count})` |
| Result row | `.fts-result` — `--surface` bg, `--line-soft` border-bottom, 12px padding | Hover → `--accent-dim` bg |
| Result file icon | 16px, `--accent` color, `--mono` font for filename | `📄` icon or custom SVG |
| Result filename | 13px `--ink`, `--mono` font, ellipsis overflow | Full path in `title` attribute |
| Result score | 11px `--mono`, `--muted`, right-aligned | FTS5 bm25 score, 2 decimal places |
| Result snippet | 12.5px `--ink-soft`, 1.6 line-height, `--serif` | Match text highlighted with `--accent-soft` bg |
| Attach button | `.fts-attach` — 12px, `--accent` border + bg, `--on-accent` text, 7px radius, 5px×10px padding | Hover → `--accent-2` |
| Index status | `.fts-index-status` — 11.5px `--muted`, `--mono` | Shows file count + chunk count |
| Reindex button | `.fts-reindex` — 12px, `--line` border, `--ink-soft` text, 7px radius, 4px×12px padding | Hover → `--accent` border + text |
| Empty state | `.fts-empty` — 13px `--muted`, centered, 24px padding | `输入关键词开始搜索工作区文件` |
| No results | `.fts-no-results` — 13px `--muted`, centered | `未找到匹配的文件` |
| Indexing state | `.fts-indexing` — 13px `--accent`, spinner icon | `正在索引… ({progress}%)` |

### FTS5 Search Interaction

1. **Search input:** User types keywords → debounced 300ms → `searchWorkspace(path, query, k=10)` Tauri command
2. **Results:** FTS5 returns `{ chunk_id, relative_path, text, score }[]` → rendered as result rows with highlighted snippets
3. **Attach:** User clicks "作为附件引用" → file path added to `pendingContextRefs` → visible in composer as attachment chip → submitted to Gateway as `attachment_ref` when message sent
4. **@-mention integration:** FTS5 results also populate the `WorkspaceAdapter.listFiles()` for @-mention autocomplete in the composer

### WorkspaceAdapter (Desktop Implementation)

The desktop app provides a `WorkspaceAdapter` backed by local FTS5 (unlike web which uses Gateway HTTP or empty array):

```typescript
// apps/desktop/src/adapters/workspaceAdapter.ts
export const desktopWorkspaceAdapter: WorkspaceAdapter = {
  listFiles: async (query?: string) => {
    if (query) {
      return await invoke("search_workspace", { path: workspacePath(), query, k: 20 });
    }
    return await invoke("list_directory", { path: workspacePath(), recursive: false });
  },
};
```

### FTS5 Index Status

The FTS5 index is maintained locally and can be rebuilt:

| State | Display | UI Element |
|-------|---------|------------|
| Indexed | `已索引 {file_count} 个文件 / {chunk_count} 个条文块` | Index status text in search panel + settings |
| Indexing | `正在索引… ({progress}%)` | Spinner + progress text |
| Index empty | `尚未索引工作区文件` | Prompt to index |
| Index error | `索引失败：{error}` | Error text in `--amber` |

---

## Settings Panel

### Purpose

Desktop-specific settings panel — a modal overlay with tabbed sections for desktop-only configuration. Ported from `lawyer-desktop`'s `SettingsPanel` (963 lines), with significant changes: LLM provider, skills root, and MCP health tabs are **removed** (these are now platform-side via Gateway). Desktop-specific tabs for auto-update, workspace path, and FTS5 index are retained or added.

### Settings Panel Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  设置                                                     ×        │  ← header
├──────────────────────────────────────────────────────────────────┤
│  [工作区] [自动更新] [文件访问] [关于]                             │  ← tabs
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  (active tab content)                                              │
│                                                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### Settings Panel Visual Contract

Inherited from `lawyer-desktop` `SettingsPanel.css`:

| Element | Style | Notes |
|---------|-------|-------|
| Overlay | `.settings-overlay` — `position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1000` | Click outside to close |
| Panel | `.settings-panel` — `--surface` bg, `var(--radius)` border-radius, 560px width, `max-height: 80vh`, `--shadow-pop`, `--line` border | Centered |
| Header | `.settings-header` — flex, space-between, 20px×24px×16px padding, `--line` bottom border | h2: `--serif` 18px `--ink` |
| Close button | `.close-btn` — transparent bg, 24px font, `--muted` color | Hover → `--ink` |
| Tabs | `.settings-tabs` — flex row, 24px padding, `--line` bottom border | |
| Tab | `.tab` — 14px `--ink-soft`, 12px×16px padding, 2px transparent bottom border | Active: `--accent` text + border |
| Content | `.settings-content` — 24px padding, `overflow-y: auto`, `flex: 1`, `scrollbar-gutter: stable` | |
| Form group | `.form-group` — 16px margin-bottom | Label: 13px `--ink-soft`; Input: `--line` border, 9px radius, `--surface-2` bg, 14px |
| Primary button | `.btn-primary` — `--accent` bg, `--on-accent` text, 9px radius, 8px×20px padding, 14px | Hover → `--accent-2` |
| Secondary button | `.btn-secondary` — `--surface-2` bg, `--ink` text, `--line` border, 9px radius | Hover → `--accent-soft` |
| Toggle switch | `.toggle-switch` — 44×24px, 999px radius, `--line` bg | `.on` → `--accent` bg; knob: 18px round, `--surface` bg |
| Divider | `.settings-divider` — `1px solid var(--line)`, 20px margin | |
| Test result | `.test-result` — `--surface-2` bg, 9px radius, 13px, 10px×14px padding | |

### Settings Tabs (Desktop)

| Tab | Label | Content | Ported from lawyer-desktop? |
|-----|-------|---------|---------------------------|
| 工作区 | `工作区` | Workspace path selector, FTS5 index status, reindex button | Yes (skills tab repurposed) |
| 自动更新 | `自动更新` | Update channel selector (stable/beta), check-for-update button, update history | Yes (sync tab repurposed) |
| 文件访问 | `文件访问` | Allowed file directories list, add/remove directory buttons | Yes (files tab, verbatim) |
| 关于 | `关于` | App version, build info, Gateway URL, legal disclaimer | Yes (about tab, modified) |

**Removed tabs (now platform-side):**
- ~~LLM 模型~~ — Provider configuration is now Gateway-side (desktop app has no LLM provider)
- ~~法律技能~~ — Skills are now platform-side (desktop app has no skill loader)
- ~~数据源~~ — MCP health is now platform-side (desktop app has no MCP client)
- ~~同步~~ — Sync settings replaced by auto-update tab (feedback sync is now via Gateway)

### Tab: 工作区 (Workspace)

```
工作区路径
┌──────────────────────────────────────────────┐
│  C:\Users\lawyer\Documents\法律工作区          │  ← current path
└──────────────────────────────────────────────┘
[选择目录]                                      ← native directory picker

FTS5 索引状态
已索引 128 个文件 / 3,420 个条文块
上次索引: 2026-08-08 14:32
[重新索引]                                      ← reindex button
```

- **Workspace path:** Tauri `plugin-dialog` `open({ directory: true })` → `setWorkspacePath(path)` Tauri command
- **Index status:** `getLawLibraryStatus()` Tauri command → `{ file_count, chunk_count, last_indexed_at }`
- **Reindex:** `reindexLawLibrary()` Tauri command → progress shown inline

### Tab: 自动更新 (Auto-Update)

```
更新通道
○ 稳定版 (stable)    ● 测试版 (beta)

自动检查更新
[●ON]                                              ← toggle switch

当前版本: 3.0.0 (build 20260808)
Gateway: https://api.inkstatute.example.com

[立即检查更新]                                     ← manual check button
```

- **Update channel:** Radio buttons — `stable` / `beta` (stored in local settings)
- **Auto-check toggle:** Whether to check for updates on app launch
- **Manual check:** Button triggers `checkForAppUpdate()` → shows result inline
- **Gateway URL:** Display only (configured via environment or config file, not editable in UI)

### Tab: 文件访问 (File Access)

```
允许访问的目录
┌──────────────────────────────────────────────┐
│  C:\Users\lawyer\Documents\合同              × │  ← directory row with remove button
├──────────────────────────────────────────────┤
│  C:\Users\lawyer\Documents\案件              × │
└──────────────────────────────────────────────┘
[+ 添加目录]                                      ← native directory picker
```

- **Allowed dirs list:** `getAllowedFileDirs()` / `setAllowedFileDirs(dirs)` Tauri commands
- **Add directory:** Tauri `plugin-dialog` `open({ directory: true })` → `persistAllowedDirs([...dirs, selected])`
- **Remove directory:** `persistAllowedDirs(dirs.filter(d => d !== path))`
- **Path display:** `--mono` 12px, ellipsis overflow

### Tab: 关于 (About)

```
              墨
        墨律 InkStatute

        版本: 3.0.0
        构建: 20260808
        平台: darwin-arm64

  ┌──────────────────────────────────────────┐
  │ 本工具生成的法律文书仅供参考，            │
  │ 不构成正式法律意见。最终文书              │
  │ 应由执业律师审核确认。                    │
  └──────────────────────────────────────────┘
```

- **Brand seal:** 26px round, `var(--seal-bg)`, `var(--seal-text)`, `--serif` 700 15px, centered
- **Brand name:** `--serif` 700 15px, centered
- **Version info:** 14px `--ink-soft`, centered, `--mono` for version/build/platform values
- **Disclaimer:** `--surface-2` bg, 9px radius, 12px `--muted`, 12px padding

---

## Native Menus

### Purpose

Tauri native menu bar integration for macOS (system menu bar) and Windows (window menu bar). Provides standard application menus with keyboard shortcuts.

### Menu Structure

```
墨律 InkStatute
├── 关于墨律                    → open About settings tab
├── ────────────
├── 设置...          Ctrl+,     → open Settings panel
├── ────────────
└── 退出             Ctrl+Q     → close app

文件
├── 新建对话          Ctrl+N    → new conversation (disabled offline)
├── ────────────
├── 打开文件...       Ctrl+O    → file dialog (attach to conversation)
├── ────────────
└── 导出为 Word       Ctrl+E    → export current document (in workspace)

编辑
├── 撤销              Ctrl+Z    → browser default
├── 重做              Ctrl+Y    → browser default
├── ────────────
├── 剪切              Ctrl+X    → browser default
├── 复制              Ctrl+C    → browser default
├── 粘贴              Ctrl+V    → browser default
└── 全选              Ctrl+A    → browser default

视图
├── 主题
│   ├── 传统律所 (A)             → setTheme("a")
│   ├── 深色法务终端 (B)          → setTheme("b")
│   └── 克制现代 (C)             → setTheme("c")
├── ────────────
├── 放大              Ctrl+=    → increase doc scale (--doc-scale)
├── 缩小              Ctrl+-    → decrease doc scale
├── 实际大小          Ctrl+0    → reset doc scale to 1
└── ────────────
    └── 切换全屏        F11      → toggle fullscreen

窗口
├── 最小化            Ctrl+M    → minimize()
├── 最大化                     → toggleMaximize()
└── ────────────
    └── 关闭窗口        Ctrl+W   → close()

帮助
├── 搜索工作区文件    Ctrl+Shift+F → open FTS5 search panel
├── ────────────
└── 检查更新                    → check for app update
```

### Menu Configuration

Menus are configured in `src-tauri/tauri.conf.json` or programmatically via Tauri's `Menu` API:

```rust
// src-tauri/src/lib.rs
use tauri::menu::{Menu, MenuItem, Submenu, PredefinedMenuItem};

let menu = Menu::with_items(app, &[
    Submenu::with_items(app, "墨律 InkStatute", true, &[
        MenuItem::with_id(app, "about", "关于墨律", true, None::<&str>)?,
        PredefinedMenuItem::separator(app)?,
        MenuItem::with_id(app, "settings", "设置...", true, Some("CmdOrCtrl+,"))?,
        PredefinedMenuItem::separator(app)?,
        MenuItem::with_id(app, "quit", "退出", true, Some("CmdOrCtrl+Q"))?,
    ])?,
    // ... File, Edit, View, Window, Help menus
])?;
```

### Menu Event Handling

Menu events are handled in the frontend via Tauri event listeners:

```typescript
// apps/desktop/src/menuHandlers.ts
import { listen } from "@tauri-apps/api/event";

listen("menu://settings", () => setSettingsOpen(true));
listen("menu://new-conversation", () => handleNewConversation());
listen("menu://theme-a", () => setTheme("a"));
listen("menu://theme-b", () => setTheme("b"));
listen("menu://theme-c", () => setTheme("c"));
listen("menu://search-workspace", () => setFtsSearchOpen(true));
listen("menu://check-update", () => checkForUpdate());
```

### Platform Differences

| Menu aspect | macOS | Windows |
|-------------|-------|---------|
| Menu bar location | System menu bar (top of screen) | Window menu bar (below TitleBar) |
| App menu name | "墨律 InkStatute" (bold) | "文件" (first menu) |
| Quit shortcut | `Cmd+Q` | `Ctrl+Q` |
| Settings shortcut | `Cmd+,` | `Ctrl+,` |
| Close window | `Cmd+W` | `Ctrl+W` |

---

## Auto-Update UI

### Purpose

The desktop app uses Tauri's `@tauri-apps/plugin-updater` for auto-updates. The UI shows update notifications, download progress, and restart prompts. Ported from `lawyer-desktop`'s `AppUpdateBanner` (52 lines), with enhanced progress UI.

### AppUpdateBanner Component

Ported from Phase 92 deferred component (originally `lawyer-desktop/src/components/layout/AppUpdateBanner.tsx`), updated to use 墨律 theme tokens instead of `--molv-*` fallbacks:

#### Update Available State

```
┌──────────────────────────────────────────────────────────────────┐
│  ✨ 发现新版本 3.1.0 — 修复文书导出问题       [下载并安装]  ×    │
└──────────────────────────────────────────────────────────────────┘
```

**Visual contract:**
- Container: `.app-update-banner` — `flex; align-items: center; gap: 12px; padding: 8px 16px`
- Background: `var(--accent-soft)` (accent-tinted background)
- Border-bottom: `1px solid var(--line)`
- Text: 13px `--ink`, `--serif`
- Version number: `--mono` font, `--accent` color
- Install button: `--accent` bg, `--on-accent` text, 6px radius, 4px×12px padding, 13px
- Close/dismiss button: `--muted` color, transparent bg, 16px
- `role="status"`, `aria-live="polite"`

#### Downloading State

```
┌──────────────────────────────────────────────────────────────────┐
│  下载中...  ────────────────████████████░░░░░░  62%              │
└──────────────────────────────────────────────────────────────────┘
```

**Visual contract:**
- Install button text changes to `下载中…`, `disabled`, `opacity: 0.6`
- Progress bar: 100% width, 4px height, `--line` track bg, `--accent` fill, 2px radius
- Progress percentage: 11.5px `--mono`, `--muted`, right-aligned

#### Download Error State

```
┌──────────────────────────────────────────────────────────────────┐
│  ✨ 发现新版本 3.1.0    [下载并安装]    ⚠ 下载失败：网络超时      │
└──────────────────────────────────────────────────────────────────┘
```

- Error text: 12px `--amber` (or `--accent` in theme A), `.app-update-error` class
- Install button re-enabled for retry

#### Restart Prompt State

```
┌──────────────────────────────────────────────────────────────────┐
│  ✓ 更新已就绪 — 重启应用以完成安装                    [立即重启]  │
└──────────────────────────────────────────────────────────────────┘
```

- Text: 13px `--ink`, `--serif`
- Restart button: `--accent` bg, `--on-accent` text, 6px radius, 4px×12px padding
- Calls `relaunch()` from `@tauri-apps/plugin-process`

### Auto-Update Flow

```
App Launch
    │
    ▼
checkForAppUpdate()  ← Tauri updater plugin
    │
    ├── No update → banner hidden, silent
    │
    └── Update available
            │
            ▼
        Show AppUpdateBanner (update available state)
            │
            ├── User clicks "下载并安装"
            │       │
            │       ▼
            │   installAppUpdate() ← download + install
            │       │
            │       ├── Downloading → progress bar
            │       │
            │       ├── Error → error text, retry enabled
            │       │
            │       └── Download complete
            │               │
            │               ▼
            │           Show restart prompt
            │               │
            │               └── User clicks "立即重启"
            │                       │
            │                       ▼
            │                   relaunch()
            │
            └── User clicks "×" (dismiss)
                    │
                    ▼
                Banner hidden, update deferred to next launch
```

### Auto-Update Implementation

```typescript
// apps/desktop/src/adapters/updateAdapter.ts
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

export async function checkForAppUpdate(): Promise<AppUpdateInfo | null> {
  const update = await check();
  if (update?.available) {
    return { available: true, version: update.version, body: update.body };
  }
  return { available: false };
}

export async function installAppUpdate(
  onProgress?: (percent: number) => void
): Promise<void> {
  const update = await check();
  if (!update?.available) return;
  let total = 0;
  let downloaded = 0;
  await update.downloadAndInstall((event) => {
    switch (event.event) {
      case "Started":
        total = event.data.contentLength ?? 0;
        break;
      case "Progress":
        downloaded += event.data.chunkLength;
        if (total > 0) onProgress?.(Math.round((downloaded / total) * 100));
        break;
      case "Finished":
        break;
    }
  });
  // After download+install, prompt restart
}
```

---

## Copywriting

All UI text is in **Chinese** (per `lawyer-desktop/AGENTS.md`: "UI text: Chinese"). This section covers desktop-app-specific copy not already defined in the Phase 92 UI-SPEC copywriting contract.

### Offline Mode

| Element | Copy |
|---------|------|
| Offline banner | `当前处于离线模式 — 可查看历史对话与已下载文书，新任务需要联网` |
| Composer offline placeholder | `需要联网才能发送新任务` |
| New conversation disabled tooltip | `需要联网才能发起新对话` |
| Reconnection toast | `已恢复连接` |
| SSE disconnect toast | `连接中断，正在重连…` (from Phase 92) |
| Feedback queued toast | `反馈已保存，将在联网后自动提交` |
| Cached artifact badge | `已缓存` |
| Artifact not cached (offline) | `此文书尚未下载，无法在离线模式下查看` |

### FTS5 Search

| Element | Copy |
|---------|------|
| Search input placeholder | `输入关键词…` |
| Search panel title | `搜索工作区文件` |
| Result count | `搜索结果 ({count})` |
| Attach button | `作为附件引用` |
| Index status — indexed | `已索引 {file_count} 个文件 / {chunk_count} 个条文块` |
| Index status — empty | `尚未索引工作区文件` |
| Index status — indexing | `正在索引… ({progress}%)` |
| Index status — error | `索引失败：{error}` |
| Reindex button | `重新索引` |
| Empty state | `输入关键词开始搜索工作区文件` |
| No results | `未找到匹配的文件` |

### Settings Panel

| Element | Copy |
|---------|------|
| Panel title | `设置` |
| Tab: workspace | `工作区` |
| Tab: auto-update | `自动更新` |
| Tab: file access | `文件访问` |
| Tab: about | `关于` |
| Workspace path label | `工作区路径` |
| Select directory button | `选择目录` |
| FTS5 index status label | `FTS5 索引状态` |
| Last indexed | `上次索引: {date}` |
| Update channel label | `更新通道` |
| Channel: stable | `稳定版 (stable)` |
| Channel: beta | `测试版 (beta)` |
| Auto-check toggle | `自动检查更新` |
| Current version label | `当前版本: {version} (build {build})` |
| Gateway URL label | `Gateway: {url}` |
| Check now button | `立即检查更新` |
| Allowed dirs label | `允许访问的目录` |
| Add directory button | `+ 添加目录` |
| About disclaimer | `本工具生成的法律文书仅供参考，不构成正式法律意见。最终文书应由执业律师审核确认。` |

### Auto-Update

| Element | Copy |
|---------|------|
| Update available | `发现新版本 {version}` |
| Update available with body | `发现新版本 {version} — {body}` |
| Download button | `下载并安装` |
| Downloading | `下载中…` |
| Download error | `下载失败：{error}` |
| Restart prompt | `更新已就绪 — 重启应用以完成安装` |
| Restart button | `立即重启` |
| No update available | `当前已是最新版本` |

### Native Menus

| Menu item | Copy |
|-----------|------|
| App menu title (macOS) | `墨律 InkStatute` |
| About | `关于墨律` |
| Settings | `设置...` |
| Quit | `退出` |
| File menu | `文件` |
| New conversation | `新建对话` |
| Open file | `打开文件...` |
| Export Word | `导出为 Word` |
| Edit menu | `编辑` |
| Undo | `撤销` |
| Redo | `重做` |
| Cut | `剪切` |
| Copy | `复制` |
| Paste | `粘贴` |
| Select all | `全选` |
| View menu | `视图` |
| Theme submenu | `主题` |
| Theme A | `传统律所 (A)` |
| Theme B | `深色法务终端 (B)` |
| Theme C | `克制现代 (C)` |
| Zoom in | `放大` |
| Zoom out | `缩小` |
| Actual size | `实际大小` |
| Toggle fullscreen | `切换全屏` |
| Window menu | `窗口` |
| Minimize | `最小化` |
| Maximize | `最大化` |
| Close window | `关闭窗口` |
| Help menu | `帮助` |
| Search workspace | `搜索工作区文件` |
| Check for updates | `检查更新` |

### Error Messages (desktop-specific)

| Scenario | Copy |
|----------|------|
| Gateway unreachable (app launch) | `无法连接服务器，请检查网络后重试` |
| Gateway unreachable (during task) | `连接中断，正在重连…` (from Phase 92) |
| Artifact download failed (online) | `下载失败，请重试` (from Phase 92) |
| Artifact not cached (offline) | `此文书尚未下载，无法在离线模式下查看` |
| File access denied | `无权访问此目录` |
| Workspace path invalid | `工作区路径无效或不存在` |
| FTS5 index corrupt | `索引损坏，请重新索引` |
| Update check failed | `检查更新失败，请稍后重试` |

---

## Accessibility

### Keyboard Navigation

The desktop app inherits all keyboard navigation from ui-core components (documented in Phase 92 UI-SPEC §Accessibility). Desktop-specific additions:

| Element | Key | Action |
|---------|-----|--------|
| New conversation | `Ctrl+N` | Create new conversation (via native menu) |
| Open file | `Ctrl+O` | Open file dialog (via native menu) |
| Settings | `Ctrl+,` | Open settings panel (via native menu) |
| Search workspace | `Ctrl+Shift+F` | Open FTS5 search panel (via native menu) |
| Quit app | `Ctrl+Q` / `Cmd+Q` | Close application (via native menu) |
| Zoom in | `Ctrl+=` | Increase document scale |
| Zoom out | `Ctrl+-` | Decrease document scale |
| Reset zoom | `Ctrl+0` | Reset document scale to 1 |
| Toggle fullscreen | `F11` | Toggle window fullscreen |
| Close settings | `Escape` | Close settings panel overlay |
| Close FTS5 search | `Escape` | Close FTS5 search panel |
| Minimize | `Ctrl+M` / `Cmd+M` | Minimize window (via native menu) |
| Close window | `Ctrl+W` / `Cmd+W` | Close window (via native menu) |

### ARIA Labels (desktop-specific additions)

| Element | `aria-label` | Notes |
|---------|-------------|-------|
| Offline banner | `role="status"`, `aria-live="polite"` | Announced when connection state changes |
| AppUpdateBanner | `role="status"`, `aria-live="polite"` | Announced when update is available |
| FTS5 search input | `aria-label="搜索工作区文件"` | |
| FTS5 attach button | `aria-label="作为附件引用"` | Icon-only or short text button |
| FTS5 reindex button | `aria-label="重新索引工作区文件"` | |
| Settings panel overlay | `role="dialog"`, `aria-modal="true"`, `aria-label="设置"` | |
| Settings tab | `role="tab"`, `aria-selected` | |
| Settings tab list | `role="tablist"` | |
| Settings close button | `aria-label="关闭设置"` | Icon-only button (×) |
| Window control buttons | `aria-label="最小化"` / `aria-label="最大化"` / `aria-label="关闭"` | From Phase 92 TitleBar |
| Workspace path input | `aria-label="工作区路径"` | |

### Focus Management

| Scenario | Behavior |
|----------|----------|
| App launch (online) | Focus moves to home page starter input |
| App launch (offline) | Focus moves to conversation list (read-only mode) |
| Settings open | Focus moves to first tab |
| Settings close | Focus returns to settings button in TitleBar |
| FTS5 search open | Focus moves to search input |
| FTS5 search close | Focus returns to search trigger element |
| Update banner appear | Focus not moved (banner is `aria-live`, announced but doesn't steal focus) |
| Offline → online transition | Focus preserved on current element |
| Online → offline transition | If composer was focused, focus moves to conversation list |

### Screen Reader Considerations

- **Offline banner:** `aria-live="polite"` announces "当前处于离线模式" when offline state activates
- **Update banner:** `aria-live="polite"` announces "发现新版本 {version}" when update is available
- **Connection state changes:** Route announcer element (from Phase 93 pattern) announces "已恢复连接" / "连接中断"
- **FTS5 search results:** `aria-live="polite"` on result count element announces "搜索结果 {count} 项"
- **Settings panel:** `role="dialog"` with `aria-modal="true"` traps focus within panel while open
- **Native menus:** Tauri native menus are accessible by default (OS-level accessibility)

### Color Contrast

Inherited from Phase 92 UI-SPEC §Accessibility §Color Contrast:
- All three themes have WCAG AAA contrast for primary text (`--ink` on `--app-bg`)
- `--muted` colors are acceptable for large text/labels but not body text
- `--ink-soft` should be used for secondary body text
- The desktop app adds no new color combinations — all colors come from ui-core tokens
- Offline banner uses `--doc-risk-*` tokens (amber family) — verify contrast in all three themes

---

## UI Considerations

> State coverage for each desktop-specific UI element — loading, error, empty, success states.
> Component-level state coverage is inherited from Phase 92 UI-SPEC §UI Considerations (14 covered, 2 backstop).
> This section covers desktop-app-specific states.

Applicable state considerations resolved: 16 covered, 1 backstop, 0 unresolved

| Category | Element(s) | Status | Resolution / Reason |
|----------|------------|--------|---------------------|
| loading | App launch (connection check) | ✅ covered | Full-screen loading overlay with spinner + "加载中…" text, `aria-busy="true"`; transitions to home or offline mode after probe |
| loading | FTS5 search (query in flight) | ✅ covered | Search input shows spinner icon, results area shows "搜索中…" text |
| loading | FTS5 reindex | ✅ covered | Index status shows "正在索引… ({progress}%)" with spinner, reindex button disabled |
| loading | AppUpdateBanner (downloading) | ✅ covered | Progress bar with percentage, install button shows "下载中…" and is disabled |
| loading | Artifact download (online) | ✅ covered | DocPreview shows DocDraftingLoader skeleton (from Phase 92) |
| error | Gateway unreachable (app launch) | ✅ covered | Offline banner appears, app enters read-only mode; toast: "无法连接服务器，请检查网络后重试" |
| error | Gateway unreachable (during task) | ✅ covered | SSE disconnect toast "连接中断，正在重连…" (from Phase 92), EventStreamStore auto-reconnects |
| error | FTS5 search failure | ✅ covered | Error text in search panel: "索引损坏，请重新索引" with reindex button |
| error | FTS5 reindex failure | ✅ covered | Index status shows "索引失败：{error}" in `--amber` text |
| error | Update download failure | ✅ covered | Error text in update banner: "下载失败：{error}", install button re-enabled for retry |
| error | Artifact not cached (offline) | ✅ covered | DocPreview shows "此文书尚未下载，无法在离线模式下查看" empty state |
| error | File access denied | ✅ covered | Toast: "无权访问此目录", directory not added to allowed list |
| empty | FTS5 search — no query | ✅ covered | "输入关键词开始搜索工作区文件" empty state |
| empty | FTS5 search — no results | ✅ covered | "未找到匹配的文件" no-results state |
| empty | FTS5 index — not built | ✅ covered | "尚未索引工作区文件" with reindex button |
| success | Update check — no update | ✅ covered | Inline result in settings: "当前已是最新版本" |
| long-text | FTS5 search results (100+ matches) | 🧪 backstop | FTS5 returns top-k (default 10) results, so large result sets are truncated by design. However, very long snippets or many concurrent searches may impact UI responsiveness. Visual test needed. |

<!-- Status vocabulary:
     ✅ covered   → a plain truth string lifted into must_haves.truths
     🧪 backstop  → a flat scalar { statement, verification: backstop }; at verify time, no explicit
                    evidence → insufficient_spec → human_needed (never a silent pass)
     ⚠ unresolved → an explicit planner assumption (surfaced, never silently dropped)
     Rows are REPLACED (not appended) on a probe re-run — idempotent. -->

---

## Adapter Wiring

The desktop app provides concrete implementations of ui-core adapter interfaces. These are the key differentiators from the web client.

| Adapter | Desktop Implementation | UI Impact |
|---------|----------------------|-----------|
| `FileAdapter` | `open()`: Tauri `plugin-dialog` `open()` (native OS dialog, returns real paths); `save()`: Tauri `plugin-dialog` `save()` + write file | File open uses native dialog with real OS paths; save uses native save dialog |
| `DropAdapter` | `classifyDroppedPaths()`: Tauri path classification (real OS paths from drop event) | Drag-drop works with real file paths, not just file objects |
| `AppInfoAdapter` | `getVersion()`: Tauri `app.getVersion()`; `checkForUpdate()`: Tauri updater plugin | TitleBar shows desktop version; AppUpdateBanner shows update notifications |
| `WorkspaceAdapter` | `listFiles()`: local FTS5 search or `list_directory` Tauri command | @-mention autocomplete has real local files; FTS5 search panel available |
| `DocumentParser` | Calls Gateway HTTP parse API (same as web) — desktop has no local parser | DocPreview parses document JSON via Gateway |
| `WindowAdapter` | **Provided** — backed by Tauri `@tauri-apps/api/window` | TitleBar shows window controls (traffic lights / min/max/close) |

### WindowAdapter Impact on TitleBar

Unlike the web client (where `WindowAdapter` is not provided), the desktop app provides a full `WindowAdapter` implementation. The ui-core `TitleBar` component:
- **macOS:** Shows traffic light dots (`.tb-traffic`) on the left — close (red), minimize (yellow), maximize (green)
- **Windows:** Shows window control buttons (`.tb-win-ctrls`) on the right — minimize, maximize/restore, close
- **Drag region:** `data-tauri-drag-region` on crumbs area (macOS) or `-webkit-app-region: drag` (Windows)
- **Double-click:** On drag region toggles maximize

### invoke() Migration Summary

Per UI-05 requirement, the 57 `invoke()` calls from `lawyer-desktop` are migrated:

| Category | Original invoke() calls | Migration target | Count |
|----------|------------------------|------------------|-------|
| Agent / LLM | `send_message`, `classify_agent_mode`, `generate_followup_prompts`, `get_active_provider`, `setup_provider`, `test_provider`, `get_fast_provider`, `setup_fast_provider`, `test_fast_provider`, `get_provider_presets`, `get_fast_model_presets` | **Gateway HTTP/SSE** | ~11 |
| Sessions / messages | `create_conversation`, `get_conversations`, `get_messages`, `update_message_metadata`, `delete_conversation`, `set_active_conversation`, `update_conversation_title` | **Gateway HTTP** | ~7 |
| Skills | `get_skills_root`, `set_skills_root`, `reload_skills`, `list_skills`, `get_skillopt_settings`, `set_skillopt_settings`, `get_skillopt_overview` | **Gateway HTTP** (`/v1/skills`) | ~7 |
| Feedback | `submit_message_feedback`, `get_message_feedback`, `list_all_feedback` | **Gateway HTTP** (`/v1/feedback`) | ~3 |
| Eval / proposals | `list_eval_cases`, `set_eval_case_active`, `run_eval_case`, `list_eval_runs`, `list_proposals`, `adopt_proposal`, `reject_proposal`, `mine_eval_cases`, `run_skill_refinement` | **Removed** (platform-side, not in desktop app scope) | ~9 |
| Documents | `parse_legal_document`, `generate_docx` | **Gateway HTTP** (artifact download) | ~2 |
| MCP | `get_mcp_health` | **Removed** (platform-side) | ~1 |
| Sync | `get_sync_settings`, `set_sync_settings`, `get_sync_status_cmd`, `flush_feedback_outbox`, `test_sync_connection` | **Simplified** — feedback outbox via Gateway, sync settings → auto-update settings | ~5 |
| **Desktop-only (retained)** | `check_for_app_update`, `install_app_update`, `get_law_library_status`, `reindex_law_library`, `search_workspace`, `bind_workspace`, `get_workspace_index_status`, `read_file_content`, `list_directory`, `prepare_attachment`, `classify_dropped_paths`, `grant_path_access`, `get_allowed_file_dirs`, `set_allowed_file_dirs` | **Retained as Tauri commands** | ~14 |

**Total: ~59 invoke() calls → ~14 retained as Tauri commands, ~35 migrated to Gateway HTTP, ~10 removed (platform-side).**

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| `@inkstatute/ui-core` | 17 components + 2 utils + 3 deferred (this phase) + themes | `workspace:*` protocol — local package, no registry risk |
| `@tauri-apps/api` | `core`, `window`, `event` | Official Tauri SDK, npm package |
| `@tauri-apps/plugin-dialog` | `open()`, `save()` | Official Tauri plugin, npm package |
| `@tauri-apps/plugin-updater` | `check()`, `downloadAndInstall()` | Official Tauri plugin, npm package |
| `@tauri-apps/plugin-process` | `relaunch()` | Official Tauri plugin, npm package |
| `solid-markdown` | Markdown rendering | Peer dependency from ui-core, provided by desktop app |
| `remark-gfm` | GitHub-flavored markdown | Peer dependency from ui-core |
| `highlight.js` | Code syntax highlighting | Peer dependency from ui-core |
| Google Fonts | Noto Serif SC, Noto Sans SC, Newsreader, Spline Sans Mono | **Bundled locally** — no CDN dependency (offline-capable) |

**No third-party component registries used.** All UI components come from `@inkstatute/ui-core` (hand-written SolidJS). No shadcn/radix/base-ui dependency. Tauri plugins are official first-party plugins.

---

## Component Port Summary (Phase 94)

Components deferred from Phase 92, now ported in Phase 94:

| # | Component | Source | Lines | Port strategy |
|---|-----------|--------|-------|---------------|
| 18 | SkillRefinementPanel | `workspace/SkillRefinementPanel.tsx` | 390 | **Not ported** — skill refinement is now platform-side (Gateway/router-service). Desktop app does not include this component. |
| 19 | AppUpdateBanner | `layout/AppUpdateBanner.tsx` | 52 | **Ported with changes** — update `--molv-*` tokens to `--*` tokens; add download progress bar; add restart prompt state |
| 20 | SettingsPanel | `settings/SettingsPanel.tsx` | 963 | **Ported with major changes** — remove LLM/skills/MCP/sync tabs; add workspace/auto-update tabs; retain file-access/about tabs |

**New desktop-specific components (not in lawyer-desktop):**

| Component | Purpose | Est. lines |
|-----------|---------|------------|
| FTS5SearchPanel | Local workspace full-text search panel | ~120 |
| OfflineBanner | Offline mode banner with connection state | ~40 |
| ConnectionContext | Connection state provider (online/offline/checking) | ~80 |

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS — offline messages, FTS5 search labels, settings labels, auto-update messages, native menu labels, error messages documented in Chinese
- [x] Dimension 2 Visuals: PASS — desktop layout, TitleBar with window controls (macOS + Windows), offline banner, FTS5 search panel, settings panel, auto-update banner documented with CSS values
- [x] Dimension 3 Color: PASS — inherits 墨律 three-theme system from Phase 92, no new colors; offline banner uses existing `--doc-risk-*` tokens
- [x] Dimension 4 Typography: PASS — inherits type scale from Phase 92; desktop-specific elements (offline banner, FTS5 results, settings) use existing font families and sizes
- [x] Dimension 5 Spacing: PASS — desktop layout dimensions (sidebar 280px, TitleBar 46px, settings panel 560px) documented; inherits spacing patterns from Phase 92
- [x] Dimension 6 Registry Safety: PASS — only official Tauri plugins added; all UI from ui-core; fonts bundled locally (no CDN); no third-party component registries
