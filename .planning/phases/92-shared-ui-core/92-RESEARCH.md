---
phase: 92
slug: shared-ui-core
researched_at: 2026-08-07
researcher: auto
status: complete
---

# Phase 92 Research — Shared UI Core

## 1. lawyer-desktop Component Inventory

All 23 SolidJS components live under `/home/sorawatcher/workspace/lawyer-desktop/src/`.
Total: ~6,022 lines of `.tsx` (excluding test files, `App.tsx`, `index.tsx`, and utils).
Five components have direct `@tauri-apps/*` imports — confirmed by `grep -rl "@tauri-apps" src/components/`.

| # | Component | File path | Lines | Tauri deps | Category | Notes |
|---|-----------|-----------|-------|------------|----------|-------|
| 1 | ChatPanel | `src/components/workspace/ChatPanel.tsx` | 704 | Y | Core chat | `@tauri-apps/plugin-dialog` (open), `@tauri-apps/api/webview` (getCurrentWebview). Needs FileAdapter + DropAdapter. |
| 2 | Workspace | `src/components/workspace/Workspace.tsx` | 277 | N | Layout | Orchestrates ChatPanel + DocPreview + CitationPanel. Remove Tauri event listeners. |
| 3 | DocPreview | `src/components/workspace/DocPreview.tsx` | 323 | Y | Document | `@tauri-apps/plugin-dialog` (save). Needs FileAdapter for save dialog. Uses `generateDocx` invoke → replace with Gateway. |
| 4 | CitationPanel | `src/components/workspace/CitationPanel.tsx` | 105 | N | Citation | Pure presentational. Driven by `citationGroups()` from conversation store. |
| 5 | WorkflowProgressSteps | `src/components/workspace/WorkflowProgressSteps.tsx` | 367 | N | Progress | Contains `ClarificationCard`, `WorkflowNotice`, `ModeSwitchCard`, `WorkflowSuggestions`. |
| 6 | DraftingProgressSteps | `src/components/workspace/DraftingProgressSteps.tsx` | 77 | N | Progress | 5 static steps. `phaseToActiveIndex()` maps thinking/tool/streaming/review → 1/2/3/4. |
| 7 | MessageFeedback | `src/components/workspace/MessageFeedback.tsx` | 169 | N | Feedback | Thumbs up/down + comment. Port verbatim. |
| 8 | DocDraftingLoader | `src/components/workspace/DocDraftingLoader.tsx` | 24 | N | Loading | Pure presentational animation. Port verbatim. |
| 9 | AgentTracePanel | `src/components/workspace/AgentTracePanel.tsx` | 799 | N | Dev trace | Developer-only trace viewer. Port but gate behind dev flag. |
| 10 | SkillRefinementPanel | `src/components/workspace/SkillRefinementPanel.tsx` | 390 | N | Admin | Defer to Phase 94 (desktop-admin-only). |
| 11 | Icons | `src/components/icons/Icons.tsx` | 315 | N | Icons | SVG icon set. Port verbatim. |
| 12 | MentionComposer | `src/components/MentionComposer.tsx` | 340 | N | Input | Needs WorkspaceAdapter for file listing. |
| 13 | MentionMenu | `src/components/MentionMenu.tsx` | 45 | N | Input | Dropdown for @-mentions. Port verbatim. |
| 14 | ConversationDrawer | `src/components/layout/ConversationDrawer.tsx` | 308 | N | Layout | Conversation history sidebar. Port verbatim. |
| 15 | TitleBar | `src/components/layout/TitleBar.tsx` | 226 | Y | Layout | `@tauri-apps/api/app` (getVersion). Needs AppInfoAdapter. |
| 16 | AppUpdateBanner | `src/components/layout/AppUpdateBanner.tsx` | 52 | Y | Layout | `@tauri-apps/plugin-updater`. Defer to Phase 94 (desktop-only). |
| 17 | HomePage | `src/components/home/HomePage.tsx` | 291 | Y | Home | `@tauri-apps/plugin-updater` (checkForAppUpdate, installAppUpdate). Needs AppInfoAdapter. |
| 18 | SettingsPanel | `src/components/settings/SettingsPanel.tsx` | 963 | Y | Settings | Multiple Tauri plugins. Defer to Phase 94 (desktop-admin-only). |
| 19 | App | `src/App.tsx` | 141 | N | Root | App shell — not ported (consumers build their own shell). |
| 20 | index | `src/index.tsx` | 9 | N | Entry | Vite entry — not ported. |
| 21 | jsonHighlight | `src/utils/jsonHighlight.tsx` | 50 | N | Util | JSON syntax highlighter for AgentTracePanel. Port verbatim. |
| 22 | renderSegs | `src/utils/renderSegs.tsx` | 47 | N | Util | Text segment renderer (inline formatting). Port verbatim. |
| 23 | Icons.test | `src/components/icons/__tests__/Icons.test.tsx` | — | N | Test | Test file — port as fixture. |

