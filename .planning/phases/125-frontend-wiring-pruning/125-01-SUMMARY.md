# Plan 125-01 Summary: Prune V3 Platform Coupling and Arena

**Date:** 2026-08-16
**Status:** ✅ Complete
**Wave:** 1
**Requirements:** UIW-02, UIW-03

## What was done

### Task 0: Rollback tag
- `pre-125-pruning` tag created at `b65f2b29`
- `pre-125-workspace-removal` tag created at `899665f0`

### Task 1: 拆 Arena — keep presentation, delete transport
**Deleted (transport layer):**
- `packages/ui-core/src/stores/arenaStream.ts`
- `packages/ui-core/src/stores/sseUtils.ts`
- `packages/ui-core/src/stores/eventStream.ts`
- `packages/ui-core/tests/test_arena_stream.ts`
- `apps/desktop/src/pages/ArenaPage.tsx`
- `apps/desktop/src/config/arena.ts`
- `createEventStream` / `createArenaStream` exports from `index.ts`

**Kept (presentation layer for Phase 128):**
- 6 Arena components: ArenaWorkflowCreator, ParallelStreamPanel, ScoreCard, SynthesisViewer, ReviewSummary, SlotStreamView
- `reducers/arenaEventReducer.ts`, `types/arena.ts`
- All Arena component tests

**Fixed 3 pre-existing type errors in retained tests:**
- `test_arena_workflow_creator.tsx:44` — mock missing `title`/`sections`
- `test_parallel_stream_panel.tsx:77` — payload type cast via `unknown`
- `test_synthesis_viewer.tsx:121-123` — `mock.calls` tuple indexing

### Task 2: Delete Gateway / Auth / Connection / upload / runBuilder
**Deleted:**
- `apps/desktop/src/config/gateway.ts`
- `apps/desktop/src/contexts/AuthContext.tsx`
- `apps/desktop/src/contexts/ConnectionContext.tsx`
- `apps/desktop/src/lib/upload.ts`
- `apps/desktop/src/lib/runBuilder.ts`
- `apps/desktop/src/lib/offlineCache.ts`
- V3-era tests: `e2e-workflow`, `tracer`, `wave2-integration`, `command-surface`, `desktop-web-consistency`, `invoke-migration`, `phase94-verification`, `workspace-sse`, `offline-cache`, `auth-context`, `arena-page`

**Stubbed (125-02 will wire to Tauri commands):**
- `ConversationContext.tsx` — local uuid-based conversations, no remote calls
- `SessionContext.tsx` — no-op actions, keeps `useEventStream` interface
- `useEventStream.ts` — returns static `initialState()`, 125-02 replaces with Tauri `listen()`

**App.tsx:** removed `AuthProvider`/`ConnectionProvider` wrappers, `auth.loading()` gate, `conn.isOffline()` checks.

**OfflineBanner:** rewritten to use `navigator.onLine` + online/offline events.

**platform-sdk-ts/package.json:** added v5.0 note.

### Task 3: Delete offline cache (Rust)
- `commands/offline_cache.rs`, `migrations/002_offline_cache.sql`
- `tauri-plugin-sql` dependency removed (only used by offline cache)
- `sql:*` permissions removed from `capabilities/default.json`

### Task 4: Delete workspace index (Rust)
**Deleted (1,725 lines):**
- `src-tauri/src/workspace/` (chunker, index_store, manager, parser, scanner, mod)
- `commands/workspace.rs`, `migrations/003_workspace_index.sql`
- `walkdir` dependency removed
- 3 workspace command registrations removed from `generate_handler!`

**FTS5SearchPanel rewrite:**
- Data source: `search_workspace` → `search_conversations` (engine history plane)
- New `SearchHit` type matches Rust serde output
- "打开对话" button replaces "作为附件引用"
- Tests rewritten (3 tests)

## Verification

| Check | Result |
|---|---|
| `packages/ui-core` tsc | 0 errors |
| `packages/ui-core` vitest | 186 tests pass |
| `apps/desktop` tsc | 0 errors |
| `apps/desktop` vitest | 32 tests pass |
| `apps/desktop/src-tauri` cargo check | green |
| `apps/desktop/src-tauri` cargo test | 83 tests pass (5 ignored) |
| V5 gates | 2 passed, 0 failed |
| `event-reducer.ts` untouched | PASS |
| All 11 ui-core components untouched | PASS |
| No `gateway`/`PlatformApiClient`/`VITE_GATEWAY_URL` in src | PASS (except SettingsPanel V3, replaced in 125-03) |
| No `arenaStream`/`sseUtils`/`eventStream` in src | PASS |
| 6 Arena components + reducer + types preserved | PASS |

## Pruning stats

```
54 files changed, 183 insertions(+), 7545 deletions(-)
```

## Commits

- `b642bf` feat(125-01): 拆 Arena — delete transport layer, keep presentation
- `0809e1` feat(125-01): delete Gateway/Auth/Connection/upload/runBuilder/offlineCache
- `ab0bbc` feat(125-01): delete offline_cache + workspace index, rewrite FTS5 panel
