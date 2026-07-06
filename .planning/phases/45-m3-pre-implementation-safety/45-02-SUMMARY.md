---
phase: 45
plan: 02
status: complete
started: 2026-07-06T00:29:09Z
completed: 2026-07-06T00:29:47Z
---

# Plan 45-02: Extend Contract-Count Freeze to RouterPort + SkillRegistryPort

## Tasks Completed

| Task | Description | Commit | Verify |
|------|-------------|--------|--------|
| 01 | Add RouterPort and SkillRegistryPort count freeze assertions | c727d91 | `python -m unittest packages/contract-test-suite/tests/test_contract_count_freeze.py -v` ✅ |

## What Was Built

Extended `test_contract_count_freeze.py` to assert all 4 frozen Protocols per SAFETY-02. The v1.6 freeze only covered `BackendAdapter` (9 methods), `ChannelAdapter` (6 methods), and `AdapterCapabilitySet` (14 fields). This plan added:

- `RouterPort` (1 method: `decide`) count assertion
- `SkillRegistryPort` (3 methods: `list_skills`, `get_skill`, `search`) count assertion

Two new imports (`from inkstatute_router_service.port import RouterPort`, `from inkstatute_skill_registry.registry import SkillRegistryPort`) resolve under the contract-test-suite gate PYTHONPATH, which already includes `router_service_src` and `skill_registry_src` (line 158 of `run_v2_gates.py`).

The SHA-256 baseline hash test (`test_contract_freeze.py`) continues passing unchanged — no platform-contract files were modified.

## Files Modified

- `packages/contract-test-suite/tests/test_contract_count_freeze.py` — added 2 imports (RouterPort, SkillRegistryPort), 2 class constants (ROUTER_PORT_METHOD_COUNT=1, SKILL_REGISTRY_PORT_METHOD_COUNT=3), and 2 test methods (test_router_port_method_count_unchanged, test_skill_registry_port_method_count_unchanged)

## Verification

**Automated verify command:**
```bash
cd /home/sorawatcher/workspace/inkstatute-suite && PYTHONPATH="packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/wecom-service/src:packages/hermes-contract-layer/src:packages/hermes-backend/src:packages/conversation-read-view/src:packages/feedback-service/src:packages/solution-loader/src:packages/lawfirm-solution/src:packages/demo-non-legal-solution/src:packages/skill-registry/src:packages/router-service/src:packages/codex-backend/src:packages/provider-model-backend/src:services/admin-console-api/src:packages/channels/core/src:packages/channels/qqbot/src" python -m unittest packages/contract-test-suite/tests/test_contract_count_freeze.py -v
```

**Result:** 5 tests pass (3 existing + 2 new) — OK

**Additional verification:**
- `test_contract_freeze.py` SHA-256 baseline hash test: 2 tests pass — OK (31 files unchanged)
- All 6 acceptance criteria grep checks pass (constants, test methods, imports all present with correct counts)

## Deviations

None — the implementation followed the plan exactly. No existing tests or constants were modified. The docstring was left unchanged as instructed (it still applies — the freeze now covers 4 Protocols + 1 dataclass).
