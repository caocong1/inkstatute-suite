---
phase: 93
plan: 02
title: "Wave 2 — Workspace ChatPanel + EventStreamStore wiring + SSE reconnection + send/clarify/feedback actions"
wave: 2
requirements:
  - UI-04
tasks_completed: 5
commits:
  - 9571174: "feat(93-02): runBuilder utility — constructs AgentTurn + SolutionBinding payload for gateway.createRun()"
  - 0470661: "feat(93-02): useEventStream hook — wraps createEventStream with SolidJS lifecycle management"
  - 09f3ea9: "feat(93-02): SessionContext — manages active run, message sending, clarification/feedback submission"
  - 08f39a8: "feat(93-02): full WorkspacePage — ChatPanel + DocPreview + CitationPanel wired to RenderState via SessionContext"
  - be0e773: "test(93-02): SSE reconnection verification — Last-Event-ID resume, no duplicate rendering, exponential backoff, terminal stop"
tests:
  web_vitest: 51
  total_new: 30
gates: 33
status: complete
self_check: PASSED
---

# Plan 93-02 Summary — Wave 2 Workspace Wiring

## Goal

Wire the ui-core `ChatPanel` to live Gateway SSE via `createEventStream()` + `PlatformApiClient`, proving the core lawyer interaction: send a message → see streaming reply → see five-phase progress → see events rendered. This plan replaces the tracer workspace shell (from Plan 93-01) with a fully functional workspace page that creates runs, streams events, and renders all ui-core chat components driven by `RenderState` from the event reducer.

## Tasks Executed

### Task 93-02-01: runBuilder utility
- Created `apps/web/src/lib/runBuilder.ts` — `buildRunBody(options: RunBodyOptions): unknown`
- Constructs the `POST /v1/runs` body with `turn` (AgentTurn) + `solution` (SolutionBinding) payload
- `turn_id`: `crypto.randomUUID()`, `channel`: `"web"`, `message_type`: `"text"`
- `solution.solution_id`: `"inkstatute-default"` (default solution)
- Created `apps/web/tests/fixtures/run-events.json` — 15-event fixture sequence copied from ui-core
- Created `apps/web/tests/runBuilder.test.ts` — 7 tests (shape, unique IDs, attachments, tenant/session/backend)
- **Commit:** `9571174`

### Task 93-02-02: useEventStream hook
- Created `apps/web/src/hooks/useEventStream.ts` — SolidJS hook wrapping `createEventStream()`
- Reactive lifecycle: `createEffect` cleans up old stream on `runId()` change, creates new one
- `onCleanup()` stops stream on unmount (prevents memory leaks)
- Returns `state()`, `isStreaming()`, `error()`, `reconnect()` signals
- Created `apps/web/tests/use-event-stream.test.ts` — 5 tests (initial state, stream creation, cleanup, runId change, error capture)
- **Commit:** `0470661`

### Task 93-02-03: SessionContext
- Created `apps/web/src/contexts/SessionContext.tsx` — per-workspace-page context
- `sendMessage()`: builds run body via `runBuilder`, calls `gateway.createRun()`, sets `runId` signal → triggers streaming
- `submitClarification()`: calls `gateway.submitElicitation()`, catches 501 errors gracefully (stub endpoint)
- `submitFeedback()`: calls `gateway.submitFeedback()` with correct body (implemented endpoint)
- `cancelRun()`: calls `gateway.cancelRun()` (EventStreamStore detects terminal event)
- Uses `useEventStream(runId)` for reactive `RenderState`
- Exported `SessionContext` and `SessionContextValue` for testing
- Added `ClarificationAnswer` + workflow type exports to `packages/ui-core/src/index.ts` (additive)
- Created `apps/web/tests/session-context.test.tsx` — 5 tests (initial state, sendMessage, submitFeedback, cancelRun, 501 graceful)
- **Commit:** `09f3ea9`

