---
phase: 92
slug: shared-ui-core
plan_count: TBD
subsystem: ui-core
tags: [solidjs, ui, sse, events, theme, typescript]
requires:
  - phase: 88
    reason: Unified event vocabulary (13 types) + TS bindings in platform-sdk-ts
  - phase: 91
    reason: Gateway SSE endpoint (/v1/runs/{id}/events) with Last-Event-ID replay
provides:
  - packages/ui-core — Shared SolidJS component package (chat UI single implementation)
  - Event stream consumer (SSE client + rendering state machine)
  - 墨律 three themes (molv-tokens.css / molv-base.css, data-theme="a|b|c")
  - platform-sdk-ts event type bindings (expanded from Phase 88)
affects:
  - apps/web_chat — to be marked deprecated (prototype renderer superseded)
  - apps/web — future consumer (Phase 93)
  - apps/desktop — future consumer (Phase 94, Tauri shell reuse)
  - lawyer-desktop — migration source (UI extracted, not modified in place)
key-files:
  - packages/ui-core/package.json
  - packages/ui-core/src/index.ts
  - packages/ui-core/src/components/ChatPanel.tsx
  - packages/ui-core/src/components/Workspace.tsx
  - packages/ui-core/src/components/CitationPanel.tsx
  - packages/ui-core/src/components/DocPreview.tsx
  - packages/ui-core/src/components/WorkflowProgressSteps.tsx
  - packages/ui-core/src/components/DraftingProgressSteps.tsx
  - packages/ui-core/src/components/MessageFeedback.tsx
  - packages/ui-core/src/components/Icons.tsx
  - packages/ui-core/src/stores/eventStream.ts
  - packages/ui-core/src/stores/theme.ts
  - packages/ui-core/src/themes/molv-tokens.css
  - packages/ui-core/src/themes/molv-base.css
  - packages/ui-core/src/types/events.ts
  - packages/ui-core/src/types/legal.ts
  - packages/ui-core/src/types/workflow.ts
  - packages/ui-core/vite.config.ts
  - packages/ui-core/tsconfig.json
  - packages/platform-sdk-ts/src/events.ts
  - packages/platform-sdk-ts/src/index.ts
  - scripts/run_v2_gates.py
key-decisions:
  - "Component extraction: port all 23 components from lawyer-desktop, strip Tauri deps via adapter pattern"
  - "Event stream consumer: SSE client with rendering state machine driven by 13 unified event types"
  - "Theme system: port molv-tokens.css + molv-base.css verbatim, data-theme attribute switching"
  - "TypeScript bindings: hand-written events.ts already exists in platform-sdk-ts; expand with Gateway client methods"
  - "Build & package: Vite library mode + tsup for dual CJS/ESM, consumed via workspace protocol"
  - "ask_user card: map elicitation.requested to ClarificationCard with single/multi/free-text support"
  - "Five-phase progress: map phase.changed events to DraftingProgressSteps"
  - "Document preview & citation panel: port DocPreview + CitationPanel, driven by artifact.created + citation.recorded events"
patterns-established:
  - "Adapter pattern for platform-specific operations (file dialog, drag-drop) — inject via context"
  - "Event-driven rendering state machine — single source of truth from SSE event stream"
  - "Theme via CSS custom properties + data-theme attribute — no JS theme engine"
  - "Single chat UI implementation — all consumers import from ui-core"
  - "platform-sdk-ts as the sole TS type source — ui-core never hand-writes event types"
requirements-targeted:
  - UI-01
  - UI-02
  - UI-03
  - UI-06
coverage:
  requirements: 4
  success_criteria: 6
duration: TBD
completed: false
status: context-gathered
created: 2026-08-08
---

# Phase 92 — Shared UI Core

<domain>

## What This Phase Delivers

