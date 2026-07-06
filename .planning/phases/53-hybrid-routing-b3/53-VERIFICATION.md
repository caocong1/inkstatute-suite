---
phase: 53-hybrid-routing-b3
verified: 2026-07-06T10:19:34Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
---

# Phase 53: Hybrid Routing (B3) Verification Report

**Phase Goal:** Operator can configure `RouterStrategy.HYBRID` to implement a Rule → Skill → Model cascade with confidence thresholds (route ≥0.8, clarify 0.5–0.8, fallback <0.5), where a legal-risk classifier forces high-risk queries to Hermes regardless of confidence score, and `RouteDecision.confidence` is populated for all hybrid routing decisions.
**Verified:** 2026-07-06T10:19:34Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Roadmap Success Criteria are the non-negotiable contract; PLAN frontmatter must-haves add plan-specific detail. Both are merged below.

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | `RouterStrategy.HYBRID` implements Rule → Skill → Model cascade with confidence thresholds (route ≥0.8, clarify 0.5–0.8, fallback <0.5) | ✓ VERIFIED | `service.py:228-340` (`_decide_hybrid` + `_run_cascade`). Rule layer: `classify_intent` + registry lookup → confidence 0.9 (≥0.8 → matched) or 0.6 (0.5–0.8 → simple_qa). Skill layer: `get_skill` → 1.0, search single → 0.85, ambiguous → 0.6. Model layer: `ModelClassifierPort.classify` → model confidence. Thresholds: `_ROUTE_THRESHOLD=0.8`, `_CLARIFY_THRESHOLD=0.5`. 23 `test_hybrid_strategy.py` tests pass. |
| 2 | Legal-risk classifier forces high-risk queries to Hermes regardless of confidence score; test asserts high-risk fixtures always route to Hermes | ✓ VERIFIED | `service.py:256-274` — legal-risk pre-check runs before cascade. If `is_high_risk=True`, returns `mode=matched, primary_skill="hermes", metadata["forced_to_hermes"]=True`. `test_hybrid_high_risk_forced_to_hermes`, `test_hybrid_high_risk_overrides_high_confidence`, `test_hybrid_high_risk_with_low_confidence` all pass. `legal_risk.py` defines `KeywordLegalRiskClassifier` with high-risk keywords (诉讼, litigation, criminal, etc.). 16 `test_legal_risk.py` tests pass. |
| 3 | `RouteDecision.confidence` is populated (float 0.0–1.0) for all hybrid routing decisions; strategy recorded in `metadata["router_strategy"]` without modifying frozen `RouteDecision` schema | ✓ VERIFIED | `test_hybrid_confidence_always_populated` tests 5 different contexts (rule match, skill exact, model fallback, high-risk override, no match) — all produce `confidence` as `float` in `[0.0, 1.0]`. `test_hybrid_metadata_router_strategy` asserts `metadata["router_strategy"]=="hybrid"` for all contexts. `RouteDecision` schema unchanged (events.py:207-222 — `confidence: float` already existed). Platform-contract tests: 21 pass. |
| 4 | `hybrid_routing_enabled` defaults to `False`; cold-start defaults to safe (Hermes) path; `ModelClassifierPort` is host-injected with `None` default | ✓ VERIFIED | `feature_flags.py:33` — `hybrid_routing_enabled: bool = False` (added in Phase 45). `service.py:60-61` — `legal_risk_classifier` and `model_classifier` default to `None`. When `model_classifier=None`, Model layer skipped → confidence=0.0 → `mode=zero_match, metadata["fallback_to_hermes"]=True`. `test_hybrid_no_match_no_model` passes. |
| 5 | `RouterStrategy.HYBRID = "hybrid"` added to router-internal enum (NOT frozen `RouteMode`) | ✓ VERIFIED | `strategies.py:31` — `HYBRID = "hybrid"`. `test_router_strategy_hybrid_value` asserts `RouterStrategy.HYBRID.value == "hybrid"`. `test_router_strategy_not_in_route_mode` asserts `"hybrid"` not in frozen RouteMode set. |
| 6 | `LegalRiskClassifierPort` Protocol with `classify(message) -> LegalRiskAssessment` defined in `legal_risk.py` | ✓ VERIFIED | `legal_risk.py:52-58` — `LegalRiskClassifierPort(Protocol)` with `classify(self, message: str | None) -> LegalRiskAssessment`. `test_classifier_satisfies_protocol` passes. |
| 7 | `LegalRiskAssessment` frozen dataclass with `risk_level`, `is_high_risk`, `evidence`, `metadata` fields | ✓ VERIFIED | `legal_risk.py:27-33` — frozen dataclass with all 4 fields. `test_assessment_is_frozen` asserts `FrozenInstanceError` on mutation. `test_assessment_default_evidence_empty` and `test_assessment_default_metadata_empty` pass. |
| 8 | `KeywordLegalRiskClassifier` classifies high-risk legal keywords and returns `is_high_risk=True` with evidence list | ✓ VERIFIED | `legal_risk.py:79-118` — `KeywordLegalRiskClassifier.classify()` matches high-risk keywords (Chinese substring, English word-boundary). `test_high_risk_chinese_keyword`, `test_high_risk_english_keyword`, `test_high_risk_compliance_review`, `test_evidence_list_populated` all pass. |
| 9 | `ModelClassifierPort` Protocol with `classify(context) -> ModelClassificationResult` defined in `model_classifier.py` | ✓ VERIFIED | `model_classifier.py:37-43` — `ModelClassifierPort(Protocol)` with `classify(self, context: Mapping[str, Any]) -> ModelClassificationResult`. |
| 10 | `ModelClassificationResult` frozen dataclass with `confidence`, `predicted_skill`, `metadata` fields | ✓ VERIFIED | `model_classifier.py:20-27` — frozen dataclass with `confidence: float`, `predicted_skill: str | None = None`, `metadata: dict = field(default_factory=dict)`. |
| 11 | All new symbols exported from `__init__.py` | ✓ VERIFIED | `__init__.py:8-12` — imports from `.legal_risk` and `.model_classifier`. `__all__` includes `KeywordLegalRiskClassifier`, `LegalRiskAssessment`, `LegalRiskClassifierPort`, `LegalRiskLevel`, `ModelClassificationResult`, `ModelClassifierPort`. |
| 12 | `dependencies = []` invariant preserved — no new external imports | ✓ VERIFIED | `legal_risk.py` imports: `re`, `dataclasses`, `enum`, `typing` (stdlib only). `model_classifier.py` imports: `dataclasses`, `typing` (stdlib only). `service.py` new imports: `.legal_risk` and `.model_classifier` (relative). `pyproject.toml` still has `dependencies = []`. |
| 13 | Existing `test_strategies.py` enum count test updated from 2 to 3 values | ✓ VERIFIED | `test_strategies.py:73-74` — `test_router_strategy_has_exactly_three_values` asserts `len(list(RouterStrategy)) == 3`. Passes. |
| 14 | Existing RULE and SKILL strategies continue to work unchanged (regression) | ✓ VERIFIED | `test_existing_rule_strategy_unchanged` asserts RULE produces `confidence=0.7, mode=matched, router_strategy="rule"`. `test_existing_skill_strategy_unchanged` asserts SKILL produces `confidence=1.0, mode=matched, router_strategy="skill"`. `test_existing_rule_strategy_zero_match_unchanged` passes. All 45 pre-existing tests still pass. |
| 15 | All hybrid `RouteDecision.mode` values are frozen `RouteMode` values | ✓ VERIFIED | `test_hybrid_mode_is_frozen_value` tests 5 contexts — all modes in `{"matched", "simple_qa", "skipped", "zero_match"}`. Passes. |
| 16 | `RouterService` accepts `legal_risk_classifier` and `model_classifier` as optional constructor params with `None` defaults | ✓ VERIFIED | `service.py:55-61` — both params default to `None`, stored as `self._legal_risk_classifier` and `self._model_classifier`. |

