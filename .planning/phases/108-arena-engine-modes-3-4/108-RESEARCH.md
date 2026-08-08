---
phase: 108
slug: arena-engine-modes-3-4
status: complete
created: 2026-08-09
---

# Phase 108 — Technical Research

## 1. Mode 3 (Arena Review) Design

**Findings:**
- Mode 2 foundation exists (mode2.py lines 167-330): `run_mode2_iteration` with self-score iteration, parallel slots, best-result tracking
- Event vocabulary already defined (unified_events.py lines 189-211): `ArenaReviewCompletedPayload`, `ArenaSynthesisStartedPayload`, `ArenaSynthesisCompletedPayload`
- Mode dispatch pattern in ArenaEngine (engine.py lines 265-302)
- No cross-review implementation yet

**Implementation approach (mode3.py):**
- `run_mode3_arena_review(config, agent_adapters, synthesis_adapter, event_emitter, stop_signal, artifact_store, backend_families)` — 3 phases:
  1. **Self-score iteration** — reuse Mode 2 logic (run_mode2_iteration or inline)
  2. **Cross-review** — each agent's best output reviewed by a different-family agent; cyclic pairing with cross-family enforcement
  3. **Synthesis** — independent agent session takes best result + all review findings, produces final version
- `Mode3Result` frozen slotted dataclass: `best_results`, `review_findings: dict[str, list[ReviewFinding]]`, `synthesis_content`, `rounds_completed`, `stopped_early`
- Emit `arena.review_completed` after each cross-review, `arena.synthesis_started`/`arena.synthesis_completed` for synthesis

**Patterns to follow:**
- Mode 2's iteration loop with asyncio.TaskGroup (mode2.py lines 208-295)
- Mode 2's `_emit()` helper (mode2.py lines 108-119)
- Mode 2's result dataclass pattern

## 2. Mode 4 (Adversarial) Design

**Findings:**
- Early stop event exists (unified_events.py lines 224-229): `ArenaEarlyStopTriggeredPayload`
- Adversarial event exists (unified_events.py lines 214-221): `ArenaAdversarialChallengeCompletedPayload`
- Mode 2 has user stop pattern (mode2.py lines 210-212, 298-308)
- No adversarial implementation yet

**Implementation approach (mode4.py):**
- `run_mode4_adversarial(config, agent_adapters, synthesis_adapter, adversarial_adapter, event_emitter, stop_signal, artifact_store, backend_families)` — builds on Mode 3:
  1. Run Mode 3 arena review (self-score + cross-review + synthesis)
  2. **Adversarial challenge** — adversarial agent reviews synthesis output for weaknesses
  3. **Multi-round synthesis** — if adversarial finds issues, re-synthesize with adversarial findings
  4. **Early stopping** — hard round cap + ≥8/10 score + zero high-severity findings
- `_should_stop_early(round, max_rounds, synthesis_score, adversarial_findings) -> tuple[bool, str]`
- Emit `arena.adversarial_challenge_completed` after each adversarial review
- Emit `arena.early_stop_triggered` with `reason="converged"` or `reason="hard_round_cap"`

**Patterns to follow:**
- Mode 2's stop signal pattern (mode2.py lines 210-212)
- Mode 2's round tracking with `rounds_completed` counter

## 3. Cross-Family Review Enforcement (SAFE-06)

**Findings:**
- `backend_family` NOT defined in codebase — only in planning docs
- ACP agentInfo contains `name` and `version` (capability_negotiation.py lines 123-127)
- Backend ID available via `adapter.backend_id()` (mock_acp.py line 104, adapter.py line 165)
- No family taxonomy exists — needs to be defined

**Implementation approach:**
- Define `backend_family` mapping in `packages/arena-engine/src/arena_engine/families.py`:
  - `get_backend_family(backend_id: str) -> str` — maps backend_id to family (e.g., "claude", "gpt", "gemini", "inkstatute")
  - `DEFAULT_FAMILY_MAP: dict[str, str]` — known mappings (hermes→claude, codex→gpt, gemini-cli→gemini, inkstatute-agent→inkstatute)
  - Unknown backends default to their backend_id as family
