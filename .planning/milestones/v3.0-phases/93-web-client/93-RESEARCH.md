---
phase: 93
slug: web-client
researched_at: 2026-08-08
researcher: auto
status: complete
---

# Phase 93 Research — Web Client

## 1. ui-core API Surface

The full export list from `packages/ui-core/src/index.ts` (186 lines). Everything the web client needs for chat UI is already exported — the web app writes **zero** chat UI code.

### Components (14 exported)

| Component | Export | Props Type | Source |
|-----------|--------|------------|--------|
| `ChatPanel` | `export { ChatPanel }` | `ChatPanelProps` | `./components/ChatPanel` |
| `ClarificationCard` | `export { ClarificationCard }` | `ClarificationCardProps` | `./components/ClarificationCard` |
| `DraftingProgressSteps` | `export { DraftingProgressSteps, DRAFTING_STEPS, phaseToActiveIndex, stepState }` | `DraftingProgressStepsProps` | `./components/DraftingProgressSteps` |
| `MessageFeedback` | `export { MessageFeedback }` | `MessageFeedbackProps` | `./components/MessageFeedback` |
| `DocDraftingLoader` | `export { DocDraftingLoader }` | `DocDraftingLoaderProps` | `./components/DocDraftingLoader` |
| `WorkflowProgressSteps` | `export { WorkflowProgressSteps, WorkflowNotice, ModeSwitchCard, WorkflowSuggestions }` | `WorkflowProgressStepsProps, ModeSwitchCardProps` | `./components/WorkflowProgressSteps` |
| `CitationPanel` | `export { CitationPanel }` | `CitationPanelProps` | `./components/CitationPanel` |
| `DocPreview` | `export { DocPreview }` | `DocPreviewProps` | `./components/DocPreview` |
| `MentionComposer` | `export { MentionComposer }` | `MentionComposerProps, MentionComposerApi` | `./components/MentionComposer` |
| `MentionMenu` | `export { MentionMenu }` | `MentionMenuProps` | `./components/MentionMenu` |
| `Icon, Icons` | `export { Icon, Icons }` | `IconName` | `./components/Icons` |
| `TitleBar` | `export { TitleBar }` | `TitleBarProps` | `./components/TitleBar` |
| `HomePage` | `export { HomePage }` | `HomePageProps` | `./components/HomePage` |
| `ConversationDrawer` | `export { ConversationDrawer }` | `ConversationDrawerProps` | `./components/ConversationDrawer` |
| `AgentTracePanel` | `export { AgentTracePanel }` | `AgentTracePanelProps` | `./components/AgentTracePanel` |

### Stores & Event Stream

| Export | Source | Notes |
|--------|--------|-------|
| `useTheme` + `ThemeVariant` | `./stores/theme` | `createSignal<"a"\|"b"\|"c">` with localStorage persistence, `applyTheme()` sets `data-theme` attribute |
| `createEventStream` + `EventStreamStore, EventStreamOptions` | `./stores/eventStream` | SSE consumer with SolidJS signals, Last-Event-ID reconnection, exponential backoff (1s→30s) |
| `useTrace` | `./stores/trace` | Trace store for AgentTracePanel |

### Event Reducer

| Export | Source | Notes |
|--------|--------|-------|
| `reduce` | `./event-reducer` | Pure function `(state, RunEventEnvelope) → RenderState` — processes all 13 event types |
| `initialState` | `./event-reducer` | Returns initial `RenderState` |
| `traceToolLabel` | `./event-reducer` | Maps tool names to Chinese display labels |
| `normalizeClarification` | `./event-reducer` | Maps `ElicitationRequestedPayload` → `ClarificationRequest` |
| `RenderState, ChatMessage` (types) | `./event-reducer` | Core state types |

### Adapter Interfaces (6 + context)

| Interface | Source | Web Implementation Needed |
|-----------|--------|--------------------------|
| `FileAdapter` | `./adapters` | `<input type="file">` for open, `<a download>` for save |
| `DropAdapter` + `DroppedPath` | `./adapters` | `DataTransferItemList` → file classification (limited in browser — no real paths) |
| `AppInfoAdapter` + `UpdateInfo` | `./adapters` | `getVersion()` reads `package.json`; no update check (web) |
| `WorkspaceAdapter` + `WorkspaceFile` | `./adapters` | `listFiles()` returns empty or Gateway-backed listing (no local FS) |
| `DocumentParser` | `./adapters` | Client-side parse using ui-core utils, or Gateway API |
| `WindowAdapter` | `./adapters` | **Not provided** for web — `AdapterContextValue.window` is optional |
| `AdapterContext` + `useAdapters` + `AdapterContextValue` | `./adapters` | SolidJS context for adapter injection |

### Legal Types & Utilities

