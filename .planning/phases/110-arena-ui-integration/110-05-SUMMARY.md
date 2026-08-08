---
phase: 110-arena-ui-integration
plan: 05
status: complete
requirements: [GATE-02, UI-07, GATE-03]
---

# Plan 05: demo_non_legal Composability + Gate Registration + Baseline Update - Summary

## Objective

Create the `demo_non_legal` arena composability test verifying that arena lifecycle events contain no legal-specific fields in top-level required fields. Register the `ui-arena` gate (for arena UI component vitest tests) and `arena-e2e` gate (for E2E integration tests) in `scripts/run_v2_gates.py`. Update the gate-coverage meta-test baseline from 38 to 40.

## Tasks Completed

### Task 1: test_arena_composability.py (GATE-02)

**File:** `solutions/demo_non_legal/tests/test_arena_composability.py`

Created `ArenaComposabilityTests` with 10 test methods verifying:

1. `ArenaWorkflowStartedPayload` — required fields `{arena_id, mode}`, no legal-specific fields
2. `ArenaScoreRecordedPayload` — required fields `{arena_id, agent_slot, round, score}`, no legal-specific fields
3. `ArenaReviewCompletedPayload` — required fields `{arena_id, reviewer_slot, reviewed_slot, round}`, no legal-specific fields
4. `ArenaSynthesisStartedPayload` + `ArenaSynthesisCompletedPayload` — required fields `{arena_id, round}`, no legal-specific fields
5. `ArenaAdversarialChallengeCompletedPayload` — required fields `{arena_id, challenger_slot, challenged_slot, round}`, no legal-specific fields
6. `ArenaEarlyStopTriggeredPayload` — required fields `{arena_id, reason, round}`, no legal-specific fields
7. `ArenaWorkflowConfig` — required fields `{arena_id, mode, agent_slots, task_instruction}`, no legal-specific fields
8. `ArenaMode` values (`standard`, `self_score`, `arena_review`, `adversarial`) — none contain legal-specific keywords
9. Full arena event sequence (5 events) passes recursive `_walk` legal-keyword check at all levels
10. `metadata.agent_slot` is not in the `LEGAL_KEYWORDS` set — it's a generic demultiplexing key

The `_required_fields` helper correctly identifies required fields by checking both `default` and `default_factory` are `dataclasses.MISSING`. The `_walk` recursive checker follows the same pattern as `test_demo_non_legal_solution.py` lines 75-86, but uses the expanded `LEGAL_KEYWORDS` set including `statute`, `fagui`, `wenshu`.

**Verification:** `python -m unittest solutions.demo_non_legal.tests.test_arena_composability -v` → 10 tests, all OK (exit 0)

### Task 2: Gate Registration + Baseline Update (UI-07, GATE-03)

**Files modified:**
- `scripts/run_v2_gates.py` — added 2 new gates
- `packages/contract-test-suite/tests/test_gate_coverage.py` — updated baseline from 38 to 40

**`ui-arena` gate** (after `ui-core` gate, line 217):
- Runs `npx vitest run` with 7 arena UI component test files in `packages/ui-core/`
- Test files: `test_arena_event_reducer.ts`, `test_arena_stream.ts`, `test_arena_workflow_creator.tsx`, `test_parallel_stream_panel.tsx`, `test_score_card.tsx`, `test_review_summary.tsx`, `test_synthesis_viewer.tsx`
- 95 vitest tests, all passing
- Uses `bash -c` to run the Node.js vitest command (PYTHONPATH not needed)

**`arena-e2e` gate** (after `arena-service` gate, line 279):
- Runs `python -m unittest packages/contract-test-suite/tests/test_arena_e2e.py`
- 10 E2E integration tests covering all 4 arena modes, event ordering, SSE reconnection, auth, output boundary, review findings
- PYTHONPATH includes `contract_tests_dir` so `fixtures` package is importable

**Baseline update:** `test_gate_count_meets_baseline` now asserts `>= 40` (was `>= 38`). Total gate count is 41 (39 existing + 2 new).

**Verification:**
- `python scripts/run_v2_gates.py --list | wc -l` → 41 gates
- `python -m unittest packages/contract-test-suite/tests/test_gate_coverage.py` → 3 tests, all OK
- `test_all_packages_src_covered` passes — no new uncovered `packages/*/src` directories
- `test_all_services_src_covered` passes — `arena-service/src` already covered
- `compileall` gate already includes `packages/arena-engine/src` and `services/arena-service/src`

## Pre-existing Failures (not caused by this plan)

The `qqbot-channel` gate has 2 pre-existing failures (`test_backend_adapter_has_exactly_9_methods` and `test_recall01_c2c_over_window_wakeup_omits_msg_id_on_wire`) that exist on the baseline before this plan's changes. These are unrelated to the arena UI integration work.

## Artifacts

- `solutions/demo_non_legal/tests/test_arena_composability.py` — arena event composability test (GATE-02)
- `scripts/run_v2_gates.py` — `ui-arena` gate entry (UI-07)
- `scripts/run_v2_gates.py` — `arena-e2e` gate entry (UI-07)
- `packages/contract-test-suite/tests/test_gate_coverage.py` — baseline updated to 40 (GATE-03)

## Commits

1. `feat(110-05): test_arena_composability.py — arena events have no legal-specific fields in top-level required`
2. `feat(110-05): register ui-arena + arena-e2e gates and update gate-coverage baseline to 40`
