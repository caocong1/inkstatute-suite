# Phase 53: Hybrid Routing (B3) - Research

**Researched:** 2026-07-06
**Status:** Complete
**Confidence:** HIGH (source-confirmed against frozen contracts, existing router-service code, and architecture research)

---

## 1. Phase Boundary

Operator can configure `RouterStrategy.HYBRID` to implement a Rule → Skill → Model cascade with confidence thresholds (route ≥0.8, clarify 0.5–0.8, fallback <0.5), where a legal-risk classifier forces high-risk queries to Hermes regardless of confidence score, and `RouteDecision.confidence` is populated for all hybrid routing decisions.

**Depends on:** Phase 50 (MCP Registry — complete), Phase 48 (Multi-Provider Runners — complete)
**Requirements:** HYBRID-01, HYBRID-02, HYBRID-03

---

## 2. Existing Code Insights

### 2.1 RouterService (`packages/router-service/src/inkstatute_router_service/service.py`)

- `RouterService` is a stateless `RouterPort` implementation with two strategies: `RULE` and `SKILL`.
- `decide()` dispatches to `_decide_rule()` or `_decide_skill()` based on `self._strategy`.
- `_build_decision()` (line 221-250) is the shared factory that constructs frozen `RouteDecision` records. It accepts `mode`, `primary_skill`, `confidence`, `required_tools`, `matched_rule`, `reason`, `supporting_skills`, and `metadata_extra`.
- The strategy is recorded in `metadata["router_strategy"]` (already the established pattern).
- `metadata["router_service_version"]` is set to `ROUTER_SERVICE_VERSION = "0.1.0"`.
- `confidence` is already a field on `RouteDecision` (float, line 211 in events.py) — no schema change needed.

### 2.2 RouterStrategy Enum (`packages/router-service/src/inkstatute_router_service/strategies.py`)

- `RouterStrategy(StrEnum)` with two values: `RULE = "rule"`, `SKILL = "skill"`.
- This is a **router-internal** enum, NOT the frozen `RouteMode` enum. The distinction is explicitly documented (lines 9-13).
- Adding `HYBRID = "hybrid"` is additive and does not touch any frozen contract surface.
- **Existing test constraint:** `test_strategies.py:73-74` asserts `len(list(RouterStrategy)) == 2`. This test must be updated to expect 3 values.

### 2.3 Intent Classifier (`packages/router-service/src/inkstatute_router_service/classifier.py`)

- `classify_intent(message: str | None) -> str | None` — pure keyword/regex classifier.
- Four intent categories: `factual_qa`, `drafting`, `analysis`, `review`.
- Chinese keywords matched as substrings; English keywords matched with `\b` word boundaries.
- The HYBRID strategy will reuse `classify_intent` for the Rule layer of the cascade.

### 2.4 RouteDecision (`packages/platform-contract/src/platform_contract/events.py:207-222`)

- Frozen dataclass with `confidence: float` field (line 211) — already exists, no schema change needed.
- `mode: RouteMode | str` — frozen values: `matched`, `simple_qa`, `skipped`, `zero_match`.
- `metadata: JsonObject` — used for strategy recording, legal-risk assessment, and cascade evidence.
- **MUST NOT be modified** (SAFETY-06 contract freeze).

### 2.5 Feature Flags (`packages/platform-runtime/src/platform_runtime/feature_flags.py`)

- `hybrid_routing_enabled: bool = False` already exists (line 33) — added in Phase 45.
- Defaults to `False` — cold-start safe path.

### 2.6 Architecture Research (`/.planning/research/ARCHITECTURE.md`)

- Section 8 (line 99-105): HYBRID strategy combines RULE + SKILL + model-based scoring.
- `ModelClassifierPort` is host-injected with `None` default → falls back to RULE+SKILL only.
- Confidence scoring data flow: `context` → HYBRID strategy → rule_score + skill_score + model_score → weighted `confidence` → `RouteDecision(mode, primary_skill, confidence, metadata)`.
- Legal-risk classifier forces high-risk queries to Hermes regardless of confidence (PITFALLS.md line 84).

