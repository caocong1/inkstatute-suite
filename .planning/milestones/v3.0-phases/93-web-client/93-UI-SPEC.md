---
phase: 93
slug: web-client
status: draft
created: 2026-08-08
inherits_from: 92-UI-SPEC.md
---

# Phase 93 — UI Design Contract

> Responsive web application shell and interaction contract for `apps/web`.
> This spec builds on the Phase 92 UI-SPEC (墨律 three-theme system, 17 components, adapter pattern).
> The web client contains **zero chat UI code** — all chat rendering comes from `@inkstatute/ui-core`.
> This spec covers the app shell, routing, responsive layout, login page, and mobile-specific concerns.

---

## Design System

### Inheritance from ui-core (Phase 92)

The web client inherits the complete 墨律 design system from `@inkstatute/ui-core`. No new themes, tokens, or component styles are created — the web app provides the **shell** (routing, auth, layout, adapter wiring) and **responsive CSS overrides** only.

| Property | Value | Source |
|----------|-------|--------|
| Component library | `@inkstatute/ui-core` — 17 components + 2 utils | Phase 92, `workspace:*` |
| Theme system | 墨律 three themes via `data-theme="a|b|c"` | `molv-tokens.css` + `molv-base.css` |
| Theme switcher | Pill toggle in TitleBar with 3 color dots | ui-core `TitleBar` component |
| Theme persistence | `localStorage["ml-theme"]`, values `"a"|"b"|"c"`, default `"a"` | ui-core `useTheme()` store |
| Font families | Noto Serif SC + Newsreader (serif), Noto Sans SC (sans), Spline Sans Mono (mono) | `molv-tokens.css` `@import url(...)` |
| CSS strategy | CSS custom properties + `data-theme` attribute switching — no JS theme engine | Phase 92 §Design System |
| Icon library | Custom SVG icon set from ui-core `Icons.tsx` (30+ icons, stroke-based) | Phase 92 |
| Markdown | `solid-markdown` + `remark-gfm` (peer dependency, provided by web app) | Phase 92 |
| Syntax highlight | `highlight.js` (peer dependency, provided by web app) | Phase 92 |

### Theme Application in the Web App

The web app imports ui-core CSS as side-effect imports:

```typescript
// apps/web/src/main.tsx
import "@inkstatute/ui-core/themes";  // molv-tokens.css + molv-base.css
import "./app-shell.css";              // responsive layout overrides (this phase)
```

The `useTheme()` store from ui-core is used directly — no web-specific theme logic. On app mount, `useTheme()` reads `localStorage["ml-theme"]` and applies `document.documentElement.setAttribute("data-theme", variant)`. The `TitleBar` component renders the theme switcher pill.

**No web-specific theme tokens.** All CSS custom properties are defined in `molv-tokens.css`. The web app's `app-shell.css` only adds layout-specific CSS (responsive breakpoints, mobile drawer, safe-area insets) — it references existing `var(--*)` tokens, never hardcodes colors.

### CSS Import Order

1. `molv-tokens.css` — `:root` + `[data-theme="a|b|c"]` custom properties (~80 tokens × 3 themes)
2. `molv-base.css` — base styles (app frame, titlebar, home, workspace, chat, doc, citation, toast)
3. Component CSS files — imported by ui-core components via `<style>` or CSS modules
4. `app-shell.css` — **web-only** responsive overrides (breakpoints, mobile layout, safe-area)

---

## App Shell Layout

### Architecture Overview

The web app shell wraps `@solidjs/router` with two context providers and a route guard:

```
App.tsx
├── AuthContext.Provider          (session, login, logout)
├── AdapterContext.Provider       (web adapter implementations)
└── Router
    ├── /login                    → LoginPage (unauthenticated)
    ├── /                         → AppLayout > HomePage (authenticated)
    └── /workspace/:convId        → AppLayout > WorkspacePage (authenticated)
```

**Route guard:** A `<Show when={auth.isAuthenticated()} fallback={<Navigate href="/login" />}>` wraps authenticated routes. When the AuthContext probes the Gateway on init and finds no valid session, it redirects to `/login`.

### Desktop Layout (≥768px)

```
┌──────────────────────────────────────────────────────────────────┐
│ TitleBar (46px) — brand · crumbs · theme switch · menu button     │
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
  <TitleBar ... />                         // flex: 0 0 46px
  <div class="stage">                      // flex: 1; min-height: 0; flex row
    <ConversationDrawer open={true} ... /> // sidebar: flex: 0 0 280px
    <div class="main-content">             // flex: 1; min-width: 0
      {route content}                      // HomePage or WorkspacePage
    </div>
  </div>
</div>
```

**Desktop sidebar (ConversationDrawer):**
- Width: `var(--sidebar-width, 280px)` — fixed left sidebar, always visible
- `position: relative` in the flex flow (not an overlay)
- Contains: conversation search, conversation list, new conversation button
- The ui-core `ConversationDrawer` component's `open` prop is `true` on desktop
- Border-right: `1px solid var(--line)` separates sidebar from main content

**Desktop TitleBar:**
- Full controls: brand seal + name, breadcrumbs (current screen), theme switcher pill, conversation list toggle (hidden on desktop since sidebar is always open), home button
- No window controls (web has no traffic lights) — `WindowAdapter` is not provided
- Height: 46px, `--titlebar-bg` background, `--titlebar-line` bottom border

### Mobile Layout (<768px)

```
┌──────────────────────────────┐
│ TitleBar (46px) — brand · ☰  │  (condensed: theme switch + menu only)
├──────────────────────────────┤
│                              │
│ Main Stage (full width)      │
│                              │
│ Home page:  full width,      │
│  reduced padding             │
│ Workspace:  stacked          │
│  (chat full width, doc       │
│   preview as tab/overlay)    │
│                              │
│                              │
├──────────────────────────────┤
│ (safe-area-inset-bottom)     │
└──────────────────────────────┘

When drawer open:
┌──────────────────────────────┐
│ TitleBar                     │
├──────────────┬───────────────┤
│ Drawer       │ (backdrop     │
│ (min(360px,  │  rgba dim)    │
│  100vw))     │               │
│ Conversation │               │
│ list         │               │
│              │               │
└──────────────┴───────────────┘
```

