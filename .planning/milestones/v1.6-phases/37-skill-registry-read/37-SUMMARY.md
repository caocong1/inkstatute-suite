---
phase: 37
slug: skill-registry-read
status: complete
plans: 3
requirements: 2
tests: 526
gates: 10
created: 2026-07-04
---

# Phase 37 Summary — Skill Registry Read

## Goal

Operator can query a read-only Skill Registry that exposes Hermes skill metadata as `NeutralSkillDescriptor` records with list, get, search, and well-known discovery endpoint operations.

## Plans Executed

| Plan | Wave | Requirements | Commits | Tests Added | Status |
|------|------|-------------|---------|-------------|--------|
| 37-01 | 1 | SKILL-01 | ec3ea11, aae2ea4, 39c965e | 14 (test_mapper: 4, test_registry: 10) | ✅ |
| 37-02 | 2 | SKILL-02, SKILL-01 | 92c223a, cb3c5dc, ba7c16b | 21 (test_discovery: 9, test_api: 12) | ✅ |
| 37-03 | 3 | SKILL-01, SKILL-02 | a5e429b, 04d2498, 5c44c2c | 0 (gate integration + count fix) | ✅ |

## Requirement Satisfaction

| Requirement | Description | Plan | Verification |
|-------------|-------------|------|--------------|
| SKILL-01 | Read-only Skill Registry with list/get/search returning NeutralSkillDescriptor | 37-01, 37-02 | test_registry.py (10 tests) + test_api.py (12 tests) + read-only enforcement ✅ |
| SKILL-02 | /.well-known/agent-skills/index.json per Cloudflare RFC v0.2.0 | 37-02 | test_discovery.py (9 tests) + well-known endpoint route ✅ |

## Test Results

- **Full V2 gate suite:** 10/10 gates green (new skill-registry gate added)
- **Total tests:** 526 (up from 491 at Phase 36 close — 35 new skill-registry tests)
- **Contract freeze:** SAFETY-06 preserved — no `packages/platform-contract/` modifications

## Key Artifacts Created

### New Package: `packages/skill-registry/`
- `pyproject.toml` — package definition
- `src/inkstatute_skill_registry/__init__.py` — re-exports
- `src/inkstatute_skill_registry/mapper.py` — `manifest_skill_to_descriptor()` + `load_skills_from_manifests()`
- `src/inkstatute_skill_registry/registry.py` — `SkillRegistryPort` Protocol + `SkillRegistry` class (list/get/search, read-only)
- `src/inkstatute_skill_registry/discovery.py` — `build_discovery_index()` (Cloudflare RFC v0.2.0)
- `src/inkstatute_skill_registry/api.py` — `handle_get()` with 4 routes + feature flag integration
- `tests/test_mapper.py` — 4 mapper unit tests
- `tests/test_registry.py` — 10 registry unit tests (including read-only enforcement)
- `tests/test_discovery.py` — 9 discovery unit tests
- `tests/test_api.py` — 12 API unit tests (including feature flag default-off)

### Modified Files
- `scripts/run_v2_gates.py` — new `skill-registry` gate, updated `compileall` and `contract-test-suite` gates
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — gate count assertion 9→10

## Deviations

1. **Gate count assertion fix (37-03):** The existing test `test_v2_gates_includes_traceability_gate` hardcoded the gate count as 9. Adding the 10th gate required updating this assertion to 10. This file is in `packages/contract-test-suite/tests/`, not `packages/platform-contract/`, so SAFETY-06 is not violated.

2. **Route ordering (37-02):** `/skills/search` route is checked before `/skills/{skill_id}` to avoid prefix collision.

## Phase Status

**COMPLETE** — All 2 SKILL requirements satisfied. Read-only Skill Registry is operational with list/get/search and Cloudflare RFC v0.2.0 discovery endpoint. Feature flag `skill_registry_enabled` defaults to False.

Next phase: 38 (Router Service)
