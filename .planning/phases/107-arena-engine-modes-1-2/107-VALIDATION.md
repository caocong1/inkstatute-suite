---
phase: 107
slug: arena-engine-modes-1-2
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-09
---

# Phase 107 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Test framework | unittest (stdlib) with IsolatedAsyncioTestCase |
| Test runner | `python -m unittest discover` |
| Gate runner | `python scripts/run_v2_gates.py` |
| Mock ACP | MockACPBackendAdapter (deterministic, no subprocesses) |
| TDD mode | false |

---

## Requirement → Test Mapping

| Requirement | Test File | Test Class/Method | Gate |
|-------------|-----------|-------------------|------|
| ENGINE-01 | test_mode1.py | Mode1ParallelTests | arena-engine (NEW) |
| ENGINE-02 | test_mode2.py | Mode2IterationTests | arena-engine |
| ENGINE-05 | test_no_llm_imports.py | TestNoLLMImports | arena-engine |
| ENGINE-06 | test_fresh_context.py | TestFreshContext | arena-engine |
| ENGINE-07 | test_artifact_store.py | ArtifactStoreTests | arena-engine |
| ENGINE-08 | test_slot_runner.py | SlotRunnerFailureTests | arena-engine |
| ENGINE-09 | test_engine.py | EngineCancelTests | arena-engine |
| SAFE-01 | test_guardrail_boundary.py | GuardrailBoundaryTests | arena-engine |
| SAFE-02 | test_guardrail_boundary.py | CitationAuditTests | arena-engine |
| SAFE-03 | test_guardrail_boundary.py | DeAIPolishTests | arena-engine |
| SAFE-04 | test_guardrail_boundary.py | HighRiskReviewTests | arena-engine |
| SAFE-07 | test_provenance.py | ProvenanceLoggerTests | arena-engine |

---

## Validation Waves

### Wave 0 (Pre-execution)
- [x] Research complete (107-RESEARCH.md)
- [x] Context complete (107-CONTEXT.md)
- [x] Validation strategy complete (107-VALIDATION.md)

### Wave 1 (Core primitives — no dependencies)
- [ ] Package scaffold (pyproject.toml, __init__.py)
- [ ] MockACPBackendAdapter (mock_acp.py)
- [ ] SlotRunner with exception isolation (slot_runner.py)
- [ ] ArtifactStore with reference-first logging (artifact_store.py)
- [ ] GuardrailBoundary with post-hoc guardrails (guardrail_boundary.py)
- [ ] ProvenanceLogger (provenance.py)
- [ ] Gate tests: test_no_llm_imports.py, test_fresh_context.py

### Wave 2 (Mode implementations — depend on Wave 1)
- [ ] Mode 1 parallel (mode1.py) — depends on slot_runner, mock_acp
- [ ] Mode 2 iteration (mode2.py) — depends on slot_runner, mock_acp
- [ ] ArenaEngine class (engine.py) — depends on mode1, mode2, guardrail_boundary

### Wave 3 (Gate integration)
- [ ] Add arena-engine gate to run_v2_gates.py
- [ ] Update gate count baseline (35 → 36)
- [ ] Add arena-engine to compileall gate

---

## Acceptance Criteria

1. **Mode 1**: N agents run in parallel via asyncio.TaskGroup, events tagged with agent_slot, user can select result
2. **Mode 2**: Self-score iteration with 10-point framework, user can stop, best result preserved
3. **No LLM imports**: AST gate test passes — no openai/anthropic/ollama imports in arena-engine
4. **Fresh context**: AST gate test passes — no session.resume calls in arena-engine
5. **Artifact persistence**: Structured output stored with raw_payload_ref, not full content
6. **Failure recovery**: Timeout/crash isolated to single slot, partial results preserved
7. **Cancel**: Zero orphaned processes after cancel (mock: all sessions closed)
8. **Guardrails**: Post-hoc citation audit + de-AI polish for external agents
9. **High-risk**: requires_human_review=true for high-risk legal conclusions
10. **Provenance**: agent → reviewer → source chain logged per claim

---

## Nyquist Sampling

- Every task has automated verify (unittest command)
- No 3 consecutive tasks without automated verify
- Feedback latency: < 30s per test run (mock-based, no subprocesses)
