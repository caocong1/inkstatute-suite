---
phase: 38
slug: router-service
status: complete
plans: 3
requirements: 2
tests: 564
gates: 11
created: 2026-07-04
---

# Phase 38 Summary — Router Service

## Goal

Operator can inject a standalone router library into `hermes-contract-layer/mapper.py` that produces `RouteDecision` events with the same JSONL shape as the inline implementation, supporting RULE and SKILL routing modes with a `None` default that preserves in-process fallback behavior.

## Plans Executed

| Plan | Wave | Requirements | Commits | Tests Added | Status |
|------|------|-------------|---------|-------------|--------|
| 38-01 | 1 | ROUTER-01, ROUTER-02 | d0405e9, 21ef323, 076d7ea | 25 (test_port: 3, test_service: 7, test_strategies: 15) | ✅ |
| 38-02 | 2 | ROUTER-02, ROUTER-01 | caa6996, 895f53a, 7220171 | 13 (test_skill_strategy: 8, test_mapper: 5 new) | ✅ |
| 38-03 | 3 | ROUTER-01, ROUTER-02 | 4dc938b, 4c3714a | 0 (gate integration + count fix) | ✅ |

## Requirement Satisfaction

| Requirement | Description | Plan | Verification |
|-------------|-------------|------|--------------|
| ROUTER-01 | Injectable router with same JSONL shape + None default | 38-01, 38-02, 38-03 | RouterPort Protocol + mapper injection + None fallback + 11 gates green ✅ |
| ROUTER-02 | RULE and SKILL routing modes with skill lookup + intent classification | 38-01, 38-02 | RouterStrategy enum + RULE strategy + SKILL strategy with Skill Registry ✅ |

## Test Results

- **Full V2 gate suite:** 11/11 gates green (new router-service gate added)
- **Total tests:** 564 (up from 526 at Phase 37 close — 38 new router-service tests)
- **Contract freeze:** SAFETY-06 preserved — no `packages/platform-contract/` modifications

## Key Artifacts Created

### New Package: `packages/router-service/`
- `pyproject.toml` — package definition
- `src/inkstatute_router_service/__init__.py` — re-exports
- `src/inkstatute_router_service/port.py` — RouterPort Protocol
- `src/inkstatute_router_service/strategies.py` — RouterStrategy enum (RULE, SKILL)
- `src/inkstatute_router_service/classifier.py` — intent classifier (keyword/regex)
- `src/inkstatute_router_service/service.py` — RouterService class (RULE + SKILL strategies)
- `src/inkstatute_router_service/skill_strategy.py` — SKILL strategy with Skill Registry integration
- `tests/test_port.py` — 3 Protocol tests
- `tests/test_service.py` — 7 service tests
- `tests/test_strategies.py` — 15 strategy/classifier tests
- `tests/test_skill_strategy.py` — 8 SKILL strategy tests

### Modified Files
- `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` — router injection with None default + exception fallback
- `services/hermes-contract-layer/tests/test_mapper.py` — 5 new router injection tests
- `scripts/run_v2_gates.py` — new `router-service` gate, updated PYTHONPATHs and compileall
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — gate count assertion 10→11

## Deviations

1. **Classifier word boundary (38-01):** Used `\b` word boundaries for English keywords to prevent false matches (e.g., "is" matching inside "this"), while preserving substring matching for Chinese keywords.
2. **None reason handling (38-02):** `RouteDecision` allows `reason: str | None`, but JSONL schema requires a string. When router's reason is None, substitutes a default string. No changes to frozen dataclass or schemas.
3. **Wave 2 retry (38-02):** First execution attempt failed partway through. Working tree was reset and executor was relaunched successfully.

## Phase Status

**COMPLETE** — All 2 ROUTER requirements satisfied. Standalone router library is injectable into mapper.py with None default preserving inline fallback. RULE and SKILL strategies produce normalized RouteDecision records. Feature flag `router_service_enabled` defaults to False.

Next phase: 39 (Codex Adapter Prototype)
