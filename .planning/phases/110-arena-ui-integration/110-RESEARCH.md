---
phase: 110
slug: arena-ui-integration
status: complete
created: 2026-08-09
---

# Phase 110 — Technical Research

## 1. UI Core Structure

**Framework**: SolidJS (`packages/ui-core/package.json` line 40: `"solid-js": "^1.9.0"`)

**Structure**:
- `packages/ui-core/src/components/` — 23 UI components (ChatPanel, WorkflowProgressSteps, ClarificationCard, DocPreview, AgentTracePanel, etc.)
- `packages/ui-core/src/stores/` — SolidJS reactive stores (eventStream.ts, theme.ts, trace.ts)
- `packages/ui-core/src/event-reducer.ts` — Pure event reducer (line 224: `reduce(state: RenderState, event: RunEventEnvelope): RenderState`)
- `packages/ui-core/src/types/` — TypeScript types (workflow.ts, events.ts, legal.ts, trace.ts)
- `packages/ui-core/src/adapters/` — Platform-agnostic adapters (FileAdapter, DropAdapter, WorkspaceAdapter)

**Existing Event Reducer** (`event-reducer.ts`):
- Pure function: `reduce(state: RenderState, event: RunEventEnvelope): RenderState` (line 224)
- Handles 13 unified event types
- Idempotent — replayed events produce same state
- No side effects, no signals, no DOM access

**State Management**:
- `RenderState` interface (lines 55-71): runId, backendId, runStatus, messages, streamingBuffer, etc.
- `createEventStream` in `stores/eventStream.ts` — SSE consumer with Last-Event-ID reconnection
- Uses SolidJS `createSignal` for reactive state

## 2. Arena Workflow Creator (UI-01)

**Existing patterns to reuse**:
- `ChatPanel.tsx` — textarea input with send button (lines 197-220)
- `WorkflowProgressSteps.tsx` — mode switching UI (ModeSwitchCard, lines 126-174)
- `ClarificationCard.tsx` — multi-option selection
- `adapters/index.ts` — FileAdapter for directory selection (lines 19-28)

**Arena contract** (`arena_contract.py`):
- `ArenaWorkflowConfig`: arena_id, mode, agent_slots, task_instruction, reference_dir, max_rounds, metadata

**Implementation approach**:
- New component: `ArenaWorkflowCreator.tsx` in `packages/ui-core/src/components/`
- Mode selector: 4 options (mode1_parallel, mode2_iteration, mode3_arena_review, mode4_adversarial)
- Agent slot selector: Multi-select checkbox list
- Task textarea: Reuse ChatPanel pattern
- Reference directory: Use `useAdapters().file.open()`
- Submit: Call arena-service POST /v1/arena

## 3. Parallel Stream Panel (UI-02)

**SSE multiplexing** (`services/arena-service/src/arena_service/sse.py`):
- Single SSE connection carries N agent events
- Each event has `metadata.agent_slot` tag
- `encode_arena_sse_event` preserves agent_slot in JSON (lines 30-70)

**Existing stream components**:
- `ChatPanel.tsx` — streaming message with `streamingBuffer` (lines 161-169)
- `AgentTracePanel.tsx` — per-turn trace with streaming (lines 464-481)
- `CodeBlock` component with `live` prop for real-time updates

**Implementation approach**:
- New component: `ParallelStreamPanel.tsx`
- Props: `arenaId: string, agentSlots: string[]`
- Internal state: `Map<string, RenderState>` (per-slot state via existing reduce())
- Grid layout with N columns (one per agent slot)
- Each column: Mini ChatPanel-like rendering with streaming buffer, thought, tool calls

## 4. Score Card + Review Summary (UI-03)

**Review data structures** (`packages/arena-engine/src/arena_engine/review.py`):
- `ConfidenceLevel`: CERTAIN, LIKELY, POSSIBLE (categorical)
- `SeverityLevel`: HIGH, MEDIUM, LOW
- `ReviewFinding`: description, confidence, severity, confirmed, source_slot, reviewed_slot

**Arena events** (`unified_events.py`):
- `ArenaScoreRecordedPayload` (lines 181-186): arena_id, agent_slot, round, score
- `ArenaReviewCompletedPayload` (lines 190-196): arena_id, reviewer_slot, reviewed_slot, round, findings

**Implementation approach**:
- `ScoreCard.tsx` — Table with rows: agent_slot, round scores, best score; 10-point visual bar
- `ReviewSummary.tsx` — List of findings grouped by reviewed_slot; confidence/severity badges; confirmed/disproved toggle

## 5. Synthesis Viewer + Word Export (UI-04)

**Existing DocPreview** (`packages/ui-core/src/components/DocPreview.tsx`):
- Already has Word export button (lines 164-172)
- Uses `useAdapters().file.save()` for file dialog
- Has `onExport` callback prop

**Track-changes pattern** (`packages/agent-core/tests/test_e2e_trackchanges.py`):
- Tool: `generate_review_docx` — python-docx with OOXML `<w:ins>` and `<w:del>` elements
- Artifact kind: `TRACKCHANGES_DOCX`

**Implementation approach**:
- `SynthesisViewer.tsx` wraps DocPreview with arena-specific props
- Word export flow: user clicks export → call arena-service → generate track-changes docx → save file

## 6. ArenaEventReducer (UI-05)

**Existing reduce()** (`event-reducer.ts` line 224):
```typescript
export function reduce(state: RenderState, event: RunEventEnvelope): RenderState
```

