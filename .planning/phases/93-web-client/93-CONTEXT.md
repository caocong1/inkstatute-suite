---
phase: 93
slug: web-client
plan_count: TBD
subsystem: apps/web
tags: [solidjs, web, responsive, mobile, sse, gateway, auth, vite, playwright]
requires:
  - phase: 92
    reason: packages/ui-core — shared SolidJS components, event reducer, event stream store, adapters, themes
  - phase: 91
    reason: services/gateway — HTTP+SSE endpoints, auth middleware, session management, Last-Event-ID replay
provides:
  - apps/web — Responsive web client (desktop + mobile browser), using ui-core, communicating via Gateway HTTP/SSE
  - Web adapter implementations (FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter, DocumentParser)
  - Login page + auth context for web session management
  - Responsive layout shell with mobile drawer navigation
  - E2E test harness with fixture Gateway backend
affects:
  - services/gateway — may need a POST /v1/auth/login endpoint addition for web login flow
  - apps/web_chat — fully superseded (already deprecated in Phase 92)
  - apps/desktop — future consumer (Phase 94) can reuse web adapter patterns
key-files:
  - apps/web/package.json
  - apps/web/index.html
  - apps/web/src/main.tsx
  - apps/web/src/App.tsx
  - apps/web/src/adapters/webAdapters.ts
  - apps/web/src/adapters/webFileAdapter.ts
  - apps/web/src/adapters/webDropAdapter.ts
  - apps/web/src/adapters/webWorkspaceAdapter.ts
  - apps/web/src/adapters/webDocumentParser.ts
  - apps/web/src/contexts/AuthContext.tsx
  - apps/web/src/contexts/SessionContext.tsx
  - apps/web/src/pages/LoginPage.tsx
  - apps/web/src/pages/HomePage.tsx
  - apps/web/src/pages/WorkspacePage.tsx
  - apps/web/src/layouts/AppLayout.tsx
  - apps/web/src/layouts/MobileNav.tsx
  - apps/web/src/stores/conversationStore.ts
  - apps/web/src/config/gateway.ts
  - apps/web/vite.config.ts
  - apps/web/tsconfig.json
  - apps/web/e2e/flow.spec.ts
  - apps/web/e2e/fixtures/gateway-mock.ts
  - package.json (root — add apps/web to workspaces)
  - scripts/run_v2_gates.py (add web gate if needed)
key-decisions:
  - "App structure: SPA with @solidjs/router, three routes (login, home, workspace)"
  - "Responsive layout: CSS media queries at 768px breakpoint, drawer navigation on mobile, fluid grid"
  - "Auth flow: Login page POSTs to Gateway /v1/auth/login, session cookie HttpOnly, auth context wraps app"
  - "State management: SolidJS context for auth + conversation list, ui-core EventStreamStore for run state"
  - "Backend connection: Vite dev proxy /v1 → Gateway, configurable VITE_GATEWAY_URL env var"
  - "E2E testing: Playwright with fixture Gateway mock server, covers full lawyer flow"
  - "Build & deployment: Vite SPA build, static dist served by Gateway or standalone static server"
  - "Mobile touch UX: 44px min touch targets, responsive font sizes, mobile-optimized composer"
patterns-established:
  - "Web adapter pattern — concrete implementations of ui-core adapter interfaces for browser environment"
  - "Auth context — SolidJS context wrapping the app, redirects to /login when unauthenticated"
  - "Gateway URL configuration — VITE_GATEWAY_URL env var, dev proxy, runtime config injection"
  - "Responsive shell — desktop sidebar + mobile drawer, CSS media query at 768px"
  - "E2E fixture backend — Playwright test harness with mock Gateway returning fixture events"
requirements-targeted:
  - UI-04
coverage:
  requirements: 1
  success_criteria: 6
duration: TBD
completed: false
status: context-gathered
created: 2026-08-08
---

# Phase 93 — Web Client

<domain>

## What This Phase Delivers

A responsive web application (`apps/web`) that lawyers can open in any browser (desktop or mobile) to log in to 墨律, complete a full legal task, and see streaming replies, clarification cards, document artifacts, and citations — all powered by `packages/ui-core` and communicating with the platform via the Gateway HTTP/SSE API.

**Core principle (UI-06, enforced in Phase 92):** The web client contains **zero chat UI code**. All chat-related rendering comes from `@inkstatute/ui-core`. The web app's job is to provide the application shell (routing, auth, layout, adapter wiring), connect ui-core components to the Gateway, and handle responsive/mobile concerns.

