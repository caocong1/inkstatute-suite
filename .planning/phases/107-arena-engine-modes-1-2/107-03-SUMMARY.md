---
phase: 107-arena-engine-modes-1-2
plan: 03
status: complete
requirements: [ENGINE-01, ENGINE-07, ENGINE-08]
---

# Plan 03: Mode 1 Standard Parallel - Summary

## What Was Built
- `arena_engine.mode1.Mode1Result` — frozen slotted dataclass with `arena_id`, `slot_results: dict[str, SlotResult]`, `artifacts: dict[str, RoundArtifact | None]`, `metadata: dict`
- `arena_engine.mode1.EventEmitter` — Protocol for async event emission callback (`async def emit(event_type, payload, metadata) -> None`)
- `arena_engine.mode1.run_mode1_parallel` — async function that runs N agents in parallel via `asyncio.TaskGroup`, emits `arena.workflow_started` / `arena.workflow_completed` lifecycle events, re-emits per-slot `RunEvent`s with `metadata["agent_slot"]` tagging, and persists successful outputs via `ArtifactStore`
- `tests/test_mode1.py::Mode1ParallelTests` — 7 tests covering all acceptance criteria (unittest `IsolatedAsyncioTestCase`)
- Updated `arena_engine/__init__.py` to re-export `Mode1Result` and `run_mode1_parallel`

## Tasks Completed
- [x] Task 1: run_mode1_parallel — N agents via asyncio.TaskGroup with agent_slot tagging

## Verification Results
```
cd /home/sorawatcher/workspace/inkstatute-suite && PYTHONPATH=packages/arena-engine/src:packages/platform-contract/src:packages/platform-runtime/src:packages/agent-core/src python -m unittest discover -s packages/arena-engine/tests -p "test_mode1.py" -v

test_1_all_slots_run_concurrently_and_succeed ... ok
test_2_every_runevent_has_agent_slot_metadata ... ok
test_3_lifecycle_events_first_and_last ... ok
test_4_one_slot_crash_does_not_cancel_others ... ok
test_5_artifact_store_persists_successful_slots ... ok
test_6_one_run_agent_slot_call_per_slot ... ok
test_7_mode1_result_is_frozen_slotted_dataclass ... ok

Ran 7 tests in 0.082s
OK
```

No-LLM-imports gate: **PASS** (2 tests, 0 LLM provider imports).

## Artifacts Produced
- `packages/arena-engine/src/arena_engine/mode1.py` — Mode 1 implementation (EventEmitter Protocol, Mode1Result dataclass, run_mode1_parallel function)
- `packages/arena-engine/tests/test_mode1.py` — 7-test suite with RecordingEmitter test double
- `packages/arena-engine/src/arena_engine/__init__.py` — updated to re-export mode1 symbols

## Notes
- **EventEmitter sharing**: Both mode1.py and mode2.py define an `EventEmitter` Protocol with the same signature. The `__init__.py` exports `EventEmitter` from mode2 (already present from Plan 02's mode2 work). Mode1's `EventEmitter` is identical and available via `arena_engine.mode1.EventEmitter`.
- **Per-slot event re-emission**: After each slot completes via `run_agent_slot`, its collected `RunEvent`s are re-emitted through the `EventEmitter` with merged metadata (`agent_slot`, `arena_id`, `arena_phase`). This ensures downstream consumers can demultiplex the interleaved parallel event stream.
- **Lifecycle event metadata**: `arena.workflow_started` and `arena.workflow_completed` events carry arena-level metadata (`arena_id`, `arena_phase`) but no `agent_slot` — they are arena-level, not slot-level. Per-slot events (Test 2) are filtered from lifecycle events in the test.
- **Exception isolation**: `run_agent_slot` (from Plan 01) never raises — a crashed slot returns `SlotResult(status="failed")`. This guarantees `asyncio.TaskGroup` does NOT raise when one slot crashes (Test 4 verified).
- **Pre-existing mode2 test failures**: `test_mode2.py` has 6 pre-existing errors (confirmed by stashing this plan's changes) related to `ArenaWorkflowStartedPayload.__dict__` access in mode2.py. These are NOT caused by Plan 03 and are out of scope.
- **Frozen slotted verification**: Test 7 verifies `Mode1Result` is frozen (raises `FrozenInstanceError` on mutation), slotted (no `__dict__`), and has exactly the 4 required fields.
