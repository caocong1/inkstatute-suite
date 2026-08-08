---
phase: 110
slug: arena-ui-integration
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-09
---

# Phase 110 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| UI framework | SolidJS (ui-core) |
| UI test runner | vitest |
| Python test runner | unittest |
| Gate runner | `python scripts/run_v2_gates.py` |
| E2E fixtures | MockACPBackendAdapter |
| TDD mode | false |

## Requirement → Test Mapping

| Requirement | Test File | Test Class/Method | Gate |
|-------------|-----------|-------------------|------|
| UI-01 | test_arena_components.tsx | ArenaWorkflowCreatorTests | ui-arena |
| UI-02 | test_arena_components.tsx | ParallelStreamPanelTests | ui-arena |
| UI-03 | test_arena_components.tsx | ScoreCardTests, ReviewSummaryTests | ui-arena |
| UI-04 | test_arena_components.tsx | SynthesisViewerTests | ui-arena |
| UI-05 | test_arena_event_reducer.ts | ArenaEventReducerTests | ui-arena |
| UI-06 | test_arena_stream.ts | ArenaStreamPersistenceTests | ui-arena |
| UI-07 | test_gate_coverage.py | GateCoverageTests | gate-coverage |
| GATE-01 | test_arena_e2e.py | ArenaE2EIntegrationTests | arena-e2e |
| GATE-02 | test_arena_composability.py | ArenaComposabilityTests | demo-non-legal |
| GATE-03 | test_gate_coverage.py | GateCoverageTests | gate-coverage |

## Validation Waves

### Wave 0 (Pre-execution)
- [x] Research complete (110-RESEARCH.md)
- [x] Context complete (110-CONTEXT.md)
- [x] Validation strategy complete (110-VALIDATION.md)

### Wave 1 (Core reducer + state — no dependencies)
- [x] arenaEventReducer.ts — compose reduce() per slot (UI-05)
- [x] arenaStream.ts — SSE consumer with slot state persistence (UI-06)

### Wave 2 (UI components — depend on Wave 1)
- [x] ArenaWorkflowCreator.tsx + ParallelStreamPanel.tsx (UI-01, UI-02)
- [x] ScoreCard.tsx + ReviewSummary.tsx + SynthesisViewer.tsx (UI-03, UI-04)

### Wave 3 (Integration + gates — depend on Wave 1+2)
- [x] E2E integration tests — all 4 modes (GATE-01)
- [x] demo_non_legal composability test (GATE-02)
- [x] Gate registration + baseline update (UI-07, GATE-03)

## Acceptance Criteria

1. **Arena workflow creator**: Mode selection (1-4), N agent selection, task input, reference dir
2. **Parallel stream panel**: N demultiplexed streams with per-slot rendering
3. **Score card + Review summary**: 10-point self-score, findings with categorical confidence
4. **Synthesis viewer**: Final version display + Word track-changes export
5. **ArenaEventReducer**: Composes existing reduce() per slot, no rewrite
6. **State persistence**: Run state + SSE reconnection without re-rendering
7. **Gate coverage**: 40+ gates, arena-engine + arena-service covered
8. **E2E integration**: All 4 modes, fixture agents, full flow
9. **demo_non_legal composability**: Arena events no legal-specific fields in top-level required

## Nyquist Sampling

- Every task has automated verify
- No 3 consecutive tasks without automated verify
- Feedback latency: < 30s per test run