**Implementation approach**:
- New file: `packages/ui-core/src/reducers/arenaEventReducer.ts`
- `arenaEventReducer(slotStates: Map<string, RenderState>, event: RunEventEnvelope): Map<string, RenderState>`
- Algorithm:
  1. Extract `agent_slot` from `event.metadata.agent_slot`
  2. If missing (lifecycle events), apply to all slots
  3. If specific slot: get/create slot state → apply existing reduce() → update map
- **No rewrite of single-stream reducer logic** — just routing and composition

## 7. State Persistence (UI-06)

**Existing SSE reconnection** (`stores/eventStream.ts`):
- Already implements Last-Event-ID reconnection (lines 75-83)
- Exponential backoff: 1s, 2s, 4s, 8s, max 30s
- Reducer is idempotent — replayed events produce same state

**Arena event buffer** (`services/arena-service/src/arena_service/event_buffer.py`):
- `replay(arena_id, last_seq)` returns events with `seq > last_seq`
- FIFO eviction, terminal state retention for 300 seconds

**Implementation approach**:
- Extend `createEventStream` to support arena-specific slot states
- Persist to localStorage: `arena-state-{arena_id}` → JSON of `Map<string, RenderState>`
- On mount, restore from localStorage
- SSE reconnection already handled — idempotent reducer prevents re-rendering

## 8. Gate Coverage (UI-07, GATE-03)

**Current state**: 39 gates (scripts/run_v2_gates.py)
- Baseline in test_gate_coverage.py: 38
- arena-engine and arena-service already covered

**Implementation approach**:
- Add `ui-arena` gate for arena UI components/tests
- Update baseline from 38 to 40 (39 existing + 1 new)
- Verify arena-engine + arena-service src covered and green

## 9. End-to-End Integration Tests (GATE-01)

**Existing test patterns**:
- `test_mode1.py` through `test_mode4.py` — Mode-specific tests with MockACPBackendAdapter
- `test_engine_integration.py` — Engine wiring tests
- `test_sse_multiplexing.py` — SSE encoding tests

**Implementation approach**:
- New test file covering all 4 modes with full flow: create → stream → score → review → synthesis → export
- Use MockACPBackendAdapter from arena-engine
- Test in `packages/ui-core/tests/` (TypeScript) or `packages/contract-test-suite/tests/` (Python)

## 10. demo_non_legal Composability (GATE-02)

**Existing test** (`solutions/demo_non_legal/tests/test_demo_non_legal_solution.py`):
- `test_no_legal_only_fields_at_any_level` (lines 72-87) — recursively checks for legal-specific keywords
- `test_industry_context_is_education_domain_not_legal` (lines 62-66)

**Implementation approach**:
- Add arena event composability test
- Verify arena lifecycle events can be emitted without legal-specific fields
- Verify `metadata.agent_slot` is the only required field (not legal-specific)

## 11. Word Track-Changes Export

**Pattern from agent-core**:
- Tool: `generate_review_docx` — python-docx with OOXML `<w:ins>` and `<w:del>` elements
- Review items JSON format: id, find_text, old_text, new_text, comment, level
- Artifact kind: `TRACKCHANGES_DOCX`

**Integration with UI**:
- DocPreview already has export button
- Flow: synthesis produces content → call generate_review_docx → emit artifact.created → UI displays → user exports

## 12. Integration with Arena Service

**Arena service endpoints**:
- POST /v1/arena — create arena
- GET /v1/arena/{arena_id}/stream — SSE stream
- POST /v1/arena/{arena_id}/cancel — cancel
- POST /v1/arena/{arena_id}/action — user action
- GET /v1/arena/{arena_id}/status — status

**Auth flow**: localhost check (403) → token auth (401) → route

**UI integration**:
- Use `@inkstatute/platform-sdk-ts` PlatformApiClient
- Create arena → stream events → demultiplex by slot → render

## Key Files to Create/Modify

**New UI components (packages/ui-core/src/components/):**
1. `ArenaWorkflowCreator.tsx` — Mode/agent/task/dir selection (UI-01)
2. `ParallelStreamPanel.tsx` — N demultiplexed streams (UI-02)
3. `ScoreCard.tsx` — Self-score display (UI-03)
4. `ReviewSummary.tsx` — Findings with confidence (UI-03)
5. `SynthesisViewer.tsx` — Final version + Word export (UI-04)

**New reducer (packages/ui-core/src/reducers/):**
6. `arenaEventReducer.ts` — Compose reduce() per slot (UI-05)

**New/modified state (packages/ui-core/src/stores/):**
7. `arenaStream.ts` — Arena SSE consumer with slot state persistence (UI-06)

**New tests:**
8. `packages/ui-core/tests/test_arena_event_reducer.ts` — Reducer tests (UI-05)
9. `packages/ui-core/tests/test_arena_components.tsx` — Component tests (UI-01..04)
10. `packages/contract-test-suite/tests/test_arena_e2e.py` — E2E integration (GATE-01)
11. `solutions/demo_non_legal/tests/test_arena_composability.py` — Composability (GATE-02)

**Modified files:**
12. `scripts/run_v2_gates.py` — Add ui-arena gate (UI-07, GATE-03)
13. `packages/contract-test-suite/tests/test_gate_coverage.py` — Update baseline to 40

## Anti-Patterns to Avoid

1. Rewriting single-stream reducer logic (must compose existing reduce())
2. Legal-specific fields in arena event top-level required (composability)
3. Non-idempotent state updates (reconnection would duplicate)
4. Framework dependency beyond SolidJS (keep ui-core portable)
5. Missing gate coverage for new arena UI components
6. Separate chat UI implementation (must extend existing ui-core)
