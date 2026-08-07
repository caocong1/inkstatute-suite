# Plan 98-03 Summary — Decision Logging + RouteDecision Mapping + route_mismatch + Phase Completion

**Phase:** 98 — Real-Index Routing
**Plan:** 98-03 (Wave 3, depends on 98-02)
**Requirements:** SKILL-07, SKILL-08
**Status:** COMPLETE
**Executed:** 2026-08-10

## Tasks Executed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 98-03-01 | Create `decision_log.py` — JSONL append per session + integrate into RouterService | `529a50f` | PASS |
| 98-03-02 | Complete RouteDecision field mapping + route_mismatch + report_routing_error + 19 decision log tests | `3fad904` | PASS |
| 98-03-03 | Verify all 6 success criteria + 27 explicit assertions + all 36 gates green | `51421ef` | PASS |
| 98-03-04 | Mark SKILL-07, SKILL-08 complete + Phase 98 complete + planning doc updates | (this commit) | PASS |

## Files Created

- `packages/router-service/src/inkstatute_router_service/decision_log.py` — JSONL decision logging module ported from `lawfirm-profile/scripts/router.py` (lines 299-337). Contains `append_decision_log()` (appends RouteDecision as JSON to `{log_dir}/{session_id}.jsonl`, no-op when session_id is empty, creates log dir if needed, ensure_ascii=False) and `record_routing_error()` (appends routing error record with timestamp, session_id, user_msg, router_primary, router_confidence, router_matched_rule, actual_skill to error log)
- `packages/router-service/tests/test_decision_log.py` — 19 tests covering: JSONL format verification, all 15 RouteDecision fields in log records, multiple calls append multiple lines, empty session_id no-op, log directory creation, Chinese text preservation (ensure_ascii=False), error recording with all required fields, RouterService with log_dir integration, report_routing_error() with and without log_dir, route_mismatch field from context, all 15 RouteDecision fields populated, contract freeze verification (no new top-level fields)
- `packages/router-service/tests/test_phase98_success_criteria.py` — 27 tests with explicit assertions for each of the 6 Phase 98 success criteria: (1) real-index data source + RULE/SKILL/HYBRID strategies + legal risk grading, (2) 12 strong-signal rules + golden 对拍集 ≥80% accuracy, (3) soft matching threshold 0.4 + gate semantics, (4) Chat/Draft/Evidence mode detection + LLM fallback, (5) RouteDecision event + decision log JSONL + route_mismatch feedback, (6) leaf skill matching (not 4 fake names)

## Files Modified

- `packages/router-service/src/inkstatute_router_service/__init__.py` — added re-exports for `append_decision_log` and `record_routing_error`
- `packages/router-service/src/inkstatute_router_service/service.py` — added `log_dir: Path | None = None` parameter to `__init__`; `decide()` calls `append_decision_log()` after computing the decision when `log_dir` is set and `session_id` is present; added `report_routing_error()` method (re-routes message, records error, returns decision); `_build_decision()` now stores `session_id` in `metadata` (not as a top-level field — contract freeze preserved)

## Acceptance Criteria Results

### Task 98-03-01: decision_log.py
- [x] `append_decision_log(decision, user_msg, log_dir, session_id)` appends a JSON line to `{log_dir}/{session_id}.jsonl`
- [x] Each log record contains: all RouteDecision fields (serialized via `dataclasses.asdict`), `timestamp` (ISO-8601 UTC), `user_msg`
- [x] `append_decision_log()` is a no-op when `session_id` is empty
- [x] `append_decision_log()` creates the log directory if it does not exist (`mkdir(parents=True, exist_ok=True)`)
- [x] `record_routing_error(decision, user_msg, actual_skill, error_log)` appends to the error log with: `timestamp`, `session_id` (from metadata), `user_msg`, `router_primary`, `router_confidence`, `router_matched_rule`, `actual_skill`
- [x] JSON is written with `ensure_ascii=False` (preserving Chinese text)
- [x] `RouterService.__init__` accepts `log_dir: Path | None = None`; when set, `decide()` calls `append_decision_log()` after computing the decision
- [x] When `log_dir` is None, no logging occurs (backward compatible — existing tests unaffected)

### Task 98-03-02: RouteDecision field mapping + route_mismatch
- [x] All 15 RouteDecision fields are populated by the router: `route_decision_id`, `turn_id`, `primary_skill`, `confidence`, `mode`, `created_at`, `supporting_skills`, `gates_before`, `gates_after`, `required_tools`, `matched_rule`, `reason`, `route_mismatch`, `industry_context`, `metadata` (includes `skip_clarification`, `session_id`, `agent_mode`, `mode_action`, `mode_label`, `mode_source`, `router_strategy`, `router_service_version`)
- [x] `report_routing_error(context, actual_skill) -> RouteDecision` — re-routes the message, calls `record_routing_error()`, returns the decision
- [x] `test_decision_log.py` verifies: JSONL format (each line is valid JSON), required fields present (`timestamp`, `primary_skill`, `session_id`, `user_msg`), multiple calls append multiple lines, empty session_id → no log file created
- [x] `test_decision_log.py` verifies error recording: `record_routing_error()` produces a record with `router_primary`, `router_confidence`, `router_matched_rule`, `actual_skill`
- [x] `route_mismatch` field on `RouteDecision` can be set to `True` when feedback indicates wrong routing (from `context.get("route_mismatch")`)
- [x] No new top-level fields added to `RouteDecision` (contract freeze preserved)