**Score:** 10/10 truths verified (all roadmap success criteria + all plan must-haves)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `packages/router-service/src/inkstatute_router_service/strategies.py` | `HYBRID = "hybrid"` added | ✓ VERIFIED | line 31 |
| `packages/router-service/src/inkstatute_router_service/legal_risk.py` | `LegalRiskClassifierPort`, `LegalRiskAssessment`, `KeywordLegalRiskClassifier` | ✓ VERIFIED | 160 lines, all symbols defined |
| `packages/router-service/src/inkstatute_router_service/model_classifier.py` | `ModelClassifierPort`, `ModelClassificationResult` | ✓ VERIFIED | 50 lines, all symbols defined |
| `packages/router-service/src/inkstatute_router_service/service.py` | `_decide_hybrid()` + `_run_cascade()` + constructor params | ✓ VERIFIED | lines 47-49 (dispatch), 55-61 (constructor), 228-430 (hybrid methods) |
| `packages/router-service/src/inkstatute_router_service/__init__.py` | Exports new symbols | ✓ VERIFIED | lines 8-12, 18-23 |
| `packages/router-service/tests/test_legal_risk.py` | Legal-risk classifier tests | ✓ VERIFIED | 16 tests pass |
| `packages/router-service/tests/test_hybrid_strategy.py` | HYBRID strategy cascade tests | ✓ VERIFIED | 23 tests pass |
| `packages/router-service/tests/test_strategies.py` | Enum count updated to 3 | ✓ VERIFIED | line 73-74, passes |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `RouterService.decide()` | `_decide_hybrid()` | `RouterStrategy.HYBRID` dispatch | ✓ VERIFIED | `service.py:47-49` — `if self._strategy == RouterStrategy.HYBRID: return self._decide_hybrid(context)` |
| `_decide_hybrid()` | `LegalRiskClassifierPort.classify()` | legal-risk pre-check | ✓ VERIFIED | `service.py:258-261` — calls `self._classify_legal_risk(message_str)` |
| `_decide_hybrid()` | `_run_cascade()` | Rule → Skill → Model | ✓ VERIFIED | `service.py:265-266` — calls `self._run_cascade(context, message_str)` |
| `_run_cascade()` | `classify_intent()` | Rule layer | ✓ VERIFIED | `service.py:295` — `intent = classify_intent(message)` |
| `_run_cascade()` | `self._registry.search()` | Skill layer | ✓ VERIFIED | `service.py:314, 322` — `get_skill()` and `_search_by_message()` |
| `_run_cascade()` | `ModelClassifierPort.classify()` | Model layer | ✓ VERIFIED | `service.py:343` — `self._model_classifier.classify(context)` |
| `_decide_hybrid()` | `_build_decision()` | RouteDecision construction | ✓ VERIFIED | `service.py:275, 296` — all paths use `_build_decision()` |
| `__init__.py` | `.legal_risk` / `.model_classifier` | Re-exports | ✓ VERIFIED | lines 8-12 |