**Mobile shell structure:**

```tsx
<div class="app mobile">                   // position: fixed; inset: 0; flex column
  <TitleBar ... />                         // flex: 0 0 46px (condensed)
  <div class="stage">                      // flex: 1; min-height: 0
    <div class="main-content">             // flex: 1; min-width: 0; full width
      {route content}
    </div>
  </div>
  <Show when={drawerOpen()}>               // overlay drawer
    <ConversationDrawer open={true} ... />
  </Show>
</div>
```

**Mobile drawer (ConversationDrawer):**
- Hidden by default, opened via hamburger menu button in TitleBar
- Width: `min(360px, 100vw)` — slides in from left as an overlay
- Backdrop: semi-transparent `rgba` dim behind the drawer, tap to close
- The ui-core `ConversationDrawer` component is reused — its existing `position: fixed; inset: 46px 0 0` and slide-in animation work for mobile overlay
- On mobile, the drawer's `onClose` is triggered by backdrop tap or selecting a conversation

**Mobile TitleBar:**
- Condensed: brand seal + name (short), hamburger menu button (left or right), theme switcher pill
- No breadcrumbs (screen context is obvious on mobile)
- No window controls
- Safe area: `padding-top: env(safe-area-inset-top)` on the `.app` container for notched devices

### Layout CSS Custom Properties (web-only)

The web app defines layout-specific CSS custom properties in `app-shell.css`:

```css
:root {
  --sidebar-width: 280px;
  --sidebar-width-mobile: min(360px, 100vw);
  --main-max-width: 1040px;
  --safe-area-top: env(safe-area-inset-top, 0px);
  --safe-area-bottom: env(safe-area-inset-bottom, 0px);
  --app-height: 100dvh;
}
```

These are layout dimensions, not theme colors — they don't vary per theme.

---

## Responsive Breakpoints

### Breakpoint Strategy

Single breakpoint at **768px**. Desktop ≥768px, mobile <768px. This matches the Phase 92 UI-SPEC note: "explicit breakpoints are Phase 93 (Web Client) scope."

| Breakpoint | Range | Layout |
|------------|-------|--------|
| Desktop | ≥768px | Sidebar + main content, full TitleBar, chat+doc split workspace |
| Mobile | <768px | Full-width main content, drawer overlay, stacked workspace |

### What Changes at Each Breakpoint

| Element | Desktop (≥768px) | Mobile (<768px) |
|---------|------------------|------------------|
| **ConversationDrawer** | Fixed sidebar, 280px, always open | Overlay drawer, `min(360px, 100vw)`, toggle via hamburger |
| **TitleBar** | Full: brand + crumbs + theme switch + menu | Condensed: brand (short) + hamburger + theme switch |
| **Home page padding** | `64px 40px 80px` (from `molv-base.css`) | `24px 16px 40px` (reduced) |
| **Home type grid** | `repeat(4, 1fr)`, 14px gap | `repeat(2, 1fr)`, 12px gap |
| **Home max-width** | 1040px centered | 100% (no max-width constraint) |
| **Workspace layout** | Chat (500px) \| Splitter \| DocPreview (flex: 1) | Stacked: chat full-width, doc preview as toggle tab |
| **Chat panel width** | `var(--chat-w, 500px)` | 100% (full width) |
| **DocPreview** | Side-by-side with chat, splitter resizable | Tab/overlay — toggle between "对话" and "文书" |
| **CitationPanel** | Slide-in overlay, 410px, from right | Full-width overlay from bottom or right |
| **Composer** | Standard padding `14px 22px 18px` | Reduced padding `12px 16px 16px`, larger touch targets |
| **Font size (base)** | 14px | 16px (prevents iOS auto-zoom on input focus) |
| **Chat message font** | 13.5px | 15px |
| **Touch targets** | Standard (30px buttons) | Min 44×44px |
| **Safe area** | Not needed | `env(safe-area-inset-*)` padding |
| **Viewport height** | `100vh` | `100dvh` (dynamic viewport height) |

### Media Query Implementation

All responsive overrides live in `apps/web/src/app-shell.css`:

```css
/* ===== Desktop default (≥768px) — no media query needed ===== */
.app .stage {
  flex-direction: row;
}
.app .sidebar {
  flex: 0 0 var(--sidebar-width, 280px);
  position: relative;
}
.app .main-content {
  flex: 1;
  min-width: 0;
}

/* ===== Mobile (<768px) ===== */
@media (max-width: 767px) {
  .app {
    height: var(--app-height, 100dvh);
    padding-top: var(--safe-area-top);
  }
  .app .stage {
    flex-direction: column;
  }
  .app .sidebar {
    display: none;  /* hidden by default, shown as overlay */
  }
  .app.mobile-drawer-open .sidebar {
    display: flex;
    position: fixed;
    inset: 46px 0 0;
    z-index: 65;
    width: var(--sidebar-width-mobile);
  }
  .app .main-content {
    flex: 1;
    width: 100%;
  }

  /* Home page responsive */
  .home-inner {
    max-width: 100%;
    padding: 24px 16px 40px;
  }
  .types {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  .home-hi h1 {
    font-size: 28px;
  }

  /* Workspace stacked */
  .ws {
    flex-direction: column;
  }
  .ws .chat {
    flex: 1 1 auto;
    border-right: none;
    border-bottom: 1px solid var(--line);
  }
  .ws .doc {
    flex: 0 0 0;
    display: none;  /* hidden, shown via tab toggle */
  }
  .ws.doc-visible .chat {
    display: none;
  }
  .ws.doc-visible .doc {
    flex: 1;
    display: flex;
  }

  /* Citation panel full-width on mobile */
  .cite-panel {
    width: 100%;
  }

  /* Touch targets */
  .btn-accent, .send-btn, .dbtn, .chip, .clarify-option {
    min-height: 44px;
    min-width: 44px;
  }

  /* Composer */
  .composer {
    padding: 12px 16px calc(16px + var(--safe-area-bottom));
  }

  /* Font sizes */
  .input-box textarea {
    font-size: 16px;  /* prevent iOS auto-zoom */
  }
  .prose {
    font-size: 15px;
  }
  .bubble-user {
    font-size: 15px;
  }
}
```

