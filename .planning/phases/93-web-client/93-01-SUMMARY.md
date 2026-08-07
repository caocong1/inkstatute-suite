---
phase: 93
plan: 01
title: "Wave 1 Tracer — apps/web scaffold, Gateway login endpoint, auth flow, home page with conversation list"
wave: 1
requirements:
  - UI-04
tasks_completed: 6
commits:
  - cc5c8a8: "feat(93-01): scaffold apps/web + register gate — Vite SPA, solid-router, workspace:* deps, dev proxy"
  - 160369e: "feat(93-01): Gateway POST /v1/auth/login — unauthenticated session creation, dev-mode cookie (no Secure flag)"
  - 5572872: "feat(93-01): web adapter implementations — FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter, DocumentParser"
  - 2aa6de1: "feat(93-01): AuthContext + ConversationContext + gateway config + App shell with router and route guard"
  - 92bf3d2: "feat(93-01): LoginPage + HomePage + WorkspacePage tracer — login → home → workspace navigation proven"
  - 53fa743: "test(93-01): tracer integration test — login → home → workspace slice verified, all 33 gates green"
tests:
  web_vitest: 21
  gateway_login: 8
  total_new: 29
gates: 33
status: complete
self_check: PASSED
---

# Plan 93-01 Summary — Wave 1 Tracer

## Goal

Create the `apps/web` application scaffold and prove the end-to-end vertical slice: login → auth context → home page with conversation list → click a conversation → see workspace shell. This is the minimal tracer that proves the web app builds, the Gateway login endpoint works, the auth flow (cookie-based session) functions, `@solidjs/router` routing works, and `@inkstatute/ui-core` components render in a browser context — all without writing any chat UI code.

## Tasks Executed

### Task 93-01-01: Scaffold apps/web + register gate
- Created `apps/web/` directory structure with `src/`, `tests/`, config files
- `package.json` with `@inkstatute/web`, `workspace:*` deps for ui-core and platform-sdk-ts, `@solidjs/router`
- `tsconfig.json` with strict mode, solid-js JSX, path mappings for workspace packages
- `vite.config.ts` with vite-plugin-solid, debug shim, dev proxy `/v1` → Gateway, vitest config
- `index.html` with viewport meta including `viewport-fit=cover`
- `src/main.tsx` with `@inkstatute/ui-core/themes` import
- `tests/test_web.py` Python gate wrapper (scaffold + vitest runner)
- Added `"apps/web"` to root `package.json` workspaces (additive)
- Registered `web` gate in `scripts/run_v2_gates.py` (33 gates total)
- Updated `test_audit_v2_requirements.py` gate count assertion 32 → 33
- **Commit:** `cc5c8a8`

### Task 93-01-02: Gateway POST /v1/auth/login endpoint
- Created `services/gateway/src/gateway/login.py` with `GatewayLoginHandler`
- Dev mode (`rbac_enabled=False`): accepts any credentials, uses `SameSite=Lax` cookie without `Secure` flag
- RBAC mode (`rbac_enabled=True`): validates token against static token, 401 on invalid
- Added `OPERATION_LOGIN` constant and route parsing for `POST /v1/auth/login`
- Modified `dispatch()` to check login BEFORE `require_auth` — scoped bypass for exactly one route
- Added `rbac_enabled` field to `GatewayConfig`
- Created `services/gateway/tests/test_login.py` with 8 test cases
- **Commit:** `160369e`

