# Plan 125-02 Summary: Tauri Event Transport

**Date:** 2026-08-16
**Status:** ✅ Complete
**Wave:** 2
**Depends on:** 125-01

## What was done

### Task 1: `apps/desktop/src/services/engine.ts`

Created the single module for all engine interactions. Components and contexts never call `invoke` directly.

**Exported wrappers:**
- `engineStart()`, `engineStatus()`, `engineSend()`, `engineCancel()`, `engineRespondPermission()`
- `onRunEvent(handler)` — subscribes to `inkstatute://run-event`, returns `UnlistenFn`
- `listConversations()`, `searchConversations()`, `getConversationDocs()` — history plane
- `RUN_EVENT = "inkstatute://run-event"`

### Task 1 (Rust side): `commands/engine.rs`

5 new Tauri commands registered in `lib.rs`:

| Command | Behavior |
|---|---|
| `engine_start` | Spawn `EngineSupervisor`, initialize ACP, return `EngineStatus` |
| `engine_status` | Check if supervisor is running |
| `engine_send` | Ensure ACP session via `SessionMap`, start observation, emit `session.started`, send prompt |
| `engine_cancel` | Cancel active run for a conversation |
| `engine_respond_permission` | Convert `bool` → `PermissionDecision`, respond to ACP |

`EngineState` (RwLock<Option<EngineSupervisor>> + SessionMap) managed by Tauri. Provider auto-selected (DeepSeek preferred, fallback to any with key).

### Task 2: `useEventStream.ts` rewrite

- Subscribes to `inkstatute://run-event` via Tauri `listen()`
- Filters events by `run_id` (conversation ID)
- Reduces through `reduce()` from `@inkstatute/ui-core` (pure reducer, untouched)
- `onCleanup` calls unlisten
- `createEffect(on(conversationId, ...))` re-subscribes when conversation changes
- `reconnect()` resets state and resubscribes
- External interface preserved: `{ state, isStreaming, error, reconnect }`

### Task 3: Context rewrites

**ConversationContext:**
- Data source: `listConversations()` from history plane
- New conversations: local uuid (ACP session created lazily by engine)
- No remote create/delete calls

**SessionContext:**
- `sendMessage` → `engineSend(conversationId, prompt)`
- `cancelRun` → `engineCancel(conversationId)`
- `submitClarification` → `engineRespondPermission(requestId, true)`
- `useEventStream(conversationId)` provides reactive `RenderState`

### Task 4: Event transport test

4 tests in `tests/event-transport.test.tsx`:
1. Reduces all envelopes from `expected-envelopes.json` to terminal state
2. Renders `ChatPanel` with reduced state showing `.msg` elements
3. `onRunEvent` calls `listen` with correct channel
4. `useEventStream` subscribes and unlistens on conversation switch

## Verification

| Check | Result |
|---|---|
| `packages/ui-core` tsc + vitest | 186 tests pass |
| `apps/desktop` tsc | 0 errors |
| `apps/desktop` vitest | 36 tests pass (6 files) |
| `apps/desktop/src-tauri` cargo check | green |
| `apps/desktop/src-tauri` cargo test | 83 tests pass (5 ignored) |
| `event-reducer.ts` untouched | PASS |
| `useEventStream` has `onCleanup` | PASS |
| No direct `invoke` in components (except V3 SettingsPanel, replaced in 125-03) | PASS |
| `onRunEvent` uses `inkstatute://run-event` channel | PASS |
