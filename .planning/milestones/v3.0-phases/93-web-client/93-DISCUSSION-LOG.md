# Phase 93 — Web Client: Discussion Log

**Mode:** --auto
**Date:** 2026-08-08
**Phase:** 93 (Web Client)
**Requirements:** UI-04
**Depends on:** Phase 92 (Shared UI Core — COMPLETE)

---

## Context Loading

Read the following files for prior context:
- `.planning/PROJECT.md` — V3 architecture, key decisions, milestone state
- `.planning/REQUIREMENTS.md` — UI-04 requirement definition
- `.planning/STATE.md` — Phase 92 complete, 32 gates green, ready for Phase 93
- `.planning/ROADMAP.md` — Phase 93 success criteria (6 criteria)
- `AGENTS.md` — Binding architecture decisions, implementation priorities
- `.planning/phases/92-shared-ui-core/92-CONTEXT.md` — ui-core component inventory, adapter interfaces, event reducer, event stream store
- `.planning/phases/91-unified-gateway/91-CONTEXT.md` — Gateway endpoints, auth, SSE, session management

---

## Codebase Scouting

Scanned the following areas:
- `packages/ui-core/src/` — 18+ components exported, event reducer (13.8KB), event stream store with Last-Event-ID reconnection, adapter interfaces, theme system, utilities
- `packages/ui-core/src/index.ts` — Full export list (components, stores, adapters, types, utils)
- `packages/ui-core/src/adapters/index.ts` — 6 adapter interfaces (FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter, DocumentParser, WindowAdapter)
- `packages/ui-core/src/stores/eventStream.ts` — SSE consumer with SolidJS signals, exponential backoff reconnection
- `packages/ui-core/package.json` — `@inkstatute/ui-core`, workspace:*, Vite library mode, peer deps (solid-js, solid-markdown, remark-gfm, highlight.js)
- `packages/platform-sdk-ts/src/index.ts` — PlatformApiClient with all 12 Gateway endpoints, streamRun() async generator
- `packages/platform-sdk-ts/src/events.ts` — 13 event type TS bindings (RunEventEnvelope + all payload interfaces)
- `services/gateway/src/gateway/app.py` — 12 endpoints, route parsing, no login endpoint
- `services/gateway/src/gateway/auth.py` — GatewayAuth (resolve_identity, require_auth, require_role, check_tenant)
- `services/gateway/src/gateway/sessions.py` — GatewaySessionManager (create_session with cookie, multi-device tracking)
- `services/gateway/src/gateway/config.py` — GatewayConfig (from_env, default_tenant_id, enabled flag)
- `apps/web_chat/src/render.ts` — Deprecated DOM-free renderer (263 lines, superseded by ui-core)
- `apps/web/` — **DOES NOT EXIST** — Phase 93 creates it
- Root `package.json` — workspaces: [packages/platform-sdk-ts, packages/ui-core] — needs apps/web added
- CSS patterns — ui-core uses CSS custom properties, max-width/min-width constraints, @media (prefers-reduced-motion), but NO @media breakpoint queries for mobile

Key findings:
1. ui-core is complete and ready to consume — all chat UI is there
2. PlatformApiClient has all Gateway endpoints — ready to use
3. Gateway has NO login endpoint — needs a small addition for web auth flow
4. No router exists in ui-core — web app needs its own routing
5. No mobile breakpoints in ui-core CSS — web app adds responsive shell
6. apps/web does not exist — created from scratch in Phase 93

---

## Gray Area Selection

[--auto] Selected all gray areas: App Structure & Routing, Responsive Layout, Authentication Flow, State Management, Backend Connection, E2E Testing, Build & Deployment, Mobile Touch UX.

---

## Auto-Selected Decisions

### 1. App Structure & Routing

[auto] [App Structure & Routing] — Q: "Should the web client be a single-page app or multi-page, and which router?" → Selected: "SPA with @solidjs/router, three routes (login, home, workspace)" (recommended default)

**Options considered:**
- A) SPA with @solidjs/router, three routes (login, home, workspace) ← **SELECTED**
- B) Multi-page app with server-side rendering
- C) SPA with hash-based routing (no router library)

**Rationale:** SPA matches SolidJS/ui-core architecture. @solidjs/router is the official SolidJS router. Three routes cover the full lawyer flow. No SEO benefit from multi-page. Hash routing is unnecessary complexity.

---

### 2. Responsive Layout

[auto] [Responsive Layout] — Q: "How to handle desktop vs mobile layouts?" → Selected: "CSS media queries at 768px breakpoint, drawer navigation on mobile, fluid grid layout" (recommended default)

**Options considered:**
- A) CSS media queries at 768px breakpoint, drawer navigation on mobile, fluid grid ← **SELECTED**
- B) Separate mobile and desktop layouts (different component trees)
- C) CSS container queries (newer, less browser support)

**Rationale:** 768px is the standard tablet/mobile breakpoint. ui-core components are desktop-first but flexible. A responsive shell with media queries is the simplest approach. Separate layouts would duplicate code. Container queries have less browser support.

---

### 3. Authentication Flow

