---
phase: 36
slug: m2-pre-implementation-safety
status: complete
plans: 3
requirements: 6
tests: 491
gates: 9
created: 2026-07-04
---

# Phase 36 Summary — M2 Pre-Implementation Safety

## Goal

Establish safety baselines and guardrails BEFORE M2 feature work begins. Six SAFETY requirements covering selection gate integrity, contract freeze, privacy scrub unification, feature flag defaults, output boundary rules, and contract hash baseline.

## Plans Executed

| Plan | Wave | Requirements | Commits | Tests Added | Status |
|------|------|-------------|---------|-------------|--------|
| 36-01 | 1 | SAFETY-01, SAFETY-04 | fa0c3f3, 0612bc4, 432c861 | 2 test functions (14 subtests) | ✅ |
| 36-02 | 1 | SAFETY-02, SAFETY-06 | a26ba94, e9310b2, 0795b29 | 2 test files (5 functions, 34 subtests) | ✅ |
| 36-03 | 2 | SAFETY-03, SAFETY-05 | b225eda, d64724a | 3 test files (13 functions, 73 subtests) | ✅ |

## Requirement Satisfaction

| Requirement | Description | Plan | Verification |
|-------------|-------------|------|--------------|
| SAFETY-01 | Selection gate bypass removed | 36-01 | `test_non_hermes_manifest_production_ready_bypass_is_blocked` ✅ |
| SAFETY-02 | Contract-count freeze (9/14/6) | 36-02 | `test_contract_count_freeze.py` (3 tests) ✅ |
| SAFETY-03 | Privacy scrub unification (11 keys) | 36-03 | `test_privacy_keys.py` (7 tests) + `test_privacy_scrub.py` (6 tests) ✅ |
| SAFETY-04 | M2 feature flags default False | 36-01 | `test_all_m2_flags_default_to_false_via_introspection` ✅ |
| SAFETY-05 | Output boundary rules (5 patterns) | 36-03 | `test_output_boundary.py` (17 tests) + false-positive guard ✅ |
| SAFETY-06 | Contract freeze baseline hash | 36-02 | `test_contract_freeze.py` (2 tests, 31 subtests) ✅ |

## Test Results

- **Full V2 gate suite:** 9/9 gates green
- **Total tests:** 491 (up from 479 at v1.5 close — 12 new test functions added)
- **Pre-existing errors:** 2 hindsight client aiohttp errors in platform-runtime (unrelated to phase changes)

## Key Artifacts Created

### Source Files
- `packages/platform-runtime/src/platform_runtime/privacy_keys.py` — shared forbidden keys module (11 keys)
- `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` — SHA-256 baseline for 31 contract surface files
- `packages/contract-test-suite/fixtures/provider_noise_cases.json` — output boundary test fixtures

### Test Files
- `packages/contract-test-suite/tests/test_contract_count_freeze.py`
- `packages/contract-test-suite/tests/test_contract_freeze.py`
- `packages/platform-runtime/tests/test_privacy_keys.py`
- `services/conversation-read-view/tests/test_privacy_scrub.py`

### Modified Files
- `services/wecom-service/src/wecom_service/agent_backend.py` — removed selection gate bypass (lines 50-51)
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — added 6 M2 feature flags
- `packages/platform-runtime/src/platform_runtime/store.py` — imports from shared privacy_keys
- `packages/platform-runtime/src/platform_runtime/interrupts.py` — imports from shared privacy_keys
- `packages/platform-runtime/src/platform_runtime/session_resolver.py` — imports from shared privacy_keys
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` — 5 new generic patterns
- `services/conversation-read-view/src/conversation_read_view/privacy.py` — unified 11-key check
- `services/conversation-read-view/src/conversation_read_view/api.py` — scrub all API paths

## Deviations

1. **Error message format (36-03):** Included key name in error message (`forbidden {key}`) instead of plan's `forbidden key` to preserve backward compatibility with existing test regex assertions.
2. **provider_leak pattern (36-03):** Removed `rate[_-]?limit` from hard-block and `context window exceeded` from `api_error` to prevent hard-block/rewrite overlap.
3. **model[:\s] lookahead (36-03):** Replaced trailing `\b` with `(?!\w)` negative lookahead — the plan's `\b` after `model[:\s]` was logically inverted. Also fixed `token[_-]?usage` → `token[_\s-]?usage`.

## Risk Mitigation

All 4 risks identified in 36-RESEARCH.md were mitigated:
1. **Output boundary false-positives on legal text** — false-positive guard test confirms "model clause" is still ALLOWed ✅
2. **Privacy scrub breaking existing read-view tests** — full conversation-read-view suite green ✅
3. **Contract-count baseline mismatch** — used actual runtime introspection counts (9/14/6), not research text values ✅
4. **Feature flag additions breaking consumers** — all existing RuntimeFeatureFlags consumers continue to work (new fields have defaults) ✅

## Phase Status

**COMPLETE** — All 6 SAFETY requirements satisfied. M2 feature work can now proceed with safety baselines in place.

Next phase: 37 (Skill Registry Read)
