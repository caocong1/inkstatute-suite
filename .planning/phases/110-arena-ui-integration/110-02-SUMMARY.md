---
phase: 110-arena-ui-integration
plan: 02
status: complete
requirements: [UI-01, UI-02]
---

# Plan 02: ArenaWorkflowCreator + ParallelStreamPanel — Summary

## Objective

Create the `ArenaWorkflowCreator` component where lawyers select mode (1-4),
choose N ACP backend agents, input task instructions, and select a reference
file directory. Create the `ParallelStreamPanel` that renders N demultiplexed
real-time agent streams in a grid, each slot independently rendering streaming
replies, thoughts, and tool calls.

## Tasks Completed

### Task 1: ArenaWorkflowCreator.tsx — mode/agent/task/directory selection (UI-01)

**Files created:**
- `packages/ui-core/src/components/ArenaWorkflowCreator.tsx` — component with
  4-mode selector (2x2 grid), multi-select agent checkbox list, task textarea,
  reference directory picker via `useAdapters().file.open()`, max-rounds input
  (clamp 1-10), and submit button emitting `ArenaWorkflowConfig` via `onCreate`.
- `packages/ui-core/src/components/ArenaWorkflowCreator.css` — BEM-like styles.
- `packages/ui-core/tests/test_arena_workflow_creator.tsx` — 11 tests covering
  all 10 behaviors.

**Key decisions:**
- Component does NOT call arena-service directly — emits `ArenaWorkflowConfig`
  via `props.onCreate(config)`; parent handles `POST /v1/arena`.
- `ARENA_MODES` constant: standard / self_score / arena_review / adversarial
  with Chinese labels and descriptions.
- `clampMaxRounds` helper exported for reuse: invalid/0/negative → 1, >10 → 10.
- Ctrl+Enter does NOT submit (unlike ChatPanel) — arena creation uses a
  dedicated submit button.
- Uses `useAdapters()` for file operations — no direct platform imports.

**Verify:** `npx vitest run tests/test_arena_workflow_creator.tsx` → 11 passed.

**Commit:** `feat(110-02): ArenaWorkflowCreator mode/agent/task/directory selection UI (UI-01)`

### Task 2: ParallelStreamPanel.tsx + SlotStreamView.tsx — N demultiplexed live streams (UI-02)

**Files created:**
- `packages/ui-core/src/components/SlotStreamView.tsx` — per-slot rendering:
  header with status pill (running/completed/error/idle/cancelled), message
  thread (markdown via SolidMarkdown), streaming buffer while running,
  collapsible thinking section, workflow steps with state indicators.
- `packages/ui-core/src/components/ParallelStreamPanel.tsx` — responsive CSS
  grid (`repeat(auto-fill, minmax(320px, 1fr))`) with one `SlotStreamView`
  per agent slot.
- `packages/ui-core/src/components/ParallelStreamPanel.css` — shared styles
  for both components.
- `packages/ui-core/tests/test_parallel_stream_panel.tsx` — 16 tests
  (ParallelStreamPanelTests + SlotStreamViewTests) covering all 12 behaviors.

**Key decisions:**
- `ParallelStreamPanel` receives `slotStates: () => ArenaSlotStates` and
  `agentSlots: string[]` as props — it does NOT create its own SSE store.
  Parent wires `createArenaStream` (Plan 01).
- Uses `getSlotState` from `arenaEventReducer` (Plan 01) to resolve each slot's
  `RenderState` — no duplicate stream consumption.
- `SlotStreamView` uses `step.label` directly (already resolved by
  `traceToolLabel` in the reducer) — no duplicate label logic.
- Empty slots (idle, no messages) show "等待 agent 启动…" placeholder.
- Auto-scroll via `createEffect` tracking streamingBuffer + messages.length.

**Verify:** `npx vitest run tests/test_parallel_stream_panel.tsx` → 16 passed.

**Commit:** `feat(110-02): ParallelStreamPanel + SlotStreamView N demultiplexed live streams (UI-02)`

## Supporting Changes

- `packages/ui-core/vite.config.ts` — added `tests/**/test_*.tsx` to vitest
  `include` pattern so the new `.tsx` test files are discovered.
- `packages/ui-core/src/index.ts` — exported `ArenaWorkflowCreator`,
  `ARENA_MODES`, `clampMaxRounds`, `ParallelStreamPanel`, `SlotStreamView`
  and their prop/type interfaces.

## Verification

```
cd packages/ui-core && npx vitest run tests/test_arena_workflow_creator.tsx tests/test_parallel_stream_panel.tsx
```

Result: 2 test files passed, 27 tests passed (11 + 16), exit 0.

## Artifacts Produced

- `ui-core.src.components.ArenaWorkflowCreator.ArenaWorkflowCreator`
- `ui-core.src.components.ArenaWorkflowCreator.ARENA_MODES`
- `ui-core.src.components.ParallelStreamPanel.ParallelStreamPanel`
- `ui-core.src.components.SlotStreamView.SlotStreamView`
- `tests/test_arena_workflow_creator.tsx::ArenaWorkflowCreatorTests`
- `tests/test_parallel_stream_panel.tsx::ParallelStreamPanelTests`
- `tests/test_parallel_stream_panel.tsx::SlotStreamViewTests`

## Key Links

- `ArenaWorkflowCreator.onCreate` emits `ArenaWorkflowConfig` → parent calls
  `POST /v1/arena` on arena-service.
- `ParallelStreamPanel` consumes `slotStates()` from `createArenaStream`
  (Plan 01) — demultiplexed per-slot RenderStates.
- `SlotStreamView` renders `step.label` produced by `traceToolLabel` in the
  reducer — no duplicate label logic.
- Both components use `useAdapters()` for platform operations — portable
  across web/desktop.
