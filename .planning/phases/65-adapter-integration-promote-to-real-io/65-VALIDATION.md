---
phase: 65
slug: adapter-integration-promote-to-real-io
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 65 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (stdlib; asyncio.run for async Protocol methods) |
| **Config file** | `packages/channels/qqbot/pyproject.toml` (existing; `dependencies = []`) |
| **Quick run command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest packages.channels.qqbot.tests.test_adapter_two_tier_ack packages.channels.qqbot.tests.test_adapter_real_io packages.channels.qqbot.tests.test_feature_flag -v` |
| **Full suite command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest discover -s packages/channels/qqbot/tests -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command (two-tier ACK + real-IO + feature flag)
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 65-W0-01 | 01 | 0 | INGRESS-06 | T-65-01 | Wave 0: RED stubs for op=12 metadata + interaction PUT Fake path | unit | `test -f packages/channels/qqbot/tests/test_adapter_two_tier_ack.py` | ❌ W0 | ⬜ pending |
| 65-W0-02 | 01 | 0 | ADAPTER-01 | T-65-02 | Wave 0: RED stubs for flag-on Fake real-IO across 6 Protocol methods | unit | `test -f packages/channels/qqbot/tests/test_adapter_real_io.py` | ❌ W0 | ⬜ pending |
| 65-01-01 | 01 | 1 | INGRESS-06 | T-65-01 | verified message ACK includes `http_callback_ack_body={"op":12}` | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_adapter_two_tier_ack -v` | ❌ W0 | ⬜ pending |
| 65-01-02 | 01 | 1 | INGRESS-06 | T-65-03 | INTERACTION_CREATE sets interaction_ack_required + PUT `/interactions/{id}` `{code:0}` when live | unit | same as 65-01-01 | ❌ W0 | ⬜ pending |
| 65-01-03 | 01 | 1 | INGRESS-06 / ADAPTER-02 | T-65-04 | flag/config off: no PUT call; fixture metadata `network_io=False` | unit | same as 65-01-01 | ❌ W0 | ⬜ pending |
| 65-02-01 | 02 | 2 | ADAPTER-01 | T-65-02 | capabilities/health/normalize/deliver/verify reflect live vs fixture metadata honestly | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_adapter_real_io -v` | ❌ W0 | ⬜ pending |
| 65-02-02 | 02 | 2 | ADAPTER-01 | T-65-05 | deliver text/card/file still uses sender; live only when enabled+token+transport | unit | same as 65-02-01 | ❌ W0 | ⬜ pending |
| 65-02-03 | 02 | 2 | ADAPTER-02 | T-65-04 | `RuntimeFeatureFlags.qqbot_channel_enabled` and `QQBotChannelConfig.enabled` default False; loop CI path unchanged | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_feature_flag packages.channels.qqbot.tests.test_qqbot_channel_loop -v` | ✅ extend | ⬜ pending |
| 65-03-01 | 03 | 3 | ADAPTER-03 | T-65-06 | no wecom_service imports; sender/adapter still covered by AST ban | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_no_wecom_import -v` | ✅ | ⬜ pending |
| 65-03-02 | 03 | 3 | ADAPTER-04 | T-65-07 | ChannelAdapter still 6 methods; platform-contract/channel-core untouched; deps=[] | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_contract_freeze_not_violated packages.channels.qqbot.tests.test_v1_8_safety_baseline -v` | ✅ | ⬜ pending |
| 65-03-03 | 03 | 3 | ADAPTER-01 | T-65-08 | Ack/Delivery metadata never contains access_token / Authorization / raw secrets | unit | same as 65-02-01 | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/channels/qqbot/tests/test_adapter_two_tier_ack.py` — op=12 body metadata; interaction PUT Fake URL/body; flag-off skips PUT (RED before adapter ACK changes)
- [ ] `packages/channels/qqbot/tests/test_adapter_real_io.py` — all 6 Protocol methods under enabled+FakeToken+FakeTransport; fixture path when disabled
- [ ] Extend `FakeMessageTransport` (or twin) with `put_json` coverage once sender gains PUT
- [ ] Keep `test_qqbot_channel_loop.py` green: default path `network_io=False`
- [ ] Privacy assertions: no token/Authorization/raw payload keys in AckResponse/DeliveryResult metadata

*Existing unittest infrastructure in `packages/channels/qqbot/` covers framework setup.*

---

## Manual-Only Verifications

*No live QQ network required for Phase 65 CI. Live webhook + button loading-state confirmation is Phase 67 human gate.*

Optional human gate (not blocking): with flag on and real credentials, click a feedback keyboard button and confirm QQ client loading clears after PUT ACK; confirm webhook responses include `{"op":12}`.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** researcher drafted 2026-07-09 — planner should map Wave 0 into 65-0x-PLAN.md