**Requirements targeted:**
- **UI-04**: Web 客户端交付，响应式，桌面浏览器与移动浏览器均可用

**Success Criteria (must all be TRUE):**
1. `apps/web` exists, builds, and runs, using `packages/ui-core`, communicating via Gateway HTTP/SSE, with zero own chat UI code
2. Desktop browser: login → new session → send task (with attachment upload) → see streaming reply + five-phase progress → answer clarification card → download artifact → submit feedback
3. Mobile browser: same flow usable, responsive layout (no horizontal scroll, touch targets tappable, clarification card usable)
4. Reconnection with Last-Event-ID resumes event stream from correct position, no duplicate rendering
5. Sessions visible across devices (same tenant/user in another browser sees session list and history)
6. E2E tests cover the full main flow (using fixture backend, no real LLM dependency)

</domain>

<prior_decisions>

## Decisions Carried Forward from Earlier Phases

### From Phase 92 — Shared UI Core (COMPLETE)
- **`packages/ui-core` exists** with 18+ exported components: ChatPanel, ClarificationCard, DraftingProgressSteps, MessageFeedback, DocDraftingLoader, WorkflowProgressSteps, CitationPanel, DocPreview, MentionComposer, MentionMenu, Icons, TitleBar, HomePage, ConversationDrawer, AgentTracePanel
- **Event reducer** (`event-reducer.ts`, 13.8KB): Pure function `(state, event) → state` processing all 13 event types into `RenderState`
- **EventStreamStore** (`stores/eventStream.ts`): SSE consumer with SolidJS signals, Last-Event-ID reconnection, exponential backoff (1s→30s max)
- **Adapter interfaces** (`adapters/index.ts`): `FileAdapter`, `DropAdapter`, `AppInfoAdapter`, `WorkspaceAdapter`, `DocumentParser`, `WindowAdapter` — injected via `AdapterContext` SolidJS context
- **Theme system**: `molv-tokens.css` + `molv-base.css`, `data-theme="a|b|c"`, `useTheme()` store with localStorage persistence
- **Build**: Vite library mode, `@inkstatute/ui-core` package, `workspace:*` protocol, dual ESM/CJS output
- **PlatformApiClient** expanded with all Gateway endpoints: `createSession`, `createRun`, `streamRun`, `submitElicitation`, `submitApproval`, `getArtifact`, `upload`, `submitFeedback`, `listSkills`, `cancelRun`

### From Phase 91 — Unified Gateway (COMPLETE)
- **12 Gateway endpoints**: `/v1/sessions` (POST/GET), `/v1/sessions/{id}/runs` (GET), `/v1/runs` (POST), `/v1/runs/{id}` (GET/DELETE), `/v1/runs/{id}/events` (SSE), `/v1/runs/{id}/elicitation` (POST), `/v1/runs/{id}/approvals` (POST), `/v1/artifacts/{id}` (GET), `/v1/uploads` (POST), `/v1/feedback` (POST), `/v1/skills` (GET)
- **Auth**: `GatewayAuth` with `resolve_identity()` — Bearer token first, session cookie fallback; `rbac_enabled=False` uses static_token fallback; `require_auth()` raises 401 on failure
- **Session management**: `GatewaySessionManager` creates sessions via RBAC `SessionStore`, issues cookies (`HttpOnly; Secure; SameSite=Strict`), tracks `conversation_id` and `devices[]` for multi-device sync
- **SSE**: `GatewaySseStream` with output boundary enforcement, `encode_sse_event()` from `web_sse` package, in-memory event buffer per `run_id` for Last-Event-ID replay
- **No login endpoint**: The Gateway currently has no unauthenticated login endpoint — all 12 endpoints require auth. The old `lawyer-web-chat` had `POST /login` that accepted credentials and issued RBAC tokens.

### From PROJECT.md — Binding Architecture Decisions
- **共享 UI 沿用 SolidJS**: team already has SolidJS investment; ui-core is the single chat UI implementation
- **Chat UI must converge to single implementation**: web client imports from ui-core, writes zero chat UI
- **移动原生 App 推 V4**: mobile browser support only this milestone; shared UI designed to be packageable as app but not shipped
- **先自用（≤50 律师）**: single-firm scale; in-memory session store is sufficient

</prior_decisions>

