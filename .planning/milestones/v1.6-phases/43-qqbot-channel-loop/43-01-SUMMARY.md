---
phase: 43
plan: 43-01
title: "Extract Channel-Generic Logic into channel-core Shared Package + QQBot Channel Adapter Structure"
wave: 1
requirements:
  - QQBOT-01
  - QQBOT-02
status: complete
autonomous: true
---

# Plan 43-01 — Execution Summary

## Plan ID

**43-01** — Extract Channel-Generic Logic into channel-core Shared Package + QQBot Channel Adapter Structure

## Tasks Completed

| Task | Description | Commit Hash |
|------|-------------|-------------|
| 43-01-01 | Create `packages/channel-core/` shared package with 5 extracted modules (idempotency, delivery_guard, active_task_router, output_policy, owned_notices) + unit tests | `b2d19b9` |
| 43-01-02 | Convert wecom-service modules into thin re-export shims over `channel_core` with WeCom-specific defaults | `879f429` |
| 43-01-03 | Create `packages/channels/qqbot/` package with `QQBotChannelAdapter` implementing all 6 ChannelAdapter Protocol methods + unit tests | `33efac1` |
| 43-01-04 | Create `test_no_wecom_import.py` verifying QQBot adapter does NOT import from `wecom_service` (AST + string check) | `8722403` |

## Tests Added

| Test File | Tests | Status |
|-----------|-------|--------|
| `packages/channel-core/tests/test_idempotency.py` | 12 | ✅ pass |
| `packages/channel-core/tests/test_delivery_guard.py` | 4 | ✅ pass |
| `packages/channel-core/tests/test_active_task_router.py` | 8 | ✅ pass |
| `packages/channel-core/tests/test_output_policy.py` | 8 | ✅ pass |
| `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py` | 14 | ✅ pass |
| `packages/channels/qqbot/tests/test_no_wecom_import.py` | 5 | ✅ pass |
| **Total new tests** | **51** | **✅ all pass** |

## Tests Passed (Backward Compatibility)

| Test Suite | Tests | Status |
|------------|-------|--------|
| `services/wecom-service/tests/` (all existing) | 72 | ✅ pass unchanged |

## Test Commands Used

- **channel-core:** `PYTHONPATH=packages/channel-core/src python -m unittest discover -s packages/channel-core/tests -v` → 32 tests, 0 failures
- **wecom backward compat:** `PYTHONPATH=services/wecom-service/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src python -m unittest discover -s services/wecom-service/tests -v` → 72 tests, 0 failures
- **qqbot adapter:** `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/channels/qqbot/tests -p "test_qqbot_channel_adapter.py" -v` → 14 tests, 0 failures
- **no wecom import:** `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages.channels.qqbot.tests.test_no_wecom_import -v` → 5 tests, 0 failures

## Requirements Satisfied

### QQBOT-01: Channel-generic logic extracted into shared package; QQBot does not import from wecom_service

- ✅ `packages/channel-core/` created with 5 channel-generic modules extracted from wecom-service
- ✅ `idempotency.py` — generic `channel_idempotency_key` with parameterized `channel_prefix`, `stable_fields`, `fallback_field_aliases`
- ✅ `delivery_guard.py` — pure extraction (no channel-specific aspects)
- ✅ `active_task_router.py` — parameterized `event_name` (default: `"channel_active_task_route"`, WeCom compat: `"wecom_active_task_route"`)
- ✅ `output_policy.py` — parameterized `policy_name` (default: `"inkstatute_channel_output_boundary"`) and `replacement_owner` (default: `"inkstatute_channel_service"`)
- ✅ `owned_notices.py` — pure extraction (InkStatute-owned, channel-neutral)
- ✅ wecom-service modules converted to thin re-export shims with WeCom-specific defaults
- ✅ All 72 existing wecom-service tests pass unchanged
- ✅ QQBot adapter imports from `channel_core`, NOT from `wecom_service` (verified by AST + string check)

### QQBOT-02: QQBot channel adapter implements ChannelAdapter Protocol (6 methods)

- ✅ `QQBotChannelAdapter` implements all 6 ChannelAdapter Protocol methods:
  1. `channel_id()` → returns `"qqbot"`
  2. `capabilities()` → `ChannelCapabilitySet` with supports_text=True, supports_cards=True, supports_files=False, supports_streaming=False
  3. `async verify_and_ack(raw: RawInbound) -> AckResponse` — accepts when enabled, rejects with 503 when disabled
  4. `async normalize_inbound(raw: RawInbound) -> InboundNormalized` — message → AgentTurn (channel="qqbot"), feedback → FeedbackEvent (source="card_button")
  5. `async deliver(delivery: ChannelDelivery) -> DeliveryResult` — applies output_policy, blocks internal notices, supports text and card delivery
  6. `async health() -> ComponentHealth` — reports ok=True when enabled, component_id="qqbot-channel"
- ✅ `QQBotChannelConfig` defaults to `enabled=False`
- ✅ QQBot feedback maps to existing `FeedbackSource.CARD_BUTTON` ("card_button") — no new enum values added
- ✅ Fixture-only — no network IO

## Contract Freeze Compliance

- ✅ No changes to `packages/platform-contract/`
- ✅ No changes to `packages/platform-runtime/src/platform_runtime/protocols.py`
- ✅ No changes to `packages/platform-runtime/src/platform_runtime/feature_flags.py`
- ✅ ChannelAdapter Protocol remains 6 methods (frozen)
- ✅ `Channel.QQBOT = "qqbot"` already existed (not modified)
- ✅ `qqbot_channel_enabled` feature flag already existed with default `False` (not modified)
- ✅ `FeedbackSource` enum not modified (4 values preserved)

## Files Created

- `packages/channel-core/pyproject.toml`
- `packages/channel-core/README.md`
- `packages/channel-core/src/channel_core/__init__.py`
- `packages/channel-core/src/channel_core/idempotency.py`
- `packages/channel-core/src/channel_core/delivery_guard.py`
- `packages/channel-core/src/channel_core/active_task_router.py`
- `packages/channel-core/src/channel_core/output_policy.py`
- `packages/channel-core/src/channel_core/owned_notices.py`
- `packages/channel-core/tests/__init__.py`
- `packages/channel-core/tests/test_idempotency.py`
- `packages/channel-core/tests/test_delivery_guard.py`
- `packages/channel-core/tests/test_active_task_router.py`
- `packages/channel-core/tests/test_output_policy.py`
- `packages/channels/qqbot/pyproject.toml`
- `packages/channels/qqbot/README.md`
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/__init__.py`
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py`
- `packages/channels/qqbot/tests/__init__.py`
- `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`
- `packages/channels/qqbot/tests/test_no_wecom_import.py`

## Files Modified

- `services/wecom-service/src/wecom_service/idempotency.py` — thin shim over `channel_core.idempotency`
- `services/wecom-service/src/wecom_service/delivery_guard.py` — thin shim over `channel_core.delivery_guard`
- `services/wecom-service/src/wecom_service/active_task_router.py` — thin shim with WeCom event name default
- `services/wecom-service/src/wecom_service/output_policy.py` — thin shim with WeCom policy name + replacement_owner
- `services/wecom-service/src/wecom_service/owned_notices.py` — thin shim over `channel_core.owned_notices`