| Export Category | Items |
|----------------|-------|
| Legal types | `TextSegment, DocParty, ArticleNote, ArticleBlock, Article, CitationVerification, CitationCard, CitationAuditItem, CitationAudit, DocMeta, LegalCitation, LegalParty, LegalClause, LegalSection, LegalDocumentModel, ParseLegalDocumentResponse, CitationGroups` |
| Legal document utils | `cnNum, extractLegalDocumentJson, splitMarkdownBlocks, modelToParties, modelToRecital, modelToArticles, modelToCitationGroups, modelToDocMeta, extractDraftOutputEnvelope, containsToolLeakage, isInstructionLikeTitle, sanitizeLlmDocumentContent, looksLikeLegalProse, isPublishableDocument, stripReportPreamble, markdownReportTitle, markdownToLegalDocument` + `DraftOutputEnvelope` type |
| Citation audit utils | `auditToCitationGroups, mergeAuditIntoGroups, auditSummaryLine, auditChecklistMarkdown` |
| Chat time utils | `parseTimeMs, shouldShowTimeDivider, formatTimeDivider, formatFullTime` |
| Citation grouping | `groupCitations` |
| Mention utils | `detectAtTrigger, filterMentionCandidates, buildMentionInsert, isRefMentioned, resolveInlineMentions, validateMentionPaths, serializeEditor` |
| Doc types | `DOC_TYPES, iconForConversationTitle` + `DocType` type |
| Evidence flow | `pathToRefAlias, extractDirectoryPaths, mergeDirectoryRefs` |
| Render utils | `renderSegs` + `RenderSegsOptions` |
| JSON highlight | `highlightJson, looksLikeJson, prettyJson` |
| Conversation title | `validateConversationTitle, CONVERSATION_TITLE_MIN, CONVERSATION_TITLE_MAX` |
| Conversation/trace types | `Conversation, ConversationStore, TraceKind, AgentTraceEvent, TraceUsage, TraceEntry, TraceTurn` |
| Context ref types | `ContextRefPayload` |

### Package Configuration

- **Package name**: `@inkstatute/ui-core` (private, `workspace:*`)
- **Exports**: `.` (main), `./themes` (CSS), `./events` (event types)
- **Peer deps**: `solid-js >=1.9.0`, `solid-markdown >=0.1.0`, `remark-gfm >=4.0.0`, `highlight.js >=11.0.0`
- **Direct dep**: `@inkstatute/platform-sdk-ts: workspace:*`
- **Build**: `vite build && tsc --emitDeclarationOnly` — dual ESM/CJS output
- **Vite config**: `vite-plugin-solid`, `debug` shim for `solid-markdown`, library mode with externalized peer deps

### CSS Patterns (from ui-core)

- All component CSS uses CSS custom properties (`var(--accent)`, `var(--surface)`, etc.) — no hardcoded colors
- `molv-base.css`: `.home-inner { max-width: 1040px; margin: 0 auto; padding: 64px 40px 80px; }`
- ChatPanel: `max-width: calc(100% - 48px)` for message bubbles, `max-width: min(86%, 380px)` for user bubbles, `overflow-x: auto`, `min-width: 0` on flex children
- `@media (prefers-reduced-motion: reduce)` exists in ChatPanel.css and AgentTracePanel.css
- **No `@media (max-width: ...)` breakpoints exist** — Phase 93 adds these in the app layout CSS

### Test Fixtures Available

- `packages/ui-core/tests/fixtures/events.json` — Full event sequence (session.started → phase.changed → thought.delta → tool_call → message.delta → message.completed → elicitation.requested → artifact.created → citation.recorded → run.state_changed)
- `packages/ui-core/tests/fixtures/elicitation-events.json` — Elicitation-specific events
- `packages/ui-core/tests/fixtures/phase-events.json` — Phase change events
- `packages/ui-core/tests/fixtures/citation-events.json` — Citation events

These fixtures can be reused by the E2E fixture backend.

---

## 2. platform-sdk-ts API

### PlatformApiClient (packages/platform-sdk-ts/src/index.ts, 226 lines)

Auto-generated by `generate_sdk.py`. All 12 Gateway endpoints are available as async methods:

| Method | HTTP | Path | Returns | Notes |
|--------|------|------|---------|-------|
| `createSession(body)` | POST | `/v1/sessions` | `{ session_id, tenant_id, set_cookie, status }` | Creates RBAC session + issues cookie |
| `getSession(session_id)` | GET | `/v1/sessions/{id}` | session object | |
| `listSessionRuns(session_id)` | GET | `/v1/sessions/{id}/runs` | run list | |
| `createRun(body)` | POST | `/v1/runs` | run object | Body: `{ turn, solution, tenant_id?, workspace_id? }` |
| `getRun(run_id)` | GET | `/v1/runs/{id}` | run object | |
| `cancelRun(run_id)` | DELETE | `/v1/runs/{id}` | run object | |
| `streamRun(run_id, lastEventID?)` | GET | `/v1/runs/{id}/events` | `AsyncIterable<SseFrame>` | SSE stream; `lastEventID` sends `Last-Event-ID` header |
| `submitElicitation(run_id, body)` | POST | `/v1/runs/{id}/elicitation` | response | Body: `{ interrupt_id, answers[] }` |
| `submitApproval(run_id, body)` | POST | `/v1/runs/{id}/approvals` | response | |
| `getArtifact(artifact_id)` | GET | `/v1/artifacts/{id}` | artifact metadata (reference-only) | |
| `upload(body)` | POST | `/v1/uploads` | `{ attachment_ref }` | Reference-only upload |
| `submitFeedback(body)` | POST | `/v1/feedback` | response | Body: `{ action, conversation_id }` |
| `listSkills()` | GET | `/v1/skills` | skills list | Feature-flagged |

