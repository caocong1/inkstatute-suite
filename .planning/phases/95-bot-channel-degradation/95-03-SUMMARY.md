---
phase: 95
plan: 03
title: QQ Bot Full Migration — Gateway Client + Event Consumer + Keyboard Cards + Media Delivery
wave: 2
requirements:
  - BOT-01
  - BOT-02
  - BOT-03
commits:
  - e974753: feat(95-03): create gateway_client.py for QQ bot service
  - 8aa4b99: feat(95-03): create event_consumer.py for QQ bot service
  - 8e3c45b: test(95-03): create bot_events.json fixture + FakeGatewayClient/FakeQQBotAdapter + test_gateway_client.py (17 tests) + test_event_consumer.py (21 tests)
  - ca5995f: feat(95-03): add optional gateway_client field to QQBotWiredRuntime + gateway_config param to build_qqbot_wired_runtime
  - 0ff0a16: feat(95-03): add _compose_via_gateway to webhook.py — Gateway consumer path in post-ACK composition
  - 87cba1a: feat(95-03): read Gateway config from env vars in __main__.py + update __init__.py exports + create test_webhook_gateway_migration.py (15 tests)
  - 186b237: fix(95-03): remove forbidden body markers from 95-02-SUMMARY.md to pass privacy gate
---

# Plan 95-03 Summary: QQ Bot Full Migration — Gateway Consumer Path in Post-ACK Composition

## Goal

Switch the QQ bot post-ACK composition path from direct agent calls (`runtime.create_run()` / `backend.get_run()`) to the Gateway event consumer. The `run_post_ack_composition()` function in `webhook.py` now calls `QQBotEventConsumer.consume_and_deliver()` when `wired.gateway_client` is available. The `wiring.py` injects a `GatewayClient` when `gateway_config` is provided. The `__main__.py` reads Gateway config from env vars.

After this plan:
- QQ webhook → verify_and_ack (ED25519, op=13) → post-ACK → GatewayClient.create_run → SSE stream → aggregate_events → adapter.deliver
- No `runtime.create_run()` or `backend.get_run()` calls in the gateway path (BOT-02)
- All existing QQ bot tests stay green (ED25519, op=13, webhook port, idempotency preserved — BOT-03)
- The `ingress_runtime.py` and `session_runtime.py` files are kept but no longer called from the gateway path

## What Was Done

### Task 95-03-01: gateway_client.py (commit e974753)
- Created `services/qqbot-service/src/qqbot_service/gateway_client.py`
- `GatewayClientConfig`: frozen slotted dataclass (base_url, bearer_token, tenant_id, timeout_seconds)
- `GatewayClient`: create_session, create_run, stream_events (SSE), submit_elicitation, submit_approval, download_artifact, submit_feedback
- `_parse_sse_frame`: parses SSE frames (id/event/data lines, multi-line data concatenation)
- `_build_headers`: Bearer token auth + Content-Type on all methods
- `GatewayClientError`: custom exception with status, code, message fields
- Stdlib only (urllib.request, http.client, json) — no external deps, no gateway package imports, no WeCom imports

### Task 95-03-02: event_consumer.py (commit 8aa4b99)
- Created `services/qqbot-service/src/qqbot_service/event_consumer.py`
- `QQBotEventConsumer`: Gateway run → SSE stream → aggregate_events → adapter.deliver
- `consume_and_deliver`: end-to-end async entry point (create session/run, stream, aggregate, deliver)
- QQ-specific delivery mapping:
  - `final_message` → `ChannelDelivery(delivery_type="text")` with scene, user_openid, group_openid, msg_id, msg_seq metadata
  - `cards` → `ChannelDelivery(delivery_type="card")` — QQ adapter maps to `build_feedback_keyboard_envelope()`
  - `files` → `ChannelDelivery(delivery_type="file")` with injectable media_uploader (None=skip in CI)
  - `error_prompt` → `ChannelDelivery(delivery_type="text")` with failure message