## Test Results

| Suite | Tests | Status | Notes |
| ----- | ----- | ------ | ----- |
| router-service | 88 | ✓ OK | 45 existing + 16 legal-risk + 23 hybrid + 4 updated strategies |
| platform-contract | 21 | ✓ OK | No frozen contract modified |
| V2 gates (1–17) | — | ✓ OK | platform-contract through feedback-service all pass |
| V2 gates (18) | — | ⚠ PRE-EXISTING | `phase7-privacy-boundary` fails on `tenant_scope.py` (Phase 56 file, not Phase 53) |

## FROZEN Contract Surfaces Verified

- `RouteDecision` schema: UNCHANGED — `confidence: float` already existed (events.py:211)
- `RouteMode` enum: UNCHANGED — `matched`, `simple_qa`, `skipped`, `zero_match` (no new values)
- `RouterPort.decide()`: UNCHANGED — same 1-method Protocol
- `NeutralSkillDescriptor`: UNCHANGED
- `BackendAdapter` Protocol: UNCHANGED — 9 methods
- `RuntimeFeatureFlags`: UNCHANGED — `hybrid_routing_enabled` already existed (Phase 45)
- `dependencies = []`: PRESERVED — no new external imports

## Pre-Existing Issues (NOT caused by Phase 53)

1. **`phase7-privacy-boundary` gate failure** — `packages/platform-runtime/src/platform_runtime/tenant_scope.py:38` references `wecom_payload_internal: WeCom callback payload field 'Format'` which is forbidden in neutral packages. This file was introduced by Phase 56 (commit `67751cc`), not Phase 53. Phase 53 only modified `packages/router-service/` files.