**Tauri dependency map (5 files with direct `@tauri-apps` imports):**

| File | Tauri import | Usage | Adapter replacement |
|------|-------------|-------|---------------------|
| ChatPanel.tsx | `@tauri-apps/plugin-dialog`, `@tauri-apps/api/webview` | `open()` file dialog, `getCurrentWebview()` | `FileAdapter.open()`, remove webview |
| DocPreview.tsx | `@tauri-apps/plugin-dialog` | `save()` for docx export | `FileAdapter.save()` |
| TitleBar.tsx | `@tauri-apps/api/app` | `getVersion()` | `AppInfoAdapter.getVersion()` |
| HomePage.tsx | `@tauri-apps/plugin-updater` | `checkForAppUpdate()`, `installAppUpdate()` | `AppInfoAdapter` (web: no-op) |
| SettingsPanel.tsx | multiple Tauri plugins | provider setup, skill root, MCP, eval | Deferred to Phase 94 |

**CSS files (21 component CSS + 2 theme CSS + 2 global):** All reference `var(--*)` tokens — no hardcoded colors. Port verbatim.

## 2. Event Vocabulary & TS Bindings

### 13 Event Types (Phase 88, frozen)

The unified event vocabulary is defined in three isomorphic locations:
- **JSON Schemas**: `packages/platform-contract/src/platform_contract/schemas/`
- **Python dataclasses**: `packages/platform-contract/src/platform_contract/unified_events.py`
- **TypeScript bindings**: `packages/platform-sdk-ts/src/events.ts` (187 lines, hand-written)

The TS file header explicitly states: *"Hand-written — not auto-generated."*

| Event type | TS payload interface | Key fields |
|------------|---------------------|------------|
| `session.started` | `SessionStartedPayload` | `backend_id`, `capabilities?`, `session_id?` |
| `message.delta` | `MessageDeltaPayload` | `delta`, `message_id?` |
| `message.completed` | `MessageCompletedPayload` | `content`, `message_id?` |
| `thought.delta` | `ThoughtDeltaPayload` | `delta` |
| `tool_call.started` | `ToolCallStartedPayload` | `tool_call_id`, `tool_name`, `kind?`, `title?` |
| `tool_call.delta` | `ToolCallDeltaPayload` | `tool_call_id`, `content?`, `status?` |
| `tool_call.completed` | `ToolCallCompletedPayload` | `tool_call_id`, `status`, `content?`, `file_locations?`, `error?` |
| `plan.updated` | `PlanUpdatedPayload` | `plan: Array<{title, status, steps?}>` |
| `phase.changed` | `PhaseChangedPayload` | `phase: FivePhase`, `previous_phase?` |
| `elicitation.requested` | `ElicitationRequestedPayload` | `interrupt_id`, `intro`, `questions[]`, `resume_state_ref?`, `expires_at?` |
| `permission.requested` | `PermissionRequestedPayload` | `permission_id`, `tool_call_id`, `description`, `kind?` |
| `artifact.created` | `ArtifactCreatedPayload` | `artifact: Artifact` (artifact_id, kind, name, uri, mime_type?, template_ref?, features?, source_refs?) |
| `citation.recorded` | `CitationRecordedPayload` | `citations: CitationRecord[]` (source, status: "verified"\|"retrieved"\|"unverified") |
| `run.state_changed` | `RunStateChangedPayload` | `status`, `previous_status?`, `error?` |
| `error` | `ErrorEventPayload` | `error: ErrorInfo` (category, code?, message?, stage?, retryable?) |