### Task 93-02-04: Full WorkspacePage
- Rewrote `apps/web/src/pages/WorkspacePage.tsx` — full workspace with ChatPanel + DocPreview + CitationPanel
- `ChatPanel` receives `state`, `onSend`, `onClarificationSubmit`, `onFeedback` from `SessionContext`
- `DocPreview` driven by `state().artifacts[0]` (first artifact)
- `CitationPanel` driven by `groupCitations(state().citations)` — toggle button shows count
- `DraftingProgressSteps` rendered inside ChatPanel (driven by `state().phase`)
- SSE streaming indicator: `正在思考…` with pulsing dot when `isStreaming()` is true
- SSE error indicator: `连接中断，正在重连…` when `streamError()` is set
- Exported `WorkspaceContent` for testing
- Added workspace layout CSS to `app-shell.css` (`.ws`, `.ws-chat`, `.ws-splitter`, `.ws-doc`, `.ws-cite-toggle`, streaming/error indicators)
- Zero chat UI code in WorkspacePage (grep verified: no `class="bubble"`, `class="thread"`, `class="message-"`)
- Created `apps/web/tests/workspace-page.test.tsx` — 8 tests (ChatPanel render, DocPreview, citation toggle, sendMessage wiring, clarification wiring, feedback wiring, streaming indicator, error indicator)
- **Commit:** `08f39a8`

### Task 93-02-05: SSE reconnection verification
- Created `apps/web/tests/sse-reconnection.test.ts` — 5 tests using fake timers + mock fetch
- `sends Last-Event-ID on reconnect`: First stream (events 1-5) ends non-terminal → reconnect with `Last-Event-ID: 5` header
- `replayed events do not duplicate state`: Events 1-5 then 6-15 → final state has all 15 events, no duplicate messages
- `exponential backoff on repeated failures`: Backoff schedule 1s, 2s, 4s, 8s verified via fake timers
- `stream stops on terminal run status`: All 15 events (terminal `succeeded`) → no reconnection attempt
- `manual stop cancels reconnection`: Stop before reconnect timer fires → no second fetch call
- **Commit:** `be0e773`

## Self-Check

| Criterion | Status |
|-----------|--------|
| All tasks executed and committed | ✅ PASSED |
| All acceptance_criteria PASS | ✅ PASSED |
| ChatPanel wired to Gateway SSE | ✅ PASSED |
| EventStreamStore with Last-Event-ID reconnection | ✅ PASSED |
| Web adapters fully wired | ✅ PASSED |
| Can send message and see streaming reply | ✅ PASSED |
| SSE reconnection works (no duplicate rendering) | ✅ PASSED |
| 33 gates green | ✅ PASSED |
| SUMMARY.md with Self-Check: PASSED | ✅ PASSED |

## Deviations

1. **`ClarificationAnswer` export from ui-core**: The `ClarificationAnswer` type was not exported from `@inkstatute/ui-core`'s index.ts. Added it (along with other workflow types) as an additive export — no existing exports modified.

2. **`SessionContext` export for testing**: The `SessionContext` context object was not exported (only `SessionProvider` and `useSession` were). Exported it as `SessionContext` to allow tests to inject mock session values without rendering the full provider chain. Used `_SessionContext` internally to avoid name collision.

3. **`WorkspaceContent` export**: Exported the inner `WorkspaceContent` component from `WorkspacePage.tsx` to allow tests to render it with a mock `SessionContext.Provider` without needing the full `SessionProvider` (which requires `AuthProvider` + `useEventStream`).

4. **CSS class naming**: Plan specified `.ws .chat-panel` CSS selector, but the ui-core `ChatPanel` component renders with `class="chat"` (not `chat-panel`). Used `.ws-chat` wrapper class in WorkspacePage and corresponding CSS selectors. No functional impact.

## Files Created/Modified

### Created (new files)
- `apps/web/src/lib/runBuilder.ts`
- `apps/web/src/hooks/useEventStream.ts`
- `apps/web/src/contexts/SessionContext.tsx`
- `apps/web/tests/fixtures/run-events.json`
- `apps/web/tests/runBuilder.test.ts`
- `apps/web/tests/use-event-stream.test.ts`
- `apps/web/tests/session-context.test.tsx`
- `apps/web/tests/workspace-page.test.tsx`
- `apps/web/tests/sse-reconnection.test.ts`

### Modified (existing files)
- `apps/web/src/pages/WorkspacePage.tsx` — rewritten from tracer shell to full workspace
- `apps/web/src/app-shell.css` — added workspace layout CSS + streaming/error indicators
- `packages/ui-core/src/index.ts` — added workflow type exports (ClarificationAnswer, etc.)