<decisions>

## Auto-Selected Decisions for Gray Areas

[--auto] Selected all gray areas: App Structure & Routing, Responsive Layout, Authentication Flow, State Management, Backend Connection, E2E Testing, Build & Deployment, Mobile Touch UX.

### 1. App Structure & Routing

[auto] [App Structure & Routing] — Q: "Should the web client be a single-page app or multi-page, and which router?" → Selected: "SPA with @solidjs/router, three routes (login, home, workspace)" (recommended default)

**Rationale:** The web client is a single-page application built with SolidJS, matching the ui-core technology stack. `@solidjs/router` is the standard SolidJS routing library — it provides declarative route definitions, nested routes, and programmatic navigation via `useNavigate()`.

**Route structure:**
- `/login` — Login page (unauthenticated, POSTs credentials to Gateway)
- `/` — Home page (authenticated, shows greeting + starter prompts + doc type cards, uses ui-core `HomePage` component)
- `/workspace/:conversationId` — Workspace page (authenticated, shows chat panel + document preview + citation panel, uses ui-core `ChatPanel` + `DocPreview` + `CitationPanel`)

**App shell:** `App.tsx` wraps the router with `AuthContext.Provider` and `AdapterContext.Provider`. A route guard redirects to `/login` when no valid session is detected. The `TitleBar` component from ui-core provides the top bar (theme switch, conversation drawer toggle, home navigation).

**Why not multi-page?** The app is inherently a single workspace — there's no SEO benefit to multi-page. SPA provides instant navigation, preserves event stream state across route transitions, and matches the SolidJS/ui-core architecture.

**Why @solidjs/router over alternatives?** It's the official SolidJS router, maintained by the SolidJS team, with first-class support for SolidJS signals and Suspense. No reason to introduce a different router.

### 2. Responsive Layout

[auto] [Responsive Layout] — Q: "How to handle desktop vs mobile layouts?" → Selected: "CSS media queries at 768px breakpoint, drawer navigation on mobile, fluid grid layout" (recommended default)

**Rationale:** The ui-core components are desktop-first but use CSS custom properties and flexible layouts (`flex`, `min-width: 0`, `max-width: 100%`). The web client adds a responsive shell around these components.

**Breakpoint strategy:**
- **Desktop (≥768px)**: Sidebar layout — `ConversationDrawer` as a fixed left sidebar (280px), main content area fills remaining space. `TitleBar` with full controls.
- **Mobile (<768px)**: Drawer layout — `ConversationDrawer` hidden by default, opened via hamburger menu in `TitleBar`. Main content fills full width. `TitleBar` shows condensed controls (theme switch + menu button only, no window controls).

**Implementation:**
- `AppLayout.tsx`: Responsive container with CSS `@media (max-width: 767px)` and `@media (min-width: 768px)` queries
- `MobileNav.tsx`: Mobile-specific navigation overlay (drawer toggle, back button)
- CSS custom properties for layout dimensions: `--sidebar-width: 280px`, `--sidebar-width-collapsed: 0px`
- `ConversationDrawer`'s `open` prop is controlled by the layout — on desktop it's always open, on mobile it's toggleable

**No horizontal scroll:** All components use `overflow-x: hidden` at the layout level, `min-width: 0` on flex children, and `max-width: 100%` on content containers. The `DocPreview` component may need a horizontal scroll container for wide document tables — this is contained within the component, not the page.

**Font loading:** `molv-tokens.css` imports Google Fonts via `@import url(...)`. On mobile, this remains as-is (fonts load on demand). For production, consider self-hosting fonts for performance — deferred.

### 3. Authentication Flow

[auto] [Authentication Flow] — Q: "How should login and session management work for the web client?" → Selected: "Login page POSTs to Gateway /v1/auth/login, session cookie HttpOnly, AuthContext wraps app" (recommended default)

**Rationale:** The Gateway currently requires auth for all endpoints but has no login endpoint. The old `lawyer-web-chat` had a `POST /login` endpoint that accepted credentials and issued RBAC tokens + session cookies. Phase 93 adds a lightweight `POST /v1/auth/login` endpoint to the Gateway (small addition within Phase 93 scope) and a login page in the web client.

