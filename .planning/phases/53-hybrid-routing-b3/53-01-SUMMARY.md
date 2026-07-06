# Plan 53-01 Summary: Legal-Risk Classifier, ModelClassifierPort, and HYBRID Enum

## Objective

Add the foundational components for hybrid routing: the `RouterStrategy.HYBRID` enum value, a `LegalRiskClassifierPort` Protocol with a keyword-based default implementation (`KeywordLegalRiskClassifier`), and a `ModelClassifierPort` Protocol for optional model-based confidence scoring.

## Tasks Completed

### Task 1: Add HYBRID enum value, LegalRiskClassifierPort, KeywordLegalRiskClassifier, and tests

**Files modified:**
- `packages/router-service/src/inkstatute_router_service/strategies.py` — Added `HYBRID = "hybrid"` as the third `RouterStrategy` enum value. Updated docstring to mention the HYBRID strategy.
- `packages/router-service/src/inkstatute_router_service/legal_risk.py` — New file defining `LegalRiskLevel(StrEnum)` (LOW/MEDIUM/HIGH), `LegalRiskAssessment` frozen dataclass (risk_level, is_high_risk, evidence, metadata), `LegalRiskClassifierPort(Protocol)`, and `KeywordLegalRiskClassifier` with high-risk and medium-risk keyword lists. Chinese keywords matched as substrings; English keywords matched with `\b` word boundaries (same pattern as `classifier.py`).
- `packages/router-service/src/inkstatute_router_service/__init__.py` — Added exports for `KeywordLegalRiskClassifier`, `LegalRiskAssessment`, `LegalRiskClassifierPort`, `LegalRiskLevel`.
- `packages/router-service/tests/test_strategies.py` — Updated `test_router_strategy_has_exactly_two_values` → `test_router_strategy_has_exactly_three_values` (asserting 3 values). Added `test_router_strategy_hybrid_value`. Updated `test_router_strategy_not_in_route_mode` to also assert `"hybrid"` not in frozen RouteMode.
- `packages/router-service/tests/test_legal_risk.py` — 16 tests covering high-risk Chinese/English keywords, medium-risk keywords, low-risk text, None/empty messages, frozen dataclass verification, evidence list population, metadata, enum values, and structural Protocol conformance.

**Commit:** `8f66013` — `feat(53-01): add HYBRID enum, legal-risk classifier, and ModelClassifierPort`

### Task 2: Add ModelClassifierPort Protocol and ModelClassificationResult dataclass

**Files modified:**
- `packages/router-service/src/inkstatute_router_service/model_classifier.py` — New file defining `ModelClassificationResult` frozen dataclass (confidence, predicted_skill, metadata) and `ModelClassifierPort(Protocol)` with `classify(context)` method.
- `packages/router-service/src/inkstatute_router_service/__init__.py` — Added exports for `ModelClassifierPort`, `ModelClassificationResult`.

**Commit:** `8f66013` — `feat(53-01): add HYBRID enum, legal-risk classifier, and ModelClassifierPort` (same commit as Task 1)

## Deviations

None — all tasks completed as planned.

## Test Results

- **Router-service package tests:** 65 tests pass (45 existing + 20 new legal-risk/strategies tests)
  - `python3 -m unittest discover -s packages/router-service/tests -v` — OK
- **Platform-contract tests:** 21 tests pass (no frozen contract modified)

## FROZEN Contract Surfaces Verified

- `RouteDecision` schema: UNCHANGED (confidence field already existed)
- `RouteMode` enum: UNCHANGED (no new values)
- `RouterPort.decide()`: UNCHANGED
- `NeutralSkillDescriptor`: UNCHANGED
- `dependencies = []` invariant: PRESERVED (no new external imports)

## Key Design Decisions

1. **LegalRiskAssessment is a frozen dataclass** — matches the pattern of other contract data shapes.
2. **KeywordLegalRiskClassifier** uses the same Chinese-substring / English-word-boundary pattern as `classifier.py` for consistency.
3. **High-risk keywords** include litigation, arbitration, criminal, compliance review, legal opinion, contract review/drafting, compensation, legal risk — queries that carry significant legal risk if answered incorrectly.
4. **ModelClassifierPort** defines only the Protocol and data shape — the actual model call is host-injected, preserving `dependencies = []`.
5. **RouterStrategy.HYBRID** is router-internal (NOT frozen RouteMode) — additive enum value, no contract surface touched.
