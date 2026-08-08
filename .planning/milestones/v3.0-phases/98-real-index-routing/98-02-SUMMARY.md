# Plan 98-02 Summary — Three-Mode Detection + continue/switch/aside + LLM Fallback

**Phase:** 98 — Real-Index Routing
**Plan:** 98-02 (Wave 2, depends on 98-01)
**Requirements:** SKILL-08
**Status:** COMPLETE
**Executed:** 2026-08-10

## Tasks Executed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 98-02-01 | Create `mode_classifier.py` — AgentMode enum, ClassifyContext, ClassifyResult, ModeClassifierPort | `300b7ee` | PASS |
| 98-02-02 | Port LLM classifier + `fallback_classify()` + `normalize_action()` + `parse_mode_str()` + retry logic | `f82bf6c` | PASS |
| 98-02-03 | Port 14 unit tests from `agent_classifier.rs` as Python golden tests | `0135a6c` | PASS |
| 98-02-04 | Integrate mode detection into `RouteDecision.metadata` via optional `mode_classifier` | `65c5e5a` | PASS |

## Files Created

- `packages/router-service/src/inkstatute_router_service/mode_classifier.py` — Chat/Draft/Evidence three-mode detection ported 1:1 from `agent_classifier.rs` (691 lines). Contains: `AgentMode` StrEnum, `ClassifyContext` (7 fields), `ClassifyResult` (7 fields, frozen), `ModeClassifierPort` Protocol, `LLMModeClassifier` (host-injected LLM), `fallback_classify()` (structural-only), `normalize_action()`, `parse_mode_str()`, `parse_classifier_response()`, `classify_error_diagnostic()`, `classify_with_retry()`, `extract_json_object()`, `compact_diagnostic()`, `CLASSIFIER_SYSTEM` (10 rules, verbatim), `CLASSIFIER_POLICY_SUPPLEMENT` (5 boundary rules, verbatim)
- `packages/router-service/tests/test_mode_classifier.py` — 14 unit tests ported 1:1 from `agent_classifier.rs` (lines 468-691) as Python golden tests

## Files Modified

- `packages/router-service/src/inkstatute_router_service/__init__.py` — added re-exports for `AgentMode`, `ClassifyContext`, `ClassifyResult`, `ModeClassifierPort`, and all public functions from `mode_classifier.py`
- `packages/router-service/src/inkstatute_router_service/service.py` — added `mode_classifier: ModeClassifierPort | None = None` parameter to `__init__` (after `model_classifier`); refactored `decide()` into `_decide_core()` + post-processing `_merge_mode_metadata()` that runs mode classification AFTER the routing decision and merges results into `RouteDecision.metadata`

## Acceptance Criteria Results

### Task 98-02-01: mode_classifier.py core structures
- [x] `AgentMode` is a `StrEnum` with values `chat`, `draft`, `evidence` (lowercase, matching Rust `#[serde(rename_all = "lowercase")]`)
- [x] `AgentMode.ui_label()` returns "法律问答" for Chat, "文书起草" for Draft, "案情分析" for Evidence
- [x] `ClassifyContext` dataclass has fields: `user_message` (str), `has_directory_ref` (bool), `has_file_ref` (bool), `directory_aliases` (list[str]), `current_mode` (str|None), `current_task_label` (str|None), `has_active_document` (bool)
- [x] `ClassifyResult` dataclass has fields: `mode` (AgentMode), `label` (str), `reason` (str), `action` (str), `source` (str), `fallback_reason` (str|None), `diagnostic` (str|None)
- [x] `ModeClassifierPort` is a `Protocol` with `classify(self, context: ClassifyContext) -> ClassifyResult`
- [x] `ClassifyResult` is frozen; `ClassifyContext` is mutable for construction convenience

