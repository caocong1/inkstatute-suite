---
phase: 43
slug: qqbot-channel-loop
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-04
---

# Phase 43 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (existing) |
| **Config files** | `packages/channel-core/pyproject.toml` (new — Wave 1), `packages/channels/qqbot/pyproject.toml` (new — Wave 1) |
| **Quick run (channel-core)** | `PYTHONPATH=packages/channel-core/src python -m unittest discover -s packages/channel-core/tests -v` |
| **Quick run (qqbot)** | `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/channels/qqbot/tests -v` |
| **Quick run (wecom backward compat)** | `PYTHONPATH=services/wecom-service/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src python -m unittest discover -s services/wecom-service/tests -v` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~90 seconds (15 gates including new qqbot-channel gate) |

---

## Sampling Rate

- **After every task commit:** Run quick command (channel-core or qqbot tests only)
- **After every plan wave:** Run `python scripts/run_v2_gates.py` (all gates)
- **Before `/gsd-verify-work`:** Full suite must be green (all 15 gates)
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 43-01-01 | 01 | 1 | QQBOT-01 | — | channel-core package structure + extracted idempotency/delivery_guard/active_task_router/output_policy/owned_notices with unit tests | unit | `PYTHONPATH=packages/channel-core/src python -m unittest discover -s packages/channel-core/tests -v` | ❌ W0 | ⬜ pending |
| 43-01-02 | 01 | 1 | QQBOT-01 | — | wecom-service backward compat: thin re-export shims, existing wecom-service tests pass unchanged | unit | `PYTHONPATH=services/wecom-service/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src python -m unittest discover -s services/wecom-service/tests -v` | ✅ | ⬜ pending |
| 43-01-03 | 01 | 1 | QQBOT-02 | — | QQBot channel adapter package structure + QQBotChannelAdapter implements 6 ChannelAdapter methods + QQBotChannelConfig defaults disabled | unit | `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/channels/qqbot/tests -p "test_qqbot_channel_adapter.py" -v` | ❌ W0 | ⬜ pending |
| 43-01-04 | 01 | 1 | QQBOT-01 | — | No wecom_service import: QQBot adapter source does not contain `wecom_service` import | unit | `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages.channels.qqbot.tests.test_no_wecom_import -v` | ❌ W0 | ⬜ pending |
| 43-02-01 | 02 | 2 | QQBOT-03 | — | Fixture-driven QQBot loop proof: receive → ACK → adapter (normalize) → reply (text deliver) → card (card deliver) → feedback (FeedbackEvent) end-to-end | unit | `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages.channels.qqbot.tests.test_qqbot_channel_loop -v` | ❌ W0 | ⬜ pending |
| 43-02-02 | 02 | 2 | QQBOT-03 | — | Idempotency: repeat verify_and_ack + normalize_inbound with same raw → same idempotency_key and turn_id (idempotent) | unit | `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages.channels.qqbot.tests.test_qqbot_idempotency -v` | ❌ W0 | ⬜ pending |
| 43-02-03 | 02 | 2 | QQBOT-04 | — | FeedbackEvent.source maps to existing CARD_BUTTON enum value (no new enum values added) | unit | `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages.channels.qqbot.tests.test_feedback_source_mapping -v` | ❌ W0 | ⬜ pending |
| 43-03-01 | 03 | 3 | QQBOT-04, SAFETY-04 | — | qqbot_channel_enabled defaults to False in RuntimeFeatureFlags + QQBot adapter refuses when flag off | unit | `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages.channels.qqbot.tests.test_feature_flag -v` | ❌ W0 | ⬜ pending |
| 43-03-02 | 03 | 3 | GATE-01 | — | V2 gate integration: new qqbot-channel gate + channel-core in wecom-service/contract-test-suite PYTHONPATH + compileall update (14→15 gates) | integration | `python scripts/run_v2_gates.py` | ❌ W0 | ⬜ pending |
| 43-03-03 | 03 | 3 | SAFETY-02, SAFETY-06 | — | Contract freeze not violated: ChannelAdapter 6 methods, FeedbackSource 4 values, no platform-contract edits, no protocols.py edits, no feature_flags.py edits | unit | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/contract-test-suite/tests/test_contract_count_freeze.py packages/contract-test-suite/tests/test_contract_freeze.py -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 package structure is created as the first step of Plan 43-01 Task 01. The following files are created by Wave 1 tasks:

