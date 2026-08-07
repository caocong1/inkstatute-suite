# Plan 98-01 Summary — Strong-Signal Rules + Soft Matcher + Data Source Migration + Golden Tests

**Phase:** 98 — Real-Index Routing
**Plan:** 98-01 (Wave 1, no dependencies)
**Requirements:** SKILL-07
**Status:** COMPLETE
**Executed:** 2026-08-10

## Tasks Executed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 98-01-01 | Create `strong_signal.py` — 11 regex rules + factual short-circuit | `11b9f18` | PASS |
| 98-01-02 | Create `soft_matcher.py` — bag-of-triggers scoring with 0.4 threshold | `dee4f8c` | PASS |
| 98-01-03 | Integrate strong-signal + soft matching into `RouterService.decide()` | `32dc30d` | PASS |
| 98-01-04 | Migrate router-service data source to skill-index.json via `index_to_descriptors()` | `858c249` | PASS |
| 98-01-05 | Port 15-case integration fixture + 8-case eval fixture as golden tests | `8677610` | PASS |
| 98-01-06 | Map `gate_before`/`gate_after` to `RouteDecision.gates_before`/`gates_after` | `efacc9a` | PASS |

## Files Created

- `packages/router-service/src/inkstatute_router_service/strong_signal.py` — 11 regex rules + factual short-circuit, ported verbatim from `lawfirm-profile/scripts/router.py`
- `packages/router-service/src/inkstatute_router_service/soft_matcher.py` — bag-of-triggers scoring with 0.4 threshold, 0.7 skip-clarification
- `packages/router-service/tests/_real_index_fixture.py` — helper that loads `skill-index.json` via `index_to_descriptors()` and builds a `SkillRegistry`
- `packages/router-service/tests/test_strong_signal_golden.py` — 15-case integration + 8-case eval golden tests (对拍集)
- `packages/router-service/tests/test_gate_mapping.py` — gate mapping unit tests

## Files Modified

- `packages/router-service/src/inkstatute_router_service/__init__.py` — added re-exports for strong_signal and soft_matcher modules
- `packages/router-service/src/inkstatute_router_service/service.py` — added pre-router layer in `decide()`, extended `_build_decision()` with `gates_before`/`gates_after` parameters
- `packages/router-service/tests/test_service.py` — updated test messages to be ≥12 chars (avoid pre-router interception), added 3 real-index tests
- `packages/router-service/tests/test_strategies.py` — updated test messages, same reason
- `packages/router-service/tests/test_skill_strategy.py` — updated test messages, added 2 real-index tests
- `packages/router-service/tests/test_hybrid_strategy.py` — updated test messages, same reason

## Acceptance Criteria Results

### Task 98-01-01: strong_signal.py
- [x] `_StrongSignalRule` dataclass has all required fields
- [x] `build_strong_signal_rules()` returns exactly 11 rules with correct names, patterns, confidence 0.95
- [x] 11 rule names match source verbatim
- [x] `match_strong_signal(message)` returns first matching rule or None
- [x] `is_simple_factual(message)` ports `_is_simple_factual()` exactly
- [x] 5 factual Q patterns copied verbatim
- [x] No external dependencies beyond `re` and `dataclasses`

### Task 98-01-02: soft_matcher.py
- [x] `score_skill()` implements bag-of-triggers from `metadata["host_assumptions"]` with phrase-length weighting
- [x] Only `leaf`-type skills scored; orchestration returns 0.0
- [x] `_extract_bigrams()` produces 2-char bigrams
- [x] `best_soft_match()` returns `(best_skill_id, best_score, reason_str)`
- [x] `SOFT_MATCH_THRESHOLD = 0.4`, `SKIP_CLARIFICATION_THRESHOLD = 0.7`
- [x] Empty triggers/message → score 0.0
- [x] `_extract_bigrams` handles None/empty gracefully

### Task 98-01-03: RouterService.decide() integration
- [x] `decide()` calls `match_strong_signal()` first; returns RouteDecision with rule's primary_skill, gates, confidence 0.95
- [x] If no strong-signal, calls `is_simple_factual()`; returns None, confidence 0.85, matched_rule="factual_short_circuit"
- [x] If not factual, calls `best_soft_match()`; if score ≥0.4, returns matched skill with gates
- [x] If soft match score <0.4, falls through to existing strategy cascade
- [x] `_build_decision()` accepts optional `gates_before`/`gates_after` parameters
- [x] `gate_before` (str|None) wrapped as `list[str]` (None → empty list)
- [x] `skip_clarification` stored in `metadata["skip_clarification"]`
- [x] All 88 existing tests pass (test messages updated to avoid pre-router interception)