### 2.7 Tool Resolver (`packages/router-service/src/inkstatute_router_service/tool_resolver.py`)

- Phase 50 added `resolve_tool_refs()` and `ToolResolutionMap` for joining skill `required_tool_refs` to MCP `capability_refs`.
- The HYBRID strategy can use `resolve_tool_refs` when a skill is matched, to populate `required_tools` on the `RouteDecision`.

### 2.8 Dependencies

- `packages/router-service/pyproject.toml` has `dependencies = []` — this invariant MUST be preserved.
- No new external imports at module top level. All protocols use structural subtyping (`Protocol`).

---

## 3. Design Decisions

### 3.1 HYBRID Strategy Cascade

The HYBRID strategy implements a three-layer cascade with confidence thresholds:

1. **Legal-risk pre-check** (always runs first):
   - Classify the message for legal risk using `LegalRiskClassifierPort`.
   - If high-risk → force to Hermes: `mode=matched`, `primary_skill="hermes"`, `metadata["forced_to_hermes"]=True`, `metadata["legal_risk_assessment"]={...}`.
   - The confidence is still populated (the computed cascade confidence), but the routing decision is overridden.

2. **Rule layer** (classify_intent + registry lookup):
   - Call `classify_intent(message)` → if intent found and registry has a matching skill → confidence = 0.9 (≥0.8, route directly).
   - If intent found but no registry match → confidence = 0.6 (0.5–0.8, clarify).
   - If no intent found → proceed to Skill layer.

3. **Skill layer** (skill registry lookup):
   - If `skill_id` in context → `get_skill(skill_id)` → if found, confidence = 1.0 (≥0.8, route directly).
   - If message present → `search(category=intent)` + name-substring fallback:
     - Single match → confidence = 0.85 (≥0.8, route directly).
     - Multiple matches → confidence = 0.6 (0.5–0.8, clarify with supporting_skills).
     - No match → proceed to Model layer.

4. **Model layer** (ModelClassifierPort, optional):
   - If `model_classifier` is not None → call `classify(context)` → use model confidence.
   - If `model_classifier` is None → confidence = 0.0 (<0.5, fallback to Hermes).

5. **Threshold application** (after cascade, only if not high-risk):
   - confidence ≥ 0.8 → `mode=matched`, route to matched skill.
   - 0.5 ≤ confidence < 0.8 → `mode=simple_qa`, `primary_skill=None`, `metadata["clarification_needed"]=True`.
   - confidence < 0.5 → `mode=zero_match`, `primary_skill=None`, `metadata["fallback_to_hermes"]=True`.

### 3.2 Legal-Risk Classifier

- `LegalRiskClassifierPort` Protocol with `classify(message: str | None) -> LegalRiskAssessment`.
- `LegalRiskAssessment` frozen dataclass: `risk_level: str`, `is_high_risk: bool`, `evidence: list[str]`, `metadata: dict`.
- `KeywordLegalRiskClassifier` — default keyword-based implementation.
  - High-risk keywords: litigation, lawsuit, arbitration, judgment, legal opinion, compliance, criminal, compensation, contract review/drafting, legal risk, etc.
  - Medium-risk keywords: contract, law, regulation, legal clause, etc.
  - Low-risk: everything else.
- Host-injected with `None` default → when None, all queries are treated as low-risk (no override).

### 3.3 ModelClassifierPort

- `ModelClassifierPort` Protocol with `classify(context: Mapping[str, Any]) -> ModelClassificationResult`.
- `ModelClassificationResult` frozen dataclass: `confidence: float`, `predicted_skill: str | None`, `metadata: dict`.
- Host-injected with `None` default → when None, the Model layer is skipped (falls back to confidence = 0.0).
- This preserves the `dependencies = []` invariant — the actual model call is host-injected, not imported.

### 3.4 Hermes as Safe Path