**Login flow:**
1. User navigates to `/login` — sees a login form (username/password or token input)
2. Form POSTs to `POST /v1/auth/login` on the Gateway
3. Gateway validates credentials (for self-hosted single-tenant: checks against configured static token or simple user table; for dev mode: accepts any credentials when `rbac_enabled=False`)
4. Gateway calls `GatewaySessionManager.create_session()` and returns `Set-Cookie` header (`HttpOnly; Secure; SameSite=Strict`)
5. Browser stores the cookie automatically; subsequent requests include it
6. Web client receives `{ session_id, tenant_id }` response, stores in `AuthContext`, redirects to `/`

**AuthContext:**
- SolidJS context providing `session_id`, `tenant_id`, `user_id`, `isAuthenticated()` signal
- `login(credentials)` — POSTs to Gateway, stores session info
- `logout()` — clears session, redirects to `/login`
- On app init, checks for existing cookie by calling `GET /v1/sessions/{id}` (the cookie is HttpOnly so JS can't read it directly; the app probes the Gateway to see if the session is valid)

**Gateway login endpoint (small addition):**
- `POST /v1/auth/login` — unauthenticated endpoint (bypasses `require_auth`)
- Accepts `{ username?, password?, token? }` in JSON body
- When `rbac_enabled=False`: accepts static token or any credentials, creates session with default tenant
- When `rbac_enabled=True`: validates credentials against RBAC token store, creates session
- Returns `{ session_id, tenant_id, set_cookie }` — same shape as `create_session` response

**Token storage:** Session cookie is `HttpOnly` — JavaScript cannot access it. The web client stores `session_id` and `tenant_id` in memory (SolidJS signal) for UI state, but the actual auth credential is the cookie managed by the browser. No localStorage token storage — the cookie is the sole credential.

**Dev mode:** When `rbac_enabled=False` (development), the login page can auto-submit with default credentials, or the web client can skip login entirely and use the static token as a Bearer header. The `VITE_DEV_AUTO_LOGIN` env var controls this behavior.

### 4. State Management

[auto] [State Management] — Q: "How to manage global state (auth, session list) vs local state?" → Selected: "SolidJS context for auth + conversation list, ui-core EventStreamStore for run state" (recommended default)

**Rationale:** SolidJS signals and context provide reactive state management without external libraries. The web client uses three context layers:

**1. AuthContext (global):**
- `isAuthenticated` signal, `session_id`, `tenant_id`, `user_id`
- `login()`, `logout()` methods
- Provided at the app root, wraps the router

**2. ConversationContext (global, authenticated):**
- `conversations` signal — list of conversations (from Gateway `GET /v1/sessions`)
- `currentConversationId` signal — active conversation
- `createConversation()` — calls `POST /v1/sessions`, refreshes list
- `refreshConversations()` — calls `GET /v1/sessions`, updates list
- Uses `PlatformApiClient` for all Gateway calls

**3. EventStreamStore (per-run, from ui-core):**
- Created by `createEventStream()` from `@inkstatute/ui-core`
- Manages `RenderState` (messages, phase, elicitation, artifacts, citations, run status)
- The workspace page creates an EventStreamStore per active run
- Last-Event-ID reconnection handled by the store

**No external state library:** SolidJS signals + context are sufficient. The app has minimal global state (auth + conversation list). Run state is scoped to the workspace page and managed by ui-core's EventStreamStore. No Redux/Zustand/Nanostores needed.

### 5. Backend Connection

[auto] [Backend Connection] — Q: "How does the web client connect to the Gateway (same origin, CORS, proxy)?" → Selected: "Vite dev proxy /v1 → Gateway, configurable VITE_GATEWAY_URL env var" (recommended default)

**Rationale:** The web client needs to talk to the Gateway HTTP/SSE API. In development, the Vite dev server and the Gateway run on different ports, so a proxy is needed to avoid CORS issues. In production, the web app can be served from the same origin as the Gateway (or via a reverse proxy).

**Development:**
- Vite dev server runs on `http://localhost:5173`
- Gateway runs on `http://localhost:8000` (or wherever configured)
- Vite `server.proxy` config proxies `/v1` → `http://localhost:8000`
- The web client uses relative URL `/v1/...` for all Gateway calls — the proxy handles routing
- SSE works through the proxy (Vite supports SSE proxying)

**Production:**
- `VITE_GATEWAY_URL` env var sets the base URL (defaults to empty string = same origin)
- If served from the same origin as Gateway: relative URLs work directly
- If served from a different origin: `VITE_GATEWAY_URL` is set to the Gateway URL, CORS must be configured on the Gateway (add `Access-Control-Allow-Origin` headers)
- The `PlatformApiClient` is constructed with `baseUrl = import.meta.env.VITE_GATEWAY_URL || ""`

**Configuration file:** `src/config/gateway.ts` exports a configured `PlatformApiClient` instance:
```typescript
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";
const baseUrl = import.meta.env.VITE_GATEWAY_URL || "";
export const gateway = new PlatformApiClient({ baseUrl });
```

**SSE and cookies:** The `PlatformApiClient.streamRun()` uses `fetch()` with `credentials: "include"` (or the default, since same-origin). The session cookie is sent automatically. For cross-origin, the Gateway needs `Access-Control-Allow-Credentials: true` and specific origin (not wildcard).

### 6. E2E Testing

[auto] [E2E Testing] — Q: "How to test the full web client flow end-to-end?" → Selected: "Playwright with fixture Gateway mock server, covers full lawyer flow" (recommended default)

**Rationale:** Playwright is the standard E2E testing framework for web applications. It supports Chromium, Firefox, and WebKit (Safari), can test responsive layouts by setting viewport size, and can intercept network requests.

**Test setup:**
- `apps/web/e2e/` directory with Playwright config and test specs
- A fixture Gateway mock server (`e2e/fixtures/gateway-mock.ts`) that:
  - Implements all 12 Gateway endpoints with fixture responses
  - Streams fixture SSE events (from ui-core's test fixtures) for a predefined run
  - Handles login, session creation, run creation, elicitation, feedback
  - Does NOT require a real LLM or agent backend
- Playwright launches the web app against the mock Gateway

**Test coverage (success criterion #6):**
1. Login flow: navigate to `/login`, submit credentials, redirect to `/`
2. New session: click "new conversation", see home page with starter prompts
3. Send task: type a prompt, click send, see user message in chat
4. Streaming reply: see assistant message streaming in (fixture SSE events)
5. Five-phase progress: see DraftingProgressSteps update as `phase.changed` events arrive
6. Clarification card: see ClarificationCard when `elicitation.requested` arrives, submit answers
7. Artifact download: see DocPreview when `artifact.created` arrives, click download
8. Feedback: click thumbs up/down, see feedback submitted
9. Reconnection: simulate SSE disconnect, verify Last-Event-ID resume
10. Mobile viewport: set viewport to 375x812 (iPhone), verify responsive layout, no horizontal scroll, touch targets visible

**Unit tests:** Vitest for web-specific adapter implementations and context logic. Reuses ui-core's vitest setup pattern.

### 7. Build & Deployment

[auto] [Build & Deployment] — Q: "How is the web app built and served?" → Selected: "Vite SPA build, static dist served by Gateway or standalone static server" (recommended default)

**Rationale:** The web client is a standard Vite SPA. The build produces static files (HTML, JS, CSS) that can be served by any static file server or by the Gateway itself.

**Build:**
- `vite build` produces `apps/web/dist/` with `index.html`, `assets/*.js`, `assets/*.css`
- Vite handles code splitting, tree shaking, and asset optimization
- `@inkstatute/ui-core` is consumed via `workspace:*` protocol — Vite resolves it at build time
- Type checking: `tsc --noEmit` before build

**Deployment options:**
1. **Gateway-served (recommended for self-hosted):** The Gateway adds a static file handler that serves `apps/web/dist/` for non-API routes. This keeps everything on one origin, avoiding CORS. The Gateway's `app.py` gets a fallback handler for `GET /` and static assets.
2. **Standalone static server:** `apps/web/dist/` served by nginx, Caddy, or any static server. `VITE_GATEWAY_URL` points to the Gateway. CORS configured on Gateway.
3. **Dev mode:** `vite dev` serves the app with HMR, proxy to Gateway.

**Root package.json:** Add `"apps/web"` to the `workspaces` array so bun links `@inkstatute/ui-core` and `@inkstatute/platform-sdk-ts` locally.

**Gate coverage:** Per AGENTS.md, every `packages/*/src` and `services/*/src` directory must be covered by a gate. `apps/web` is under `apps/`, not `packages/` or `services/`, so the gate-coverage meta-test does not strictly require it. However, a lightweight gate (typecheck + vitest) should be added for consistency. If the meta-test pattern is extended to `apps/*/src`, the web gate is already in place.

### 8. Mobile Touch UX

[auto] [Mobile Touch UX] — Q: "How to handle touch targets, gestures, and mobile-specific interactions?" → Selected: "44px min touch targets, responsive font sizes, mobile-optimized composer, no custom gestures" (recommended default)

**Rationale:** Mobile browser support is a success criterion (UI-04 #3: "移动浏览器下同一流程可用，布局响应式（无横向滚动、触摸目标可点、澄清卡片可用）"). The approach is CSS-first — adjust sizes and layout via media queries, not custom gesture handlers.

**Touch targets:**
- All interactive elements (buttons, links, option cards) have minimum 44×44px touch area on mobile
- Implemented via CSS: `@media (max-width: 767px) { button, .clickable { min-height: 44px; min-width: 44px; } }`
- The `ClarificationCard` options are already large enough (radio-like cards) — verify on mobile viewport
- The `MentionComposer` send button and attach button get enlarged touch areas on mobile

**Responsive font sizes:**
- Base font size: 14px desktop, 16px mobile (prevents iOS auto-zoom on input focus)
- Chat message font: 13.5px desktop, 15px mobile
- Title bar: condensed on mobile (hide window controls, show only theme switch + menu)

**Mobile-optimized composer:**
- The `MentionComposer` textarea expands vertically on mobile (more rows visible)
- The attach/menu buttons move to a compact toolbar above the keyboard
- `@-mention` autocomplete (`MentionMenu`) positions above the keyboard, not below

**No custom gestures:** Swipe-to-open drawer, pinch-to-zoom document preview, and other gesture-based interactions are NOT implemented in Phase 93. The drawer opens via a hamburger button tap. Document preview uses native browser scroll/zoom. Custom gestures can be added in Phase 94 (Desktop Client) or post-V3 if needed.

**iOS Safari considerations:**
- `viewport` meta tag: `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`
- Safe area insets: `env(safe-area-inset-top)`, `env(safe-area-inset-bottom)` for notch/home indicator
- 100vh issue: use `100dvh` (dynamic viewport height) where supported, fallback to `100vh`
- Input focus zoom: set `font-size: 16px` on inputs to prevent iOS auto-zoom

</decisions>

<canonical_refs>

## Canonical References for Downstream Agents

### ui-core (Phase 92, complete — the single chat UI source)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/index.ts` — All exports (components, stores, adapters, types, utils)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/stores/eventStream.ts` — EventStreamStore with SSE consumer + Last-Event-ID reconnection
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/event-reducer.ts` — Pure reducer for 13 event types → RenderState
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/adapters/index.ts` — Adapter interfaces (FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter, DocumentParser, WindowAdapter)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/ChatPanel.tsx` — Chat panel (props: state, onSend, onClarificationSubmit, onFeedback)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/HomePage.tsx` — Home page (props: onStart, pendingContextRefs, addContextRef, etc.)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/ConversationDrawer.tsx` — Conversation list (props: open, onClose, onOpenConversation, store)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/TitleBar.tsx` — Top bar (props: screen, onGoHome, onOpenConversations, onOpenSettings)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/DocPreview.tsx` — Document preview
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/CitationPanel.tsx` — Citation panel
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/components/ClarificationCard.tsx` — Clarification card
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/themes/molv-tokens.css` — Theme tokens (3 themes, data-theme="a|b|c")
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/src/themes/molv-base.css` — Base styles
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/package.json` — Package config (workspace:*, peer deps)

### platform-sdk-ts (Phase 92, complete — Gateway client SDK)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/platform-sdk-ts/src/index.ts` — PlatformApiClient with all 12 Gateway endpoints
- `/home/sorawatcher/workspace/inkstatute-suite/packages/platform-sdk-ts/src/events.ts` — TS bindings for 13 event types (RunEventEnvelope, all payload interfaces)

### Gateway (Phase 91, complete — HTTP+SSE backend)
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/app.py` — All 12 endpoint handlers, route parsing
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/auth.py` — GatewayAuth middleware (resolve_identity, require_auth, require_role, check_tenant)
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/sessions.py` — GatewaySessionManager (create_session, get_session, list_sessions, build_set_cookie_header)
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/sse.py` — GatewaySseStream with output boundary + Last-Event-ID replay
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/event_buffer.py` — In-memory event buffer per run_id
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/config.py` — GatewayConfig (from_env, default_tenant_id)

### Deprecated Prototype (reference only)
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web_chat/src/render.ts` — Deprecated DOM-free renderer (superseded by ui-core)
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web_chat/src/index.ts` — Deprecated entry

### Old lawyer-web-chat (login pattern reference)
- `/home/sorawatcher/workspace/inkstatute-suite/services/lawyer-web-chat/src/lawyer_web_chat/server.py` — Had `POST /login` endpoint with form-based login and RBAC token issuance

### Build & Workspace
- `/home/sorawatcher/workspace/inkstatute-suite/package.json` — Root workspace config (add apps/web)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/vite.config.ts` — Vite config pattern (vite-plugin-solid, library mode)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/ui-core/tsconfig.json` — TypeScript config pattern

### Gate Registration
- `/home/sorawatcher/workspace/inkstatute-suite/scripts/run_v2_gates.py` — Gate registration (add web gate if pattern extends to apps/)

### Project Decisions
- `/home/sorawatcher/workspace/inkstatute-suite/.planning/PROJECT.md` — Key Decisions (共享 UI 沿用 SolidJS, 移动原生 App 推 V4, 先自用)
- `/home/sorawatcher/workspace/inkstatute-suite/AGENTS.md` — Implementation Priorities #5: "extract before building apps/web or apps/desktop"

</canonical_refs>

<code_context>

## Reusable Assets and Patterns Found During Codebase Scouting

### ui-core Component API (ready to consume)

All components are exported from `@inkstatute/ui-core` and accept props driven by `RenderState` from the event reducer:

| Component | Key Props | Notes |
|-----------|-----------|-------|
| `ChatPanel` | `state: RenderState, onSend, onClarificationSubmit?, onFeedback?` | Main chat UI — messages, streaming, composer, workflow steps |
| `HomePage` | `onStart, pendingContextRefs, addContextRef, removeContextRef, addInlineMention, removeInlineMention` | Landing page with greeting + starter prompts + doc type cards |
| `ConversationDrawer` | `open, onClose, onOpenConversation, store: ConversationStore` | Conversation list with search, rename, delete |
| `TitleBar` | `screen: "home"\|"workspace", onGoHome, onOpenConversations, onOpenSettings` | Top bar with theme switch, window controls (via WindowAdapter) |
| `DocPreview` | Driven by `RenderState.artifacts` | Document preview with legal document model |
| `CitationPanel` | Driven by `RenderState.citations` | Citation verification panel |
| `ClarificationCard` | Driven by `RenderState.elicitation` | ask_user card (single/multi/free-text) |
| `DraftingProgressSteps` | Driven by `RenderState.phase` | Five-phase progress indicator |
| `MessageFeedback` | `messageId, rating, comment?` | Thumbs up/down feedback |

### Adapter Interfaces (must implement for web)

The web client must provide concrete implementations of these ui-core adapter interfaces:

| Interface | Web Implementation |
|-----------|-------------------|
| `FileAdapter` | `<input type="file">` for open, `<a download>` for save |
| `DropAdapter` | `DataTransferItemList` → file path classification (limited in browser — no real paths) |
| `AppInfoAdapter` | `getVersion()` reads `package.json` version; no update check (web) |
| `WorkspaceAdapter` | `listFiles()` returns empty or Gateway-backed file listing (no local FS in browser) |
| `DocumentParser` | Calls Gateway API to parse legal document JSON (or client-side parse using ui-core utils) |
| `WindowAdapter` | **Not provided** (web has no window controls) — `AdapterContextValue.window` is optional |

### EventStreamStore (from ui-core, ready to use)

```typescript
import { createEventStream } from "@inkstatute/ui-core";
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";

const client = new PlatformApiClient({ baseUrl: "" });
const stream = createEventStream({ client, runId: "run-123" });
stream.streamEvents(); // starts SSE consumption
stream.state(); // reactive RenderState signal
stream.stop(); // stops stream + reconnection
```

Features:
- Last-Event-ID reconnection with exponential backoff (1s → 30s max)
- Idempotent reducer — replayed events produce same state
- AbortController for clean cancellation
- Auto-reconnect when run status is non-terminal

### PlatformApiClient (from platform-sdk-ts, ready to use)

All 12 Gateway endpoints are available as async methods:
- `createSession(body)` → `{ session_id, tenant_id, set_cookie }`
- `createRun(body)` → run object
- `streamRun(run_id, lastEventID?)` → async iterable of `SseFrame`
- `submitElicitation(run_id, body)` → response
- `submitApproval(run_id, body)` → response
- `getArtifact(artifact_id)` → artifact download
- `upload(body)` → `{ attachment_ref }`
- `submitFeedback(body)` → response
- `listSkills()` → skills list
- `cancelRun(run_id)` → response
- `getSession(session_id)`, `listSessionRuns(session_id)`, `getRun(run_id)`

### Gateway Auth (existing pattern)

The Gateway's `GatewayAuth` class:
- `authenticate(headers)` → `AuthContext` (never raises, returns unauthenticated context on failure)
- `require_auth(headers)` → `AuthContext` (raises `GatewayAuthError` 401 on failure)
- `require_role(headers, allowed_roles)` → `AuthContext` (raises 403 on role mismatch)
- `check_tenant(ctx, resource_tenant_id)` → raises 403 on cross-tenant access

When `rbac_enabled=False`: uses `static_token` fallback (any request with the static token or no token gets a default admin identity). This is the dev mode.

### Gateway Session Management (existing pattern)

`GatewaySessionManager.create_session()`:
- Creates RBAC session via `SessionStore.create()`
- Issues cookie via `issue_session_cookie()` (HMAC-SHA256 signed)
- Returns `(session_id, cookie_value, GatewaySession)`
- Cookie: `HttpOnly; Secure; SameSite=Strict; Max-Age={ttl}`
- `GatewaySession` tracks `conversation_id` and `devices[]` for multi-device sync

### Existing CSS Patterns (from ui-core)

- Components use CSS custom properties (`var(--accent)`, `var(--surface)`, etc.) — no hardcoded colors
- `molv-base.css` has `.home-inner { max-width: 1040px; margin: 0 auto; padding: 64px 40px 80px; }`
- ChatPanel uses `max-width: calc(100% - 48px)` for message bubbles, `max-width: min(86%, 380px)` for user bubbles
- `@media (prefers-reduced-motion: reduce)` already in ChatPanel and AgentTracePanel CSS
- No `@media (max-width: ...)` breakpoints exist yet — Phase 93 adds these in the app layout CSS

### Root Workspace Config

Current `package.json` workspaces:
```json
{
  "workspaces": ["packages/platform-sdk-ts", "packages/ui-core"]
}
```
Phase 93 adds `"apps/web"` to this array.

### Deprecated web_chat Prototype

`apps/web_chat/src/render.ts` (263 lines) is a DOM-free render record system — a different approach from ui-core's SolidJS components. It's marked `@deprecated` and superseded. Phase 93 does NOT modify or remove it (retirement is Phase 104 / CONV-02).

</code_context>

<deferred>

## Deferred Ideas for Future Phases

1. **Settings panel** — The `SettingsPanel` (963 lines) and `SkillRefinementPanel` (390 lines) from lawyer-desktop are desktop-admin-specific. Deferred to Phase 94 (Desktop Client). The web client does not include settings UI in Phase 93.

2. **AgentTracePanel in production** — The `AgentTracePanel` (799 lines) is a developer-only trace viewer. It's available in ui-core but gated behind a dev flag in the web client. Not shown to end users in Phase 93.

3. **Custom gestures** — Swipe-to-open drawer, pinch-to-zoom document preview, swipe between conversations. Not implemented in Phase 93; native browser scroll/zoom is sufficient. Can be added post-V3.

4. **PWA / Service Worker** — Offline support via service worker is not in scope. The web client requires online connectivity. Offline read-only is a Phase 94 (Desktop Client) feature.

5. **Push notifications** — Browser push notifications for long-running tasks. Not in scope for Phase 93. Can be added post-V3.

6. **WebRTC / real-time collaboration** — Multi-user real-time document editing. Out of scope for V3.

7. **Self-hosted fonts** — `molv-tokens.css` imports Google Fonts via `@import url(...)`. For production performance, self-hosting fonts is better. Deferred — not a Phase 93 requirement.

8. **Internationalization (i18n)** — The UI is currently Chinese-only. i18n framework can be added post-V3 if needed.

9. **Accessibility (a11y) audit** — Basic accessibility (ARIA labels, keyboard navigation) should be included in Phase 93 implementation, but a full WCAG 2.1 AA audit is deferred.

10. **Performance optimization** — Code splitting, lazy loading of heavy components (DocPreview, AgentTracePanel), image optimization. Deferred — Vite's default build optimization is sufficient for ≤50 lawyers.

</deferred>
