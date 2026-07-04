---
phase: 38
slug: router-service
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-04
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x / unittest (existing) |
| **Config file** | `packages/router-service/pyproject.toml` (new — Wave 0 creates) |
| **Quick run command** | `PYTHONPATH=packages/router-service/src:packages/platform-contract/src:packages/skill-registry/src python -m pytest packages/router-service/tests/ -q` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~75 seconds (11 gates including new router-service gate) |

---

## Sampling Rate

- **After every task commit:** Run quick command (router-service tests only)
- **After every plan wave:** Run `python scripts/run_v2_gates.py` (all gates)
- **Before `/gsd-verify-work`:** Full suite must be green (all 11 gates)
- **Max feedback latency:** 75 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01-01 | 01 | 1 | ROUTER-01 | — | RouterPort Protocol + RouterService with RouterStrategy enum (RULE, SKILL) | unit | `PYTHONPATH=packages/router-service/src:packages/platform-contract/src:packages/skill-registry/src python -m unittest discover -s packages/router-service/tests -p "test_port.py"` + `python -m unittest discover -s packages/router-service/tests -p "test_service.py"` | ❌ W0 | ⬜ pending |
| 38-01-02 | 01 | 1 | ROUTER-02 | — | RULE strategy produces RouteDecision with correct RouteMode mapping | unit | `PYTHONPATH=packages/router-service/src:packages/platform-contract/src python -m unittest discover -s packages/router-service/tests -p "test_strategies.py"` | ❌ W0 | ⬜ pending |
| 38-02-01 | 02 | 2 | ROUTER-02 | — | SKILL strategy uses Skill Registry for stateless skill lookup + intent classification | unit | `PYTHONPATH=packages/router-service/src:packages/platform-contract/src:packages/skill-registry/src python -m unittest discover -s packages/router-service/tests -p "test_skill_strategy.py"` | ❌ W0 | ⬜ pending |
| 38-02-02 | 02 | 2 | ROUTER-01 | — | Inject router into mapper.py + None default preserves inline fallback + JSONL shape unchanged | unit+integration | `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/router-service/src:packages/skill-registry/src python -m unittest discover -s services/hermes-contract-layer/tests` | ❌ W0 | ⬜ pending |
| 38-03-01 | 03 | 3 | ROUTER-01, ROUTER-02 | — | V2 gate integration (new router-service gate + compileall update) | integration | `python scripts/run_v2_gates.py` | ❌ W0 | ⬜ pending |
| 38-03-02 | 03 | 3 | — | — | Contract freeze not violated (existing freeze tests green) | unit | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_contract_freeze.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 package structure is created as the first step of Plan 38-01 Task 01. The following files are created by that task:

- [ ] `packages/router-service/pyproject.toml` — package definition (Plan 38-01 Task 01)
- [ ] `packages/router-service/src/inkstatute_router_service/__init__.py` — package init (Plan 38-01 Task 01)
- [ ] `packages/router-service/src/inkstatute_router_service/port.py` — RouterPort Protocol (Plan 38-01 Task 01)
- [ ] `packages/router-service/src/inkstatute_router_service/strategies.py` — RouterStrategy enum (Plan 38-01 Task 01)
- [ ] `packages/router-service/src/inkstatute_router_service/service.py` — RouterService class (Plan 38-01 Task 01)
- [ ] `packages/router-service/tests/test_service.py` — service tests (Plan 38-01 Task 01)
- [ ] `packages/router-service/tests/test_strategies.py` — strategy tests (Plan 38-01 Task 02)
- [ ] `packages/router-service/tests/test_skill_strategy.py` — SKILL strategy tests (Plan 38-02 Task 01)

*No separate Wave 0 task needed — package structure is created inline by Plan 38-01 Task 01. Existing infrastructure (pytest, run_v2_gates.py) covers framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification — router service with assertion-based tests.*

---

## Validation Sign-Off

- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-04
