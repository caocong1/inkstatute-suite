---
phase: 104
plan: 02
title: Retire Legacy Channels + Services
status: complete
created: 2026-08-08
---

# Plan 104-02 Summary: Retire Legacy Channels + Services

## Objective

Retire `packages/channels/web_sse/`, `services/lawyer-web-chat/`, and `services/hermes-contract-layer/`. Their functionality is replaced by `services/gateway/` and `packages/acp-client/`. Remove corresponding gates. Update all external references.

## What Was Done

### Directories Deleted

- `packages/channels/web_sse/` — SSE channel adapter (replaced by `services/gateway`)
- `services/lawyer-web-chat/` — legacy HTTP chat service (replaced by `services/gateway`)
- `services/hermes-contract-layer/` — Hermes contract layer (replaced by `packages/acp-client`)

### Gates Removed (3)

- `web-sse-channel` gate
- `lawyer-web-chat` gate
- `hermes-contract-layer` gate

Gate count: 37 → 34

### Files Modified

1. **`services/gateway/src/gateway/sse.py`** — Inlined `encode_sse_event` function (previously imported from `inkstatute_channels_web_sse`). The gateway is now self-contained for SSE encoding.
2. **`services/gateway/src/gateway/__init__.py`** — Updated docstring to reflect self-contained SSE encoding.
3. **`services/gateway/tests/test_sse.py`** — Changed import from `inkstatute_channels_web_sse` to `gateway.sse`.
4. **`services/gateway/tests/test_sse_replay.py`** — Changed import from `inkstatute_channels_web_sse` to `gateway.sse`.
5. **`services/gateway/tests/test_verify_and_ack_optional.py`** — Removed `WebSseChannelAdapter` import and test (web_sse channel retired).
6. **`services/gateway/tests/test_integration.py`** — Removed `test_success_criteria_5_lawyer_web_chat_deprecated` and `test_success_criteria_6_verify_and_ack_optional` tests (services retired). Updated gate count from 38 to 34.
7. **`packages/contract-test-suite/src/contract_test_suite/boundary_checks.py`** — Removed `hermes_contract_layer` from `FORBIDDEN_IMPORT_ROOTS` and `PLATFORM_FORBIDDEN_TEXT`. Removed bundle manifest check in `assert_thin_layer_scope` (hermes-contract-layer deleted).
8. **`packages/contract-test-suite/tests/test_phase55_wecom_service_loop.py`** — Inlined `build_hermes_adapter_manifest` function (previously imported from `hermes_contract_layer.adapter_manifest`). Removed `hermes-contract-layer/src` from `sys.path`.
9. **`packages/contract-test-suite/tests/test_phase5_wecom_loop.py`** — Changed import from `hermes_contract_layer.wecom_validation` to `contract_test_suite.wecom_validation` (module moved). Removed `hermes-contract-layer/src` from `sys.path`.
10. **`packages/contract-test-suite/tests/test_phase12_channel_client_surface.py`** — Updated `WEB_SSE_FIXTURE` path from `packages/channels/web_sse/fixtures/` to `packages/contract-test-suite/fixtures/` (fixture moved before deletion).
11. **`packages/platform-runtime/src/platform_runtime/feature_flags.py`** — Added deprecation comments for `web_sse_channel_enabled` and `lawyer_web_chat_enabled` flags (kept for backward compatibility).
12. **`scripts/audit_v2_requirements.py`** — Updated `HERMES_SRC` to `ACP_CLIENT_SRC` and `ACP_EVENT_BRIDGE_SRC`. Updated HERMES-01 probes to check ACP client adapter instead of hermes-contract-layer. Updated OBSERVE-01 level 3 probe to check acp-event-bridge instead of hermes hook.py. Updated ADAPTER-01 evidence hints.
13. **`scripts/run_v2_gates.py`** — Removed 3 gate definitions, removed `hermes_src`, `web_sse_src`, `lawyer_web_chat_src` variable definitions, removed retired paths from gateway and contract-test-suite gates' pythonpath, removed retired paths from compileall gate.
14. **`packages/contract-test-suite/tests/test_audit_v2_requirements.py`** — Updated gate count from 37 to 34, removed references to retired gates (`web-sse-channel`, `lawyer-web-chat`).

### Files Created

1. **`packages/agent-core/tests/test_phase104_service_retirement.py`** — 9 tests verifying:
   - `test_no_web_sse_channel_directory_exists`
   - `test_no_lawyer_web_chat_directory_exists`
   - `test_no_hermes_contract_layer_directory_exists`
   - `test_web_sse_channel_gate_removed`
   - `test_lawyer_web_chat_gate_removed`
   - `test_hermes_contract_layer_gate_removed`
   - `test_no_imports_from_retired_services`
   - `test_gateway_sse_is_self_contained`
   - `test_feature_flags_kept_but_deprecated`

### Files Moved

1. **`packages/channels/web_sse/fixtures/multichannel_web_sse.json`** → **`packages/contract-test-suite/fixtures/multichannel_web_sse.json`** (fixture preserved for Phase 12 tests)
2. **`services/hermes-contract-layer/src/hermes_contract_layer/wecom_validation.py`** → **`packages/contract-test-suite/src/contract_test_suite/wecom_validation.py`** (module preserved for Phase 5 WeCom loop tests)

## Verification

- **Baseline**: 37 gates, all green (exit code 0)
- **After changes**: 34 gates, all green (exit code 0)
- **Agent-core tests**: 900 passed, 5 skipped (including 9 new Phase 104-02 tests)
- **No broken imports**: `test_no_imports_from_retired_services` confirms no Python files import from `inkstatute_channels_web_sse`, `lawyer_web_chat`, or `hermes_contract_layer`
- **Gateway tests pass**: 210 tests passed (2 skipped) — gateway is self-contained without web_sse dependency
- **V2 acceptance traceability**: PASS — no requirements classified as gap (HERMES-01 probes updated to check ACP client)

## Key Decisions

1. **`encode_sse_event` inlined into gateway** rather than creating a shared utility package — the function is small (60 lines) and the gateway is the sole consumer after web_sse retirement.
2. **`wecom_validation.py` moved to contract-test-suite** rather than inlined into the test file — the module is 210 lines with multiple helper functions and dataclasses, and it already depends on `contract_test_suite.event_stream_replay`.
3. **`build_hermes_adapter_manifest` inlined into test file** — it's a simple 52-line dict builder, not worth a separate module.
4. **Feature flags kept but deprecated** — `web_sse_channel_enabled` and `lawyer_web_chat_enabled` remain in `RuntimeFeatureFlags` for backward compatibility with existing config, but are marked deprecated with comments.
5. **Audit script probes updated** to point to ACP client/event-bridge equivalents — HERMES-01 now checks `ACPBackendAdapter`/`ACPBackendConfig` in acp-client, OBSERVE-01 now checks privacy scan exports in acp-event-bridge.