- "Hermes" is represented as `primary_skill="hermes"` in `RouteDecision`.
- High-risk override: `mode=matched`, `primary_skill="hermes"`, `metadata["forced_to_hermes"]=True`.
- Low-confidence fallback: `mode=zero_match`, `primary_skill=None`, `metadata["fallback_to_hermes"]=True`.
- The runtime layer interprets these metadata flags to route to the Hermes backend.

### 3.5 File Organization

New files (all inside `packages/router-service/src/inkstatute_router_service/`):
- `legal_risk.py` — `LegalRiskClassifierPort`, `LegalRiskAssessment`, `KeywordLegalRiskClassifier`
- `model_classifier.py` — `ModelClassifierPort`, `ModelClassificationResult`

Modified files:
- `strategies.py` — Add `HYBRID = "hybrid"` to `RouterStrategy`
- `service.py` — Add `_decide_hybrid()` method, `legal_risk_classifier` and `model_classifier` constructor params
- `__init__.py` — Export new symbols
- `tests/test_strategies.py` — Update enum count test from 2 to 3

New test files:
- `tests/test_hybrid_strategy.py` — HYBRID strategy cascade, confidence thresholds, legal-risk override
- `tests/test_legal_risk.py` — Legal-risk classifier tests

---

## 4. Frozen Surface Verification

| Surface | Status | Details |
|---------|--------|---------|
| `RouteDecision` schema | UNCHANGED | `confidence: float` already exists (events.py:211). No new fields. |
| `RouteMode` enum | UNCHANGED | `matched`, `simple_qa`, `skipped`, `zero_match` — no new values. |
| `RouterPort.decide()` | UNCHANGED | Same 1-method Protocol. |
| `NeutralSkillDescriptor` | UNCHANGED | No modifications. |
| `BackendAdapter` Protocol | UNCHANGED | 9 methods, no modifications. |
| `RuntimeFeatureFlags` | UNCHANGED | `hybrid_routing_enabled` already exists (Phase 45). |
| `dependencies = []` | PRESERVED | No new external imports. Protocols use structural subtyping. |

---

## 5. Risk Analysis

| Risk | Mitigation |
|------|------------|
| Existing RULE/SKILL strategies break | HYBRID is additive — `decide()` only dispatches to `_decide_hybrid()` when `strategy == HYBRID`. Existing paths unchanged. |
| `test_strategies.py:73-74` enum count test fails | Update assertion from 2 to 3 values. |
| Legal-risk classifier false positives | Keyword-based with evidence list; host can inject a more sophisticated classifier. Default classifier is conservative. |
| Model classifier unavailable at cold-start | `None` default → Model layer skipped → confidence = 0.0 → fallback to Hermes (safe path). |
| Confidence miscalibration | Legal-risk override forces high-risk to Hermes regardless of confidence. Thresholds are explicit (≥0.8, 0.5–0.8, <0.5). |

---

## 6. Test Strategy

- **Legal-risk classifier tests** (`test_legal_risk.py`): high-risk keywords → `is_high_risk=True`, low-risk → `is_high_risk=False`, None message → low-risk, evidence list populated.
- **HYBRID strategy tests** (`test_hybrid_strategy.py`):
  - Rule match + registry hit → confidence ≥0.8, mode=matched.
  - Skill exact match → confidence = 1.0, mode=matched.
  - Skill search single match → confidence ≥0.8, mode=matched.
  - Ambiguous matches → confidence 0.5–0.8, mode=simple_qa.
  - No match, no model classifier → confidence <0.5, mode=zero_match, fallback_to_hermes=True.
  - High-risk legal query → forced to Hermes regardless of confidence, metadata includes legal_risk_assessment.
  - Model classifier provides confidence → uses model confidence for threshold.
  - Confidence always populated (float 0.0–1.0) for all hybrid decisions.
  - Existing RULE/SKILL strategies unchanged (regression test).
  - Stateless behavior verified.
  - All modes are frozen RouteMode values.