### Workspace Mobile Tab Toggle

On mobile, the workspace shows either chat OR document preview — not both simultaneously. A segmented toggle in the workspace header switches between them:

```
Mobile workspace:
┌──────────────────────────────┐
│ [对话] [文书]    [引用(3)]    │  ← tab toggle bar
├──────────────────────────────┤
│                              │
│  (active tab content)        │
│  ChatPanel OR DocPreview     │
│                              │
├──────────────────────────────┤
│ Composer (always visible     │
│  when chat tab active)       │
└──────────────────────────────┘
```

**Tab toggle bar (mobile only):**
- Three segments: `对话` (chat), `文书` (document), `引用（{count}）` (citations)
- Active segment: `--accent` bg, `--on-accent` text (reuses `.seg button.on` styling)
- Inactive segment: `--muted` text
- The `引用` tab badge shows citation count; tapping it opens the CitationPanel as a full-width overlay
- When no artifact exists, the `文书` tab is disabled (greyed out, not clickable)
- When no citations exist, the `引用` tab shows `引用` without a count badge

**Desktop:** The tab toggle bar is hidden — chat and doc are side-by-side, citations slide in as overlay.

---

## Login Page

### Purpose

Minimal authentication form — lawyers enter credentials, the web app POSTs to Gateway `POST /v1/auth/login`, receives a session cookie, and redirects to home.

### Layout

```
┌──────────────────────────────────────────────────────┐
│                                                        │
│                    (centered)                          │
│                                                        │
│            ┌─────────────────────────┐                │
│            │  墨 seal (26px)          │                │
│            │  墨律 InkStatute         │                │
│            │  ─────────────────       │                │
│            │                          │                │
│            │  用户名                   │                │
│            │  ┌──────────────────┐   │                │
│            │  │                  │   │                │
│            │  └──────────────────┘   │                │
│            │                          │                │
│            │  密码                     │                │
│            │  ┌──────────────────┐   │                │
│            │  │                  │   │                │
│            │  └──────────────────┘   │                │
│            │                          │                │
│            │  ┌──────────────────┐   │                │
│            │  │     登 录         │   │                │
│            │  └──────────────────┘   │                │
│            │                          │                │
│            │  ● ● ●  (theme switch)   │                │
│            └─────────────────────────┘                │
│                                                        │
│            (error message area)                        │
│                                                        │
└──────────────────────────────────────────────────────┘
```

### Visual Contract

| Element | Style | Notes |
|---------|-------|-------|
| Login container | `min-height: 100dvh; display: grid; place-items: center; background: var(--app-bg)` | Full viewport, centered |
| Login card | `width: min(380px, calc(100vw - 32px)); background: var(--surface); border: 1px solid var(--line); border-radius: 18px; padding: 40px 32px; box-shadow: var(--shadow-pop)` | Same radius as `.starter` (18px) |
| Brand seal | 26px round, `var(--seal-bg)`, `var(--seal-text)`, `--serif` 700 15px, centered | Reuses `.seal` class from `molv-base.css` |
| Brand name | `--serif` 700 15px, `.04em` spacing, `--ink`, centered | Reuses `.brand-name` styling |
| Divider | `1px solid var(--line-soft)`, 20px vertical margin | Subtle separator |
| Field label | `--sans` 12.5px, `--ink-soft`, 6px bottom margin | Above each input |
| Text input | `width: 100%; height: 42px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); padding: 0 14px; font-size: 16px; color: var(--ink)` | 16px font to prevent iOS auto-zoom |
| Text input focus | `border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 14%, transparent)` | Accent ring |
| Password input | Same as text input + `type="password"` | |
| Login button | `width: 100%; height: 44px; background: var(--accent); color: var(--on-accent); border: none; border-radius: 10px; font-family: var(--serif); font-weight: 600; font-size: 14px; cursor: pointer` | Reuses `.btn-accent` pattern, 44px height for touch |
| Login button hover | `background: var(--accent-2)` | |
| Login button loading | `opacity: .65; cursor: progress` | Disabled state during POST |
| Theme switcher | Same pill toggle from TitleBar, centered below button | Reuses `.theme-switch` + `.theme-dot` classes |
| Error message | `color: var(--accent); font-size: 13px; text-align: center; margin-top: 14px; min-height: 20px` | Uses `--accent` (red in theme A) for error text |

### Login Form Behavior

1. **Initial state:** Empty form, focus on username field
2. **Submit:** User clicks 登录 or presses Enter in password field → `auth.login({ username, password })`
3. **Loading:** Button shows `opacity: .65; cursor: progress`, inputs disabled
4. **Success:** Redirect to `/` (home page), AuthContext stores `session_id` + `tenant_id`
5. **Error:** Error message appears below button, inputs re-enabled, focus returns to username

### Dev Auto-Login

When `VITE_DEV_AUTO_LOGIN=true` (development mode), the login page auto-submits with default credentials on mount. The form is briefly visible then redirects. This is controlled by an env var, not a UI toggle.

### Token-Based Login (Alternative)

The login form supports an alternative mode: if `VITE_LOGIN_MODE=token`, the form shows a single token input field instead of username/password. This is for programmatic/API access scenarios. The label changes to `访问令牌` (access token).