### streamRun() Implementation (lines 137-163)

```typescript
async *streamRun(run_id: string, lastEventID?: string): AsyncIterable<SseFrame> {
  const response = await this.fetchImpl(this.baseUrl + `/v1/runs/${run_id}/events`, {
    method: "GET",
    headers: { "accept": "text/event-stream", ...this.defaultHeaders,
      ...(lastEventID ? { "Last-Event-ID": String(lastEventID) } : {}),
    },
  });
  // Reads response.body, splits on "\n\n", parseSseFrame() per frame
  const reader = response.body.getReader();
  // ... buffer + yield SseFrame
}
```

- **SseFrame**: `{ event: string; id: string; data: string }` (lines 14-18)
- **Last-Event-ID**: Already supported via optional `lastEventID` parameter — sends `Last-Event-ID` header when provided
- **parseSseFrame()**: Splits raw frame on `\n`, extracts `event:`, `id:`, `data:` lines

### PlatformApiError (lines 20-35)

```typescript
class PlatformApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
}
```

### Private request() method (lines 201-225)

- Uses `fetchImpl` (defaults to global `fetch`)
- Sets `content-type: application/json` + `defaultHeaders`
- Parses JSON response, throws `PlatformApiError` on non-ok status

### events.ts (packages/platform-sdk-ts/src/events.ts, 187 lines)

Hand-written TS bindings for all 13 event types + `RunEventEnvelope` + `UnifiedEventPayload` union. Key types:

- `RunEventEnvelope`: `{ event_id, run_id, event_type, occurred_at, ingested_at?, seq, payload?, metadata? }`
- `FivePhase`: `"research" | "intake" | "retrieval" | "draft" | "review"`
- `ElicitationRequestedPayload`: `{ interrupt_id, intro, questions[], resume_state_ref?, expires_at? }`
- `ElicitationQuestion`: `{ id, question, allow_multiple?, options?[] }`
- `ElicitationOption`: `{ label, value }`
- `Artifact`: `{ artifact_id, kind, name, uri, mime_type?, template_ref?, features?, source_refs? }`
- `CitationRecord`: `{ source, status: "verified"|"retrieved"|"unverified" }`

### PlatformApiClientOptions

```typescript
interface PlatformApiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
  defaultHeaders?: Record<string, string>;
}
```

**Key note for web client**: The `baseUrl` is set from `import.meta.env.VITE_GATEWAY_URL || ""` (empty string = same-origin relative URLs). The `fetchImpl` defaults to global `fetch` (browser-native). For SSE with cookies, the browser sends cookies automatically on same-origin requests.

---

## 3. Gateway Endpoints

### All 12 Endpoints (services/gateway/src/gateway/app.py)

| # | Method | Path | Operation | Status |
|---|--------|------|-----------|--------|
| 1 | POST | `/v1/sessions` | `create_session` | ✅ Implemented |
| 2 | GET | `/v1/sessions/{id}` | `get_session` | ⚠️ `_not_implemented` stub |
| 3 | GET | `/v1/sessions/{id}/runs` | `list_session_runs` | ⚠️ `_not_implemented` stub |
| 4 | POST | `/v1/runs` | `create_run` | ✅ Implemented |
| 5 | GET | `/v1/runs/{id}` | `get_run` | ⚠️ `_not_implemented` stub |
| 6 | DELETE | `/v1/runs/{id}` | `cancel_run` | ✅ Implemented |
| 7 | GET | `/v1/runs/{id}/events` | `stream_run` (SSE) | ✅ Implemented |
| 8 | POST | `/v1/runs/{id}/elicitation` | `submit_elicitation` | ⚠️ `_not_implemented` stub |
| 9 | POST | `/v1/runs/{id}/approvals` | `submit_approval` | ⚠️ `_not_implemented` stub |
| 10 | GET | `/v1/artifacts/{id}` | `get_artifact` | ✅ Implemented |
| 11 | POST | `/v1/uploads` | `upload` | ✅ Implemented |
| 12 | POST | `/v1/feedback` | `submit_feedback` | ✅ Implemented |
| 13 | GET | `/v1/skills` | `list_skills` | ✅ Implemented (proxy to skill-registry) |

**Important finding**: Several endpoints (`get_session`, `list_session_runs`, `get_run`, `submit_elicitation`, `submit_approval`) are currently `_not_implemented` stubs in `app.py` (lines 195-203). The web client's success criteria require these to work. The planner must account for implementing these stubs or the web client must work around them.