### Task 98-03-03: Success criteria verification
- [x] `python scripts/run_v2_gates.py` exits 0 (all 36 gates green)
- [x] Criterion 1: Router data source is real skill-index (verified by test with `index_to_descriptors()`); RULE/SKILL/HYBRID strategies + legal risk grading preserved and all tests green
- [x] Criterion 2: 12 strong-signal regex rules ported (11 `_Rule` + factual short-circuit); golden 对拍集 verifies ≥80% accuracy on 15-case set
- [x] Criterion 3: Soft matching threshold 0.4, confidence <0.6 marks ambiguous, `gate_before=ask-user-enforcement`, `gate_after=legal-de-ai-polish` semantics preserved (verified by `test_gate_mapping.py`)
- [x] Criterion 4: Chat/Draft/Evidence three-mode detection + continue/switch/aside actions ported with LLM fallback (verified by 14 unit tests in `test_mode_classifier.py`)
- [x] Criterion 5: Router produces `RouteDecision` contract event + writes decision log JSONL (verified by `test_decision_log.py`); `route_mismatch` feedback association wired
- [x] Criterion 6: Given real lawyer task samples (15-case fixture), router hits specific leaf sub-skills (not the 4 fake names `case_qa`, `contract_draft`, `litigation_summary`, `compliance_review`)
- [x] `test_phase98_success_criteria.py` contains explicit assertions for each of the 6 criteria
- [x] No gate count regression (all pre-existing gates remain green)

### Task 98-03-04: Phase completion
- [x] SKILL-07 marked `[x]` with `✅ Phase 98` in REQUIREMENTS.md
- [x] SKILL-08 marked `[x]` with `✅ Phase 98` in REQUIREMENTS.md
- [x] SKILL-07 and SKILL-08 status updated to "Complete ✅" in the mapping table
- [x] Phase 98 marked `[x]` complete in ROADMAP.md
- [x] ROADMAP.md Plans line updated: `Plans: 3 (98-01 strong-signal+soft-match ✅ | 98-02 mode-detection ✅ | 98-03 decision-log+completion ✅) ✅ COMPLETE`
- [x] STATE.md `completed_phases` incremented (from 10 to 11)
- [x] STATE.md `total_plans` and `completed_plans` incremented by 3 (from 48 to 51)
- [x] STATE.md `current focus` updated to Phase 99
- [x] STATE.md `next command` updated to `/gsd-plan 99`
- [x] STATE.md `last_activity` updated to reflect Phase 98 plan + execution completion

## Test Results

- **router-service tests:** 169 passed (123 existing + 19 decision log + 27 success criteria)
- **All 36 gates:** green
- **RouteDecision contract:** frozen — no new top-level fields added (all 15 fields preserved)
- **Integration accuracy:** 12/15 = 80.0% (≥80% threshold met, verified in success criteria test)
- **Eval accuracy:** 8/8 = 100% (≥75% threshold met, verified in golden test)

## Phase 98 Success Criteria Verification

| # | Criterion | Verification | Status |
|---|-----------|-------------|--------|
| 1 | Router data source is real skill-index | `test_phase98_success_criteria.py::TestCriterion1RealIndexDataSource` (5 tests) | ✅ PASS |
| 2 | 12 strong-signal regex rules + golden 对拍集 | `test_phase98_success_criteria.py::TestCriterion2StrongSignalRules` (5 tests) | ✅ PASS |
| 3 | Soft matching threshold 0.4 + gate semantics | `test_phase98_success_criteria.py::TestCriterion3SoftMatchingSemantics` (4 tests) + `test_gate_mapping.py` (9 tests) | ✅ PASS |
| 4 | Chat/Draft/Evidence three-mode detection + LLM fallback | `test_phase98_success_criteria.py::TestCriterion4ThreeModeDetection` (5 tests) + `test_mode_classifier.py` (14 tests) | ✅ PASS |
| 5 | RouteDecision event + decision log JSONL + route_mismatch | `test_phase98_success_criteria.py::TestCriterion5DecisionLogAndRouteMismatch` (5 tests) + `test_decision_log.py` (19 tests) | ✅ PASS |
| 6 | Leaf skill matching (not 4 fake names) | `test_phase98_success_criteria.py::TestCriterion6LeafSkillMatching` (3 tests) | ✅ PASS |

## Deviations

None. All tasks executed as planned with no deviations.

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance criteria PASS
- [x] `decision_log.py` created (JSONL append per session)
- [x] RouteDecision mapping complete (all 15 fields)
- [x] `route_mismatch` feedback association works
- [x] All 6 success criteria verified with explicit test assertions
- [x] All 36 gates green
- [x] SKILL-07, SKILL-08 marked complete
- [x] Phase 98 marked complete in STATE.md and ROADMAP.md
- [x] SUMMARY.md with Self-Check: PASSED