### Login Page Copy

| Element | Copy (Chinese) |
|---------|----------------|
| Page title (document.title) | `登录 · 墨律 InkStatute` |
| Brand name | `墨律 InkStatute` |
| Username label | `用户名` |
| Password label | `密码` |
| Token label (token mode) | `访问令牌` |
| Login button | `登 录` |
| Error — invalid credentials | `用户名或密码错误` |
| Error — network failure | `无法连接服务器，请检查网络` |
| Error — session expired | `会话已过期，请重新登录` |
| Dev auto-login hint | `开发模式：自动登录中…` |

---

## Home Page

### Purpose

Authenticated landing page — greeting, starter prompt input, document type cards, recent conversations. Uses ui-core `HomePage` component.

### Layout (Desktop)

```
┌─────────────────────────────────────────────────────────────┐
│  下午好，律师                              2026年8月8日       │  ← greeting + date
│                                                               │
│  今天需要起草什么文书？                                        │  ← subtitle
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  ✦ 快速起草                                              │ │  ← starter card
│  │  ┌─────────────────────────────────────────────────┐    │ │
│  │  │  描述你的需求…                                    │    │ │  ← prompt input
│  │  │                                                    │    │ │
│  │  └─────────────────────────────────────────────────┘    │ │
│  │  📎 附件  @ 引用          [开始起草 →]                   │ │  ← toolbar + send
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  文书类型                                                     │  ← section heading
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                         │  ← 4-column grid
│  │ 合同 │ │ 律师 │ │ 法律 │ │ 案件 │                         │
│  │ review│ │函   │ │意见  │ │分析  │                         │
│  └──────┘ └──────┘ └──────┘ └──────┘                         │
│                                                               │
│  最近对话                                                     │  ← section heading
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  合同审查 — 租赁协议              2小时前                │ │  ← recent conversations
│  │  律师函 — 催款通知                昨天                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Layout (Mobile)

```
┌──────────────────────────────┐
│ 下午好，律师        8月8日     │  ← smaller greeting
│                               │
│ 今天需要起草什么文书？         │
│                               │
│ ┌───────────────────────────┐ │
│ │ ✦ 快速起草                 │ │
│ │ ┌───────────────────────┐ │ │
│ │ │ 描述你的需求…          │ │ │
│ │ └───────────────────────┘ │ │
│ │ 📎  @      [开始起草 →]    │ │
│ └───────────────────────────┘ │
│                               │
│ 文书类型                       │
│ ┌────────┐ ┌────────┐         │  ← 2-column grid
│ │ 合同   │ │ 律师函 │         │
│ │ review │ │        │         │
│ └────────┘ └────────┘         │
│ ┌────────┐ ┌────────┐         │
│ │ 法律   │ │ 案件   │         │
│ │ 意见   │ │ 分析   │         │
│ └────────┘ └────────┘         │
│                               │
│ 最近对话                       │
│ ┌───────────────────────────┐ │
│ │ 合同审查 — 租赁协议  2小时前│ │
│ │ 律师函 — 催款通知    昨天   │ │
│ └───────────────────────────┘ │
└──────────────────────────────┘
```

### Home Page Component Usage

The web app uses the ui-core `HomePage` component directly:

```tsx
<HomePage
  onStart={(prompt) => handleStart(prompt)}
  pendingContextRefs={pendingRefs()}
  addContextRef={addContextRef}
  removeContextRef={removeContextRef}
  addInlineMention={addMention}
  removeInlineMention={removeMention}
/>
```

The `HomePage` component renders the greeting, starter, type grid, and recent conversations. The web app provides the data (conversation list from `ConversationContext`) and callbacks (start → create session + navigate to workspace).

### Home Page Responsive Overrides

| Element | Desktop | Mobile |
|---------|---------|--------|
| `.home-inner` padding | `64px 40px 80px` | `24px 16px 40px` |
| `.home-inner` max-width | `1040px` | `100%` |
| `.home-hi h1` font-size | `34px` | `28px` |
| `.types` grid | `repeat(4, 1fr)`, 14px gap | `repeat(2, 1fr)`, 12px gap |
| `.type-card` padding | `18px 16px 16px` | `16px 14px 14px` |
| `.starter` margin-bottom | `40px` | `24px` |
| `.section-h` margin-bottom | `16px` | `12px` |

### Recent Conversations Section

The home page includes a "最近对话" (recent conversations) section below the document type grid. This is a web-app-specific addition — the ui-core `HomePage` component shows starter prompts and type cards, and the web app wraps it with a recent conversations list from `ConversationContext`.

**Recent conversation row:**
- Reuses `.conversation-row` styling from `ConversationDrawer.css`
- Shows: conversation title, last activity timestamp, message count
- Tap/click → navigate to `/workspace/{conversationId}`
- Max 5 recent conversations shown on home page
- "查看全部" (view all) link opens the conversation drawer

### Home Page Copy

| Element | Copy (Chinese) |
|---------|----------------|
| Greeting (morning) | `早上好，律师` |
| Greeting (afternoon) | `下午好，律师` |
| Greeting (evening) | `晚上好，律师` |
| Subtitle | `今天需要起草什么文书？` |
| Starter title | `快速起草` |
| Starter placeholder | `描述你的需求…` |
| Starter button | `开始起草` |
| Section: document types | `文书类型` |
| Section: recent conversations | `最近对话` |
| Recent conversations empty | `还没有对话记录，开始第一次起草吧` |
| View all conversations | `查看全部` |

---

## Workspace Layout

### Purpose

The workspace page is where the lawyer interacts with the agent — sends tasks, sees streaming replies, answers clarification cards, views document artifacts, and reviews citations. Uses ui-core `ChatPanel`, `DocPreview`, `CitationPanel`, `DraftingProgressSteps`, and `Workspace` orchestrator.

### Desktop Workspace (≥768px)

```
┌──────────────────────────────────────────────────────────────────┐
│ TitleBar — crumbs: 首页 / 合同审查 · 租赁协议   theme switch · ☰  │
├────────────┬──────────────────────────┬───────────────────────────┤
│            │ ChatPanel (500px)         │ DocPreview (flex: 1)      │
│ Sidebar    │ ┌──────────────────────┐ │ ┌───────────────────────┐ │
│ (280px)    │ │ context header       │ │ │ doc toolbar           │ │
│            │ │ 合同审查 · 租赁协议   │ │ │ 租赁协议  v1  [导出]  │ │
│ Conv list  │ ├──────────────────────┤ │ ├───────────────────────┤ │
│            │ │                      │ │ │                       │ │
│ - conv 1   │ │ thread (scroll)      │ │ │ document sheet        │ │
│ - conv 2   │ │                      │ │ │ (scroll)              │ │
│ - conv 3   │ │ user msg             │ │ │                       │ │
│            │ │ agent msg (stream)   │ │ │ articles...           │ │
│            │ │ clarification card   │ │ │                       │ │
│            │ │ drafting progress    │ │ │ risk notes...         │ │
│            │ │                      │ │ │                       │ │
│            │ ├──────────────────────┤ │ │                       │ │
│            │ │ composer             │ │ │                       │ │
│            │ │ [input]    [发送]    │ │ │                       │ │
│            │ └──────────────────────┘ │ └───────────────────────┘ │
│            │                          │ (CitationPanel slides in  │
│            │                          │  from right as overlay)   │
├────────────┴──────────────────────────┴───────────────────────────┤
│ (splitter between chat and doc: 6px, col-resize)                  │
└──────────────────────────────────────────────────────────────────┘
```

**Desktop workspace structure:**

```tsx
<WorkspacePage>
  <div class="ws">                          // flex row, flex: 1
    <ChatPanel state={renderState()} ... />  // flex: 0 0 var(--chat-w, 500px)
    <div class="ws-splitter" />              // 6px, col-resize
    <DocPreview state={renderState()} ... /> // flex: 1
    <CitationPanel state={renderState()} />  // absolute overlay, 410px
  </div>