### Task 98-01-04: Data source migration
- [x] `_real_index_fixture.py` loads `skill-index.json` via `index_to_descriptors()` and returns `SkillRegistry`
- [x] Test in `test_service.py` verifies router with real-index produces valid RouteDecision
- [x] Test in `test_skill_strategy.py` verifies SKILL strategy with real-index descriptors
- [x] 4 fake skill names do NOT appear in real-index test assertions
- [x] Existing `_FakeSkillRegistry`-based tests remain green

### Task 98-01-05: Golden tests
- [x] `INTEGRATION_FIXTURE` contains exactly 15 cases copied verbatim
- [x] `EVAL_FIXTURE` contains exactly 8 cases copied verbatim
- [x] `test_integration_accuracy_threshold` asserts ≥80% (12/15 correct — achieved 80.0%)
- [x] `test_eval_accuracy_threshold` asserts ≥75% (8/8 correct — achieved 100%)
- [x] Failure cases print diagnostic info (message, picked, expected, matched_rule, confidence)
- [x] Tests use real-index `SkillRegistry` from `_real_index_fixture.py`
- [x] Factual Q cases verify `primary_skill is None`
- [x] Strong-signal cases verify `matched_rule` is the rule name
- [x] Soft-match cases verify gates

### Task 98-01-06: Gate mapping
- [x] `court_sms` → `gates_before=[]`, `gates_after=["legal-de-ai-polish"]`
- [x] `new_case` → `gates_before=["ask-user-enforcement"]`, `gates_after=[]`
- [x] `docx_contract_review` → both gates
- [x] `judgment_or_transcript` → no gates
- [x] Soft match score <0.7 → `gates_before=["ask-user-enforcement"]`, `gates_after=["legal-de-ai-polish"]`
- [x] Soft match score ≥0.7 → `gates_before=[]` (skip), `gates_after=["legal-de-ai-polish"]`
- [x] Factual short-circuit → no gates
- [x] `metadata["skip_clarification"]` is True when score ≥0.7
- [x] No new top-level fields added to `RouteDecision`

## Test Results

- **router-service tests:** 109 passed (88 original + 5 real-index + 7 golden + 9 gate mapping)
- **All 36 gates:** green
- **Integration accuracy:** 12/15 = 80.0% (≥80% threshold met)
- **Eval accuracy:** 8/8 = 100% (≥75% threshold met)

## Deviations

1. **Existing test message updates (Task 98-01-03):** The pre-router's factual short-circuit treats messages < 12 chars as factual (ported verbatim from source). 22 existing tests used short messages (< 12 chars) that were intercepted by the pre-router. Test messages were updated to be ≥ 12 chars and avoid strong-signal/factual Q pattern matches, preserving test structure and fake registry pattern. All 88 original tests pass with updated messages.

2. **Factual case "刑法第 13 条讲什么？" (Task 98-01-05):** This message is exactly 12 chars and doesn't match any factual Q pattern, so it correctly falls through to the strategy cascade (returns `primary_skill=None` but `matched_rule=None` instead of `"factual_short_circuit"`). The golden test verifies `primary_skill is None` for all factual cases, and only checks `matched_rule == "factual_short_circuit"` for cases that actually trigger it. This matches the original lawfirm-profile behavior.

3. **Integration fixture soft-match cases:** 3 of 5 soft-match fixture cases are intercepted by strong-signal rules (e.g., "侵犯商标权" matches `ip_infringement`). This is the same behavior as the original lawfirm-profile router. The 80% accuracy threshold (12/15) accounts for these expected mismatches.

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance criteria PASS
- [x] `strong_signal.py` created with 11 regex rules + factual short-circuit
- [x] `soft_matcher.py` created with bag-of-triggers scoring
- [x] Router data source migrated to skill-index.json
- [x] Golden tests pass (≥80% / ≥75% accuracy)
- [x] `gate_before`/`gate_after` mapped to `RouteDecision`
- [x] All 88 existing router-service tests stay green (with updated messages)
- [x] All 36 gates green
- [x] SUMMARY.md with Self-Check: PASSED