- `_pair_cross_family(slots, families) -> dict[str, str]` — returns reviewer→reviewed mapping with cross-family constraint
  - Cyclic pairing: slot[i] reviews slot[(i+1) % n]
  - If pair is same-family, try slot[(i+2) % n], etc.
  - If ALL pairs are same-family (only 1 family present), emit warning and degrade
- Degradation: emit `arena.early_stop_triggered` with `reason="same_family_only"` + warning metadata, don't silently proceed

**Patterns to follow:**
- ACP capability negotiation rejection pattern (capability_negotiation.py lines 143-165)

## 4. Independent Session Synthesis

**Findings:**
- Fresh context pattern exists (mode2.py lines 127-159): `_build_run_request()` creates new turn_id per round
- Gate test exists (test_fresh_context.py): asserts no session/resume calls
- Engine never produces content (engine.py docstring)
- Synthesis events exist (unified_events.py lines 199-211)

**Implementation approach:**
- Synthesis session uses fresh `RunRequest` with `turn_id="{arena_id}-synthesis-round{r}"`
- Synthesis agent is a SEPARATE BackendAdapter instance (not one of the candidate slots)
- `_build_synthesis_prompt(best_content, review_findings, task_instruction) -> str` — constructs prompt with best result + findings
- Pass to synthesis adapter via `adapter.submit_run()`, stream via `slot_runner.run_agent_slot()`
- Apply `apply_post_hoc_guardrails()` to synthesis output (engine.py lines 313-360 pattern)

**Patterns to follow:**
- Mode 2's `_build_run_request()` (mode2.py lines 127-159)
- Engine's `_apply_guardrails_and_provenance()` (engine.py lines 313-360)

## 5. Structured Review Output

**Findings:**
- No structured review output exists yet
- `ArenaReviewCompletedPayload` has `findings: list[JsonObject]` (unified_events.py lines 189-196)
- Provenance logging expects structured data

**Implementation approach (review.py):**
- `ConfidenceLevel` enum: `CERTAIN`, `LIKELY`, `POSSIBLE` (categorical, NOT numeric)
- `SeverityLevel` enum: `HIGH`, `MEDIUM`, `LOW`
- `ReviewFinding` frozen slotted dataclass: `description`, `confidence: ConfidenceLevel`, `severity: SeverityLevel`, `confirmed: bool`, `source_slot`, `reviewed_slot`, `metadata`
- `_parse_review_findings(content: str, source_slot: str, reviewed_slot: str) -> list[ReviewFinding]` — regex/JSON parser to extract findings from agent output
- Validate confidence is categorical (Certain/Likely/Possible), not numeric percentages

**Patterns to follow:**
- Mode 2's `_extract_self_score()` (mode2.py lines 84-100): regex-based extraction
- Unified events payload pattern: frozen dataclasses

## 6. Early Stopping Logic

**Findings:**
- Mode 2 has user stop (mode2.py lines 210-212, 298-308)
- Early stop event exists (unified_events.py lines 224-229)
- No convergence-based early stop in Mode 2
- Research defines: hard round cap (4) + ≥8/10 + zero high-severity findings

**Implementation approach:**
- `_should_stop_early(round, max_rounds, synthesis_score, adversarial_findings) -> tuple[bool, str]`
  - `round >= max_rounds` → `(True, "hard_round_cap")`
  - `synthesis_score >= 8 AND no high-severity findings` → `(True, "converged")`
  - Otherwise → `(False, "")`
- Check at end of each synthesis round
- Emit `arena.early_stop_triggered` with appropriate reason

## 7. Event Vocabulary

**Findings:**
- ALL required events already defined in Phase 105 (unified_events.py lines 158-230):
  - `ArenaReviewCompletedPayload` (lines 189-196)
  - `ArenaSynthesisStartedPayload` (lines 199-203)
  - `ArenaSynthesisCompletedPayload` (lines 207-211)
  - `ArenaAdversarialChallengeCompletedPayload` (lines 214-221)
  - `ArenaEarlyStopTriggeredPayload` (lines 224-229)
- Event type enum (enums.py lines 126-133) and event-to-payload mapping (unified_events.py lines 236-262) complete
- **No new events needed**

## 8. Integration with Phase 107