</WorkspacePage>
```

The ui-core `Workspace` component orchestrates this layout. The web app provides the `RenderState` from `EventStreamStore` and the adapter implementations.

### Mobile Workspace (<768px)

```
┌──────────────────────────────┐
│ TitleBar — ← 合同审查  · ☰   │  ← back button + title + menu
├──────────────────────────────┤
│ [对话] [文书] [引用(3)]       │  ← tab toggle (mobile only)
├──────────────────────────────┤
│                              │
│  (active tab content)        │
│                              │
│  ChatPanel (full width)      │
│  OR DocPreview (full width)  │
│  OR CitationPanel (overlay)  │
│                              │
│                              │
├──────────────────────────────┤
│ Composer (chat tab only)     │
│ [input]          [发送]       │
└──────────────────────────────┘
```

**Mobile workspace structure:**

```tsx
<WorkspacePage>
  <div class="ws mobile">                   // flex column
    <div class="ws-tabs">                   // mobile tab toggle
      <button class={chatTab()}>对话</button>
      <button class={docTab()}>文书</button>
      <button class={citeTab()}>引用（{citeCount()}）</button>
    </div>
    <Show when={activeTab() === "chat"}>
      <ChatPanel state={renderState()} ... />  // flex: 1, full width
    </Show>
    <Show when={activeTab() === "doc"}>
      <DocPreview state={renderState()} ... /> // flex: 1, full width
    </Show>
    <Show when={activeTab() === "cite"}>
      <CitationPanel state={renderState()} />  // full width, not overlay
    </Show>
  </div>
</WorkspacePage>
```

### Workspace Component Usage

The web app uses the ui-core `Workspace` component on desktop (which orchestrates ChatPanel + DocPreview + CitationPanel with splitter). On mobile, the web app provides its own tab-based layout that renders the same ui-core components in a stacked/tabbed arrangement.

**EventStreamStore wiring:**

```tsx
const stream = createEventStream({ client: gateway, runId: currentRunId() });
stream.streamEvents();  // starts SSE consumption
const state = stream.state();  // reactive RenderState signal

<ChatPanel state={state()} onSend={handleSend} onClarificationSubmit={handleClarify} onFeedback={handleFeedback} />
<DocPreview state={state()} />
<CitationPanel state={state()} />
```

### Panel Arrangement Summary

| Panel | Desktop | Mobile |
|-------|---------|--------|
| ChatPanel | Left, 500px, resizable via splitter | Full width, "对话" tab |
| DocPreview | Right, flex: 1, side-by-side with chat | Full width, "文书" tab (hidden until artifact exists) |
| CitationPanel | Overlay, 410px, slides from right | Full width, "引用" tab |
| DraftingProgressSteps | Inside ChatPanel thread | Inside ChatPanel thread |
| DocDraftingLoader | Inside DocPreview area | Inside "文书" tab |
| Composer | Bottom of ChatPanel | Bottom of "对话" tab, safe-area padding |

---

## Navigation

### Router Structure

```
@solidjs/router
├── /login              → LoginPage           (public, no auth required)
├── /                   → AppLayout > HomePage (authenticated)
└── /workspace/:convId  → AppLayout > WorkspacePage (authenticated)
```

**Route definitions:**

```tsx
<Router>
  <Route path="/login" component={LoginPage} />
  <Route path="/" component={AppLayout}>
    <Route path="/" component={HomePage} />
    <Route path="/workspace/:conversationId" component={WorkspacePage} />
  </Route>
</Router>
```

### Navigation Flow

```
┌─────────┐     ┌─────────┐     ┌───────────────────┐
│  Login  │────→│  Home   │────→│  Workspace        │
│ /login  │     │  /      │     │  /workspace/:id   │
└─────────┘     └─────────┘     └───────────────────┘
     ↑               │                    │
     │               │                    │
     │ (logout)      │ (click conversation)│
     │               │                    │
     └───────────────┴────────────────────┘
                      (back to home via TitleBar brand click)