- `_build_delivery_metadata`: builds common metadata dict with scene, user_openid, group_openid, msg_id, msg_seq, received_at, reply_count
- `_should_send_intermediate`: FOLD for first tool_call, FIRST_THEN_SILENT for first plan/phase
- `solution_to_dict`: SolutionBinding → dict for Gateway create_run body
- `is_terminal_event`: detects run.state_changed with succeeded/failed/cancelled
- Output boundary enforced via `apply_output_policy()` (third enforcement layer)
- No direct agent/backend calls — Gateway HTTP client only (BOT-02 compliance)
- No WeCom imports (cross-contamination check)

### Task 95-03-03: Test fixtures + fakes + test files (commit 8e3c45b)
- Created `services/qqbot-service/tests/fixtures/bot_events.json`: 11 events covering full lifecycle (9 event types)
- Created `services/qqbot-service/tests/fakes.py`: FakeGatewayClient + FakeQQBotAdapter
- Created `services/qqbot-service/tests/test_gateway_client.py`: 17 unit tests (config, headers, SSE parsing, error handling, mocked HTTP, no gateway/wecom imports)
- Created `services/qqbot-service/tests/test_event_consumer.py`: 21 integration tests (final message, intermediate prompts, card delivery, file delivery, error prompt, citations, session reuse, evidence dict, thought.delta discarded, session.started silent, output boundary, full lifecycle, no direct agent calls, aggregate_events integration, progress interval, scene metadata, no wecom import, idempotent delivery IDs)
- All tests network-free

### Task 95-03-04: wiring.py — add gateway_client field (commit ca5995f)
- Added `gateway_client: GatewayClient | None = None` field to `QQBotWiredRuntime` dataclass (after `runtime`, before `live_io_ready`)
- Added `gateway_config: GatewayClientConfig | None = None` parameter to `build_qqbot_wired_runtime()`
- When `gateway_config` is provided, a `GatewayClient` is constructed and stored in `QQBotWiredRuntime.gateway_client`
- When `gateway_config` is None, `gateway_client` is None (old path, backward compat)
- Imported `GatewayClient`, `GatewayClientConfig` from `.gateway_client`
- The `backend` parameter, `DefaultRunRuntime` construction, live-IO injection, and dual-knob mapping are unchanged
- All 121 existing tests pass unchanged

### Task 95-03-05: webhook.py — _compose_via_gateway (commit 0ff0a16)
- Added gateway branch in `run_post_ack_composition()`: when `wired.gateway_client is not None and normalized.message is not None`, calls `_compose_via_gateway()` instead of the old ingress path
- The feedback branch runs BEFORE the gateway branch (unchanged)
- Created `_compose_via_gateway()` function that:
  - Extracts `AgentTurn` from `normalized.message` and serializes to dict via `_agent_turn_to_dict()`
  - Extracts QQ-specific scene metadata (scene, user_openid, group_openid, msg_id, msg_seq) via `_extract_qq_scene_metadata()`
  - Constructs `QQBotEventConsumer` with `wired.gateway_client`, `wired.adapter`, and solution binding
  - Calls `consumer.consume_and_deliver()` and returns evidence with `gateway_path=True`
- Created `_agent_turn_to_dict()` helper that serializes `AgentTurn` fields
- Created `_extract_qq_scene_metadata()` helper that extracts QQ scene metadata from normalized inbound
- Imported `QQBotEventConsumer` from `.event_consumer`, `GatewayClient` from `.gateway_client`, `AgentTurn` from `platform_contract.events`
- The old ingress path remains as fallback when `gateway_client` is None
- `handle_qqbot_webhook_request()` is unchanged — still ACK-first, still schedules post-ACK
- No `runtime.create_run()` or `backend.get_run()` in the gateway path (BOT-02)

