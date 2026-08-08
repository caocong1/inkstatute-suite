---
phase: 110-arena-ui-integration
plan: 01
status: complete
requirements: [UI-05, UI-06]
---

# Plan 01: ArenaEventReducer + Arena Stream Store - Summary

## Objective

Create the `ArenaEventReducer` that demultiplexes N interleaved agent streams by composing the existing single-stream `reduce()` per slot — no rewrite of reducer logic. Create the `arenaStream.ts` store that consumes the arena SSE endpoint, persists slot states to localStorage, and reconnects with Last-Event-ID without re-rendering already-received content.

## Tasks Completed

### Task 1: arenaEventReducer.ts — demultiplexing via composed reduce() per slot

**Files created:**
- `packages/ui-core/src/types/arena.ts` — Arena type definitions (`ArenaSlotStates`, `ArenaMetaState`, `ArenaScoreEntry`, `ArenaReviewEntry`, `initialArenaMetaState()`)
- `packages/ui-core/src/reducers/arenaEventReducer.ts` — Demultiplexing reducer composing existing `reduce()` per slot
- `packages/ui-core/tests/fixtures/arena-events.json` — Fixture with 2 slots + 8 arena lifecycle event types
- `packages/ui-core/tests/test_arena_event_reducer.ts` — 23 tests covering all 10 behaviors + `arenaMetaReducer`

**Files modified:**
- `packages/ui-core/vite.config.ts` — Added `tests/**/test_*.ts` to vitest include pattern

**Key design decisions:**
- `arenaEventReducer` imports and calls the existing `reduce()` from `event-reducer.ts` — zero rewrite of single-stream reducer logic
- `extractAgentSlot()` checks `metadata.agent_slot` first, falls back to `payload.agent_slot` for arena lifecycle events
- Arena lifecycle events without `agent_slot` are broadcast to all existing slot states
- Untagged non-lifecycle events are dropped (returned unchanged)
- Always returns a NEW Map (immutable update for SolidJS reactivity)
- `arenaMetaReducer` is a separate pure function that extracts scores, reviews, synthesis content, and status from arena lifecycle events — feeds ScoreCard/ReviewSummary/SynthesisViewer

**Verification:** `npx vitest run tests/test_arena_event_reducer.ts` — 23 tests passed, exit 0

### Task 2: arenaStream.ts — SSE consumer with slot state persistence + reconnection

**Files created:**
- `packages/ui-core/src/stores/sseUtils.ts` — Shared SSE parsing helpers (`parseEvent`, `parseSseFrame`) extracted to avoid duplication
- `packages/ui-core/src/stores/arenaStream.ts` — Arena SSE consumer store
- `packages/ui-core/tests/test_arena_stream.ts` — 14 tests covering all 12 behaviors

**Key design decisions:**
- Targets `/v1/arena/{arenaId}/stream` (NOT `/v1/runs/{runId}/events`)
- Maintains `Map<string, RenderState>` per slot via `arenaEventReducer`
- `persistToLocalStorage()` serializes Map as entries array + meta to `arena-state-{arenaId}` key, wrapped in try/catch for SSR/privacy mode
- `restoreFromLocalStorage()` reconstructs Map from entries array, returns null on missing key or parse error
- Store initializes from localStorage on creation, then SSE reconnection fills gaps
- Reconnection uses `Last-Event-ID` = max lastSeq across all slots + metaState.lastSeq
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s (same as `eventStream.ts`)
- `stop()` clears reconnect timers and aborts fetch controller
- SSE parsing helpers extracted to shared `sseUtils.ts` to avoid duplication with `eventStream.ts`

**Verification:** `npx vitest run tests/test_arena_stream.ts` — 14 tests passed, exit 0

## Test Results

- `tests/test_arena_event_reducer.ts` — 23 tests passed
- `tests/test_arena_stream.ts` — 14 tests passed
- Full ui-core suite — 142 tests passed across 11 files (no regressions)

## Commits

1. `feat(110-01): arenaEventReducer demultiplexing via composed reduce() per slot` — Task 1 (5 files, 964 insertions)
2. `feat(110-01): arenaStream SSE consumer with slot state persistence + reconnection` — Task 2 (3 files, 686 insertions)

## Artifacts Produced

- `ui-core.src.types.arena.ArenaSlotStates`
- `ui-core.src.types.arena.ArenaMetaState`
- `ui-core.src.types.arena.ArenaScoreEntry`
- `ui-core.src.types.arena.ArenaReviewEntry`
- `ui-core.src.types.arena.initialArenaMetaState`
- `ui-core.src.reducers.arenaEventReducer.arenaEventReducer`
- `ui-core.src.reducers.arenaEventReducer.arenaMetaReducer`
- `ui-core.src.reducers.arenaEventReducer.getSlotState`
- `ui-core.src.reducers.arenaEventReducer.getAllSlotStates`
- `ui-core.src.reducers.arenaEventReducer.extractAgentSlot`
- `ui-core.src.stores.sseUtils.parseEvent`
- `ui-core.src.stores.sseUtils.parseSseFrame`
- `ui-core.src.stores.arenaStream.createArenaStream`
- `ui-core.src.stores.arenaStream.persistToLocalStorage`
- `ui-core.src.stores.arenaStream.restoreFromLocalStorage`
- `tests/test_arena_event_reducer.ts::ArenaEventReducerTests`
- `tests/test_arena_stream.ts::ArenaStreamPersistenceTests`

## Key Links

- `arenaEventReducer` imports and calls `reduce` from `event-reducer.ts` — composition, not rewrite
- `arenaStream.ts` uses `arenaEventReducer` for per-slot state and `arenaMetaReducer` for arena-level metadata
- `arenaStream.ts` reuses SSE parsing helpers from `sseUtils.ts` (shared with `eventStream.ts` pattern)
- localStorage persistence keys are `arena-state-{arenaId}` — consumed by ParallelStreamPanel on mount
