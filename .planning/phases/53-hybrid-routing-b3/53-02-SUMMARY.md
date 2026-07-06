# Plan 53-02 Summary: HYBRID Strategy Cascade Implementation

## Objective

Wire the legal-risk classifier, ModelClassifierPort, and HYBRID enum value (from Plan 01) into the `RouterService._decide_hybrid()` method. This method implements the full Rule → Skill → Model cascade with confidence thresholds, legal-risk override forcing high-risk queries to Hermes, and confidence population for all hybrid routing decisions.

## Tasks Completed

### Task 1: Implement RouterService._decide_hybrid() with cascade, legal-risk override, and confidence thresholds

**Files modified:**
- `packages/router-service/src/inkstatute_router_service/service.py`:
  - Added imports for `LegalRiskAssessment`, `LegalRiskClassifierPort`, `ModelClassifierPort`.
  - Added confidence threshold constants (`_ROUTE_THRESHOLD=0.8`, `_CLARIFY_THRESHOLD=0.5`) and per-layer confidence values (`_CONFIDENCE_RULE_WITH_REGISTRY=0.9`, `_CONFIDENCE_RULE_NO_REGISTRY=0.6`, `_CONFIDENCE_SKILL_EXACT=1.0`, `_CONFIDENCE_SKILL_SINGLE=0.85`, `_CONFIDENCE_SKILL_AMBIGUOUS=0.6`, `_CONFIDENCE_NO_MATCH=0.0`).
  - Added `_HERMES_SKILL_ID = "hermes"` constant for the safe-path backend.
  - Added `legal_risk_classifier` and `model_classifier` optional params to `__init__` with `None` defaults.
  - Updated `decide()` to dispatch to `_decide_hybrid()` when `strategy == HYBRID`.
  - Added `_decide_hybrid(context)` method implementing the full cascade:
    1. Legal-risk pre-check → high-risk forces to Hermes (mode=matched, primary_skill="hermes", forced_to_hermes=True).
    2. Rule layer → classify_intent + registry lookup (confidence 0.9 or 0.6).
    3. Skill layer → get_skill or search (confidence 1.0, 0.85, or 0.6).
    4. Model layer → ModelClassifierPort.classify (model-provided confidence).
    5. Threshold application: ≥0.8 → matched, 0.5–0.8 → simple_qa (clarify), <0.5 → zero_match (fallback).
  - Added `_run_cascade()` helper returning (confidence, primary_skill, required_tools, matched_rule, supporting_skills, cascade_stage, extra_metadata).
  - Added `_classify_legal_risk()` helper returning LegalRiskAssessment or None.
  - All hybrid decisions include `metadata["router_strategy"]="hybrid"`, `metadata["router_service_version"]`, `metadata["cascade_stage"]`, and `metadata["legal_risk_assessment"]` (when classifier is present).

- `packages/router-service/tests/test_hybrid_strategy.py` — 23 tests covering:
  - Rule layer: match with registry (0.9 → matched), match without registry (0.6 → simple_qa).
  - Skill layer: exact match (1.0 → matched), single search (0.85 → matched), ambiguous (0.6 → simple_qa).
  - Model layer: high confidence (0.9 → matched), medium (0.6 → simple_qa), low (0.3 → zero_match).
  - No match: no model classifier (0.0 → zero_match, fallback_to_hermes), with registry (0.0 → zero_match).
  - Legal-risk override: high-risk forced to Hermes, high-risk overrides high confidence, high-risk with low confidence, no classifier (no override), low-risk (no override, assessment still recorded).
  - Confidence invariant: always float 0.0–1.0 for all contexts.
  - Metadata: router_strategy="hybrid", router_service_version present.
  - Frozen mode: all modes in frozen RouteMode set.
  - Stateless: two calls return equal decisions.
  - Regression: RULE strategy unchanged (0.7 confidence), SKILL strategy unchanged (1.0 confidence), RULE zero_match unchanged.

**Commit:** `853fd9c` — `feat(53-02): HYBRID strategy cascade with legal-risk override and confidence thresholds`

## Deviations

- **Test messages for Skill layer tests** — The original plan used messages like "请起草一份合同" for Skill layer tests, but these triggered the Rule layer first (intent classification matches "起草"). Updated to use messages that don't trigger intent classification ("Contract", "Case") so the cascade falls through to the Skill layer's name-substring search. This is a test-only change; the implementation is unchanged.

## Test Results

- **Router-service package tests:** 88 tests pass (65 from Plan 01 + 23 new hybrid strategy tests)
  - `python3 -m unittest discover -s packages/router-service/tests -v` — OK
- **Platform-contract tests:** 21 tests pass (no frozen contract modified)

## FROZEN Contract Surfaces Verified

- `RouteDecision` schema: UNCHANGED — `confidence: float` already existed (events.py:211)
- `RouteMode` enum: UNCHANGED — using only `matched`, `simple_qa`, `zero_match` (frozen values)
- `RouterPort.decide()`: UNCHANGED — same 1-method Protocol
- `NeutralSkillDescriptor`: UNCHANGED
- `dependencies = []` invariant: PRESERVED — `LegalRiskClassifierPort` and `ModelClassifierPort` use structural subtyping (Protocol), host-injected with `None` defaults

## Key Design Decisions

1. **Legal-risk pre-check runs first** — before the cascade, ensuring high-risk queries are always forced to Hermes regardless of what the cascade would produce.
2. **Confidence is still populated for high-risk overrides** — the cascade runs to compute confidence, but the routing decision is overridden. This satisfies HYBRID-03 (confidence always populated).
3. **Hermes represented as `primary_skill="hermes"`** — the runtime layer interprets this to route to the Hermes backend.
4. **Threshold constants are module-level** — `_ROUTE_THRESHOLD=0.8`, `_CLARIFY_THRESHOLD=0.5` for easy tuning.
5. **`_run_cascade()` is a separate helper** — keeps `_decide_hybrid()` focused on the legal-risk override and threshold application logic.
6. **Legal-risk assessment recorded in metadata** — `metadata["legal_risk_assessment"]` contains `risk_level`, `is_high_risk`, and `evidence` for all hybrid decisions when a classifier is present.
7. **Existing strategies completely unchanged** — `decide()` only dispatches to `_decide_hybrid()` when `strategy == HYBRID`. The `_decide_rule()` and `_decide_skill()` methods are untouched. The `legal_risk_classifier` and `model_classifier` params are ignored for RULE/SKILL strategies.