A shared SolidJS component package (`packages/ui-core`) extracted from `lawyer-desktop`, containing the single implementation of all chat-related UI. It consumes the unified event stream (Phase 88's 13 event types) via the Gateway SSE endpoint (Phase 91), not any platform-specific IPC.

**Core principle (UI-06):** Chat message list, streaming renderer, ask_user card, document preview, and citation panel have exactly **one implementation** in the entire project. `apps/web_chat`'s prototype renderer is deprecated. `apps/web` (Phase 93) and `apps/desktop` (Phase 94) both depend on `ui-core` — neither writes its own chat UI.

**Requirements targeted:**
- **UI-01**: `packages/ui-core` shared SolidJS component package, extracted from lawyer-desktop's 23 components and 21 CSS files (墨律三主题)
- **UI-02**: Unified event stream client (SSE consumer + rendering state machine), one implementation for all clients
- **UI-03**: Streaming chat + ask_user clarification card + document preview + citation panel + five-phase progress, all in ui-core
- **UI-06**: Single implementation — no second chat UI anywhere in the project

**Success Criteria (must all be TRUE):**
1. `packages/ui-core` exists, contains components migrated from lawyer-desktop + 墨律 three themes (`molv-tokens.css` / `molv-base.css`, `data-theme="a|b|c"`), and does not depend on any `@tauri-apps/*` package
2. Unified event stream client (SSE consumer + rendering state machine) implemented once in ui-core, can consume all 13 event types from Phase 88; has fixture-event-stream-driven render tests
3. Streaming chat, ask_user clarification card (single/multi/free-text), document preview, citation panel, five-phase progress — all implemented in ui-core and independently testable
4. `packages/platform-sdk-ts` generates unified event vocabulary TS bindings; ui-core uses it, not hand-written types
5. Project-wide grep finds no second chat message list / streaming renderer / ask_user card implementation; `apps/web_chat` prototype renderer marked deprecated
6. `ui-core` has build artifacts and type declarations, consumable by both `apps/web` and `apps/desktop`

</domain>

<prior_decisions>

## Decisions Carried Forward from Earlier Phases

### From Phase 88 — Unified Event Contract
- **13 event types** defined with JSON Schema + Python bindings + TypeScript bindings: `session.started` / `message.delta` / `message.completed` / `thought.delta` / `tool_call.started|delta|completed` / `plan.updated` / `phase.changed` / `elicitation.requested` / `permission.requested` / `artifact.created` / `citation.recorded` / `run.state_changed` / `error`
- **`RunEventEnvelope`** structure: `event_id`, `run_id`, `event_type`, `occurred_at`, `ingested_at`, `seq`, `payload`, `metadata` — `seq` enables断线续传
- **Five-phase progress**: research → intake → retrieval → draft → review, mapped to thinking/tool/streaming/review
- **Elicitation contract**: 2-4 questions, single-select / multi-select (`allow_multiple`) / free-text, with `interrupt_id` / `resume_state_ref` — semantically aligned with `ASK-USER-PROTOCOL.md`
- **TS bindings already exist**: `packages/platform-sdk-ts/src/events.ts` (187 lines, hand-written, mirrors JSON Schemas and Python dataclasses)

### From Phase 91 — Unified Gateway
- **SSE endpoint**: `GET /v1/runs/{id}/events` streams unified events as SSE frames
- **Last-Event-ID replay**: client sends `Last-Event-ID` header, gateway replays events with `seq > last_event_id`
- **SSE frame format**: `encode_sse_event()` from `web_sse` package — `event`, `id`, `data` fields, deterministic JSON
- **Output boundary at Gateway**: `GatewaySseStream` applies `DefaultAssistantOutputBoundary` before encoding — blocked events return `None`
- **Auth**: RBAC `resolve_identity()` — Bearer token first, session cookie fallback; `tenant_id` always in claims
- **Existing SDK**: `packages/platform-sdk-ts/src/index.ts` has `PlatformApiClient` with `streamRun()` async generator that yields `SseFrame` objects

### From PROJECT.md — Binding Architecture Decisions
- **共享 UI 沿用 SolidJS** (Key Decision): team already has SolidJS investment; 墨律三主题 and 23 polished components are design assets; framework switch benefit doesn't justify discarding cost
- **Chat UI must converge to single implementation** (Key Decision): current ~80% duplication between lawyer-desktop and lawyer-ai is unacceptable
- **lawyer-desktop 拆解而非整体迁入** (Key Decision): UI → `packages/ui-core`; Tauri shell → `apps/desktop`; agent logic → Python `packages/agent-core`; SQLite CRUD not migrated
- **移动原生 App 推 V4** (Key Decision): mobile browser support only this milestone; shared UI designed to be packageable as app but not shipped

</prior_decisions>

<decisions>

## Auto-Selected Decisions for Gray Areas

[--auto] Selected all gray areas: Component Extraction Strategy, Event Stream Consumer, Theme System, TypeScript Bindings, Build & Package Setup, ask_user Card Implementation, Five-Phase Progress Indicator, Document Preview & Citation Panel.

### 1. Component Extraction Strategy

[auto] [Component Extraction Strategy] — Q: "Which components to extract first, and how to handle Tauri-specific dependencies?" → Selected: "Port all 23 components in one pass, strip Tauri deps via adapter/context injection pattern" (recommended default)

**Rationale:** The 23 components in lawyer-desktop total ~5,775 lines of SolidJS. Five components have direct `@tauri-apps/*` imports (ChatPanel, DocPreview, TitleBar, HomePage, SettingsPanel). Rather than partial extraction, port all components in one pass and replace Tauri-specific calls with an injectable adapter interface:

- **File dialog** (`@tauri-apps/plugin-dialog` `open`/`save`) → `FileAdapter` interface (web: `<input type="file">`, desktop: Tauri dialog)
- **Drag-drop path classification** (`classifyDroppedPaths` invoke) → `DropAdapter` interface (web: DataTransfer items, desktop: Tauri path classification)
- **App version / updater** (`getVersion`, `checkForAppUpdate`) → `AppInfoAdapter` interface (web: package.json version, desktop: Tauri updater)
- **Webview events** (`getCurrentWebview`) → removed; not needed in ui-core

Components that are purely presentational (CitationPanel, WorkflowProgressSteps, DraftingProgressSteps, MessageFeedback, Icons, DocDraftingLoader) port with zero changes. The `MentionComposer` and `MentionMenu` depend on workspace file listing — they get a `WorkspaceAdapter` interface.

The `SettingsPanel` (963 lines) and `SkillRefinementPanel` (390 lines) are desktop-admin-specific and may be excluded from ui-core's initial scope (deferred to Phase 94 desktop client). The core chat components (ChatPanel, Workspace, DocPreview, CitationPanel, WorkflowProgressSteps, DraftingProgressSteps, MessageFeedback, Icons, DocDraftingLoader, MentionComposer, MentionMenu) are the minimum viable set for UI-01/UI-02/UI-03.

**Tauri dependency removal:** `grep -r "@tauri-apps" src/` in ui-core must return zero results. All `invoke()` calls (57 in api.ts) are replaced by Gateway HTTP calls via `PlatformApiClient`.

### 2. Event Stream Consumer

[auto] [Event Stream Consumer] — Q: "How should the SSE client and rendering state machine be designed?" → Selected: "SSE consumer using PlatformApiClient.streamRun() + SolidJS signals as rendering state machine, driven by 13 event types" (recommended default)

**Rationale:** The existing `PlatformApiClient.streamRun()` already yields `SseFrame` objects via async generator. The event stream consumer in ui-core wraps this with:

1. **`EventStreamStore`** (SolidJS signals): Maintains reactive state derived from the event stream — messages array, current phase, active elicitation, artifacts, citations, run status, tool calls, plan steps
2. **Event reducer**: A pure function `(state, event) → state` that processes each `RunEventEnvelope` and updates the appropriate signal. This is the "rendering state machine" — it maps 13 event types to UI state transitions:
   - `session.started` → initialize run state, set backend_id
   - `message.delta` → append to current streaming message buffer
   - `message.completed` → finalize message, push to messages array
   - `thought.delta` → update thinking indicator
   - `tool_call.started|delta|completed` → update tool call progress in workflow steps
   - `plan.updated` → update plan steps
   - `phase.changed` → update five-phase progress indicator
   - `elicitation.requested` → show clarification card with questions
   - `permission.requested` → show permission approval card
   - `artifact.created` → register artifact, trigger document preview
   - `citation.recorded` → update citation panel
   - `run.state_changed` → update run status (running/completed/cancelled/error)
   - `error` → show error state
3. **Reconnection**: On SSE disconnect, reconnect with `Last-Event-ID` header (the last `seq` received). The reducer is idempotent — replayed events produce the same state.
4. **Fixture-driven tests**: Feed a sequence of `RunEventEnvelope` fixtures through the reducer and assert the resulting state. No live SSE needed.

This replaces lawyer-desktop's current approach where `onChatStream` (Tauri event listener) + `onAgentTrace` (Tauri event listener) drive separate signal updates in `conversation.ts` (1,591 lines). The new approach has a single event source (SSE) and a single reducer.

### 3. Theme System

[auto] [Theme System] — Q: "How to port 墨律 three themes (molv-tokens.css, data-theme='a|b|c')?" → Selected: "Port molv-tokens.css + molv-base.css verbatim into ui-core/src/themes/, keep data-theme attribute switching" (recommended default)

**Rationale:** The theme system is pure CSS custom properties + `data-theme` attribute on `document.documentElement`. No JS theme engine — just `setAttribute("data-theme", variant)`. The `theme.ts` store (40 lines) is trivially portable:

- `molv-tokens.css` (187 lines): defines `--app-bg`, `--chat-bg`, `--surface`, `--ink`, `--accent`, `--gold`, `--sheet-*`, `--user-*`, etc. for three themes (`:root, [data-theme="a"]`, `[data-theme="b"]`, `[data-theme="c"]`)
- `molv-base.css`: base styles using the tokens
- `theme.ts`: `createSignal<ThemeVariant>`, `localStorage` persistence, `applyTheme()` sets `data-theme` attribute

Port all three files verbatim into `packages/ui-core/src/themes/` and `packages/ui-core/src/stores/theme.ts`. The 21 component CSS files also port verbatim — they reference CSS custom properties, not hardcoded colors.

**Font loading:** `molv-tokens.css` imports Google Fonts via `@import url(...)`. In ui-core, this remains as-is for web. Desktop (Tauri) may bundle fonts locally — handled in Phase 94, not here.

### 4. TypeScript Bindings

[auto] [TypeScript Bindings] — Q: "How should platform-sdk-ts provide event type bindings — manual, codegen, or schema-first?" → Selected: "Hand-written events.ts (already exists) + expand PlatformApiClient with Gateway endpoints" (recommended default)

**Rationale:** `packages/platform-sdk-ts/src/events.ts` (187 lines) already contains hand-written TS interfaces for all 13 event payload types + `RunEventEnvelope` + `UnifiedEventPayload` union. It mirrors the JSON Schemas in `packages/platform-contract/src/platform_contract/schemas/` and the Python dataclasses in `unified_events.py`. The header says "Hand-written — not auto-generated."

The existing `generate_sdk.py` generates `index.ts` (the `PlatformApiClient` class) from the OpenAPI document. Phase 91 expanded the Gateway's OpenAPI spec with all new endpoints. Phase 92 regenerates `index.ts` to include the expanded endpoint set (`/v1/sessions`, `/v1/runs/{id}/elicitation`, `/v1/runs/{id}/approvals`, `/v1/artifacts/{id}`, `/v1/uploads`, `/v1/feedback`, `/v1/skills`).

**Why not codegen events.ts?** The JSON Schemas are simple enough that hand-written TS is more readable and maintainable. The schemas are frozen (Phase 88 complete). A codegen step would add complexity without value. The hand-written file has a comment linking to the schema directory for cross-reference.

**ui-core imports:** `import type { RunEventEnvelope, ElicitationRequestedPayload, ... } from "@inkstatute/platform-sdk-ts/events"`. Never hand-writes event types.

### 5. Build & Package Setup

[auto] [Build & Package Setup] — Q: "How should ui-core be built and consumed by apps/web and apps/desktop?" → Selected: "Vite library mode for build, workspace:* protocol for consumption, dual ESM/CJS output" (recommended default)

**Rationale:** The project uses `bun` as the package manager and Vite as the build tool (lawyer-desktop uses Vite 8 + vite-plugin-solid). For ui-core:

- **Build tool**: Vite library mode (`build.lib` in `vite.config.ts`) with `vite-plugin-solid` for SolidJS JSX compilation. Output: ESM + CJS + type declarations (`.d.ts`).
- **Package name**: `@inkstatute/ui-core` (matching `@inkstatute/platform-sdk-ts` convention)
- **Consumption**: `apps/web` and `apps/desktop` declare `"@inkstatute/ui-core": "workspace:*"` in their `package.json`. Bun's workspace protocol links the package locally.
- **External deps**: `solid-js`, `solid-markdown`, `remark-gfm`, `highlight.js` are peer dependencies (consumers provide them). `@inkstatute/platform-sdk-ts` is a direct dependency.
- **CSS**: Theme CSS files are exported as side-effect imports (`import "@inkstatute/ui-core/themes"`). Component CSS is co-located and imported by components.
- **TypeScript**: `tsconfig.json` with `strict: true`, `jsx: "preserve"`, `jsxImportSource: "solid-js"`. Type declarations generated by `tsc --emitDeclarationOnly`.

**Gate coverage**: Per AGENTS.md, every `packages/*/src` directory must be covered by a gate. Add a `ui-core` gate (TypeScript typecheck + vitest test run). The gate-coverage meta-test enforces this.

### 6. ask_user Card Implementation

[auto] [ask_user Card Implementation] — Q: "How should the ask_user clarification card map to elicitation events?" → Selected: "Map elicitation.requested to ClarificationCard with single-select/multi-select/free-text, submit via Gateway /v1/runs/{id}/elicitation" (recommended default)

**Rationale:** lawyer-desktop already has a polished `ClarificationCard` component (in `WorkflowProgressSteps.tsx`, ~150 lines) that supports:
- Single-select (radio-like) and multi-select (`allow_multiple`) via `toggleSelection()`
- Free-text input (`allow_free_text`)
- 2-4 questions per card
- Answer submission with display labels (pipe-separated values for multi-select)
- Disabled state while submitting

The mapping from `ElicitationRequestedPayload` to the card:
- `interrupt_id` → card ID (for Gateway submission)
- `intro` → card header text
- `questions[]` → rendered questions with `id`, `question`, `allow_multiple`, `options[]`
- `options[].label` / `options[].value` → option display and value
- `resume_state_ref` → stored for resume (not user-visible)

**Submission**: User answers are POSTed to `POST /v1/runs/{id}/elicitation` with `{ interrupt_id, answers: [{ question_id, answer }] }`. The Gateway forwards to the ACP backend's `elicitation/answer` method via the event bridge (Phase 90).

**Port the existing `ClarificationCard`** with minimal changes — replace the internal `onClarificationSubmit` callback with a Gateway API call. The component's UI logic (selection toggling, display formatting) is already correct and tested.

### 7. Five-Phase Progress Indicator

[auto] [Five-Phase Progress Indicator] — Q: "How should the 5-phase progress be rendered from events?" → Selected: "Map phase.changed events to DraftingProgressSteps component, with phase-to-step index mapping" (recommended default)

**Rationale:** lawyer-desktop has two progress components:
1. `DraftingProgressSteps` (77 lines): 5 static steps (查询法律法规 → 解析交易背景 → 检索相似案例 → 拟定文书正文 → 审查合规风险), with `phaseToActiveIndex()` mapping `thinking→1, tool→2, streaming→3, review→4`
2. `WorkflowProgressSteps` (367 lines): Dynamic workflow steps driven by `AgentTraceEvent` (intent → skill → thinking → tool → draft → clarify → complete)

For Phase 92, the five-phase progress is driven by `phase.changed` events (Phase 88's `PhaseChangedPayload` with `FivePhase = "research" | "intake" | "retrieval" | "draft" | "review"`). The mapping:
- `research` → step 0 (查询法律法规)
- `intake` → step 1 (解析交易背景及要求)
- `retrieval` → step 2 (检索相似案例与文书)
- `draft` → step 3 (拟定文书正文)
- `review` → step 4 (审查合规风险)

Port `DraftingProgressSteps` and update `phaseToActiveIndex()` to accept `FivePhase` values directly (instead of string phase names like "thinking"/"tool"). The `WorkflowProgressSteps` component (dynamic workflow with tool calls, thinking, clarification) is also ported — it's driven by `tool_call.*`, `thought.delta`, and `elicitation.requested` events rather than `phase.changed`.

### 8. Document Preview & Citation Panel

[auto] [Document Preview & Citation Panel] — Q: "How should document preview and citation panel work in ui-core?" → Selected: "Port DocPreview + CitationPanel, driven by artifact.created + citation.recorded events, document parsing via injected parser" (recommended default)

**Rationale:** lawyer-desktop's `DocPreview` (323 lines) and `CitationPanel` (105 lines) are the most complex UI components. They currently depend on:
- `legalDocument.ts` utils (extract/parse LLM JSON into preview state) — pure functions, portable
- `types/legal.ts` (Article, CitationCard, DocMeta, etc.) — pure types, portable
- `parseLegalDocument` invoke (backend JSON parser) — replace with injected `DocumentParser` interface
- `generateDocx` invoke (backend docx generation) — replace with Gateway `POST /v1/artifacts` or download link

**Porting approach:**
- `DocPreview` + `CitationPanel` + their CSS port with adapter injection
- `types/legal.ts` + `utils/legalDocument.ts` + `utils/citationAudit.ts` + `utils/renderSegs.tsx` port verbatim (pure logic)
- `DocumentParser` interface: web/desktop inject a parser that calls the Gateway; the component itself is parser-agnostic
- **Event-driven**: `artifact.created` events populate the document preview (artifact `kind` = `docx` or `trackchanges_docx`); `citation.recorded` events populate the citation panel
- **Document download**: `GET /v1/artifacts/{id}` via Gateway, with auth + tenant check

**The `DocDraftingLoader`** (24 lines, purely presentational loading animation) ports with zero changes.

</decisions>

<canonical_refs>

## Canonical References for Downstream Agents

### Event Vocabulary & Schemas
- `/home/sorawatcher/workspace/inkstatute-suite/packages/platform-contract/src/platform_contract/unified_events.py` — Python dataclasses for 13 event types
- `/home/sorawatcher/workspace/inkstatute-suite/packages/platform-contract/src/platform_contract/enums.py` — `RunEventType` enum (23 members)
- `/home/sorawatcher/workspace/inkstatute-suite/packages/platform-contract/src/platform_contract/schemas/` — JSON Schema files for all event types
- `/home/sorawatcher/workspace/inkstatute-suite/packages/platform-sdk-ts/src/events.ts` — TypeScript bindings for 13 event types (187 lines, hand-written)

### Gateway SSE Endpoint
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/sse.py` — `GatewaySseStream` with output boundary enforcement
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/app.py` — All Gateway endpoints
- `/home/sorawatcher/workspace/inkstatute-suite/services/gateway/src/gateway/event_buffer.py` — In-memory event buffer for Last-Event-ID replay
- `/home/sorawatcher/workspace/inkstatute-suite/packages/platform-sdk-ts/src/index.ts` — `PlatformApiClient` with `streamRun()` async generator

### Migration Source (lawyer-desktop)
- `/home/sorawatcher/workspace/lawyer-desktop/src/components/workspace/` — 10 workspace components (ChatPanel, Workspace, DocPreview, CitationPanel, WorkflowProgressSteps, DraftingProgressSteps, MessageFeedback, DocDraftingLoader, AgentTracePanel, SkillRefinementPanel)
- `/home/sorawatcher/workspace/lawyer-desktop/src/components/icons/Icons.tsx` — Icon component (315 lines)
- `/home/sorawatcher/workspace/lawyer-desktop/src/components/MentionComposer.tsx` — Mention composer (340 lines)
- `/home/sorawatcher/workspace/lawyer-desktop/src/components/MentionMenu.tsx` — Mention menu (45 lines)
- `/home/sorawatcher/workspace/lawyer-desktop/src/stores/conversation.ts` — Conversation store (1,591 lines — event handling logic to extract into reducer)
- `/home/sorawatcher/workspace/lawyer-desktop/src/stores/theme.ts` — Theme store (40 lines — portable verbatim)
- `/home/sorawatcher/workspace/lawyer-desktop/src/themes/molv-tokens.css` — Theme tokens (187 lines — three themes)
- `/home/sorawatcher/workspace/lawyer-desktop/src/themes/molv-base.css` — Base styles
- `/home/sorawatcher/workspace/lawyer-desktop/src/types/workflow.ts` — Workflow types (79 lines — ClarificationQuestion, WorkflowState, etc.)
- `/home/sorawatcher/workspace/lawyer-desktop/src/types/legal.ts` — Legal document types (131 lines — Article, CitationCard, DocMeta, etc.)
- `/home/sorawatcher/workspace/lawyer-desktop/src/utils/legalDocument.ts` — Document parsing utils
- `/home/sorawatcher/workspace/lawyer-desktop/src/utils/citationAudit.ts` — Citation audit utils
- `/home/sorawatcher/workspace/lawyer-desktop/src/utils/renderSegs.tsx` — Text segment renderer
- `/home/sorawatcher/workspace/lawyer-desktop/src/utils/chatTime.ts` — Chat time formatting
- `/home/sorawatcher/workspace/lawyer-desktop/src/utils/chatVisibility.ts` — Chat message visibility filter
- `/home/sorawatcher/workspace/lawyer-desktop/src/utils/chatLayout.ts` — Chat layout utils
- `/home/sorawatcher/workspace/lawyer-desktop/src/services/api.ts` — All 57 `invoke()` calls (to be replaced by Gateway HTTP)

### Existing Prototype (to be deprecated)
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web_chat/src/render.ts` — Prototype DOM-free renderer (263 lines — superseded by ui-core)
- `/home/sorawatcher/workspace/inkstatute-suite/apps/web_chat/src/index.ts` — Prototype entry

### Gate Registration
- `/home/sorawatcher/workspace/inkstatute-suite/scripts/run_v2_gates.py` — Gate registration (add ui-core gate)

### Project Decisions
- `/home/sorawatcher/workspace/inkstatute-suite/.planning/PROJECT.md` — Key Decisions table (共享 UI 沿用 SolidJS, lawyer-desktop 拆解, chat UI 单一实现)
- `/home/sorawatcher/workspace/inkstatute-suite/AGENTS.md` — Implementation Priorities #5: "extract before building apps/web or apps/desktop"

</canonical_refs>

<code_context>

## Reusable Assets and Patterns Found During Codebase Scouting

### lawyer-desktop Component Inventory (23 components, ~5,775 lines)

| Component | Lines | Tauri Deps | Port Strategy |
|-----------|-------|-----------|---------------|
| ChatPanel.tsx | 704 | Yes (dialog, webview) | Port with FileAdapter/DropAdapter injection |
| Workspace.tsx | 277 | No | Port verbatim (remove Tauri event listeners) |
| DocPreview.tsx | 323 | Yes (dialog save) | Port with FileAdapter for save dialog |
| CitationPanel.tsx | 105 | No | Port verbatim |
| WorkflowProgressSteps.tsx | 367 | No | Port verbatim (includes ClarificationCard) |
| DraftingProgressSteps.tsx | 77 | No | Port verbatim (update phase mapping) |
| MessageFeedback.tsx | 169 | No | Port verbatim |
| DocDraftingLoader.tsx | 24 | No | Port verbatim |
| AgentTracePanel.tsx | 799 | No | Port verbatim (dev-only trace viewer) |
| SkillRefinementPanel.tsx | 390 | No | Defer to Phase 94 (admin-only) |
| Icons.tsx | 315 | No | Port verbatim |
| MentionComposer.tsx | 340 | No | Port with WorkspaceAdapter |
| MentionMenu.tsx | 45 | No | Port verbatim |
| ConversationDrawer.tsx | 308 | No | Port verbatim |
| TitleBar.tsx | 226 | Yes (app version) | Port with AppInfoAdapter |
| AppUpdateBanner.tsx | 52 | Yes (updater) | Defer to Phase 94 (desktop-only) |
| HomePage.tsx | 291 | Yes (updater) | Port with AppInfoAdapter |
| SettingsPanel.tsx | 963 | Yes (many) | Defer to Phase 94 (desktop-only) |

### Tauri Dependency Map (5 files with direct @tauri-apps imports)
- `ChatPanel.tsx`: `@tauri-apps/plugin-dialog` (open file dialog), `@tauri-apps/api/webview` (getCurrentWebview)
- `DocPreview.tsx`: `@tauri-apps/plugin-dialog` (save dialog)
- `TitleBar.tsx`: `@tauri-apps/api/app` (getVersion)
- `HomePage.tsx`: `@tauri-apps/plugin-updater` (checkForAppUpdate, installAppUpdate)
- `SettingsPanel.tsx`: multiple Tauri plugins

### Theme System (portable verbatim)
- `molv-tokens.css` (187 lines): 3 themes via `data-theme="a|b|c"`, ~80 CSS custom properties per theme
- `molv-base.css`: base styles using tokens
- `theme.ts` (40 lines): `createSignal`, `localStorage`, `setAttribute("data-theme", variant)`
- 21 component CSS files: all reference `var(--*)` tokens, no hardcoded colors

### Event Handling Logic (to extract into reducer)
- `conversation.ts` (1,591 lines): Contains `applyTraceToWorkflow()` function (lines 297-439) that maps trace events to `WorkflowState` — this is the existing "rendering state machine" but driven by Tauri events, not SSE
- `normalizeClarification()` (lines 243-295): Parses clarification payload into `ClarificationRequest` — directly reusable for `elicitation.requested` events
- `traceToolLabel()` (lines 223-241): Maps tool names to Chinese labels — reusable
- `upsertStep()`, `markStep()`, `closeRunningSteps()`: Workflow step state transitions — reusable

### Existing TS SDK (platform-sdk-ts)
- `events.ts` (187 lines): Complete TS bindings for 13 event types — **already exists and usable**
- `index.ts` (152 lines): `PlatformApiClient` with `streamRun()` async generator — needs expansion for new Gateway endpoints
- `generate_sdk.py` (297 lines): Codegen from OpenAPI doc — regenerate `index.ts` after Phase 91's OpenAPI expansion

### Existing Prototype Renderer (apps/web_chat)
- `render.ts` (263 lines): DOM-free render records — a different approach (framework-agnostic) that is being superseded by ui-core's SolidJS components
- Will be marked deprecated per UI-06 success criterion #5

### Gateway SSE (Phase 91, complete)
- `sse.py`: `GatewaySseStream.encode_event()` — applies output boundary, returns SSE frame string or `None` (blocked)
- `event_buffer.py`: In-memory buffer per `run_id`, `seq`-based replay for `Last-Event-ID`
- SSE frame: `event: {event_type}\nid: {seq}\ndata: {json}\n\n`

### Five-Phase Progress (Phase 88, complete)
- `FivePhase = "research" | "intake" | "retrieval" | "draft" | "review"` (in `events.ts` line 93)
- `PhaseChangedPayload`: `{ phase: FivePhase, previous_phase?: FivePhase }`
- Existing `DraftingProgressSteps.tsx` has 5 steps with Chinese labels matching this phases

### Elicitation Contract (Phase 88, complete)
- `ElicitationRequestedPayload`: `{ interrupt_id, intro, questions: ElicitationQuestion[], resume_state_ref?, expires_at? }`
- `ElicitationQuestion`: `{ id, question, allow_multiple?, options?: ElicitationOption[] }`
- `ElicitationOption`: `{ label, value }`
- Matches lawyer-desktop's `ClarificationQuestion` / `ClarificationOption` types (in `workflow.ts`)

</code_context>

<deferred>

## Deferred Ideas for Future Phases

1. **SettingsPanel + SkillRefinementPanel** (1,353 lines combined) — Desktop-admin-specific components, deferred to Phase 94 (Desktop Client). They have heavy Tauri dependencies (provider setup, skill root management, MCP health, eval cases, sync settings) that are not needed for web chat.

2. **AppUpdateBanner + auto-update UI** — Desktop-only feature (Tauri updater plugin), deferred to Phase 94.

3. **AgentTracePanel** (799 lines) — Developer-only trace viewer. Ported to ui-core but may be gated behind a dev flag. Not needed for MVP web product.

4. **Mobile-optimized responsive layout** — Phase 93 (Web Client) handles responsive design. ui-core components are desktop-first but use CSS custom properties that allow responsive adjustments.

5. **Offline document caching** — Phase 94 (Desktop Client) handles offline read-only mode. ui-core's document preview is online-only in this phase.

6. **AG-UI mapping layer** — Out of scope (FUTURE-05). All clients are first-party; no third-party UI integration needed.

7. **Component-level code splitting / lazy loading** — Optimization deferred. ui-core ships as a single package; consumers can code-split at the app level.

8. **Storybook / component playground** — Nice-to-have for development, not required by any requirement. Can be added post-Phase 93.

</deferred>
