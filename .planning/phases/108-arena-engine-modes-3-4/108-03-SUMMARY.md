---
phase: 108-arena-engine-modes-3-4
plan: 03
status: complete
requirements: [ENGINE-04]
---

# Plan 03: Mode 4 — Adversarial (Arena Review + Adversarial + Multi-round + Early Stop) - Summary

## Objective

Implement `mode4.py` with `run_mode4_adversarial()` — Mode 4 builds on Mode 3's arena review, then adds: (1) adversarial weakness-finding by a dedicated `adversarial_adapter` that challenges the synthesis output, (2) multi-round synthesis that re-synthesizes incorporating adversarial findings, and (3) early stopping with a hard round cap + convergence condition (≥8/10 score AND zero high-severity findings).

## Tasks Completed

### Task 1: Mode4Result dataclass + adversarial challenge + multi-round synthesis loop

**Files created:**
- `packages/arena-engine/src/arena_engine/mode4.py` — Full Mode 4 implementation
- `packages/arena-engine/tests/test_mode4.py` — 16 tests covering all behaviors

**Key implementations:**
- `SynthesisRound` — frozen slotted dataclass with `round`, `synthesis_content`, `synthesis_score`, `adversarial_findings`, `high_severity_count`
- `Mode4Result` — frozen slotted dataclass with `arena_id`, `mode3_result`, `synthesis_rounds`, `adversarial_findings`, `final_synthesis_content`, `final_synthesis_score`, `rounds_completed`, `stopped_early`, `stop_reason`, `metadata`
- `run_mode4_adversarial()` — runs Mode 3 arena review first (via `run_mode3_arena_review()` with a `_ScoreOnlyForwarder` that suppresses Mode 3's lifecycle events), then enters adversarial loop for `range(config.max_rounds)`:
  1. Check `stop_signal` at top of each round
  2. Run adversarial challenge with fresh `turn_id="{arena_id}-adversarial-round{r}"`
  3. Parse findings via `_parse_review_findings()`, count high-severity
  4. Extract synthesis score via `_extract_self_score()`
  5. Append `SynthesisRound` (before stop check to preserve round data)
  6. Emit `arena.adversarial_challenge_completed`
  7. Check `_should_stop_early()` — if stop, emit `arena.early_stop_triggered`, break
  8. If not stopping: re-synthesize with fresh `turn_id="{arena_id}-synthesis-round{r+1}"`, emit `arena.synthesis_started`/`arena.synthesis_completed`
- `_ScoreOnlyForwarder` — async wrapper emitter that forwards only `arena.score_recorded` events from Mode 3 to the real emitter (suppresses Mode 3's lifecycle events)
- `_build_adversarial_prompt()` — adversarial challenge prompt with `[FINDING]` block format
- `_build_resynthesis_prompt()` — re-synthesis prompt incorporating adversarial findings
- `_build_adversarial_run_request()` / `_build_resynthesis_run_request()` — fresh `RunRequest` builders with unique `turn_id` per round

**Tests (Mode4AdversarialTests — 11 async tests):**
1. `Mode4Result` frozen slotted dataclass shape
2. `SynthesisRound` frozen slotted dataclass shape
3. Convergence early stop (score ≥8, no high-severity → `converged`)
4. `arena.adversarial_challenge_completed` event with `challenger_slot="adversarial"`, `challenged_slot="synthesis"`
5. `arena.early_stop_triggered` event with `reason="converged"`
6. Multi-round synthesis (high-severity → re-synthesis → 2 `synthesis_rounds` entries)
7. Adversarial adapter is separate instance with fresh `turn_id` per round
8. User stop during adversarial loop (`stopped_early=True`, `stop_reason="user_stopped"`)

**Commit:** `1d6802a` — `feat(108-03): Mode4Result dataclass + adversarial challenge + multi-round synthesis loop with early stopping`

### Task 2: Early stopping logic — _should_stop_early with 3 conditions

**Implementation (in mode4.py, committed with Task 1):**
- `_should_stop_early(round, max_rounds, synthesis_score, high_severity_count) -> tuple[bool, str]`:
  1. **Hard round cap** (checked FIRST): `round >= max_rounds - 1` → `(True, "hard_round_cap")`
  2. **Convergence**: `synthesis_score >= 8 AND high_severity_count == 0` → `(True, "converged")`
  3. Otherwise → `(False, "")`
- Hard round cap takes precedence over convergence
- `stopped_early=True` only for `reason="converged"` or `reason="user_stopped"`; `False` for `reason="hard_round_cap"`
- User stop checked separately at top of each loop iteration (not in `_should_stop_early`)

**Tests (EarlyStoppingTests — 5 unit tests + 3 integration tests):**
1. Convergence: score=9, high=0 → `(True, "converged")`
2. High-severity present: score=9, high=1 → `(False, "")`
3. Score below 8: score=7, high=0 → `(False, "")`
4. Hard round cap: round=3, max=4 → `(True, "hard_round_cap")`
5. Hard cap precedence: round=4, max=4, score=9, high=0 → `(True, "hard_round_cap")`
6. Integration: max_rounds=4, always high-severity → `hard_round_cap`, `stopped_early=False`
7. Integration: round 0 no high-severity, score=8 → `converged`, `stopped_early=True`, `rounds_completed=1`
8. Integration: `arena.early_stop_triggered` payload has correct `reason` and `round`

**Commit:** `755725f` — `feat(108-03): early stopping logic — _should_stop_early with 3 conditions (hard cap + convergence) verified and wired into adversarial loop`

## Verification

```
cd /home/sorawatcher/workspace/inkstatute-suite && \
PYTHONPATH=packages/arena-engine/src:packages/platform-contract/src:packages/platform-runtime/src:packages/agent-core/src \
python -m unittest discover -s packages/arena-engine/tests -p "test_mode4.py" -v

Ran 16 tests in 0.035s — OK
```

Full arena-engine test suite (115 tests) also passes with zero regressions.

## Compliance

- **ENGINE-04**: Mode 4 adversarial arena implemented
- **ENGINE-05**: Zero LLM provider imports (AST-verified by `test_no_llm_imports.py`)
- **ENGINE-06**: Zero `session/resume` calls — every phase uses fresh `RunRequest` with new `turn_id`
- **Orchestrator never produces content**: Adversarial challenge and re-synthesis use separate adapter instances
- **Fresh context per round**: Each adversarial challenge and re-synthesis uses new `turn_id`
- **Frozen slotted dataclasses**: `Mode4Result` and `SynthesisRound` are `@dataclass(frozen=True, slots=True)`
- **unittest with IsolatedAsyncioTestCase**: All async tests use `unittest.IsolatedAsyncioTestCase`

## Artifacts Produced

- `arena_engine.mode4.Mode4Result` — frozen slotted Mode 4 result dataclass
- `arena_engine.mode4.SynthesisRound` — frozen slotted per-round synthesis state
- `arena_engine.mode4.run_mode4_adversarial` — Mode 4 adversarial arena with multi-round synthesis
- `arena_engine.mode4._should_stop_early` — early stopping logic (hard cap + ≥8/10 + zero high-severity)
- `tests/test_mode4.py::Mode4AdversarialTests` — 11 async integration tests
- `tests/test_mode4.py::EarlyStoppingTests` — 5 unit tests for `_should_stop_early`
