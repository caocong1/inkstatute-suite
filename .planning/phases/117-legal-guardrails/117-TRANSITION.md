---
phase: 117-legal-guardrails
next_phase: 119-first-run-wizard-windows-packaging
carry_forward:
  - Guardrail integrator ready for ChatController wiring
  - ClarifyLockStateMachine ready for prompt-blocking integration
  - ConfidentialityGate ready for UI dialog integration
  - High-risk task config ready for session-level task type detection
---

# Phase 117 Transition: Guardrails → Packaging

## What Phase 117 Delivered

- 6 legal guardrails with double-layer enforcement (preset persona + app-side)
- Guardrail models: GuardrailType, GuardrailSeverity, GuardrailResult
- Research-gate checker (GRD-01): "待核实" tag for conclusions without verified citations
- Citation audit enforcer (GRD-02): unverified default for invalid citations
- Clarify lock state machine (GRD-03): blocks prompts when clarification pending
- Polish checker (GRD-04): "未经润色" tag for unpolished conclusions
- Human review enforcer (GRD-05): blocks high-risk tasks without markers; immutable markers
- Confidentiality gate (GRD-06): one-time confirmation for client materials
- Guardrail integrator: single entry point for all message-level checks
- Negative regression test suite: 6 bypass-attempt tests, one per guardrail

## What Phase 119 (Packaging) Needs

Phase 119 depends on Phase 117 (per roadmap). The guardrails are complete but need UI wiring in Phase 119:

1. **ConfidentialityGate UI**: The one-time confirmation dialog needs to be rendered in the Flutter UI when client materials are detected.
2. **ClarifyLockStateMachine integration**: ChatController needs to check `canSendPrompt()` before sending and show the clarification card.
3. **GuardrailIntegrator integration**: ChatController needs to run `runAllChecks()` after receiving assistant messages and display warnings/blocks.
4. **High-risk task type detection**: Session-level task type detection needs to be wired into the ChatController.

## Carry-Forward Notes

- All guardrail modules are under `lib/guardrails/` with full test coverage
- The guardrail integrator is the single entry point for message-level checks
- The negative regression test suite locks the double-layer guarantee
- The preset persona (Phase 113) is the first layer; app enforcement (Phase 117) is the second
- No PRD RB1/RB2 rollback triggered — all 6 guardrails have both layers

## Architecture Decisions for Phase 119

- Guardrail UI wiring happens in Phase 119 (packaging), not as a separate phase
- The confidentiality dialog is a one-time per-session confirmation
- The clarify lock is per-session, reset on new session
- High-risk task type is detected from the prompt text, not from explicit user selection