**Shared types**: `ErrorInfo`, `Artifact`, `FivePhase = "research" | "intake" | "retrieval" | "draft" | "review"` (line 93).

**Union & envelope:**
```typescript
export type UnifiedEventPayload = SessionStartedPayload | MessageDeltaPayload | ... | ErrorEventPayload;
export interface RunEventEnvelope {
  event_id: string; run_id: string; event_type: string;
  occurred_at: string; ingested_at?: string; seq: number;
  payload?: UnifiedEventPayload; metadata?: Record<string, unknown>;
}
```

### PlatformApiClient.streamRun() (platform-sdk-ts/src/index.ts, lines 92-116)

The async generator already exists and is auto-generated by `generate_sdk.py`:

```typescript
async *streamRun(run_id: string): AsyncIterable<SseFrame> {
  const response = await this.fetchImpl(this.baseUrl + `/v1/runs/${run_id}/events`, {
    method: "GET",
    headers: { "accept": "text/event-stream", ...this.defaultHeaders },
  });
  // ... reads response.body, splits on "\n\n", parseSseFrame() per frame
}
```

`SseFrame` interface (lines 14-18): `{ event: string; id: string; data: string }`.

**Note:** `streamRun()` does NOT currently send `Last-Event-ID` on reconnection. The ui-core event stream consumer must add this header on reconnect (using the last `seq` received as `id`).

**Existing client methods** (from OpenAPI codegen): `cancelRun`, `createRun`, `pollRun`, `streamRun`, `submitApproval`. Phase 91's expanded Gateway endpoints (`/v1/sessions`, `/v1/runs/{id}/elicitation`, `/v1/artifacts/{id}`, `/v1/uploads`, `/v1/feedback`, `/v1/skills`) require regenerating `index.ts` via `python packages/platform-sdk-ts/scripts/generate_sdk.py`.

## 3. Gateway SSE Endpoint

### SSE Frame Encoding (services/gateway/src/gateway/sse.py, 172 lines)

`GatewaySseStream` wraps `encode_sse_event` from the `web_sse` package with output boundary enforcement:

```python
class GatewaySseStream:
    def encode_event(self, event: RunEvent | Mapping[str, Any]) -> str | None:
        payload = _event_to_mapping(event)
        text_content = _extract_text(payload)
        if text_content is not None:
            decision = self._boundary.apply("web", text=text_content, ...)
            if decision.action == BoundaryAction.BLOCK:
                return None  # blocked event dropped
            if decision.visible_text is not None:
                _replace_text(payload, decision.visible_text)
        return encode_sse_event(payload)  # "event: {type}\nid: {seq}\ndata: {json}\n\n"
```

**SSE frame format**: `event: {event_type}\nid: {seq}\ndata: {json}\n\n`

**V3→V2 event type normalization** for boundary (lines 107-114): `message.delta` → `message_delta`, `run.state_changed` → `state_changed`, `artifact.created` → `artifact_created`, `elicitation.requested` / `permission.requested` → `approval_requested`.

**`parse_last_event_id()`** (lines 77-90): Extracts `Last-Event-ID` header, parses as integer, returns `None` if absent/invalid.

### Last-Event-ID Replay (services/gateway/src/gateway/event_buffer.py, 166 lines)

`RunEventBuffer` — in-memory per-run event buffer:

```python
class RunEventBuffer:
    def __init__(self, *, max_events_per_run=1000, terminal_retention_seconds=300.0): ...

    def append(self, run_id: str, event: RunEvent) -> None:
        # FIFO eviction when over capacity; marks terminal on run.state_changed

    def replay(self, run_id: str, last_seq: int) -> list[RunEvent]:
        # Returns events with seq > last_seq, ordered by seq ascending
```