### Task 93-01-03: Web adapters
- `webFileAdapter.ts`: Browser file open (hidden `<input type="file">`) and save (download link)
- `webDropAdapter.ts`: `DataTransferItemList` → `DroppedPath[]` (browsers don't expose real paths)
- `webAppInfoAdapter.ts`: `getVersion()` returns `"0.1.0"`, `checkForUpdate()` returns `null`
- `webWorkspaceAdapter.ts`: `listFiles()` returns empty array (no local FS in browser)
- `webDocumentParser.ts`: Uses ui-core's `extractLegalDocumentJson()` + `markdownToLegalDocument()`
- `webAdapters.ts`: Barrel assembling `AdapterContextValue` with all 5 adapters, `window` undefined
- 13 adapter unit tests
- **Commit:** `5572872`

### Task 93-01-04: AuthContext + ConversationContext + App shell
- `src/config/gateway.ts`: Single `PlatformApiClient` instance with `baseUrl` from `VITE_GATEWAY_URL || ""`
- `src/contexts/AuthContext.tsx`: `AuthProvider` with `isAuthenticated()`, `login()`, `logout()`, `loading()` signals; probes Gateway on mount via `POST /v1/auth/login`
- `src/contexts/ConversationContext.tsx`: `ConversationProvider` with `conversations()`, `createConversation()`, `refreshConversations()`; uses `gateway.createSession()`
- `src/App.tsx`: `AuthProvider` → `AdapterContext.Provider` → `ConversationProvider` → `Router` with 3 routes
- `src/layouts/AppLayout.tsx`: `TitleBar` + `ConversationDrawer` sidebar + route guard (`<Show>` with `<Navigate href="/login" />`)
- 4 auth-context tests
- **Commit:** `2aa6de1`

### Task 93-01-05: LoginPage + HomePage + WorkspacePage
- `LoginPage.tsx`: Full-screen centered login card with username/password (or token mode), theme switcher, error handling, dev auto-login
- `HomePage.tsx`: Uses ui-core `HomePage` component with `onStart` → `createConversation()` → navigate to workspace; recent conversations section
- `WorkspacePage.tsx`: Tracer shell showing conversation ID placeholder (full chat panel wiring is Plan 93-02)
- `app-shell.css`: Login page CSS using `var(--*)` tokens only, layout CSS custom properties
- Vite build produces `dist/index.html` + `dist/assets/*.js`
- **Commit:** `92bf3d2`

### Task 93-01-06: Tracer verification
- `tests/tracer.test.tsx`: 3 integration tests (login → home → workspace navigation, route guard redirect, adapter context)
- All 21 web vitest tests pass
- All 33 gates green
- Vite build succeeds, TypeScript compiles
- Zero chat UI code in web app shell (grep verified)
- **Commit:** `53fa743`

## Self-Check

| Criterion | Status |
|-----------|--------|
| All tasks executed and committed | ✅ PASSED |
| All acceptance_criteria PASS | ✅ PASSED |
| apps/web scaffold created (package.json, vite.config.ts, index.html, tsconfig) | ✅ PASSED |
| Gateway login endpoint (POST /v1/auth/login) implemented | ✅ PASSED |
| Auth flow works (login → cookie → authenticated requests) | ✅ PASSED |
| Home page renders with conversation list | ✅ PASSED |
| Router works (login → home → workspace) | ✅ PASSED |
| web gate registered in run_v2_gates.py | ✅ PASSED |
| 33 gates green | ✅ PASSED |
| SUMMARY.md with Self-Check: PASSED | ✅ PASSED |

## Deviations

1. **solid-markdown version**: Plan specified `^0.1.0` but the package only has `2.x` versions. Changed to `^2.1.0` to match the installed version. No functional impact — ui-core peer dep is `>=0.1.0`.

2. **`@solidjs/router` Outlet**: Plan referenced `<Outlet />` but `@solidjs/router` v0.15.x doesn't export `Outlet`. Used `props.children` (the `RouteSectionProps` pattern) instead — functionally equivalent.

3. **GatewayConfig.rbac_enabled**: Plan referenced `config.rbac_enabled` but `GatewayConfig` didn't have this field. Added `rbac_enabled: bool = False` to `GatewayConfig` — additive, no existing field modified.

4. **Gate count assertion**: `test_audit_v2_requirements.py` asserted exactly 32 gates. Updated to 33 with `assertIn("web", gate_names)` — additive change.

## Files Created/Modified

### Created (new files)
- `apps/web/package.json`
- `apps/web/tsconfig.json`
- `apps/web/vite.config.ts`
- `apps/web/index.html`
- `apps/web/src/main.tsx`
- `apps/web/src/app-shell.css`
- `apps/web/src/App.tsx`
- `apps/web/src/shims/debug.ts`
- `apps/web/src/config/gateway.ts`
- `apps/web/src/contexts/AuthContext.tsx`
- `apps/web/src/contexts/ConversationContext.tsx`
- `apps/web/src/adapters/webFileAdapter.ts`
- `apps/web/src/adapters/webDropAdapter.ts`
- `apps/web/src/adapters/webAppInfoAdapter.ts`
- `apps/web/src/adapters/webWorkspaceAdapter.ts`
- `apps/web/src/adapters/webDocumentParser.ts`
- `apps/web/src/adapters/webAdapters.ts`
- `apps/web/src/layouts/AppLayout.tsx`
- `apps/web/src/pages/LoginPage.tsx`
- `apps/web/src/pages/HomePage.tsx`
- `apps/web/src/pages/WorkspacePage.tsx`
- `apps/web/tests/setup.ts`
- `apps/web/tests/__init__.py`
- `apps/web/tests/test_web.py`
- `apps/web/tests/scaffold.test.ts`
- `apps/web/tests/adapters.test.ts`
- `apps/web/tests/auth-context.test.tsx`
- `apps/web/tests/tracer.test.tsx`
- `services/gateway/src/gateway/login.py`
- `services/gateway/tests/test_login.py`

### Modified (existing files)
- `package.json` — added `"apps/web"` to workspaces
- `scripts/run_v2_gates.py` — added `web_src` variable and `web` gate entry
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — gate count 32 → 33
- `services/gateway/src/gateway/app.py` — added login route, operation constant, auth bypass, import
- `services/gateway/src/gateway/config.py` — added `rbac_enabled` field