### Task 95-03-06: __main__.py + __init__.py + test_webhook_gateway_migration.py (commit 87cba1a)
- `__main__.py` reads `INKSTATUTE_GATEWAY_URL` (default: `http://127.0.0.1:8081`)
- Reads `INKSTATUTE_GATEWAY_BEARER_TOKEN` (default: empty — when empty, old path used)
- Reads `INKSTATUTE_GATEWAY_TENANT_ID` (default: `default-tenant`)
- When bearer token is non-empty, constructs `GatewayClientConfig` and passes to `build_qqbot_wired_runtime()` as `gateway_config`
- Logs `"QQBot service: Gateway consumer mode enabled (url={gateway_url})"` when Gateway path is active
- `FakeBackendAdapter` still used as default backend (unchanged)
- Updated `__init__.py` to export `GatewayClient`, `GatewayClientConfig`, `GatewayClientError`, `QQBotEventConsumer`, `is_terminal_event`, `solution_to_dict` (additive)
- Created `test_webhook_gateway_migration.py`: 15 tests covering the new Gateway consumer path:
  1. `test_post_ack_uses_gateway_when_available` — gateway path used when gateway_client is set
  2. `test_post_ack_falls_back_when_no_gateway` — old path used when gateway_client is None
  3. `test_post_ack_gateway_delivers_text` — final message delivered as text
  4. `test_post_ack_gateway_delivers_card` — elicitation delivered as QQ keyboard card
  5. `test_post_ack_gateway_intermediate_prompt` — tool_call.started produces "正在检索法规…"
  6. `test_post_ack_gateway_feedback_branch_unchanged` — feedback branch runs regardless of gateway_client
  7. `test_post_ack_gateway_no_direct_agent_calls` — source inspection: no runtime.create_run or backend.get_run
  8. `test_post_ack_gateway_scene_metadata` — deliveries include QQ scene metadata (c2c, user_openid, msg_id)
  9. `test_post_ack_gateway_solution_binding` — SolutionBinding forwarded to consumer
  10. `test_ack_first_pattern_preserved` — ACK returned immediately (200 with op=12)
  11. `test_ed25519_verification_preserved` — channel disabled → 503
  12. `test_op13_validation_challenge_preserved` — op=13 challenge handled before gateway path
  13. `test_idempotency_preserved` — duplicate callbacks handled
  14. `test_full_flow_gateway_tracer` — end-to-end: webhook → verify_and_ack → post-ACK → Gateway → SSE → deliver
  15. `test_no_wecom_import_in_gateway_path` — verify _compose_via_gateway and event_consumer don't import from WeCom
- Created `DeliverRecordingAdapter` wrapper that delegates `verify_and_ack` and `normalize_inbound` to the real adapter but records `deliver()` calls
- All tests network-free (FakeGatewayClient + DeliverRecordingAdapter + signed QQ envelopes)

### Task 95-03-07: Verification + privacy gate fix (commit 186b237)
- Verified no `runtime.create_run` or `backend.get_run` in `event_consumer.py`
- Verified no `from gateway` or `import gateway` in `gateway_client.py`
- Verified no `wecom_service` or `inkstatute_channels_wecom` in `event_consumer.py` or `gateway_client.py`
- Verified `_compose_via_gateway` has no direct agent calls
- Fixed privacy gate failure in `95-02-SUMMARY.md` (removed forbidden body markers)
- All 34 gates green

## Acceptance Criteria Results