### No Login Endpoint

The Gateway currently has **no unauthenticated login endpoint**. All 12 endpoints call `auth.require_auth(headers)` before routing (line 181). The `dispatch()` method applies auth BEFORE any handler — no bypass exists.

The old `lawyer-web-chat` had `POST /login` (server.py line 97-98):
- Accepted `{ tenant_id, user_id, conversation_id?, device_id? }` JSON body
- Called `session_store.create()` to issue RBAC session
- Set `Set-Cookie: inkstatute_session=...; HttpOnly; Secure; SameSite=Strict`
- Rendered a simple HTML login form at `GET /` when unauthenticated

**Phase 93 must add `POST /v1/auth/login`** to the Gateway — a new unauthenticated endpoint that bypasses `require_auth` and creates a session. This is a small addition within Phase 93 scope per the context decisions.

### SSE Format (services/gateway/src/gateway/sse.py)

- Uses `encode_sse_event()` from `web_sse` package
- Frame format: `event: {event_type}\nid: {seq}\ndata: {json}\n\n`
- Output boundary enforced per event: `DefaultAssistantOutputBoundary.apply()` — blocked events return `None` (dropped)
- V3→V2 event type normalization for boundary: `message.delta` → `message_delta`, `run.state_changed` → `state_changed`, etc.
- `parse_last_event_id(headers)`: Extracts `Last-Event-ID` header, parses as integer

### Last-Event-ID Replay (services/gateway/src/gateway/event_buffer.py)

`RunEventBuffer` — in-memory per-run event buffer:
- `append(run_id, event)`: FIFO eviction at 1000 events/run max
- `replay(run_id, last_seq)`: Returns events with `seq > last_seq`, ordered ascending
- Thread-safe via `threading.Lock`
- Terminal states (`succeeded`, `failed`, `cancelled`) → 5-minute retention countdown
- In-memory only (sufficient for ≤50 lawyers)

**Reconnection flow** (app.py `stream()` method, lines 218-266):
1. Client connects with `Last-Event-ID: {last_seq}` header
2. Gateway calls `buffer.replay(run_id, last_seq)` → replays missed events
3. Continues streaming live events
4. Every live event is appended to buffer for future reconnections

### OpenAPI Document (services/gateway/src/gateway/openapi.py)

- OpenAPI 3.1, deterministic JSON (sort_keys, ASCII)
- Security schemes: `BearerAuth` (http bearer) + `SessionCookie` (apiKey in cookie, name `inkstatute_session`)
- All operations have security requirements applied
- `generate_sdk.py` regenerates `platform-sdk-ts/src/index.ts` from this document

### GatewayConfig (services/gateway/src/gateway/config.py)

- `enabled`: Default `False`, enabled via `INKSTATUTE_GATEWAY_ENABLED` env var
- `base_path`: Default `/v1`
- `default_tenant_id`: Default `"default"` (for self-hosted single-tenant)
- `from_env(mapping)`: Reads from environment variables

---

## 4. lawyer-desktop App Structure

### Entry Point (src/index.tsx, 9 lines)

```typescript
import { render } from "solid-js/web";
import "./themes/molv-tokens.css";
import "./themes/molv-base.css";
import App from "./App.tsx";
render(() => <App />, root!);
```

Minimal — imports themes, renders `<App />` into `#root`.

### App Shell (src/App.tsx, 141 lines)

- **Screen state**: `createSignal<"home" | "workspace">("home")` — no router, just signal-based screen switching
- **Layout**: `TitleBar` at top, `ConversationDrawer` as left sidebar (toggleable), main content area shows `HomePage` or `Workspace`
- **State management**: `useSettings()` (provider config), `useConversation()` (conversation list + messages)
- **On mount**: Restore provider → load conversations → create default conversation if none
- **Navigation**: `start(prompt)` creates conversation → switches to workspace screen; `openConversation(id)` switches to existing conversation
- **Settings**: `SettingsPanel` modal (desktop-admin-specific, deferred to Phase 94)
- **No router**: lawyer-desktop uses signal-based screen switching, not URL routing. Phase 93's web client uses `@solidjs/router` instead.

### Component Organization

```
src/components/
  home/       → HomePage.tsx, HomePage.css
  layout/     → TitleBar, ConversationDrawer, AppUpdateBanner
  workspace/  → ChatPanel, Workspace, DocPreview, CitationPanel, WorkflowProgressSteps, DraftingProgressSteps, MessageFeedback, DocDraftingLoader, AgentTracePanel, SkillRefinementPanel
  settings/   → SettingsPanel
  icons/      → Icons.tsx
  MentionComposer.tsx, MentionMenu.tsx
```

### Services (src/services/api.ts)

All 57 `invoke()` Tauri commands are wrapped here. In the web client, these are replaced by `PlatformApiClient` Gateway HTTP/SSE calls.

### Stores (src/stores/)