```

### Desktop Navigation

| Action | Trigger | Result |
|--------|---------|--------|
| Go to home | Click brand seal/name in TitleBar | `navigate("/")` |
| Open conversation | Click conversation in sidebar | `navigate("/workspace/{id}")` |
| New conversation | Click "new" button in sidebar or starter on home | Create session → `navigate("/workspace/{newId}")` |
| Go to workspace from home | Click "开始起草" or type card | Create session → `navigate("/workspace/{newId}")` |
| Logout | (Future: user menu in TitleBar) | `auth.logout()` → `navigate("/login")` |

### Mobile Navigation

| Action | Trigger | Result |
|--------|---------|--------|
| Open conversation list | Tap hamburger menu (☰) in TitleBar | Drawer overlay opens |
| Close conversation list | Tap backdrop, tap conversation, or tap close | Drawer overlay closes |
| Go to home | Tap brand in TitleBar | `navigate("/")` |
| Back from workspace | Tap back arrow (←) in TitleBar | `navigate("/")` (back to home) |
| New conversation | Tap "new" in drawer or starter on home | Create session → `navigate("/workspace/{newId}")` |

**Mobile back button:** The mobile TitleBar shows a back arrow (←) when on the workspace page (`screen === "workspace"`). Tapping it navigates to home. This replaces the desktop breadcrumb pattern.

**Mobile drawer toggle:** The hamburger menu button (☰) in the mobile TitleBar toggles the `drawerOpen()` signal. When open, a backdrop overlay appears behind the drawer. Tapping the backdrop closes the drawer.

### Deep Linking

The router supports deep linking:
- `/login` — direct login URL
- `/` — home page (requires auth, redirects to `/login` if unauthenticated)
- `/workspace/{conversationId}` — specific conversation (requires auth)

When a user navigates directly to `/workspace/{id}` and the conversation doesn't exist or belongs to another tenant, the Gateway returns 404/403, and the web app shows an error state with a "返回首页" (back to home) link.

---

## Mobile Touch UX

### Touch Targets

All interactive elements have a minimum 44×44px touch area on mobile (<768px):

| Element | Desktop size | Mobile min size | Implementation |
|---------|-------------|-----------------|----------------|
| Send button | 8px×16px padding | 44px min-height | `@media (max-width: 767px) { .send-btn { min-height: 44px; } }` |
| Login button | 44px height | 44px height | Already 44px |
| Theme dots | 18px | 24px (with padding) | `@media (max-width: 767px) { .theme-dot { width: 24px; height: 24px; } }` |
| Clarification options | 30px min-height | 44px min-height | `@media (max-width: 767px) { .clarify-option { min-height: 44px; } }` |
| Type cards | Standard | 44px min-height | Already larger than 44px |
| Conversation rows | 66px min-height | 66px min-height | Already sufficient |
| Citation tabs | 8px×14px padding | 44px min-height | `@media (max-width: 767px) { .cp-tab { min-height: 44px; } }` |
| Hamburger menu | 30px | 44px | `@media (max-width: 767px) { .tb-conv-list { width: 44px; height: 44px; } }` |
| Back button | 30px | 44px | Same as hamburger |
| Doc export button | 7px×13px padding | 44px min-height | `@media (max-width: 767px) { .dbtn { min-height: 44px; } }` |

### Responsive Font Sizes

| Element | Desktop | Mobile | Reason |
|---------|---------|--------|--------|
| Base body | 14px | 16px | Prevent iOS auto-zoom on input focus |
| Chat prose (`.prose`) | 13.5px | 15px | Readability on small screens |
| User bubble (`.bubble-user`) | 13.5px | 15px | Readability |
| Composer textarea | 13.5px | 16px | Prevent iOS auto-zoom |
| Home greeting h1 | 34px | 28px | Fit on narrow screens |
| Home subtitle | 15px | 14px | Fit on narrow screens |
| Section heading h2 | 17px | 16px | Slight reduction |
| Type card h3 | 15px | 14px | Slight reduction |
| Type card p | 12px | 12px | No change (already small) |
| Conversation row title | 14px | 14px | No change |
| Citation card title | 15px | 14px | Slight reduction |

### No Horizontal Scroll

**Guarantee:** No horizontal scroll on any page at any viewport width <768px.

**Implementation:**
- `overflow-x: hidden` on `.app` container
- `min-width: 0` on all flex children
- `max-width: 100%` on content containers
- Document sheet: `width: min(calc(660px * var(--doc-scale)), 100%)` on mobile — sheet scales down to fit
- User message bubbles: `max-width: 86%` (already in `molv-base.css`)
- Code blocks in markdown: `overflow-x: auto` within the code block container (contained scroll, not page scroll)
- Wide document tables: `overflow-x: auto` within the DocPreview scroll container (contained scroll)

### Swipe Gestures

**No custom swipe gestures in Phase 93.** The drawer opens via hamburger button tap. Document preview uses native browser scroll and pinch-to-zoom. Custom gestures (swipe-to-open drawer, swipe between conversations) are deferred to post-V3.

### iOS Safari Considerations

| Issue | Solution |
|-------|----------|
| Viewport height (100vh includes URL bar) | `height: 100dvh` (dynamic viewport height) with `100vh` fallback |
| Notch / safe area | `padding-top: env(safe-area-inset-top)`, `padding-bottom: env(safe-area-inset-bottom)` |
| Input focus auto-zoom | `font-size: 16px` on all text inputs and textareas on mobile |
| Pull-to-refresh | `overscroll-behavior: none` on `.app` container |
| Elastic scroll | `-webkit-overflow-scrolling: touch` on scroll containers (`.thread`, `.doc-scroll`, `.conversation-list`) |
| 300ms tap delay | `touch-action: manipulation` on interactive elements |

### Viewport Meta Tag

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=5" />
```

