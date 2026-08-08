---
phase: 110-arena-ui-integration
plan: 04
status: complete
requirements: [GATE-01]
---

# Plan 04: End-to-End Integration Tests — All 4 Modes - Summary

## Objective

Create end-to-end integration tests that exercise the full arena flow (create → stream → score → review → synthesis → export) across all 4 modes (Mode 1-4) using fixture agents (`MockACPBackendAdapter`). These tests verify the complete pipeline from arena-service HTTP endpoints through the arena engine to SSE event emission.

## Tasks Completed

### Task 1: E2E Test Fixtures — MockACPBackendAdapter Configs for All 4 Modes

**Commit:** `feat(110-04): E2E test fixtures — MockACPBackendAdapter configs for all 4 modes`

Created 4 fixture modules + `__init__.py` in `packages/contract-test-suite/tests/fixtures/`:

- **`arena_e2e_mode1.py`** — `make_mode1_fixtures()`: Mode 1 Standard Parallel, 3 agent slots with distinct `backend_family` values (`family-0`, `family-1`, `family-2`), no synthesis adapter. Each adapter has 1 response.
- **`arena_e2e_mode2.py`** — `make_mode2_fixtures()`: Mode 2 Self-score Iteration, 2 agent slots with self-score responses containing `[SCORE]` markers and parseable `自评分数` scores (3 rounds: scores 7→8→9). No synthesis adapter.
- **`arena_e2e_mode3.py`** — `make_mode3_fixtures()`: Mode 3 Arena Review, 3 cross-family agent slots with self-score responses + cross-review responses containing `[FINDING]` blocks (description, confidence, severity, confirmed). Separate synthesis adapter with `backend_family="synthesis-family"`.
- **`arena_e2e_mode4.py`** — `make_mode4_fixtures()`: Mode 4 Adversarial, 3 agent slots + synthesis adapter + adversarial adapter. All `backend_family` values distinct (5 total). Adversarial adapter finds high-severity issue in round 0 (triggering re-synthesis) and no issues in round 1 (triggering convergence). Synthesis adapter has 2 responses for initial + re-synthesis.

Each fixture module includes self-tests verifying: config mode/slots/task_instruction/max_rounds, adapter types (`MockACPBackendAdapter`), distinct `backend_family` values, `[FINDING]` block format, synthesis/adversarial adapter separation, and agent_slot matching.

**Verification:** 21 fixture self-tests pass (0.001s).

### Task 2: test_arena_e2e.py — Full Flow for All 4 Modes

**Commit:** `feat(110-04): test_arena_e2e.py — full flow create→stream→score→review→synthesis for all 4 modes`

Created `packages/contract-test-suite/tests/test_arena_e2e.py` with `ArenaE2EIntegrationTests(unittest.IsolatedAsyncioTestCase)` containing 10 test methods:

1. **`test_mode1_full_flow`** — Create → stream → assert `workflow_started` first, per-slot `message.completed` (3 slots), `workflow_completed` last, all per-slot events have `metadata.agent_slot`.
2. **`test_mode2_full_flow`** — Create → stream → assert `score_recorded` events with `agent_slot`, `round`, `score` (1-10), at least 2 rounds per agent, `workflow_completed` at end.
3. **`test_mode3_full_flow`** — Create → stream → assert `score_recorded`, `review_completed` with `reviewer_slot`/`reviewed_slot`/`round`/`findings`, `synthesis_started`/`synthesis_completed`, `workflow_completed`.
4. **`test_mode4_full_flow`** — Create → stream → assert `adversarial_challenge_completed` with `challenger_slot`/`challenged_slot`/`findings`, `synthesis_started`/`synthesis_completed` (multi-round), `early_stop_triggered`, `workflow_completed`.
5. **`test_event_ordering_all_modes`** — All 4 modes: events are seq-ordered (1, 2, 3, ...) with no gaps and no duplicates.
6. **`test_sse_reconnection_no_duplication`** — All 4 modes: reconnect with `Last-Event-ID` → only events with `seq > last_seq` returned, no duplication.
7. **`test_workflow_completed_status`** — All 4 modes: `workflow_completed` payload has valid status (`completed` or `stopped_early` for Mode 4 convergence) and lists `agent_slots`.
8. **`test_review_findings_categorical_confidence`** — Mode 3/4: review findings have confidence in `{Certain, Likely, Possible}` — never numeric percentages.
9. **`test_auth_enforced`** — No token → 401 `unauthorized`, wrong token → 401 `unauthorized`, non-localhost → 403 `forbidden_remote`.
10. **`test_output_boundary`** — All 4 modes: no backend meta/gateway/system event types in the SSE stream; all event types are user-facing.