[auto] [Authentication Flow] — Q: "How should login and session management work for the web client?" → Selected: "Login page POSTs to Gateway /v1/auth/login, session cookie HttpOnly, AuthContext wraps app" (recommended default)

**Options considered:**
- A) Login page POSTs to Gateway /v1/auth/login, session cookie HttpOnly, AuthContext wraps app ← **SELECTED**
- B) Static token in localStorage, Bearer header for all requests
- C) OAuth/OIDC external provider

**Rationale:** The Gateway already has session management with HttpOnly cookies. Adding a lightweight `/v1/auth/login` endpoint is a small addition. HttpOnly cookies are more secure than localStorage tokens. OAuth is overkill for ≤50 lawyers in a single-firm deployment. The old lawyer-web-chat had a similar login pattern.

---

### 4. State Management

[auto] [State Management] — Q: "How to manage global state (auth, session list) vs local state?" → Selected: "SolidJS context for auth + conversation list, ui-core EventStreamStore for run state" (recommended default)

**Options considered:**
- A) SolidJS context for auth + conversation list, ui-core EventStreamStore for run state ← **SELECTED**
- B) External state library (Redux/Zustand/Nanostores)
- C) Prop drilling without context

**Rationale:** SolidJS signals + context provide reactive state management without external dependencies. The app has minimal global state (auth + conversation list). Run state is scoped to the workspace page and managed by ui-core's EventStreamStore. No need for Redux/Zustand.

---

### 5. Backend Connection

[auto] [Backend Connection] — Q: "How does the web client connect to the Gateway (same origin, CORS, proxy)?" → Selected: "Vite dev proxy /v1 → Gateway, configurable VITE_GATEWAY_URL env var" (recommended default)

**Options considered:**
- A) Vite dev proxy /v1 → Gateway, configurable VITE_GATEWAY_URL env var ← **SELECTED**
- B) Hardcoded Gateway URL, CORS on Gateway
- C) Same-origin only (Gateway serves the web app)

**Rationale:** Vite dev proxy avoids CORS in development. VITE_GATEWAY_URL env var allows flexible deployment. Same-origin is the recommended production deployment (Gateway serves static files), but the env var supports alternative deployments. SSE works through Vite proxy.

---

### 6. E2E Testing

[auto] [E2E Testing] — Q: "How to test the full web client flow end-to-end?" → Selected: "Playwright with fixture Gateway mock server, covers full lawyer flow" (recommended default)

**Options considered:**
- A) Playwright with fixture Gateway mock server, covers full lawyer flow ← **SELECTED**
- B) Cypress with real Gateway + fixture backend
- C) Manual testing only

**Rationale:** Playwright supports multiple browsers (Chromium, Firefox, WebKit), can set viewport size for mobile testing, and can intercept network requests. A fixture Gateway mock server avoids LLM dependency. Cypress is Chromium-only and heavier. Manual testing doesn't scale.

---

### 7. Build & Deployment

[auto] [Build & Deployment] — Q: "How is the web app built and served?" → Selected: "Vite SPA build, static dist served by Gateway or standalone static server" (recommended default)

**Options considered:**
- A) Vite SPA build, static dist served by Gateway or standalone static server ← **SELECTED**
- B) Next.js/SolidStart SSR
- C) CDN-hosted SPA with API Gateway

**Rationale:** Vite SPA build is the standard approach for SolidJS apps. Static files can be served by the Gateway (same-origin, no CORS) or any static server. SSR adds complexity without benefit for a ≤50 lawyer internal tool. CDN is overkill for self-hosted single-firm.

---

### 8. Mobile Touch UX

[auto] [Mobile Touch UX] — Q: "How to handle touch targets, gestures, and mobile-specific interactions?" → Selected: "44px min touch targets, responsive font sizes, mobile-optimized composer, no custom gestures" (recommended default)

**Options considered:**
- A) 44px min touch targets, responsive font sizes, mobile-optimized composer, no custom gestures ← **SELECTED**
- B) Custom gesture library (swipe, pinch, long-press)
- C) Mobile-native feel with framework7/ionic components

**Rationale:** CSS-first approach is simplest and most maintainable. 44px is the Apple HIG minimum touch target. Responsive font sizes prevent iOS auto-zoom. No custom gestures — native browser scroll/zoom is sufficient. Framework7/ionic would conflict with ui-core's SolidJS components.

---

## Summary

- **Gray areas selected:** 8 (all)
- **All decisions:** auto-selected recommended defaults
- **Key architectural choices:**
  - SPA with @solidjs/router (3 routes: login, home, workspace)
  - CSS media queries at 768px for responsive layout
  - Gateway `/v1/auth/login` endpoint addition + HttpOnly session cookie
  - SolidJS context for auth/conversation state, ui-core EventStreamStore for run state
  - Vite dev proxy + VITE_GATEWAY_URL env var for backend connection
  - Playwright E2E with fixture Gateway mock
  - Vite SPA build, static dist served by Gateway
  - CSS-first mobile UX (44px targets, responsive fonts, no custom gestures)
- **Gateway change required:** Add `POST /v1/auth/login` endpoint (small addition within Phase 93 scope)
- **Root package.json change:** Add `"apps/web"` to workspaces array