- `conversation.ts` (1,591 lines) — The original "rendering state machine" driven by Tauri events. Replaced by ui-core's `event-reducer.ts` + `eventStream.ts`.
- `settings.ts` — Provider config (desktop-only, deferred)
- `theme.ts` (40 lines) — Ported to ui-core as `stores/theme.ts`

### Key Pattern: Signal-based Screen Switching

lawyer-desktop does NOT use a router. It uses:
```typescript
const [screen, setScreen] = createSignal<"home" | "workspace">("home");
// Show <Show when={screen() === "home"}><HomePage /></Show>
// Show <Show when={screen() === "workspace"}><Workspace /></Show>
```

The web client replaces this with `@solidjs/router` for URL-based navigation (`/login`, `/`, `/workspace/:conversationId`), enabling browser back/forward, deep linking, and bookmarkable URLs.

---

## 5. Responsive Layout Patterns

### lawyer-desktop CSS (src/index.css)

lawyer-desktop's `index.css` has minimal responsive patterns:
- `#root { width: 1126px; max-width: 100%; }` — fixed width with max-width fallback
- `@media (max-width: 1024px) { font-size: 16px; }` — font size reduction
- `@media (max-width: 1024px) { h1 { font-size: 36px; } }` — heading reduction
- `@media (prefers-color-scheme: dark)` — dark mode (not used by 墨律 themes)
- `min-height: 100svh` — small viewport height unit

**These are Vite scaffold defaults, not 墨律-specific responsive design.** The actual 墨律 app (Tauri desktop) doesn't need mobile responsiveness — it's a fixed-window desktop app.

### ui-core CSS (no breakpoints)

Confirmed: ui-core component CSS has **zero `@media (max-width: ...)` breakpoints**. Only `@media (prefers-reduced-motion: reduce)` exists in ChatPanel.css and AgentTracePanel.css.

Flexible layout patterns already in ui-core:
- `max-width: 100%` on content containers
- `min-width: 0` on flex children (prevents flex overflow)
- `overflow-x: auto` on scrollable containers
- `flex-wrap: wrap` on card grids (HomePage)
- `max-width: calc(100% - 48px)` on message bubbles
- `max-width: min(86%, 380px)` on user message bubbles

### Phase 93 Responsive Strategy (from context decisions)

- **Breakpoint**: 768px (standard tablet/mobile boundary)
- **Desktop (≥768px)**: Sidebar layout — `ConversationDrawer` as fixed left sidebar (280px), main content fills remaining
- **Mobile (<768px)**: Drawer layout — `ConversationDrawer` hidden by default, opened via hamburger menu
- **CSS custom properties**: `--sidebar-width: 280px`, `--sidebar-width-collapsed: 0px`
- **No horizontal scroll**: `overflow-x: hidden` at layout level, `min-width: 0` on flex children
- **Implementation**: `AppLayout.tsx` with `@media (max-width: 767px)` and `@media (min-width: 768px)` queries

### molv-base.css Layout

```css
.home-inner { max-width: 1040px; margin: 0 auto; padding: 64px 40px 80px; }
```

This is desktop-first. On mobile, the padding needs to be reduced (e.g., `padding: 32px 16px 48px`).

---

## 6. Auth Patterns

### GatewayAuth (services/gateway/src/gateway/auth.py, 154 lines)

**Identity resolution flow**:
1. Extract `Authorization` header (Bearer token) and `Cookie` header (session cookie)
2. Call `rbac.identity.resolve_identity()` — Bearer token first, session cookie fallback
3. When `rbac_enabled=False`: uses `static_token` fallback (any request with static token or no token gets default admin identity)
4. Returns `AuthContext` with `identity`, `authenticated`, `tenant_id`, `error`

**Methods**:
- `authenticate(headers)` → `AuthContext` (never raises, returns unauthenticated context on failure)
- `require_auth(headers)` → `AuthContext` (raises `GatewayAuthError` 401 on failure)
- `require_role(headers, allowed_roles)` → `AuthContext` (raises 403 on role mismatch)
- `check_tenant(ctx, resource_tenant_id)` → raises 403 on cross-tenant access

**AuthContext** (frozen dataclass):
```python
@dataclass(frozen=True, slots=True)
class AuthContext:
    identity: Identity | None
    authenticated: bool
    tenant_id: str
    error: str | None
```

### Session Cookie Mechanism (services/gateway/src/gateway/sessions.py)

**GatewaySessionManager.create_session()**:
1. Calls `SessionStore.create(role, tenant_id, ttl_seconds)` → gets `sid`
2. Calls `issue_session_cookie(rbac_secret, sid, role, tenant_id, ttl)` → HMAC-SHA256 signed cookie value
3. Creates `GatewaySession` record (tracks `conversation_id` + `devices[]`)
4. Returns `(session_id, cookie_value, GatewaySession)`

**Cookie header format** (from `build_set_cookie_header()`):
```
inkstatute_session={cookie_value}; Max-Age={ttl}; HttpOnly; Secure; SameSite=Strict
```