**Findings:**
- ArenaEngine dispatch (engine.py lines 265-302): switch on `config.mode`
- Current modes: "mode1_parallel", "mode2_iteration"
- Shared infrastructure: SlotRunner, ArtifactStore, GuardrailBoundary, ProvenanceLogger, EventEmitter

**Implementation approach:**
- Add mode dispatch in `ArenaEngine._run_arena()`:
  - `config.mode == "mode3_arena_review"` → `run_mode3_arena_review(...)`
  - `config.mode == "mode4_adversarial"` → `run_mode4_adversarial(...)`
- `Mode3Result` and `Mode4Result` frozen slotted dataclasses
- Reuse `run_agent_slot()` for all agent executions
- Reuse `ArtifactStore` for persisting review findings and synthesis outputs
- Reuse `apply_post_hoc_guardrails()` for synthesis output
- Extend `ProvenanceLogger.log_claim()` to include `reviewer_slot` (field already exists, provenance.py line 38)

## 9. Mock ACP Extensions

**Findings:**
- MockACPBackendAdapter exists (mock_acp.py lines 34-302) with configurable responses and backend_id
- No backend_family field currently

**Implementation approach:**
- Add `backend_family: str = "mock-family"` parameter to `MockACPBackendAdapter.__init__()`
- Add `backend_family()` method to BackendAdapter Protocol (protocols.py)
- Implement in MockACPBackendAdapter and ACPBackendAdapter
- For ACPBackendAdapter: derive from agent_name via `DEFAULT_FAMILY_MAP` or config field
- Test helpers for creating cross-family mock adapter sets (e.g., 2 Claude-family + 2 GPT-family)

## 10. Gate Tests

**Findings:**
- Existing gate tests: test_mode1.py (7 tests), test_mode2.py (9 tests)
- Fresh context gate (test_fresh_context.py): asserts no session/resume
- No LLM imports gate (test_no_llm_imports.py): asserts no LLM provider imports
- No Mode 3/4 tests yet

**Implementation approach:**
- `test_mode3.py`: cross-review pairing, same-family degradation, structured findings, fresh context synthesis, independent synthesis agent, event emission
- `test_mode4.py`: adversarial challenge, multi-round synthesis, early stop on convergence, early stop on hard cap, event emission
- `test_families.py`: backend_family mapping, cross-family pairing logic, degradation behavior
- `test_review.py`: ReviewFinding parsing, confidence levels, severity levels
- Existing AST gate tests (test_no_llm_imports.py, test_fresh_context.py) automatically cover new mode3.py/mode4.py files
- No gate count change needed (arena-engine gate already covers all tests in the package)

## Key Files to Create/Modify

**New files:**
1. `packages/arena-engine/src/arena_engine/mode3.py` — Mode 3 arena review
2. `packages/arena-engine/src/arena_engine/mode4.py` — Mode 4 adversarial
3. `packages/arena-engine/src/arena_engine/review.py` — ReviewFinding, ConfidenceLevel, SeverityLevel
4. `packages/arena-engine/src/arena_engine/families.py` — backend_family mapping, cross-family pairing
5. `packages/arena-engine/tests/test_mode3.py`
6. `packages/arena-engine/tests/test_mode4.py`
7. `packages/arena-engine/tests/test_families.py`
8. `packages/arena-engine/tests/test_review.py`

**Modified files:**
9. `packages/arena-engine/src/arena_engine/engine.py` — Add mode3/mode4 dispatch
10. `packages/arena-engine/src/arena_engine/mock_acp.py` — Add backend_family parameter
11. `packages/arena-engine/src/arena_engine/__init__.py` — Re-exports
12. `packages/platform-runtime/src/platform_runtime/protocols.py` — Add backend_family() to BackendAdapter Protocol

## Anti-Patterns to Avoid

1. Orchestrator produces synthesis content (must use independent agent session)
2. Same-family cross-review without warning (must degrade explicitly)
3. Numeric confidence percentages (must use categorical: Certain/Likely/Possible)
4. Session reuse for synthesis (must use fresh context)
5. Auto-stop without all 3 conditions (hard cap + ≥8/10 + zero high-severity)
6. LLM provider imports (forbidden by ENGINE-05 gate)
7. Silent degradation on same-family (must emit warning)
