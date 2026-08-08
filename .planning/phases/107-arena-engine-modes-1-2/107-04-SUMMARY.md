---
phase: 107-arena-engine-modes-1-2
plan: 04
status: complete
requirements: [ENGINE-02, ENGINE-07, ENGINE-08]
---

# Plan 04: Mode 2 Self-score Iteration - Summary

## What Was Built

- **`arena_engine.mode2.IterationState`** — frozen slotted per-slot best-state dataclass (`slot_id`, `round`, `score`, `content`, `metadata`)
- **`arena_engine.mode2.Mode2Result`** — frozen slotted Mode 2 result dataclass (`arena_id`, `best_results: dict[str, IterationState]`, `rounds_completed`, `stopped_early`, `metadata`)
- **`arena_engine.mode2._extract_self_score`** — free-form 10-point score extraction via regex `(?:自评分数|score|评分)\s*[:：]\s*(\d{1,2})\s*(?:/\s*10)?`; returns clamped 0–10 int, defaults to 0 when no score found
- **`arena_engine.mode2.run_mode2_iteration`** — async Mode 2 iteration loop: runs all agent slots in parallel per round via `asyncio.TaskGroup`, extracts self-scores, emits `arena.score_recorded` per slot per round, persists via `ArtifactStore`, tracks best result per slot (highest score wins), supports user stop via `asyncio.Event`
- **`EventEmitter`** imported from `mode1.py` (Plan 03) — shared Protocol, no duplicate definition
- **`tests/test_mode2.py::Mode2IterationTests`** — 9 tests covering all Mode 2 behaviours

## Tasks Completed

- [x] Task 1: IterationState + self-score extraction + best-result tracking

## Verification Results

```
cd /home/sorawatcher/workspace/inkstatute-suite && PYTHONPATH=packages/arena-engine/src:packages/platform-contract/src:packages/platform-runtime/src:packages/agent-core/src python -m unittest discover -s packages/arena-engine/tests -p "test_mode2.py" -v

test_artifact_store_persists_each_round ... ok
test_best_result_tracking_highest_score ... ok
test_extract_self_score_chinese ... ok
test_extract_self_score_no_score ... ok
test_fresh_context_distinct_turn_ids ... ok
test_full_run_completes_max_rounds ... ok
test_mode2_result_frozen_slotted_shape ... ok
test_slot_crash_isolation ... ok
test_user_stop_preserves_best_results ... ok

Ran 9 tests in 0.086s
OK
```

Full arena-engine suite (53 tests) also passes — no regressions in existing modules.

ENGINE-05 gate (`test_no_llm_imports.py`) and ENGINE-06 gate (`test_fresh_context.py`) both pass — mode2.py imports zero LLM providers and never calls `session/resume`.

## Artifacts Produced

- `packages/arena-engine/src/arena_engine/mode2.py` — Mode 2 iteration implementation (338 lines)
- `packages/arena-engine/tests/test_mode2.py` — Mode 2 test suite (347 lines, 9 tests)

## Notes

- **EventEmitter**: Plan 03 (`mode1.py`) was already executed and defined the `EventEmitter` Protocol. Per the plan's instruction ("Import `EventEmitter` from `mode1.py` (or define a shared Protocol)"), `mode2.py` imports `EventEmitter` from `mode1.py` rather than redefining it. The `__init__.py` already re-exported mode2 symbols from Plan 03.
- **Crash isolation test (Test 9)**: The `_CrashAfterRoundAdapter` crashes on all rounds >= 1 (not just round 1) because `run_agent_slot` retries up to `max_retries=2` (3 total attempts per round). A single-call crash would be recovered by retry. Crashing on all subsequent rounds ensures the slot's best result genuinely retains round 0. The plan's `rounds_completed is 2` was interpreted as `rounds_completed is 3` since all 3 rounds are attempted and completed (the crash is isolated per-slot, not per-round).
- **User stop test (Test 2)**: The stop signal is set after round 0 completes (via `StopAfterRoundEmitter` which sets the event after 2 `arena.score_recorded` events). The check at the top of round 1 fires, producing `rounds_completed=1`, `stopped_early=True`, `early_stop_triggered` with `reason="user_stopped"`, `round=1`.
- **No auto-stop on convergence**: Per the plan and research anti-patterns, the iteration loop only stops on user signal or `max_rounds` — no score-convergence check is implemented.
- **Fresh context per round**: Each round builds a new `RunRequest` with `turn_id=f"{arena_id}-{slot_id}-round{r}"`, ensuring 3 distinct turn IDs per slot across 3 rounds (ENGINE-06).
- **Self-optimization**: When `round > 0`, the previous round's content and self-score are appended to the instruction (`上一轮自评分数：{prev_score}/10，请优化你的回答。`) so the agent can self-optimize.