- **Cookie name**: `inkstatute_session` (from RBAC `SESSION_COOKIE_NAME`)
- **Flags**: `HttpOnly` (JS can't read), `Secure` (HTTPS only), `SameSite=Strict` (CSRF protection)
- **TTL**: `DEFAULT_SESSION_TTL_SECONDS` from RBAC package

### Multi-device Sync

`GatewaySession` tracks `devices: list[str]` — `add_device(session_id, device_id)` adds devices to existing sessions. `list_sessions(tenant_id)` returns all sessions for a tenant, enabling cross-device session visibility.

### Dev Mode (rbac_enabled=False)

When `rbac_enabled=False`:
- `resolve_identity()` uses `static_token` fallback
- Any request with the static token (or no token when static_token is also None) gets a default admin identity
- This is the development mode — the web client can auto-login or use `VITE_DEV_AUTO_LOGIN`

### Login Endpoint Gap

The Gateway has no `POST /v1/auth/login` endpoint. Phase 93 must add one:
- **Unauthenticated** endpoint (bypasses `require_auth`)
- Accepts `{ username?, password?, token?, tenant_id?, user_id? }` JSON body
- When `rbac_enabled=False`: accepts any credentials, creates session with default tenant
- When `rbac_enabled=True`: validates against RBAC token store
- Calls `GatewaySessionManager.create_session()` → returns `{ session_id, tenant_id, set_cookie }`
- Implementation: Add a new route in `_parse_route()` and a handler that bypasses the `require_auth` call in `dispatch()`

**Old lawyer-web-chat login pattern** (reference):
- `POST /login` with `{ tenant_id, user_id, conversation_id?, device_id? }`
- Issues RBAC session + sets cookie
- Simple HTML form at `GET /` when unauthenticated

---

## 7. E2E Testing

### Current State

**Playwright is NOT set up** anywhere in the project. No `playwright.config.ts`, no `@playwright/test` dependency, no `e2e/` directories exist in any app. The only `.spec.ts` files found are in `node_modules` (entities library).

### Existing Test Infrastructure

- **Vitest**: Used by `packages/ui-core` (configured in `vite.config.ts`, `environment: "jsdom"`, `setupFiles: ["tests/setup.ts"]`)
- **Vitest testing library**: `@solidjs/testing-library` + `@testing-library/dom` in ui-core devDeps
- **Python gates**: `scripts/run_v2_gates.py` — 28+ gates for Python packages
- **ui-core tests**: 5 test files in `packages/ui-core/tests/` (icons, clarification-card, message-feedback, citation-panel, integration)
- **Fixture events**: 4 JSON fixture files in `packages/ui-core/tests/fixtures/` — reusable for E2E

### Phase 93 E2E Setup (from context decisions)

**Playwright** with fixture Gateway mock server:
- `apps/web/e2e/` directory with Playwright config and test specs
- `apps/web/e2e/fixtures/gateway-mock.ts` — mock Gateway implementing all 12 endpoints
- Streams fixture SSE events from ui-core's test fixtures
- No real LLM dependency

**Test coverage** (10 scenarios):
1. Login flow → redirect to `/`
2. New session → home page with starter prompts
3. Send task → user message in chat
4. Streaming reply → fixture SSE events
5. Five-phase progress → `phase.changed` events
6. Clarification card → `elicitation.requested` + submit answers
7. Artifact download → `artifact.created` + click download
8. Feedback → thumbs up/down
9. Reconnection → simulate SSE disconnect, verify Last-Event-ID resume
10. Mobile viewport → 375×812 (iPhone), verify responsive layout

**Unit tests**: Vitest for web-specific adapter implementations and context logic.

**Gate coverage**: `apps/web` is under `apps/`, not `packages/` or `services/`, so the gate-coverage meta-test does not strictly require it. However, a lightweight gate (typecheck + vitest) should be added for consistency.

---

## 8. Build Tooling

### Root Workspace (package.json)

```json
{
  "name": "inkstatute-suite",
  "private": true,
  "workspaces": [
    "packages/platform-sdk-ts",
    "packages/ui-core"
  ]
}
```

**Phase 93 adds `"apps/web"` to the workspaces array.**

### Package Manager: Bun

The project uses `bun` as the package manager. Bun's workspace protocol links packages locally via `"workspace:*"`.

### Vite Configuration Pattern (from ui-core)

```typescript
// vite.config.ts
import { defineConfig } from "vitest/config";
import solid from "vite-plugin-solid";
import path from "node:path";

export default defineConfig({
  plugins: [solid()],
  resolve: {
    alias: {
      debug: path.resolve(__dirname, "src/shims/debug.ts"), // solid-markdown needs debug shim
    },
  },
  // ...
});
```

**For apps/web**, the Vite config needs:
- `vite-plugin-solid` for SolidJS JSX compilation
- `debug` shim for `solid-markdown`
- `server.proxy`: `/v1` → `http://localhost:8000` (Gateway dev proxy)
- `build`: Standard SPA build (not library mode) → `dist/` with `index.html`, `assets/*.js`, `assets/*.css`
- `test`: Vitest with jsdom environment

### ui-core Build

- `vite build` → library mode, ESM + CJS output
- `tsc --emitDeclarationOnly` → `.d.ts` type declarations
- External: `solid-js`, `solid-markdown`, `remark-gfm`, `highlight.js`, `@inkstatute/platform-sdk-ts`

### Deployment Options

1. **Gateway-served (recommended)**: Gateway adds static file handler for `apps/web/dist/` — same origin, no CORS
2. **Standalone static server**: nginx/Caddy serving `dist/`, `VITE_GATEWAY_URL` points to Gateway, CORS configured
3. **Dev mode**: `vite dev` with HMR + proxy to Gateway

### TypeScript Configuration

- `tsconfig.json` with `strict: true`, `jsx: "preserve"`, `jsxImportSource: "solid-js"`
- Type checking: `tsc --noEmit` before build

---

## 9. Mobile Considerations

### Touch Targets

- **Minimum 44×44px** for all interactive elements on mobile (Apple HIG standard)
- Implemented via CSS: `@media (max-width: 767px) { button, .clickable { min-height: 44px; min-width: 44px; } }`
- `ClarificationCard` options are already large (radio-like cards) — verify on mobile viewport
- `MentionComposer` send/attach buttons get enlarged touch areas on mobile

### Responsive Font Sizes

- Base font: 14px desktop, **16px mobile** (prevents iOS auto-zoom on input focus)
- Chat message font: 13.5px desktop, 15px mobile
- Title bar: condensed on mobile (hide window controls, show only theme switch + menu)

### Viewport Meta Tag

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

- `viewport-fit=cover` enables safe area inset environment variables

### iOS Safari Considerations

- **Safe area insets**: `env(safe-area-inset-top)`, `env(safe-area-inset-bottom)` for notch/home indicator
- **100vh issue**: Use `100dvh` (dynamic viewport height) where supported, fallback to `100vh`
- **Input focus zoom**: Set `font-size: 16px` on inputs to prevent iOS auto-zoom
- **No custom gestures**: Swipe-to-open drawer, pinch-to-zoom are NOT implemented. Drawer opens via hamburger button tap. Document preview uses native browser scroll/zoom.

### Mobile-Optimized Composer

- `MentionComposer` textarea expands vertically on mobile (more rows visible)
- Attach/menu buttons move to compact toolbar above keyboard
- `@-mention` autocomplete (`MentionMenu`) positions above keyboard, not below

### No Horizontal Scroll

- `overflow-x: hidden` at layout level
- `min-width: 0` on flex children
- `max-width: 100%` on content containers
- `DocPreview` may need horizontal scroll for wide tables — contained within component, not page

---

## 10. Fixture Backend

### Approach

A fixture Gateway mock server (`apps/web/e2e/fixtures/gateway-mock.ts`) that:
- Implements all 12 Gateway endpoints with fixture responses
- Streams fixture SSE events (from ui-core's test fixtures) for a predefined run
- Handles login, session creation, run creation, elicitation, feedback
- Does NOT require a real LLM or agent backend

### Available Fixture Events

From `packages/ui-core/tests/fixtures/`:
- `events.json` — Full event sequence: `session.started` (seq 1) → `phase.changed` (seq 2) → `thought.delta` (seq 3) → `tool_call.started` (seq 4) → `tool_call.completed` (seq 5) → `message.delta` (seq 6) → `message.completed` (seq 7) → `elicitation.requested` (seq 8) → `artifact.created` (seq 9) → `citation.recorded` (seq 10) → `run.state_changed` (seq 11)
- `elicitation-events.json` — Elicitation-specific events
- `phase-events.json` — Phase change events
- `citation-events.json` — Citation events

### Mock Server Implementation Pattern

The fixture backend can be:
1. **A Node.js HTTP server** (using `node:http` or a lightweight framework) that listens on a port
2. **Playwright route interception** — `page.route("**/v1/**", handler)` intercepts all Gateway calls in the browser context

**Option 2 (Playwright route interception)** is simpler — no separate server process, all mocking happens in the test:

```typescript
// e2e/flow.spec.ts
await page.route("**/v1/auth/login", (route) => {
  route.fulfill({ status: 200, body: JSON.stringify({ session_id: "test-sess", tenant_id: "default" }) });
});
await page.route("**/v1/runs/*/events**", (route) => {
  // Stream fixture SSE events
  route.fulfill({ status: 200, contentType: "text/event-stream", body: sseStream });
});
```

**However**, SSE streaming via Playwright route interception may be tricky. A hybrid approach:
- Use Playwright routes for non-streaming endpoints (login, create session, create run, elicitation, feedback)
- Use a real lightweight HTTP server for the SSE endpoint (or pre-recorded SSE response body)

### Events the Gateway Expects

The fixture backend needs to produce `RunEventEnvelope` objects with:
- `event_id`: Unique string
- `run_id`: Matches the run created by `POST /v1/runs`
- `event_type`: One of 13 unified types
- `occurred_at`: ISO timestamp
- `seq`: Monotonically increasing integer
- `payload`: Event-specific payload (matching `events.ts` interfaces)

SSE frame format: `event: {event_type}\nid: {seq}\ndata: {json_envelope}\n\n`

### Reconnection Test

To test Last-Event-ID reconnection:
1. Start streaming events
2. After seq 5, simulate disconnect (close the SSE connection)
3. Reconnect with `Last-Event-ID: 5` header
4. Verify events 6+ are received without duplicates
5. The fixture backend needs to support `Last-Event-ID` header parsing and replay

---

## Summary & Recommendations

### Key Findings

1. **ui-core is complete and ready to consume** — 14+ components, event reducer, event stream store, adapter interfaces, theme system, legal types, and utilities are all exported from `@inkstatute/ui-core`. The web app writes zero chat UI code.

2. **PlatformApiClient has all Gateway endpoints** — 13 methods covering all 12 Gateway endpoints, including `streamRun()` with `Last-Event-ID` support. Ready to use with `baseUrl = import.meta.env.VITE_GATEWAY_URL || ""`.

3. **Gateway has NO login endpoint** — All 12 endpoints require auth. Phase 93 must add `POST /v1/auth/login` as a new unauthenticated endpoint. This requires modifying `app.py`'s `dispatch()` to bypass `require_auth` for this specific route.

4. **Several Gateway endpoints are stubs** — `get_session`, `list_session_runs`, `get_run`, `submit_elicitation`, `submit_approval` return `_not_implemented`. The web client's success criteria (full lawyer flow) require these to work. The planner must account for implementing these stubs.

5. **No router in ui-core or lawyer-desktop** — lawyer-desktop uses signal-based screen switching. The web client needs `@solidjs/router` for URL-based navigation (3 routes: `/login`, `/`, `/workspace/:conversationId`).

6. **No mobile breakpoints in ui-core CSS** — Only `@media (prefers-reduced-motion)` exists. Phase 93 adds `@media (max-width: 767px)` / `@media (min-width: 768px)` in the app layout CSS.

7. **Playwright is NOT set up** — No E2E testing infrastructure exists. Phase 93 sets up Playwright from scratch with fixture Gateway mock.

8. **Root package.json needs `apps/web`** — Current workspaces: `["packages/platform-sdk-ts", "packages/ui-core"]`. Add `"apps/web"`.

9. **6 adapter interfaces to implement** — `FileAdapter`, `DropAdapter`, `AppInfoAdapter`, `WorkspaceAdapter`, `DocumentParser` (web implementations needed); `WindowAdapter` (not provided for web — optional in `AdapterContextValue`).

10. **Fixture events available** — 4 JSON fixture files in ui-core tests can be reused for E2E fixture backend.

### Risks

1. **Gateway stub implementation** — 5 of 12 endpoints are `_not_implemented` stubs. The web client can't complete the full lawyer flow without them. This may expand Phase 93 scope beyond pure web client work. **Recommendation**: Implement the stubs as part of Phase 93, or ensure the fixture backend covers them for E2E while real implementation is deferred.

2. **Login endpoint addition** — Adding `POST /v1/auth/login` to the Gateway requires modifying the auth middleware bypass logic. This is a security-sensitive change — must ensure no other endpoint accidentally bypasses auth.

3. **SSE through Vite proxy** — SSE streaming through Vite's dev proxy needs verification. Vite supports proxying but SSE long-lived connections may have timeout issues. **Recommendation**: Test SSE early in development.

4. **`streamRun()` credentials** — The SDK's `streamRun()` uses `fetch()` without explicit `credentials: "include"`. For same-origin (dev proxy + production same-origin), cookies are sent automatically. For cross-origin, `credentials: "include"` must be added. The `EventStreamStore` in ui-core re-implements the fetch directly (not using `streamRun()`), so it also needs `credentials: "include"` for cross-origin.

5. **Cookie `Secure` flag in dev** — The session cookie has `Secure` flag, which requires HTTPS. In local development (HTTP), the browser won't store the cookie. **Recommendation**: The login endpoint should conditionally omit `Secure` in dev mode, or use `SameSite=Lax` for localhost.

### Recommendations for Planner

1. **Plan 1**: Scaffold `apps/web` — package.json, vite.config.ts, tsconfig.json, index.html, main.tsx, App.tsx with router, add to root workspaces
2. **Plan 2**: Web adapters + auth context + Gateway login endpoint — implement 5 adapter interfaces, AuthContext, add `POST /v1/auth/login` to Gateway
3. **Plan 3**: Responsive layout shell + pages — AppLayout, MobileNav, LoginPage, HomePage, WorkspacePage, conversation store
4. **Plan 4**: E2E tests + Gateway stub implementations — Playwright setup, fixture backend, full flow tests, implement remaining Gateway stubs