| Criterion | Result |
|-----------|--------|
| `gateway_client.py` created with GatewayClient, GatewayClientConfig, GatewayClientError | PASS |
| `event_consumer.py` created with QQBotEventConsumer | PASS |
| GatewayClient uses only stdlib HTTP (urllib.request, http.client) | PASS |
| GatewayClient includes Bearer token auth on all methods | PASS |
| GatewayClient.stream_events() parses SSE frames correctly | PASS |
| QQBotEventConsumer creates Gateway runs via HTTP, not runtime.create_run() | PASS |
| QQBotEventConsumer consumes SSE stream and collects events | PASS |
| QQBotEventConsumer sends intermediate prompts during stream | PASS |
| QQBotEventConsumer calls aggregate_events() at terminal state | PASS |
| QQBotEventConsumer maps BotDelivery.cards to QQ keyboard card deliveries | PASS |
| QQBotEventConsumer maps BotDelivery.files to QQ rich media deliveries | PASS |
| QQBotEventConsumer passes QQ scene metadata (scene, user_openid, group_openid, msg_id, msg_seq) | PASS |
| Output boundary enforced (apply_output_policy third layer) | PASS |
| No direct agent/backend calls in event_consumer.py (BOT-02) | PASS |
| `QQBotWiredRuntime` has `gateway_client: GatewayClient \| None = None` field | PASS |
| `build_qqbot_wired_runtime(backend=fake_backend)` works without `gateway_config` (backward compat) | PASS |
| `build_qqbot_wired_runtime(backend=fake_backend, gateway_config=...)` creates `gateway_client` not None | PASS |
| `run_post_ack_composition()` with `gateway_client is not None` calls `_compose_via_gateway()` | PASS |
| `run_post_ack_composition()` with `gateway_client is None` uses old ingress path | PASS |
| Feedback branch unchanged and runs before gateway branch | PASS |
| `handle_qqbot_webhook_request()` unchanged — ACK-first, ED25519, op=13 | PASS |
| `_compose_via_gateway()` calls `QQBotEventConsumer.consume_and_deliver()` | PASS |
| No `runtime.create_run()` or `backend.get_run()` in gateway path (BOT-02) | PASS |
| `__main__.py` reads `INKSTATUTE_GATEWAY_URL`, `INKSTATUTE_GATEWAY_BEARER_TOKEN`, `INKSTATUTE_GATEWAY_TENANT_ID` | PASS |
| When bearer token is set, `gateway_config` is passed to `build_qqbot_wired_runtime()` | PASS |
| When bearer token is empty, old path is used | PASS |
| `FakeBackendAdapter` still used as default backend | PASS |
| `test_gateway_client.py` has 16+ tests | PASS (17) |
| `test_event_consumer.py` has 18+ tests | PASS (21) |
| `test_webhook_gateway_migration.py` has 14+ tests | PASS (15) |
| ED25519 signature verification preserved | PASS |
| op=13 validation challenge handling preserved | PASS |
| Passive reply window checking in adapter.deliver() unchanged | PASS |
| Idempotency via channel_idempotency_key() preserved | PASS |
| Webhook port constraints in __main__.py preserved | PASS |
| No imports from wecom_service in any new QQ module | PASS |
| No imports from gateway package in gateway_client.py | PASS |
| `ingress_runtime.py` and `session_runtime.py` kept (not deleted) | PASS |
| All existing QQ bot tests pass (BOT-03 regression) | PASS (136 total) |
| All 34 gates green | PASS |

## Test Counts

- qqbot-service gate: 136 tests (83 existing + 53 new: 17 gateway_client + 21 event_consumer + 15 webhook gateway migration)
- qqbot-channel gate: 342 tests (unchanged — all pass)
- Full gate suite: 34 gates green
- New test files: test_gateway_client.py (17 tests), test_event_consumer.py (21 tests), test_webhook_gateway_migration.py (15 tests)
- New fixture: bot_events.json (11 events, 9 types)

## Deviations

1. **DeliverRecordingAdapter wrapper**: The plan specified using `FakeQQBotAdapter` from `fakes.py` to capture deliveries. However, `FakeQQBotAdapter.normalize_inbound()` returns an empty `InboundNormalized()` (message=None), which prevents the gateway branch from triggering (it requires `normalized.message is not None`). To solve this, a `DeliverRecordingAdapter` wrapper was created that delegates `verify_and_ack` and `normalize_inbound` to the real `QQBotChannelAdapter` (which properly normalizes QQ envelopes into `AgentTurn`) but intercepts `deliver()` to record deliveries. This preserves test fidelity while capturing delivery assertions. This is the same pattern used in Plan 95-02 for WeCom.

2. **Privacy gate fix in 95-02-SUMMARY.md**: The `95-02-SUMMARY.md` file contained a raw callback body marker (in the context of describing a previous privacy fix) which matched the privacy scanner's forbidden-body-marker pattern. Fixed by rewording the text to avoid the forbidden marker. This is a documentation-only fix.

3. **Test fakes in separate module**: The plan specified FakeGatewayClient and FakeQQBotAdapter should be in the test files. To avoid code duplication between test_gateway_client.py and test_event_consumer.py, a shared `fakes.py` module was created in the tests directory. Both test files import from it. This is a minor structural deviation that improves maintainability without changing the test interface. This mirrors the WeCom pattern from Plan 95-01.

## Self-Check: PASSED

All 7 tasks executed and committed. All acceptance criteria pass. 34 gates green. No existing test broken. QQ webhook.py uses Gateway instead of direct agent calls when gateway_client is available. Keyboard cards, media delivery, intermediate pushes all preserved via the event consumer. Backward-compatible fallback when gateway_client is None. Phase 95 (Bot Channel Degradation) is now complete — both WeCom and QQ bot services are Gateway event stream consumers.