- [ ] `packages/channel-core/pyproject.toml` — package definition (Plan 43-01 Task 01)
- [ ] `packages/channel-core/src/channel_core/__init__.py` — package init (Plan 43-01 Task 01)
- [ ] `packages/channel-core/src/channel_core/idempotency.py` — generic idempotency (Plan 43-01 Task 01)
- [ ] `packages/channel-core/src/channel_core/delivery_guard.py` — delivery guard (Plan 43-01 Task 01)
- [ ] `packages/channel-core/src/channel_core/active_task_router.py` — active task router (Plan 43-01 Task 01)
- [ ] `packages/channel-core/src/channel_core/output_policy.py` — output policy (Plan 43-01 Task 01)
- [ ] `packages/channel-core/src/channel_core/owned_notices.py` — owned notices (Plan 43-01 Task 01)
- [ ] `packages/channel-core/tests/test_*.py` — unit tests for each module (Plan 43-01 Task 01)
- [ ] `packages/channels/qqbot/pyproject.toml` — package definition (Plan 43-01 Task 03)
- [ ] `packages/channels/qqbot/src/inkstatute_channels_qqbot/__init__.py` — package init (Plan 43-01 Task 03)
- [ ] `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` — QQBotChannelAdapter (Plan 43-01 Task 03)
- [ ] `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` — QQBotChannelConfig (Plan 43-01 Task 03)
- [ ] `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py` — adapter tests (Plan 43-01 Task 03)
- [ ] `packages/channels/qqbot/tests/test_no_wecom_import.py` — import boundary test (Plan 43-01 Task 04)
- [ ] `packages/channels/qqbot/fixtures/qqbot_channel_loop.json` — loop proof fixture (Plan 43-02 Task 01)
- [ ] `packages/channels/qqbot/tests/test_qqbot_channel_loop.py` — loop proof test (Plan 43-02 Task 01)
- [ ] `packages/channels/qqbot/tests/test_qqbot_idempotency.py` — idempotency test (Plan 43-02 Task 02)
- [ ] `packages/channels/qqbot/tests/test_feedback_source_mapping.py` — FeedbackEvent.source mapping test (Plan 43-02 Task 03)
- [ ] `packages/channels/qqbot/tests/test_feature_flag.py` — feature flag default-off test (Plan 43-03 Task 01)

*No separate Wave 0 task needed — package structure is created inline by Plan 43-01 Task 01. Existing infrastructure (unittest, run_v2_gates.py) covers framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification — fixture-driven adapter tests with no real QQBot API or network calls required. The QQBot adapter performs no network IO (fixture-only, same pattern as web_sse adapter).*

---

## Backward Compatibility Verification

After channel-core extraction, the following wecom-service tests must pass unchanged:

- `services/wecom-service/tests/test_idempotency.py` — via re-export shim
- `services/wecom-service/tests/test_delivery_guard.py` — via re-export shim
- `services/wecom-service/tests/test_active_task_router.py` — via re-export shim
- `services/wecom-service/tests/test_output_policy.py` — via re-export shim
- `services/wecom-service/tests/test_normalization.py` — uses idempotency + protocol (indirect)
- `services/wecom-service/tests/test_ingress_runtime.py` — uses active_task_router (indirect)
- `services/wecom-service/tests/test_session_runtime.py` — uses output_policy (indirect)

The wecom-service gate (`python scripts/run_v2_gates.py` → wecom-service gate) must remain green after Wave 1.

---

## Validation Sign-Off

- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-04
