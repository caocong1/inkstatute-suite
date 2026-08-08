---
phase: 107-arena-engine-modes-1-2
plan: 05
status: complete
requirements: [ENGINE-01, ENGINE-02, ENGINE-05, ENGINE-06, ENGINE-07, ENGINE-08, ENGINE-09, SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-07]
---

# Plan 05: ArenaEngine Class — ArenaWorkflow Protocol + User Stop/Cancel - Summary

## What Was Built
- `arena_engine.engine.ArenaEngine` — top-level orchestration class implementing the `ArenaWorkflow` Protocol from `platform_runtime.protocols` (runtime_checkable; `isinstance(engine, ArenaWorkflow)` passes).
- `ArenaEngine.start(config)` — registers arena config, creates initial `ArenaStatus(status="running")`, prepares stop/pause `asyncio.Event` signals, returns `ArenaHandle`. Synchronous setup; background execution launched via `run()` / `_run_arena()`.
- `ArenaEngine.cancel(arena_id)` — graceful shutdown: sets stop signal, cancels background task (best-effort, never raises), calls `adapter.cancel_run(run_id)` for every active run, then `adapter.shutdown()` to close all sessions. Updates status to `"cancelled"`. Zero orphaned sessions (ENGINE-09).
- `ArenaEngine.submit_user_action(arena_id, action)` — handles `select` (records `selected_slot` in status metadata), `stop` (sets stop signal, status `"stopped"`), `pause` (sets pause flag, status `"paused"`), `resume` (clears pause flag, status `"running"`).
- `ArenaEngine.query_status(arena_id)` — returns current `ArenaStatus` (raises `KeyError` if unknown).
- `ArenaEngine._run_arena(arena_id, adapters, event_emitter)` — dispatches to `run_mode1_parallel` or `run_mode2_iteration` based on `config.mode`, then applies guardrails + provenance.
- `ArenaEngine._apply_guardrails_and_provenance(arena_id, slot_results, is_external)` — non-bypassable post-hoc guardrail boundary: calls `apply_post_hoc_guardrails` for every slot with content, records `requires_human_review` in arena metadata, logs one `ProvenanceChain` per extracted claim (SAFE-01..04, SAFE-07).
- `ArenaEngine._external_map(adapters)` — slot → is_external map; self-built core (`inkstatute-agent`) skips post-hoc guardrails (already run in `turn_loop.py`).
- `MockACPBackendAdapter` extended with `_sessions` set tracking + `shutdown()` method mirroring the real `ACPBackendAdapter.shutdown()` pattern, enabling ENGINE-09 zero-orphan validation with mocks.
- `arena_engine.__init__` re-exports `ArenaEngine`.

## Tasks Completed
- [x] Task 1: ArenaEngine core — Protocol implementation, start, cancel, user action, status (Tests 1-9)
- [x] Task 2: Guardrail + provenance wiring in ArenaEngine (Tests 10-13)

## Verification Results
- `python -m unittest discover -s packages/arena-engine/tests -p "test_engine.py" -v` → 13 tests, OK (exit 0)
- Full arena-engine suite: 66 tests, OK (53 pre-existing + 13 new, no regressions)
- ENGINE-05 AST gate (`test_no_llm_imports.py`) still green — engine.py imports zero LLM providers.
- Test 1: `isinstance(engine, ArenaWorkflow)` passes (runtime_checkable Protocol).
- Test 4: cancel asserts `adapter._sessions == set()` for every adapter (zero orphans) + `cancel_run` called.
- Test 9: cancel during active Mode 2 iteration does not propagate exceptions.
- Test 12: spy on `apply_post_hoc_guardrails` asserts it is awaited once per external slot (non-bypassable).
- Test 13: high-risk content (违法, 无效) → `requires_human_review=True` recorded in `ArenaStatus` metadata.

## Artifacts Produced
- `packages/arena-engine/src/arena_engine/engine.py` — `ArenaEngine` class
- `packages/arena-engine/tests/test_engine.py` — `EngineLifecycleTests` (Tests 1-9) + `EngineGuardrailTests` (Tests 10-13)
- `packages/arena-engine/src/arena_engine/mock_acp.py` — `_sessions` tracking + `shutdown()` added
- `packages/arena-engine/src/arena_engine/__init__.py` — `ArenaEngine` re-exported

## Notes
- **ENGINE-09 scope split (deliberate):** Phase 107 uses mock adapters (no real subprocesses), so "zero orphaned processes" is validated by asserting `adapter._sessions` is empty after cancel. The real subprocess PID assertion is Phase 109 (Arena Service) where real ACP subprocesses are spawned. This mirrors the plan's scope note.
- **Atomic commits:** Two commits made — `feat(107-05): ArenaEngine core …` (Task 1, Tests 1-9) and `feat(107-05): guardrail + provenance wiring …` (Task 2, Tests 10-13).
- **Self-built core guardrail skip (SAFE-01):** `_external_map` treats `backend_id == "inkstatute-agent"` as non-external so post-hoc guardrails are skipped (they already run inside `turn_loop.py`), avoiding double execution. All other backends are external and always pass through `apply_post_hoc_guardrails` — no bypass path.
- **Provenance claim extraction:** When the citation audit produces items, each citation `reference` is logged as a claim; otherwise the polished content is logged as a single claim so `get_all_chains(arena_id)` is never empty.
- STATE.md and ROADMAP.md were NOT modified, per instructions. Pre-existing uncommitted changes to `.planning/STATE.md` and `.planning/config.json` were left unstaged.
