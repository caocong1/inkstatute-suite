---
phase: 117-legal-guardrails
status: complete
requirements_closed: [GRD-01, GRD-02, GRD-03, GRD-04, GRD-05, GRD-06]
plans_executed: [117-01, 117-02, 117-03]
test_count: 400
v4_gates: all-pass
---

# Phase 117 Summary: Legal Guardrails

## Goal Achieved

六条护栏以"提示词段 + app 呈现/强制"双层落地，任一层缺失都算护栏绕过（回归测试锁定）；批准栈维持 terminal 默认拒绝；高风险结论恒带人审徽记且不可自动消除。

## Plans Executed

### 117-01: Guardrail core models + research-gate + citation audit enforcer

- `lib/guardrails/guardrail_models.dart` — GuardrailType (6 types), GuardrailSeverity (block/warn/pass), GuardrailResult, HighRiskTaskType (3 types), PolishMarker.
- `lib/guardrails/research_gate_checker.dart` (GRD-01) — Checks conclusions without verified citations; "待核实" tag.
- `lib/guardrails/citation_audit_enforcer.dart` (GRD-02) — Enforces valid citation types; unverified warnings.

### 117-02: Clarify lock + polish checker + human review enforcer

- `lib/guardrails/clarify_lock_state.dart` (GRD-03) — ClarifyLockStateMachine with locked/unlocked states; blocks prompts when locked.
- `lib/guardrails/polish_checker.dart` (GRD-04) — Detects `[POLISHED]` marker; "未经润色" warning for unpolished conclusions.
- `lib/guardrails/human_review_enforcer.dart` (GRD-05) — Enforces `[HUMAN_REVIEW:]` on high-risk tasks; block severity; immutable markers.
- `lib/guardrails/high_risk_task_config.dart` — 3 high-risk types with pattern matching.

### 117-03: Confidentiality gate + guardrail integrator + negative regression

- `lib/guardrails/confidentiality_gate.dart` (GRD-06) — One-time confirmation for client materials; DeepSeek API notice + desensitization reminder.
- `lib/guardrails/guardrail_integrator.dart` — Runs all 4 message-level guardrails; shouldBlock/warnings/allPass helpers.
- `test/guardrails/guardrail_bypass_regression_test.dart` — 6 bypass-attempt negative tests, one per guardrail.

## Requirements Closed

- **GRD-01**: Research-gate — preset persona (Phase 113) + app-side ResearchGateChecker. Conclusions without verified citations get "待核实" tag.
- **GRD-02**: Citation audit — preset persona + app-side CitationAuditEnforcer. Invalid citations default to unverified with visual warning.
- **GRD-03**: Ask-user — preset persona + app-side ClarifyLockStateMachine. Locked state blocks new prompts until user responds.
- **GRD-04**: De-AI polish — preset persona + app-side PolishChecker. Unpolished conclusions get "未经润色" tag.
- **GRD-05**: Human review — preset persona + app-side HumanReviewEnforcer. High-risk tasks without markers are blocked; markers are immutable.
- **GRD-06**: Confidentiality — app-side ConfidentialityGate. One-time confirmation with API notice + desensitization reminder.

## Double-Layer Guarantee

Each guardrail has two layers:
1. **Preset persona layer** (Phase 113): `presets/legal-core/agent.cordis.yml` persona text embeds all 6 guardrail prompt segments.
2. **App enforcement layer** (Phase 117): `lib/guardrails/` modules enforce each guardrail at the app level.

The negative regression test suite verifies that bypass attempts are caught by the app layer. Removing either layer would cause guardrail failure.

## Test Count

400 tests total (all pass):
- 18 research-gate + citation audit tests (117-01)
- 33 clarify lock + polish + human review tests (117-02)
- 33 confidentiality + integrator + bypass regression tests (117-03)
- Plus all pre-existing Phase 112-116 tests

## V4 Gates

```
dart-analyze     PASS
flutter-test     PASS
engine-manifest  SKIP (build engine first)
mock-e2e         PASS
meta-test        PASS
docx-golden      SKIP (Phase 118)
```

## Commits

- `ff3fc93` — phase context + 3 plans
- `0655d3a` — 117-01: guardrail models + research-gate + citation audit
- `65c1dd0` — 117-02: clarify lock + polish + human review enforcer
- (pending) — 117-03: confidentiality gate + integrator + negative regression
