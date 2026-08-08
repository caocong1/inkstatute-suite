---
phase: 108
slug: arena-engine-modes-3-4
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-09
---

# Phase 108 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| Test framework | unittest with IsolatedAsyncioTestCase |
| Test runner | `python -m unittest discover` |
| Gate runner | `python scripts/run_v2_gates.py` |
| Mock ACP | MockACPBackendAdapter with backend_family support |
| TDD mode | false |

## Requirement → Test Mapping

| Requirement | Test File | Test Class/Method | Gate |
|-------------|-----------|-------------------|------|
| ENGINE-03 | test_mode3.py | Mode3ArenaReviewTests | arena-engine |
| ENGINE-04 | test_mode4.py | Mode4AdversarialTests | arena-engine |
| SAFE-06 | test_families.py | CrossFamilyEnforcementTests | arena-engine |

## Validation Waves

### Wave 0 (Pre-execution)
- [x] Research complete (108-RESEARCH.md)
- [x] Context complete (108-CONTEXT.md)
- [x] Validation strategy complete (108-VALIDATION.md)

### Wave 1 (Core primitives — no dependencies)
- [ ] review.py — ReviewFinding, ConfidenceLevel, SeverityLevel, parsing
- [ ] families.py — backend_family mapping, cross-family pairing, degradation

### Wave 2 (Mode implementations — depend on Wave 1)
- [ ] mode3.py — Arena review (self-score + cross-review + synthesis)
- [ ] mode4.py — Adversarial (arena review + adversarial + multi-round + early stop)

### Wave 3 (Integration)
- [ ] engine.py — Add mode3/mode4 dispatch
- [ ] mock_acp.py — Add backend_family parameter
- [ ] protocols.py — Add backend_family() to BackendAdapter Protocol

## Acceptance Criteria

1. **Mode 3**: Self-score iteration + cross-review + independent session synthesis
2. **Mode 4**: Mode 3 + adversarial weakness-finding + multi-round synthesis + early stopping
3. **Cross-family**: Reviewer family != reviewed family; degradation on same-family only
4. **Fresh context**: Synthesis uses independent session (AST gate covers new files)
5. **Structured review**: Findings + categorical confidence + confirmed/disproved
6. **Early stopping**: Hard cap + ≥8/10 + zero high-severity → stop with reason="converged"

## Nyquist Sampling

- Every task has automated verify
- No 3 consecutive tasks without automated verify
- Feedback latency: < 30s per test run