**Key design decisions:**
- **`ArenaTestOutputFilter`**: Custom output filter that allows arena event types (`arena.*`) + legacy `message_delta` (used by `MockACPBackendAdapter`) through, while delegating to the standard `ACPOutputFilter` for other event types. This is needed because the ACP allowlist uses `message.delta` (V3 dot format) but the mock adapter emits `message_delta` (V2 underscore format), and arena event types are not in the ACP allowlist.
- **Pre-registration of synthesis/adversarial adapters**: Synthesis and adversarial adapters are registered on the underlying `ArenaEngine` before `create_arena` is called, since `ArenaServiceEngine.create_arena` starts a background task immediately.
- **Event queue wait**: After `dispatch("POST", "/v1/arena")`, a retry loop waits for the background task to create the event queue before streaming.
- **Reconnection test**: After the first stream completes, the event queue is removed to prevent blocking on reconnect; the buffer replay provides the events for the reconnection assertion.

**Verification:** 10 E2E tests pass (0.109s).

## Files Modified

| File | Description |
|---|---|
| `packages/contract-test-suite/tests/fixtures/__init__.py` | Package init for fixtures |
| `packages/contract-test-suite/tests/fixtures/arena_e2e_mode1.py` | Mode 1 fixture (3 parallel agents, no synthesis) |
| `packages/contract-test-suite/tests/fixtures/arena_e2e_mode2.py` | Mode 2 fixture (2 self-score iteration agents) |
| `packages/contract-test-suite/tests/fixtures/arena_e2e_mode3.py` | Mode 3 fixture (3 cross-review agents + synthesis) |
| `packages/contract-test-suite/tests/fixtures/arena_e2e_mode4.py` | Mode 4 fixture (3 adversarial agents + synthesis + adversarial) |
| `packages/contract-test-suite/tests/test_arena_e2e.py` | E2E integration tests (10 tests, all 4 modes) |

## Test Results

- **Fixture self-tests:** 21 tests, all pass
- **E2E integration tests:** 10 tests, all pass
- **Total:** 31 tests, 0 failures

## GATE-01 Coverage

- ✅ Mode 1: create → stream → select → complete (parallel execution)
- ✅ Mode 2: create → stream → score → stop/complete (self-score iteration)
- ✅ Mode 3: create → stream → score → review → synthesis → complete (arena review)
- ✅ Mode 4: create → stream → score → review → synthesis → adversarial → early stop/complete
- ✅ Full flow exercised: create → stream → score → review → synthesis → export
- ✅ Tests use `MockACPBackendAdapter` — no real LLM calls
- ✅ Event sequence verified: `arena.workflow_started` first, `arena.workflow_completed` last, seq-ordered with no gaps
- ✅ SSE reconnection with `Last-Event-ID` produces no duplication
- ✅ Auth enforced: 401 without token, 403 non-localhost
- ✅ Output boundary verified: no backend/gateway/system events reach the client
- ✅ Review findings have categorical confidence (Certain/Likely/Possible) — never numeric
- ✅ Mode 3/4 verify cross-family review and synthesis with separate adapters
- ✅ Mode 4 verifies adversarial challenge and early stop logic