### Task 98-02-02: Classification logic
- [x] `normalize_action()` maps: "switch"/"切换" → "switch", "aside"/"插问"/"提问" → "aside", anything else → "continue"
- [x] `parse_mode_str()` handles Chinese aliases: "文书"/"起草"/"文书起草"/"法律文书"/"法律文书起草" → Draft; "案情"/"案情分析"/"诉讼"/"诉讼方案"/"分析"/"证据"/"证据分析" → Evidence; "咨询"/"问答"/"法律问答"/"法律咨询" → Chat; plus English: "draft"/"document"/"doc", "evidence"/"caseanalysis"/"case", "chat"/"qa"/"q&a"
- [x] `fallback_classify()` — structural only: if `has_active_document` → use `current_mode` (parse via `parse_mode_str`, default Chat); else → Chat; action always "continue"; source "fallback"; reason "AI 分类失败，已使用结构性安全默认模式"
- [x] `LLMModeClassifier` accepts a host-injected LLM callable (`LlmCallable` Protocol); system prompt and policy supplement ported verbatim from Rust lines 92-123
- [x] Action pinning: when `current_mode` is None, action is always pinned to "continue" regardless of LLM output
- [x] `parse_classifier_response()` parses JSON, normalizes action, parses mode, pins action when current_mode is None
- [x] `classify_error_diagnostic()` categorizes errors as `auth_failed`, `model_not_found`, `timeout`, `response_parse_failed`, `network_error`, `request_failed`
- [x] `classify_with_retry()` tries fast provider first, retries with primary on fallback, returns second fallback result if both fail
- [x] `fallback_classify()` does NOT read `ctx.user_message` for keyword matching (safety property verified by test)

### Task 98-02-03: 14 unit tests
- [x] `test_parses_classifier_json` — JSON parsing, no committed task → action pinned to "continue"
- [x] `test_aviation_regulatory_risk_question_is_chat` — Chat mode for risk analysis question
- [x] `test_formal_legal_opinion_document_is_draft` — Draft mode for formal document request
- [x] `test_retry_uses_primary_when_fast_falls_back` — retry: fast fails → primary succeeds
- [x] `test_double_failure_degrades_to_current_committed_mode` — double failure → fallback keeps current_mode
- [x] `test_parses_switch_action_when_task_committed` — switch action when task is committed
- [x] `test_parses_aside_action_for_mid_draft_question` — aside action for mid-draft question
- [x] `test_unknown_action_degrades_to_continue` — unknown action → continue (safe default)
- [x] `test_parses_qa_mode_alias` — Chinese mode aliases (问答, 法律问答, 文书起草, 案情分析)
- [x] `test_parses_llm_chinese_mode_label_for_draft` — Chinese mode label "文书起草" → Draft
- [x] `test_fallback_defaults_to_chat_without_current_artifact` — fallback → Chat when no active document
- [x] `test_fallback_does_not_infer_draft_from_user_text` — fallback does NOT infer from user text keywords (safety property)
- [x] `test_fallback_keeps_invalid_json_diagnostic` — fallback keeps diagnostic for invalid JSON
- [x] `test_fallback_keeps_invalid_mode_diagnostic` — fallback keeps diagnostic for invalid mode
- [x] All 14 tests pass with the ported Python implementation
- [x] Test assertions match the Rust-side expected values (mode, action, source, label)

### Task 98-02-04: RouteDecision.metadata integration
- [x] `RouterService.__init__` accepts `mode_classifier: ModeClassifierPort | None = None` (after `model_classifier`)
- [x] When `mode_classifier` is not None, `decide()` builds a `ClassifyContext` from the routing context (mapping: `message` → `user_message`, `has_directory_ref`, `has_file_ref`, `directory_aliases`, `current_mode`, `current_task_label`, `has_active_document`)
- [x] The `ClassifyResult` is stored in `RouteDecision.metadata`: `agent_mode` (str), `mode_action` (str), `mode_label` (str), `mode_source` (str), `mode_fallback_reason` (str|None)
- [x] When `mode_classifier` is None, no mode-related metadata keys are present (backward compatible — existing tests unaffected)
- [x] No new top-level fields added to `RouteDecision` (contract freeze preserved — SAFETY-06)
- [x] All 109 existing tests + 14 mode classifier tests pass (123 total)
- [x] Mode classification runs AFTER the routing decision is computed (orthogonal to skill routing)

## Test Results

- **router-service tests:** 123 passed (109 existing + 14 new mode classifier tests)
- **All 36 gates:** green
- **RouteDecision contract:** frozen — no new top-level fields added

## Deviations

None. All tasks executed as planned with no deviations.

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance criteria PASS
- [x] `mode_classifier.py` created (ported 1:1 from `agent_classifier.rs`)
- [x] Chat/Draft/Evidence mode detection works
- [x] continue/switch/aside actions with action pinning when current_mode is None
- [x] LLM fallback is structural-only (no keyword matching on user text, action always "continue")
- [x] 14 unit tests ported from Rust test suite as golden fixture
- [x] Mode detection results stored in `RouteDecision.metadata` (no new top-level fields)
- [x] All 109 existing router-service tests stay green
- [x] All 36 gates green
- [x] SUMMARY.md with Self-Check: PASSED