- **Thread-safe** via `threading.Lock` — supports concurrent SSE connections.
- **Terminal states**: `succeeded`, `failed`, `cancelled` → triggers 5-minute retention countdown.
- **Single-firm scale**: in-memory only, no persistence (sufficient for ≤50 lawyers per Key Decision #4).

**Reconnection flow**: Client disconnects → reconnects with `Last-Event-ID: {last_seq}` → Gateway calls `buffer.replay(run_id, last_seq)` → replays missed events → continues streaming new events.

## 4. web_chat Prototype (to be deprecated)

**File**: `/home/sorawatcher/workspace/inkstatute-suite/apps/web_chat/src/render.ts` (263 lines)

A **DOM-free, framework-agnostic** renderer that converts `RunEvent` records into `RenderRecord` objects:

```typescript
export interface RenderRecord {
  role: "user" | "assistant" | "system" | "artifact";
  text: string; kind: string; refs: string[];
  meta: Record<string, string>;
}
```

**Current event handling** (lines 136-248): Handles only 6 event types — `state_changed`, `message_delta`, `artifact_ready`, `approval_requested`, `error`, `run_completed`. Uses **V2 event names** (not the Phase 88 unified vocabulary). All other events fall to `default` → "unknown" record.

**Safety features**: `assertSafeMetadata()` rejects forbidden keys (`raw_payload`, `rawbody`, etc.); `assertSafeText()` rejects forbidden markers (`sk-`, `AKIA`, `BEGIN PRIVATE KEY`); `escapeText()` HTML-escapes all output.

**Why it's deprecated**: It's a prototype that:
1. Uses V2 event names, not the 13 unified types from Phase 88
2. Is framework-agnostic (DOM-free) — a different approach than ui-core's SolidJS components
3. Handles only 6 of 13 event types
4. Has no ask_user card, no document preview, no citation panel, no five-phase progress
5. Cannot be consumed by `apps/web` (Phase 93) or `apps/desktop` (Phase 94) as a UI package

**UI-06 success criterion #5**: Project-wide grep must find no second chat message list / streaming renderer / ask_user card implementation; `apps/web_chat` prototype renderer marked deprecated.

## 5. conversation.ts Reusable Logic

**File**: `/home/sorawatcher/workspace/lawyer-desktop/src/stores/conversation.ts` (1,591 lines)

This is the existing "rendering state machine" — but driven by Tauri events (`onChatStream`, `onAgentTrace`), not SSE. Three functions are directly reusable for the ui-core event reducer:

### `traceToolLabel()` (lines 223-241)

Maps tool names to Chinese display labels. Reusable for `tool_call.started` events:

```typescript
function traceToolLabel(name: string): { label: string; detail?: string } {
  if (name.startsWith("mcp__")) {
    if (/law|legal|fagui|statute|wenshu|case|judgment/i.test(name))
      return { label: "检索法律法规与类案" };
    return { label: "查询外部数据源" };
  }
  if (name === "legal_search") return { label: "聚合检索法律依据" };
  if (name === "ask_user") return { label: "发现还需要补充信息" };
  // ... 10+ more mappings
  return { label: "处理辅助任务" };
}
```

### `normalizeClarification()` (lines 243-295)

Parses raw clarification payload into `ClarificationRequest`. Directly maps to `elicitation.requested` event handling:

- Accepts string or object options (generates `id` if missing)
- Trims and validates question text
- Caps at 4 questions (`.slice(0, 4)`)
- Sets `allow_multiple` and `allow_free_text` defaults
- Returns `undefined` if no valid questions

**Mapping to `ElicitationRequestedPayload`**: The Phase 88 payload already has structured `questions[]` with `id`, `question`, `allow_multiple`, `options[]` — so `normalizeClarification()` becomes a thin adapter that maps `ElicitationOption` → `ClarificationOption` and `ElicitationQuestion` → `ClarificationQuestion`.

### `applyTraceToWorkflow()` (lines 297-439)

The core reducer — maps `AgentTraceEvent` kinds to `WorkflowState` transitions:

| Trace kind | Action | Unified event equivalent |
|------------|--------|--------------------------|
| `turn_start` | no-op | `session.started` |
| `classify_start` / `classify_result` | upsert "intent" step | `plan.updated` |
| `skill_activated` | upsert "skill" step (done) | `plan.updated` |
| `thinking` / `thinking_delta` | upsert "thinking" step (run) | `thought.delta` |
| `tool_call` | upsert "tool" step (run) via `traceToolLabel` | `tool_call.started` |
| `tool_result` | markStep done/error | `tool_call.completed` |
| `ask_user` | normalizeClarification + upsert "clarify" + "wait-user" steps, status="waiting" | `elicitation.requested` |
| `final_answer` / `stream_delta` | upsert "draft" step (run) | `message.delta` |
| `citation_audit` | upsert "cite-audit" step (done) | `citation.recorded` |
| `stream_done` | markStep "draft" done | `message.completed` |
| `error` | upsert "error" step, status="error" | `error` |
| `turn_end` | closeRunningSteps + upsert "complete", status="complete"/"error" | `run.state_changed` |

**Helper functions** (reusable): `upsertStep()`, `markStep()`, `closeRunningSteps()` — workflow step state transitions.

**New reducer design**: The ui-core event reducer replaces this with a pure function `(state, RunEventEnvelope) → state` that processes all 13 unified event types. The `applyTraceToWorkflow` logic is the blueprint — same step-state transitions, different event source.

## 6. 墨律 Theme System

### molv-tokens.css (187 lines)

**File**: `/home/sorawatcher/workspace/lawyer-desktop/src/themes/molv-tokens.css`

Three themes via `data-theme` attribute on `document.documentElement`:

| Theme | Selector | Character | Key colors |
|-------|----------|-----------|------------|
| A 传统律所 (default) | `:root, [data-theme="a"]` | Warm parchment, red seal | `--app-bg: #f4ede0`, `--accent: #74302d`, `--gold: #a3823f` |
| B 深色法务终端 | `[data-theme="b"]` | Dark terminal, blue accent | `--app-bg: #13161d`, `--accent: #6b9bff`, `--gold: #57c8c0` |
| C 克制现代 | `[data-theme="c"]` | Clean white, green accent | `--app-bg: #ffffff`, `--accent: #1f5132`, `--gold: #1f5132` |

**~80 CSS custom properties per theme**: `--app-bg`, `--chat-bg`, `--surface`, `--surface-2`, `--ink`, `--ink-soft`, `--muted`, `--line`, `--accent`, `--gold`, `--amber`, `--sheet-*` (document sheet styling), `--user-*` (user message bubble), `--titlebar-*`, `--seal-*`, `--doc-risk-*`, `--en-*` (English text styling), `--cite-font`, `--radius`, `--shadow-pop`.

**Font families** (shared `:root`): `--serif` (Noto Serif SC + Newsreader), `--sans` (Noto Sans SC), `--mono` (Spline Sans Mono). Loaded via `@import url('https://fonts.googleapis.com/...')` at top of file.

### molv-base.css (336 lines)

**File**: `/home/sorawatcher/workspace/lawyer-desktop/src/themes/molv-base.css`

Base styles using the tokens — app frame, titlebar, scrollbar, etc. All reference `var(--*)`, no hardcoded colors.

### theme.ts (40 lines)

**File**: `/home/sorawatcher/workspace/lawyer-desktop/src/stores/theme.ts`

```typescript
export type ThemeVariant = "a" | "b" | "c";
const STORAGE_KEY = "ml-theme";

const [theme, setThemeSignal] = createSignal<ThemeVariant>(readStoredTheme());

function applyTheme(variant: ThemeVariant) {
  document.documentElement.setAttribute("data-theme", variant);
}

export function useTheme() {
  // onMount: applyTheme(theme())
  // setTheme(variant): signal + localStorage + applyTheme
  // cycleTheme(): a → b → c → a
  return { theme, setTheme, cycleTheme };
}
```

**Port strategy**: All three files port verbatim into `packages/ui-core/src/themes/` and `packages/ui-core/src/stores/theme.ts`. No JS theme engine — just `setAttribute("data-theme", variant)`. The 21 component CSS files also port verbatim (they reference CSS custom properties, not hardcoded colors).

**Font loading**: `@import url(...)` remains as-is for web. Desktop (Tauri) may bundle fonts locally — handled in Phase 94.

## 7. Build Tooling

### Vite Library Mode for SolidJS

lawyer-desktop uses **Vite 8 + vite-plugin-solid** (per its AGENTS.md). For ui-core:

- **Build tool**: Vite library mode (`build.lib` in `vite.config.ts`) with `vite-plugin-solid` for SolidJS JSX compilation
- **Output**: ESM + CJS + type declarations (`.d.ts`)
- **Package name**: `@inkstatute/ui-core` (matching `@inkstatute/platform-sdk-ts`)
- **Consumption**: `apps/web` and `apps/desktop` declare `"@inkstatute/ui-core": "workspace:*"` — Bun's workspace protocol links locally
- **Peer dependencies**: `solid-js`, `solid-markdown`, `remark-gfm`, `highlight.js` (consumers provide them)
- **Direct dependency**: `@inkstatute/platform-sdk-ts`
- **CSS export**: `import "@inkstatute/ui-core/themes"` (side-effect import)
- **TypeScript**: `tsconfig.json` with `strict: true`, `jsx: "preserve"`, `jsxImportSource: "solid-js"`. Type declarations via `tsc --emitDeclarationOnly`.

### Gate Coverage

Per AGENTS.md: *"Every new `packages/*/src` directory must be covered by a gate — the `gate-coverage` meta-test enforces this."*

Add a `ui-core` gate in `scripts/run_v2_gates.py`: TypeScript typecheck + vitest test run. The existing 28 gates must stay green.

### solid-markdown shim

lawyer-desktop's AGENTS.md notes: `solid-markdown` needs a `debug` shim in `vite.config.ts` (see `src/shims/debug.ts`). This must be carried into ui-core's Vite config.

## 8. ask_user / Elicitation Mapping

### ClarificationCard (WorkflowProgressSteps.tsx, lines 146-297)

The `ClarificationCard` component is a polished, tested implementation supporting:

- **Single-select** (radio-like): `toggleSelection()` with `allowMultiple=false` → returns `[entry]`
- **Multi-select**: `toggleSelection()` with `allowMultiple=true` → toggle add/remove
- **Free-text input**: `allow_free_text !== false` → `<input class="clarify-free">` alongside options
- **2-4 questions** per card (enforced by `normalizeClarification().slice(0, 4)`)
- **Answer formatting**: multi-select values joined with `|`, display labels joined with `、`
- **Disabled state** while submitting (`props.disabled?.()`)
- **Answered state**: shows `已选：{display_answer}` when `status === "answered"`

### Type Mapping: ElicitationRequestedPayload → ClarificationCard

| `ElicitationRequestedPayload` (events.ts) | `ClarificationRequest` (workflow.ts) | Notes |
|-------------------------------------------|--------------------------------------|-------|
| `interrupt_id` | `id` | Used for Gateway submission |
| `intro` | `intro` | Card header text |
| `questions[].id` | `questions[].id` | Direct map |
| `questions[].question` | `questions[].question` | Direct map |
| `questions[].allow_multiple` | `questions[].allow_multiple` | Direct map |
| `questions[].options[].label` | `options[].label` | Direct map |
| `questions[].options[].value` | `options[].value` | Direct map (ClarificationOption.value is optional) |
| — | `options[].id` | Generated if missing (normalizeClarification) |
| — | `options[].description` | Not in elicitation schema; optional |
| — | `questions[].allow_free_text` | Not in elicitation schema; default true |
| `resume_state_ref` | — | Stored for resume, not user-visible |
| `expires_at` | — | Could drive timeout UI (future) |

**Submission**: User answers POSTed to `POST /v1/runs/{id}/elicitation` with `{ interrupt_id, answers: [{ question_id, answer }] }`. The Gateway forwards to the ACP backend's `elicitation/answer` method via the event bridge (Phase 90).

**Port approach**: Replace internal `onClarificationSubmit` callback with a Gateway API call. The component's UI logic (selection toggling, display formatting) is already correct and tested.

### Supporting types (workflow.ts, 79 lines)

```typescript
export interface ClarificationOption { id: string; label: string; value?: string; description?: string; }
export interface ClarificationQuestion { id: string; question: string; options: ClarificationOption[]; allow_multiple?: boolean; allow_free_text?: boolean; }
export interface ClarificationAnswer { question_id: string; question: string; answer: string; display_answer?: string; }
export interface ClarificationRequest { id: string; intro?: string; questions: ClarificationQuestion[]; status: "pending" | "answered"; answers?: ClarificationAnswer[]; }
```

## 9. Five-Phase Progress

### DraftingProgressSteps.tsx (77 lines)

5 static steps with Chinese labels, driven by a `phase` signal:

```typescript
export const DRAFTING_STEPS = [
  { id: "law", label: "查询法律法规" },
  { id: "intake", label: "解析交易背景及要求" },
  { id: "research", label: "检索相似案例与文书" },
  { id: "draft", label: "拟定文书正文" },
  { id: "review", label: "审查合规风险" },
] as const;
```

**Current `phaseToActiveIndex()`** maps V2 phase strings:
- `thinking` → 1, `tool` → 2, `streaming` → 3, `review` → 4, default → 0

**Phase 92 update**: Map `FivePhase` values directly:
- `research` → 0 (查询法律法规)
- `intake` → 1 (解析交易背景及要求)
- `retrieval` → 2 (检索相似案例与文书)
- `draft` → 3 (拟定文书正文)
- `review` → 4 (审查合规风险)

**Driven by**: `phase.changed` events → `PhaseChangedPayload.phase` → `DraftingProgressSteps` `phase` prop.

**`stepState()`**: Returns `"done"` (index < active), `"run"` (index === active), or `"wait"` (index > active).

### WorkflowProgressSteps.tsx (367 lines) — Dynamic workflow

Also ported — driven by `tool_call.*`, `thought.delta`, and `elicitation.requested` events (not `phase.changed`). Contains:
- `WorkflowNotice` — collapsible progress header with running/done/error status
- `ClarificationCard` — the ask_user card (see §8)
- `ModeSwitchCard` — pre-turn confirmation when switching modes
- `WorkflowSuggestions` — clickable suggestion prompts

## 10. Document Preview & Citation Panel

### DocPreview.tsx (323 lines)

The most complex UI component. Currently depends on:
- `legalDocument.ts` utils — pure functions (extract/parse LLM JSON into preview state) → port verbatim
- `types/legal.ts` (131 lines) — `Article`, `ArticleBlock`, `CitationCard`, `DocMeta`, `TextSegment`, `LegalDocumentModel` → port verbatim
- `parseLegalDocument` invoke (backend JSON parser) → replace with injected `DocumentParser` interface
- `generateDocx` invoke (backend docx generation) → replace with Gateway `GET /v1/artifacts/{id}` or download link
- `save` from `@tauri-apps/plugin-dialog` → replace with `FileAdapter.save()`

**Two rendering modes**:
1. **Structured document**: `articles()` array → rendered with `renderSegs()` for inline formatting, `contentEditable` for edit mode, article notes with risk warnings
2. **Markdown document**: `documentMarkdown()` → `<SolidMarkdown remarkPlugins={[remarkGfm]}>` with audit checklist

**Features**: preview/edit toggle, version pill (第 N 稿), citation toggle, version compare, docx export, audit checklist (`auditChecklistMarkdown`), `DocDraftingLoader` fallback during streaming.

### CitationPanel.tsx (105 lines)

Pure presentational, driven by `citationGroups()` from conversation store:

- **Two tabs**: 法条 (law) / 判例·类案 (case)
- **Verification badges**: `verified` → "✓ 已核验", `retrieved` → "✓ 已检索", `unverified` → "⚠ 待律师复核"
- **Tier labels**: L1-法规（本地库）/ L2-入库
- **Actions**: 插入引用 (insert), 在文中定位 (locate)

**Event-driven mapping**:
- `citation.recorded` events → `CitationRecordedPayload.citations[]` → populate citation panel
- `CitationRecord.status` ("verified" | "retrieved" | "unverified") maps directly to `CitationCard.verified`

### Legal types (types/legal.ts, 131 lines)

Key types to port verbatim:
- `TextSegment` — inline formatting segments (`t`, `b`, `cite`, `risk`, `accent`)
- `Article` / `ArticleBlock` — structured document articles with mixed prose + GFM tables
- `CitationCard` — citation display model with verification status
- `CitationAudit` / `CitationAuditItem` — mirrors backend citation audit
- `DocMeta` — document metadata (title, en, parties, recital)
- `LegalDocumentModel` — mirrors backend Rust types
- `CitationGroups` — `{ law: CitationCard[], case: CitationCard[] }`

## Summary & Recommendations

### Key Findings

1. **23 components, ~6,022 lines** — 5 with Tauri deps (ChatPanel, DocPreview, TitleBar, HomePage, SettingsPanel). Adapter pattern (FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter) cleanly separates platform concerns.

2. **TS event bindings already complete** — `events.ts` (187 lines) has all 13 types + `RunEventEnvelope` + `UnifiedEventPayload` union. `PlatformApiClient.streamRun()` async generator exists. Only gap: `streamRun()` doesn't send `Last-Event-ID` on reconnect — ui-core must add this.

3. **Gateway SSE is production-ready** — `GatewaySseStream` with output boundary + `RunEventBuffer` with seq-based replay. Frame format: `event: {type}\nid: {seq}\ndata: {json}\n\n`.

4. **conversation.ts is the reducer blueprint** — `applyTraceToWorkflow()` (lines 297-439) maps trace events to `WorkflowState` with the exact same state transitions needed for the 13 unified event types. `normalizeClarification()` and `traceToolLabel()` are directly reusable.

5. **Theme system ports verbatim** — `molv-tokens.css` (187 lines, 3 themes, ~80 tokens each) + `molv-base.css` (336 lines) + `theme.ts` (40 lines). No JS theme engine. 21 component CSS files all use `var(--*)`.

6. **ClarificationCard is production-quality** — supports single/multi/free-text, 2-4 questions, disabled state, answered display. Maps cleanly to `ElicitationRequestedPayload`.

7. **web_chat render.ts is a dead-end prototype** — V2 event names, 6 of 13 types, DOM-free (wrong approach for SolidJS ui-core). Mark deprecated per UI-06.

8. **Deferred components** (1,353 lines): SettingsPanel (963) + SkillRefinementPanel (390) → Phase 94. AppUpdateBanner (52) → Phase 94. AgentTracePanel (799) → port but gate behind dev flag.

### Risks

1. **`streamRun()` missing Last-Event-ID** — The auto-generated SDK doesn't send the reconnection header. Either patch `streamRun()` to accept a `lastEventId` param, or have ui-core's event stream consumer manage reconnection at the fetch level. **Recommendation**: Add `lastEventId?: number` param to `streamRun()` in the OpenAPI spec / codegen template.

2. **`generate_sdk.py` regeneration** — Phase 91 expanded Gateway endpoints but `index.ts` may not yet reflect all new endpoints (`/v1/sessions`, `/v1/runs/{id}/elicitation`, `/v1/artifacts/{id}`, `/v1/uploads`, `/v1/feedback`, `/v1/skills`). Verify before ui-core depends on them.

3. **`solid-markdown` debug shim** — Required in Vite config or build breaks. Easy to miss.

4. **Document parser injection** — DocPreview depends on `parseLegalDocument` (backend JSON parser via Tauri invoke). The `DocumentParser` interface must be defined and both web/desktop must implement it. This is the most complex adapter.

5. **CSS side-effect imports** — Bun/Vite must correctly handle `import "@inkstatute/ui-core/themes"` as a side-effect CSS import. Verify in build config.

6. **Gate coverage enforcement** — The `gate-coverage` meta-test will fail if `packages/ui-core/src` is not registered in `scripts/run_v2_gates.py`. Must add gate early.

### Recommendations for Planner

1. **Port all 23 components in one pass** — partial extraction creates integration debt. Strip Tauri deps via 4 adapter interfaces.
2. **Build the event reducer first** — it's the foundation. Use `applyTraceToWorkflow()` as the blueprint, map 13 unified types. Write fixture-driven tests before any component ports.
3. **Port theme system + types verbatim** — zero-risk, immediate value. `molv-tokens.css`, `molv-base.css`, `theme.ts`, `types/legal.ts`, `types/workflow.ts` all port as-is.
4. **Regenerate `index.ts`** from expanded OpenAPI before adding Gateway-dependent features (elicitation submission, artifact download).
5. **Add `lastEventId` support to `streamRun()`** — either via codegen template or manual patch with a comment to preserve on next regen.
6. **Mark `apps/web_chat/src/render.ts` deprecated** with a header comment pointing to `@inkstatute/ui-core`.
7. **Register ui-core gate** in `scripts/run_v2_gates.py` before any source lands in `packages/ui-core/src/`.
