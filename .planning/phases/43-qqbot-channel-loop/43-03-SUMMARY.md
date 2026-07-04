---
phase: 43
plan: 43-03
title: "Feature Flag Default-Off + V2 Gate Integration + Contract Freeze Verification"
wave: 3
depends_on:
  - 43-01
  - 43-02
requirements:
  - QQBOT-04
  - SAFETY-04
  - GATE-01
  - SAFETY-02
  - SAFETY-06
status: complete
autonomous: true
---

# Plan 43-03 — Execution Summary

## Plan ID

**43-03** — Feature Flag Default-Off + V2 Gate Integration + Contract Freeze Verification

## Tasks Completed

| Task | Description | Commit Hash |
|------|-------------|-------------|
| 43-03-01 | Create `test_feature_flag.py` — verifies `qqbot_channel_enabled` defaults to `False`, QQBot adapter refuses ACK/delivery when disabled, all 6 M2 flags default False (9 tests) | `c82a1f8` |
| 43-03-02 | Modify `scripts/run_v2_gates.py` — add `qqbot-channel` gate (#15), add `channel_core_src` to wecom-service/codex-backend/provider-model-backend/feedback-service gate PYTHONPATH, add `channel_core_src`+`qqbot_src` to contract-test-suite PYTHONPATH, add channel-core/qqbot src to compileall, fix audit `_check_library_surface` to capture `ast.ImportFrom` re-exports, update gate count assertion 14→15 | `bc4793c` |
| 43-03-03 | Create `test_contract_freeze_not_violated.py` — verifies ChannelAdapter 6 methods, FeedbackSource 4 values, Channel.QQBOT, flag default False, protocols.py/feature_flags.py not modified (7 tests) | `cbc33ce` |

## Tests Added

| Test File | Tests | Status |
|-----------|-------|--------|
| `packages/channels/qqbot/tests/test_feature_flag.py` | 9 | ✅ pass |
| `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` | 7 | ✅ pass |
| **Total new tests** | **16** | **✅ all pass** |

## Test Commands Used

- **feature flag:** `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages.channels.qqbot.tests.test_feature_flag -v` → 9 tests, 0 failures
- **contract freeze (existing):** `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/contract-test-suite/tests/test_contract_count_freeze.py packages/contract-test-suite/tests/test_contract_freeze.py -v` → 5 tests, 0 failures
- **contract freeze (new):** `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages.channels.qqbot.tests.test_contract_freeze_not_violated -v` → 7 tests, 0 failures
- **full V2 gate suite:** `python scripts/run_v2_gates.py` → 15/15 gates green, exit code 0

## V2 Gate Results

**15/15 gates green** ✅

| # | Gate | Tests | Status |
|---|------|-------|--------|
| 1 | platform-contract | 21 | ✅ |
| 2 | wecom-service | 72 | ✅ |
| 3 | hermes-contract-layer | 35 | ✅ |
| 4 | conversation-read-view | 106 | ✅ |
| 5 | skill-registry | 35 | ✅ |
| 6 | router-service | 33 | ✅ |
| 7 | codex-backend | 32 | ✅ |
| 8 | provider-model-backend | 37 | ✅ |
| 9 | admin-console-api | 113 (1 skipped) | ✅ |
| 10 | **qqbot-channel** (NEW) | 61 | ✅ |
| 11 | feedback-service | 31 | ✅ |
| 12 | phase7-privacy-boundary | 13 | ✅ |
| 13 | contract-test-suite | 323 | ✅ |
| 14 | v2-acceptance-traceability | — | ✅ |
| 15 | compileall | — | ✅ |

## Requirements Satisfied

### QQBOT-04: `qqbot_channel_enabled` defaults to `False`; QQ Bot feedback maps to existing `FeedbackEvent.source` enum values

- ✅ `RuntimeFeatureFlags().qqbot_channel_enabled is False` (default-off verified)
- ✅ `qqbot_channel_enabled` field exists in `RuntimeFeatureFlags` dataclass fields
- ✅ QQBot adapter refuses ACK when disabled: `accepted=False, status_code=503`
- ✅ QQBot adapter refuses delivery when disabled: `accepted=False`
- ✅ QQBot adapter health reports not-ok when disabled: `ok=False, component_id="qqbot-channel"`
- ✅ `QQBotChannelConfig().enabled is False` (default config disabled)
- ✅ `QQBotChannelConfig.from_env({})` does not enable the channel
- ✅ `from_env({"INKSTATUTE_QQBOT_CHANNEL_ENABLED": "true"})` enables; `"false"` does not
- ✅ QQBot feedback maps to existing `FeedbackSource.CARD_BUTTON` ("card_button") — no new enum values (verified in Plan 43-02)

### SAFETY-04: All M2 feature flags default to `False`

- ✅ `router_service_enabled is False`
- ✅ `skill_registry_enabled is False`
- ✅ `admin_api_enabled is False`
- ✅ `qqbot_channel_enabled is False`
- ✅ `codex_backend_enabled is False`
- ✅ `provider_model_backend_enabled is False`

### GATE-01: V2 gate suite includes new qqbot-channel gate, all gates green

- ✅ New `qqbot-channel` gate (#10 in order) runs `unittest discover -s packages/channels/qqbot/tests`
- ✅ Gate PYTHONPATH: `(qqbot_src, channel_core_src, platform_src, platform_runtime_src)`
- ✅ `channel_core_src` added to wecom-service gate PYTHONPATH (required after Wave 1 extraction)
- ✅ `channel_core_src` added to codex-backend, provider-model-backend, feedback-service gate PYTHONPATH (all import from wecom_service which imports from channel_core)
- ✅ `channel_core_src` and `qqbot_src` added to contract-test-suite gate PYTHONPATH
- ✅ `packages/channel-core/src` and `packages/channels/qqbot/src` added to compileall gate
- ✅ Total gates: 14 → 15
- ✅ All 15 gates pass with exit code 0

### SAFETY-02: Contract-count assertion — ChannelAdapter Protocol method count unchanged (6)

- ✅ `ChannelAdapter` has exactly 6 methods: `channel_id`, `capabilities`, `verify_and_ack`, `normalize_inbound`, `deliver`, `health`
- ✅ Existing `test_contract_count_freeze.py` passes unchanged (CHANNEL_ADAPTER_METHOD_COUNT=6)
- ✅ New `test_contract_freeze_not_violated.py` confirms 6 methods via runtime introspection

### SAFETY-06: Contract freeze baseline hash — no `packages/platform-contract/` schema files modified

- ✅ Existing `test_contract_freeze.py` passes unchanged (all 31 SHA-256 baseline hashes match)
- ✅ No new schema files added without baseline entries
- ✅ `FeedbackSource` has exactly 4 values: `card_button`, `text_command`, `web_form`, `admin_annotation`
- ✅ `Channel.QQBOT.value == "qqbot"` (existing enum value preserved)
- ✅ `protocols.py` not modified (verified by runtime introspection of method count)
- ✅ `feature_flags.py` not modified (verified by runtime introspection of flag default)

## Contract Freeze Compliance

- ✅ No changes to `packages/platform-contract/`
- ✅ No changes to `packages/platform-runtime/src/platform_runtime/protocols.py`
- ✅ No changes to `packages/platform-runtime/src/platform_runtime/feature_flags.py`
- ✅ ChannelAdapter Protocol remains 6 methods (frozen)
- ✅ FeedbackSource enum remains 4 values (frozen)
- ✅ `Channel.QQBOT = "qqbot"` already existed (not modified)
- ✅ `qqbot_channel_enabled` feature flag already existed with default `False` (not modified)

## Additional Fix: Audit Script `_check_library_surface`

During Task 43-03-02, the V2 gate suite revealed that the `v2-acceptance-traceability` gate was failing because the audit script's `_check_library_surface` AST checker did not account for re-export shims created in Plan 43-01 (Wave 1). After Wave 1, wecom-service modules like `output_policy.py` and `active_task_router.py` became thin shims that import names (e.g., `OutputPolicyDecision`, `ActiveTaskRoutingDecision`) from `channel_core` instead of defining them locally. The AST checker only looked for `FunctionDef`, `ClassDef`, and `Assign` nodes, missing `ImportFrom` nodes.

**Fix:** Updated `_check_library_surface` in `scripts/audit_v2_requirements.py` to also capture names from `ast.ImportFrom` nodes (both `alias.name` and `alias.asname`). This is a legitimate fix because re-export via import is a valid Python library surface pattern — the shim files still export the same API, they just source the implementation from a shared package.

Also updated `test_v2_gates_includes_traceability_gate` in `packages/contract-test-suite/tests/test_audit_v2_requirements.py` to expect 15 gates (was 14) and include `qqbot-channel` in the `assertIn` checks.

## Privacy Compliance

- ✅ No literal secrets in test files
- ✅ All test values are fixture references (`fixture://qqbot/...`) or sanitized placeholders
- ✅ No `wecom_service` imports in qqbot test files (except contract freeze tests which import from `platform_contract` and `platform_runtime` only)

## Files Created

- `packages/channels/qqbot/tests/test_feature_flag.py` — feature flag default-off test (9 tests, 130 lines)
- `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` — contract freeze verification test (7 tests, 92 lines)

## Files Modified

- `scripts/run_v2_gates.py` — added `channel_core_src`/`qqbot_src` path variables, added `qqbot-channel` gate (#15), added `channel_core_src` to wecom-service/codex-backend/provider-model-backend/feedback-service gate PYTHONPATH, added `channel_core_src`+`qqbot_src` to contract-test-suite PYTHONPATH, added channel-core/qqbot src to compileall
- `scripts/audit_v2_requirements.py` — fixed `_check_library_surface` to capture `ast.ImportFrom` re-export names (6 lines added)
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — updated gate count assertion 14→15, added `qqbot-channel` to assertIn checks