- `viewport-fit=cover` — extends into safe area, padding handles insets
- `maximum-scale=5` — allows pinch-to-zoom for accessibility (don't disable zoom)
- `initial-scale=1` — no zoom on load

---

## Copywriting

All UI text is in **Chinese** (per `lawyer-desktop/AGENTS.md`: "UI text: Chinese"). This section covers web-app-specific copy not already defined in the Phase 92 UI-SPEC copywriting contract.

### Login Page

| Element | Copy |
|---------|------|
| Page title | `登录 · 墨律 InkStatute` |
| Brand name | `墨律 InkStatute` |
| Username label | `用户名` |
| Password label | `密码` |
| Token label (token mode) | `访问令牌` |
| Login button | `登 录` |
| Error — invalid credentials | `用户名或密码错误` |
| Error — network failure | `无法连接服务器，请检查网络` |
| Error — session expired | `会话已过期，请重新登录` |
| Error — server error | `服务器暂时不可用，请稍后重试` |
| Dev auto-login hint | `开发模式：自动登录中…` |

### Home Page

| Element | Copy |
|---------|------|
| Greeting (morning, <12:00) | `早上好，律师` |
| Greeting (afternoon, 12:00–18:00) | `下午好，律师` |
| Greeting (evening, ≥18:00) | `晚上好，律师` |
| Subtitle | `今天需要起草什么文书？` |
| Section: document types | `文书类型` |
| Section: recent conversations | `最近对话` |
| Recent conversations empty | `还没有对话记录，开始第一次起草吧` |
| View all conversations | `查看全部` |

### Navigation Labels

| Element | Copy |
|---------|------|
| Mobile tab: chat | `对话` |
| Mobile tab: document | `文书` |
| Mobile tab: citations | `引用（{count}）` |
| Mobile tab: citations (empty) | `引用` |
| Back button (mobile) | (icon only, `aria-label="返回"`) |
| Hamburger menu | (icon only, `aria-label="打开对话列表"`) |
| Close drawer | (icon only, `aria-label="关闭对话列表"`) |
| New conversation | `新建对话` |

### Error Messages (web-specific)

| Scenario | Copy |
|----------|------|
| Session invalid (401 on page load) | `会话已过期，请重新登录` (redirect to /login) |
| Conversation not found (404) | `对话不存在或已被删除` |
| Conversation access denied (403) | `无权访问此对话` |
| Gateway unreachable | `无法连接服务器，请检查网络后重试` |
| SSE connection lost | `连接中断，正在重连…` (from Phase 92 copywriting) |
| SSE reconnection failed | `重连失败，请刷新页面` |
| Upload failed | `文件上传失败，请重试` |
| Artifact download failed | `下载失败，请重试` (from Phase 92 copywriting) |

### Loading States

| Scenario | Copy |
|----------|------|
| App init (checking session) | `加载中…` (from `App.css` loading overlay) |
| Login submitting | (button shows loading state, no text change) |
| Creating conversation | (no explicit loading text — navigation happens quickly) |
| Loading conversation history | (skeleton or spinner in conversation list) |

---

## Accessibility

### Keyboard Navigation

The web app inherits all keyboard navigation from ui-core components (documented in Phase 92 UI-SPEC §Accessibility). Web-specific additions:

| Element | Key | Action |
|---------|-----|--------|
| Login form | `Enter` (in password field) | Submit login |
| Login form | `Tab` | Navigate between fields |
| Mobile tab toggle | `←` / `→` | Switch between 对话/文书/引用 tabs |
| Mobile drawer (open) | `Escape` | Close drawer |
| Route navigation | Browser back/forward | Standard browser history navigation |

### ARIA Labels (web-specific additions)

| Element | `aria-label` | Notes |
|---------|-------------|-------|
| Hamburger menu button | `打开对话列表` | Icon-only button |
| Back button (mobile) | `返回` | Icon-only button |
| Mobile tab toggle | `role="tablist"` | Container |
| Mobile tab: chat | `role="tab"`, `aria-selected` | |
| Mobile tab: document | `role="tab"`, `aria-selected`, `aria-disabled` (when no artifact) | |
| Mobile tab: citations | `role="tab"`, `aria-selected` | |
| Login form | `role="form"`, `aria-label="登录表单"` | |
| Login error message | `role="alert"` | Announced on appearance |
| App loading overlay | `aria-busy="true"`, `aria-label="加载中"` | |
| Drawer backdrop | `aria-hidden="true"` | Not announced |

### Focus Management

| Scenario | Behavior |
|----------|----------|
| Login page load | Focus username input |
| Login error | Focus returns to username input |
| Login success | Focus moves to home page starter input |
| Mobile drawer open | Focus moves to drawer search input or first conversation |
| Mobile drawer close | Focus returns to hamburger menu button |
| Mobile tab switch | Focus moves to active tab content |
| Route change (home → workspace) | Focus moves to composer textarea |
| Route change (workspace → home) | Focus moves to starter input |

### Screen Reader Considerations

- **Route changes:** Use `aria-live="polite"` on a route announcer element to announce page transitions (e.g., "首页", "工作区 — 合同审查")
- **Loading overlay:** `aria-busy="true"` on app root during session check
- **Login errors:** `role="alert"` on error message container for immediate announcement
- **Mobile tabs:** `role="tablist"` with `role="tab"` children, `aria-selected` on active tab
- **Drawer:** `role="dialog"` with `aria-label="对话列表"` when open, `aria-modal="true"`
- **Document preview (mobile):** `aria-label="文书预览"` on the DocPreview container

### Color Contrast

Inherited from Phase 92 UI-SPEC §Accessibility §Color Contrast:
- All three themes have WCAG AAA contrast for primary text (`--ink` on `--app-bg`)
- `--muted` colors are acceptable for large text/labels but not body text
- `--ink-soft` should be used for secondary body text
- The web app adds no new color combinations — all colors come from ui-core tokens

---

## UI Considerations

> State coverage for each page — loading, error, empty, success states.
> Component-level state coverage is inherited from Phase 92 UI-SPEC §UI Considerations (14 covered, 2 backstop).
> This section covers web-app-specific page-level states.

Applicable state considerations resolved: 12 covered, 0 backstop, 0 unresolved

| Category | Page/Element | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| loading | App init (session check) | ✅ covered | Full-screen loading overlay with spinner + "加载中…" text, `aria-busy="true"` |
| loading | Login submit | ✅ covered | Button shows `opacity: .65; cursor: progress`, inputs disabled |
| loading | Home page (conversation list) | ✅ covered | Skeleton rows or spinner in recent conversations section while `GET /v1/sessions` is in flight |
| loading | Workspace (SSE connecting) | ✅ covered | WorkflowNotice shows "正在处理" with pulsing dot (from Phase 92) |
| error | Login — invalid credentials | ✅ covered | Error text below button: "用户名或密码错误", `role="alert"`, focus returns to username |
| error | Login — network failure | ✅ covered | Error text: "无法连接服务器，请检查网络", `role="alert"` |
| error | Workspace — conversation not found | ✅ covered | Error state with "对话不存在或已被删除" + "返回首页" link |
| error | Workspace — SSE reconnection | ✅ covered | Toast: "连接中断，正在重连…" (from Phase 92), EventStreamStore auto-reconnects with Last-Event-ID |
| error | Workspace — SSE reconnection failed | ✅ covered | Toast: "重连失败，请刷新页面", manual refresh needed |
| empty | Home — no conversations | ✅ covered | "还没有对话记录，开始第一次起草吧" in recent conversations section |
| empty | Workspace — no artifact yet | ✅ covered | DocPreview shows DocDraftingLoader skeleton (from Phase 92); mobile "文书" tab disabled |
| success | Login → redirect | ✅ covered | AuthContext stores session, `navigate("/")`, home page loads |

<!-- Status vocabulary:
     ✅ covered   → a plain truth string lifted into must_haves.truths
     🧪 backstop  → a flat scalar { statement, verification: backstop }; at verify time, no explicit
                    evidence → insufficient_spec → human_needed (never a silent pass)
     ⚠ unresolved → an explicit planner assumption (surfaced, never silently dropped)
     Rows are REPLACED (not appended) on a probe re-run — idempotent. -->

---

## Adapter Wiring

The web app provides concrete implementations of ui-core adapter interfaces. These are not UI concerns per se, but they affect how UI components behave in the browser.

| Adapter | Web Implementation | UI Impact |
|---------|-------------------|-----------|
| `FileAdapter` | `open()`: `<input type="file" multiple>` dialog; `save()`: `<a download={filename} href={blobUrl}>` | File open uses browser dialog (no native path); save uses download attribute |
| `DropAdapter` | `classifyDroppedPaths()`: `DataTransferItemList` → file objects (no real paths in browser) | Drag-drop works for file objects, not OS paths |
| `AppInfoAdapter` | `getVersion()`: reads `package.json` version via Vite import; no update check | TitleBar shows web version, no update banner |
| `WorkspaceAdapter` | `listFiles()`: returns empty array (no local FS in browser) or Gateway-backed listing | @-mention autocomplete has no local files; only Gateway resources if available |
| `DocumentParser` | Calls Gateway API or client-side parse using ui-core `legalDocument.ts` utils | DocPreview parses document JSON client-side |
| `WindowAdapter` | **Not provided** — `AdapterContextValue.window` is optional | TitleBar hides window controls (no traffic lights, no min/max/close) |

### WindowAdapter Impact on TitleBar

The ui-core `TitleBar` component uses `WindowAdapter` for window controls (traffic lights, minimize, maximize, close). In the web app, `WindowAdapter` is not provided, so the TitleBar:
- Hides traffic light dots (no `.tb-traffic`)
- Hides window control buttons (no `.tb-win-ctrls`)
- Shows only: brand, breadcrumbs (desktop) or back button (mobile), theme switcher, menu button (mobile)

The TitleBar component should conditionally render window controls based on whether `WindowAdapter` is available in the `AdapterContext`.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| `@inkstatute/ui-core` | 17 components + 2 utils + themes | `workspace:*` protocol — local package, no registry risk |
| `@solidjs/router` | `Router`, `Route`, `Navigate`, `useNavigate` | Official SolidJS router, npm package |
| `solid-markdown` | Markdown rendering | Peer dependency from ui-core, provided by web app |
| `remark-gfm` | GitHub-flavored markdown | Peer dependency from ui-core |
| `highlight.js` | Code syntax highlighting | Peer dependency from ui-core |
| Google Fonts | Noto Serif SC, Noto Sans SC, Newsreader, Spline Sans Mono | `@import url(...)` in `molv-tokens.css` — loaded from Google CDN |

**No third-party component registries used.** All UI components come from `@inkstatute/ui-core` (hand-written SolidJS). No shadcn/radix/base-ui dependency. The only new dependency is `@solidjs/router` (official SolidJS routing library).

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS — login labels, home page text, navigation labels, error messages, loading states documented in Chinese
- [x] Dimension 2 Visuals: PASS — app shell layout (desktop + mobile), login page, home page, workspace layout, mobile tab toggle documented with CSS values
- [x] Dimension 3 Color: PASS — inherits 墨律 three-theme system from Phase 92, no new colors
- [x] Dimension 4 Typography: PASS — responsive font sizes documented for desktop and mobile, iOS auto-zoom prevention
- [x] Dimension 5 Spacing: PASS — responsive padding, touch targets (44px min), safe-area insets documented
- [x] Dimension 6 Registry Safety: PASS — only `@solidjs/router` added, all UI from ui-core, no third-party component registries
