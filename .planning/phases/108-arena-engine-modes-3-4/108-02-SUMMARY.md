---
phase: 108-arena-engine-modes-3-4
plan: 02
status: complete
requirements: [ENGINE-03]
---

# Plan 02: Mode 3 — Arena Review (Self-score + Cross-review + Independent Synthesis) - Summary

## Objective

Implement `mode3.py` with `run_mode3_arena_review()` — the Mode 3 arena review that builds on Mode 2's self-score iteration, then adds multi-agent cross-review (each agent's best output reviewed by a different-family agent, enforced by `_pair_cross_family()` from Plan 01), and finally an independent agent session (fresh context) that takes the highest-scoring result plus all review findings to produce the final synthesized version.

## Tasks Completed

### Task 1: Mode3Result dataclass + self-score iteration reuse + cross-review phase

- Created `packages/arena-engine/src/arena_engine/mode3.py` with:
  - `Mode3Result` frozen slotted dataclass with fields: `arena_id`, `best_results`, `review_findings`, `synthesis_content`, `synthesis_slot`, `rounds_completed`, `stopped_early`, `cross_family_degraded`, `metadata`
  - `run_mode3_arena_review()` implementing 3 phases:
    - **Phase 1 — Self-score iteration**: Reuses `run_mode2_iteration()` from mode2.py via a `_ScoreOnlyEmitter` wrapper that forwards only `arena.score_recorded` events (so stop-signal logic works) while suppressing Mode 2's own workflow events
    - **Phase 2 — Cross-review**: Builds families dict via `get_backend_family()`, calls `_pair_cross_family()` for cross-family pairing enforcement (SAFE-06), runs each review pair via `run_agent_slot()`, parses findings via `_parse_review_findings()`, emits `arena.review_completed`, persists via `ArtifactStore`
    - **Phase 3 — Synthesis**: Selects highest-scoring result via `_select_best_result()`, builds synthesis prompt via `_build_synthesis_prompt()`, runs independent `synthesis_adapter` with fresh `turn_id`, emits `arena.synthesis_started`/`arena.synthesis_completed`, persists via `ArtifactStore`
  - `_ScoreOnlyEmitter` — filtered emitter wrapper for Mode 2 reuse
  - `_build_review_run_request()` — fresh context RunRequest builder for cross-review
  - `_build_synthesis_run_request()` — fresh context RunRequest builder for synthesis
  - Degradation handling: same-family-only → `cross_family_degraded=True`, `arena.early_stop_triggered` with `reason="same_family_only"`, cross-review skipped, synthesis still runs; partial-same-family → proceeds with available pairs
  - User stop handling: `stopped_early=True`, cross-review and synthesis skipped, `arena.early_stop_triggered` with `reason="user_stopped"`
  - Provenance logging with `reviewer_slot` populated for cross-review findings

- Created `packages/arena-engine/tests/test_mode3.py` with `Mode3ArenaReviewTests(unittest.IsolatedAsyncioTestCase)` covering all 16 test cases (9 from Task 1 + 7 from Task 2)

### Task 2: Independent session synthesis + provenance with reviewer_slot

- `_build_synthesis_prompt(best_content, review_findings, task_instruction)` — constructs synthesis prompt including original task instruction, highest-scoring content labeled "最高分回答", and all review findings formatted as structured text with description, confidence, severity, confirmed/disproved status, and reviewer identity
- `_select_best_result(best_results)` — selects the `IterationState` with the highest `score`; ties broken by first occurrence
- Synthesis uses a separate `synthesis_adapter` BackendAdapter instance (not one of the candidate slot adapters) — orchestrator never produces content
- Synthesis `RunRequest.turn_id` is `"{arena_id}-synthesis-round0"` — fresh context, no session reuse (ENGINE-06)
- `arena.synthesis_started` event payload includes `source_slots` (all candidate slots) and `round=0`; `arena.synthesis_completed` includes `round=0`
- Synthesis output persisted via `ArtifactStore.store_round_output()` with `agent_slot="synthesis"` and metadata `{"phase": "synthesis", "round": 0}`
- Cross-review provenance: when `provenance_logger` is passed, each review finding is logged via `ProvenanceLogger.log_claim()` with `reviewer_slot` populated (not None)

## Verification

```
cd /home/sorawatcher/workspace/inkstatute-suite && PYTHONPATH=packages/arena-engine/src:packages/platform-contract/src:packages/platform-runtime/src:packages/agent-core/src python -m unittest discover -s packages/arena-engine/tests -p "test_mode3.py" -v
```

Result: **16 tests, all OK** (exit 0)

Also verified: `test_no_llm_imports.py` passes (zero LLM provider imports in mode3.py — ENGINE-05 compliant).

## Artifacts Produced

- `arena_engine.mode3.Mode3Result` — frozen slotted Mode 3 result dataclass
- `arena_engine.mode3.run_mode3_arena_review` — 3-phase arena review: self-score + cross-review + synthesis
- `arena_engine.mode3._build_synthesis_prompt` — synthesis prompt builder (best content + findings)
- `arena_engine.mode3._select_best_result` — highest-score result selector
- `arena_engine.mode3._ScoreOnlyEmitter` — filtered emitter for Mode 2 reuse
- `tests/test_mode3.py::Mode3ArenaReviewTests` — 16 test cases

## Key Design Decisions

1. **Mode 2 reuse via `_ScoreOnlyEmitter`**: Rather than duplicating Mode 2's iteration logic, Mode 3 calls `run_mode2_iteration()` with a filtered emitter that forwards only `arena.score_recorded` events. This ensures stop-signal logic works while preventing Mode 2's `workflow_started`/`workflow_completed` events from leaking into Mode 3's event stream.

2. **Synthesis is a separate adapter**: The `synthesis_adapter` parameter is a distinct `BackendAdapter` instance — the orchestrator never produces content. The synthesis agent runs with a fresh `turn_id` (`{arena_id}-synthesis-round0`), ensuring no session reuse (ENGINE-06).

3. **Cross-family enforcement via `_pair_cross_family`**: Cross-review pairing is delegated to the Plan 01 function, which returns explicit degradation results (`same_family_only`, `partial_same_family`, `single_agent`) — never silent.

4. **Provenance with `reviewer_slot`**: Cross-review findings are logged with `reviewer_slot` populated, completing the agent → reviewer → source chain (SAFE-07) that Phase 107 left as `None`.

## Compliance

- ENGINE-05: Zero LLM provider imports (AST-verified by `test_no_llm_imports.py`)
- ENGINE-06: No `session/resume` or `resume_session` calls — all phases use fresh `RunRequest` with new `turn_id`
- SAFE-06: Cross-family review pairing enforced via `_pair_cross_family()`
- SAFE-07: Provenance logging with `reviewer_slot` populated for cross-review
- Orchestrator never produces content — synthesis done by independent `synthesis_adapter`
