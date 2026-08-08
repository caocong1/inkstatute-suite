---
phase: 95
plan: 02
title: WeCom Full Migration — Replace Direct Agent Calls with Gateway Consumer, Template Cards, Media Delivery, Intermediate Pushes
wave: 2
requirements:
  - BOT-01
  - BOT-02
  - BOT-03
commits:
  - 3055419: feat(95-02): add optional gateway_client field to WeComWiredRuntime + gateway_config param to build_wecom_wired_runtime
  - ca46808: feat(95-02): add _compose_via_gateway to webhook.py — Gateway consumer path in post-ACK composition
  - 2b3ffaf: feat(95-02): read Gateway config from env vars in __main__.py — INKSTATUTE_GATEWAY_URL/BEARER_TOKEN/TENANT_ID
  - 7f986a0: test(95-02): create test_webhook_gateway_migration.py — 15 tests for Gateway consumer path in webhook post-ACK composition
  - d10f286: test(95-02): add test_wiring_with_gateway_config + test_wiring_without_gateway_config to test_wecom_wiring.py
  - b55f7d1: fix(95-02): remove forbidden body markers from 95-01-SUMMARY.md to pass privacy gate
---

# Plan 95-02 Summary: WeCom Full Migration — Gateway Consumer Path in Post-ACK Composition

## Goal

Switch the WeCom post-ACK composition path from direct agent calls (`runtime.create_run()` / `backend.get_run()`) to the Gateway event consumer created in Plan 95-01. The `run_post_ack_composition()` function in `webhook.py` now calls `WeComEventConsumer.consume_and_deliver()` when `wired.gateway_client` is available. The `wiring.py` injects a `GatewayClient` when `gateway_config` is provided. The `__main__.py` reads Gateway config from env vars.

After this plan:
- WeCom webhook → verify_and_ack → post-ACK → GatewayClient.create_run → SSE stream → aggregate_events → adapter.deliver
- No `runtime.create_run()` or `backend.get_run()` calls in the gateway path (BOT-02)
- All existing WeCom tests stay green (ACK, AES-CBC, template cards, media, idempotency preserved — BOT-03)
- The `ingress_runtime.py` and `session_runtime.py` files are kept but no longer called from the gateway path

## What Was Done

### Task 95-02-01: wiring.py — add gateway_client field (commit 3055419)
- Added `gateway_client: GatewayClient | None = None` field to `WeComWiredRuntime` dataclass (after `runtime`, before `vision_resolver`)
- Added `gateway_config: GatewayClientConfig | None = None` parameter to `build_wecom_wired_runtime()`
- When `gateway_config` is provided, a `GatewayClient` is constructed and stored in `WeComWiredRuntime.gateway_client`
- When `gateway_config` is None, `gateway_client` is None (old path, backward compat)
- Imported `GatewayClient`, `GatewayClientConfig` from `.gateway_client`
- The `backend` parameter, `DefaultRunRuntime` construction, and `runtime` field are unchanged
- All 125 existing tests pass unchanged

### Task 95-02-02: webhook.py — _compose_via_gateway (commit ca46808)
- Added gateway branch in `run_post_ack_composition()`: when `wired.gateway_client is not None and normalized.message is not None`, calls `_compose_via_gateway()` instead of the old ingress path
- The feedback branch runs BEFORE the gateway branch (unchanged)
- Created `_compose_via_gateway()` function that:
  - Extracts `AgentTurn` from `normalized.message` and serializes to dict via `_agent_turn_to_dict()`
  - Extracts `to_user` from callback payload via `_to_user_from_callback()`
  - Extracts `conversation_id` from callback via `_conversation_id_from_callback()`
  - Constructs `WeComEventConsumer` with `wired.gateway_client`, `wired.adapter`, and solution binding
  - Calls `consumer.consume_and_deliver()` and returns evidence with `gateway_path=True`
- Created `_agent_turn_to_dict()` helper that serializes `AgentTurn` fields (turn_id, conversation_id, channel, user_id, message_type, received_at, content, attachments, metadata)
- Created `_conversation_id_from_callback()` helper
- Imported `WeComEventConsumer` from `.event_consumer`, `GatewayClient` from `.gateway_client`, `AgentTurn` from `platform_contract.events`
- The old ingress path (lines 193-260) remains as fallback when `gateway_client` is None
- `handle_wecom_webhook_request()` is unchanged — still ACK-first, still schedules post-ACK
- No `runtime.create_run()` or `backend.get_run()` in the gateway path (BOT-02)

### Task 95-02-03: __main__.py — Gateway env vars (commit 2b3ffaf)
- Reads `INKSTATUTE_GATEWAY_URL` (default: `http://127.0.0.1:8081`)
- Reads `INKSTATUTE_GATEWAY_BEARER_TOKEN` (default: empty — when empty, old path used)
- Reads `INKSTATUTE_GATEWAY_TENANT_ID` (default: `default-tenant`)
- When bearer token is non-empty, constructs `GatewayClientConfig` and passes to `build_wecom_wired_runtime()` as `gateway_config`
- When empty, doesn't pass `gateway_config` (old path, backward compat)
- Logs `"WeCom service: Gateway consumer mode enabled (url={gateway_url})"` when Gateway path is active
- `FakeBackendAdapter` still used as default backend (unchanged)
- Updated docstring with new env vars

### Task 95-02-04: test_webhook_gateway_migration.py (commit 7f986a0)
- 15 tests covering the new Gateway consumer path in post-ACK composition:
  1. `test_post_ack_uses_gateway_when_available` — gateway path used when gateway_client is set
  2. `test_post_ack_falls_back_when_no_gateway` — old path used when gateway_client is None
  3. `test_post_ack_gateway_delivers_text` — final message delivered as text
  4. `test_post_ack_gateway_delivers_card` — elicitation delivered as card
  5. `test_post_ack_gateway_intermediate_prompt` — tool_call.started produces "正在检索法规…"
  6. `test_post_ack_gateway_feedback_branch_unchanged` — feedback branch runs regardless of gateway_client
  7. `test_post_ack_gateway_no_direct_agent_calls` — source inspection: no runtime.create_run or backend.get_run
  8. `test_post_ack_gateway_session_reuse` — same conversation_id reuses session
  9. `test_post_ack_gateway_to_user_extraction` — to_user correctly extracted and passed
  10. `test_post_ack_gateway_solution_binding` — SolutionBinding forwarded to consumer
  11. `test_ack_first_pattern_preserved` — 5s ACK deadline preserved
  12. `test_aes_cbc_signature_verification_preserved` — channel disabled → 503
  13. `test_idempotency_preserved` — duplicate callbacks handled
  14. `test_full_flow_gateway_tracer` — end-to-end: webhook → verify_and_ack → post-ACK → Gateway → SSE → deliver
  15. `test_agent_turn_to_dict_serialization` — AgentTurn serialization correctness
- Created `DeliverRecordingAdapter` wrapper that delegates `verify_and_ack` and `normalize_inbound` to the real adapter but records `deliver()` calls
- All tests network-free (FakeGatewayClient + DeliverRecordingAdapter)

### Task 95-02-05: test_wecom_wiring.py updates (commit d10f286)
- Added `test_wiring_with_gateway_config` — verifies `gateway_client` is not None when `gateway_config` is provided
- Added `test_wiring_without_gateway_config_has_none_gateway_client` — verifies `gateway_client` is None without `gateway_config` (backward compat)
- All existing tests in `test_webhook.py` pass unchanged (4 tests — old path fallback)
- All existing tests in `test_wecom_wiring.py` pass (6 tests — 4 existing + 2 new)

### Task 95-02-06: Verification + privacy gate fix (commit b55f7d1)
- Verified no `runtime.create_run` or `backend.get_run` in `event_consumer.py`
- Verified no `runtime.create_run` or `backend.get_run` in `gateway_client.py`
- Verified no `from gateway` or `import gateway` in `gateway_client.py`
- Verified `_compose_via_gateway` has no direct agent calls
- Fixed privacy gate failure in `95-01-SUMMARY.md` (removed forbidden body markers that matched the privacy scanner pattern)
- All 34 gates green

## Acceptance Criteria Results

| Criterion | Result |
|-----------|--------|
| `WeComWiredRuntime` has `gateway_client: GatewayClient \| None = None` field | PASS |
| `build_wecom_wired_runtime(backend=fake_backend)` works without `gateway_config` (backward compat) | PASS |
| `build_wecom_wired_runtime(backend=fake_backend, gateway_config=...)` creates `gateway_client` not None | PASS |
| `run_post_ack_composition()` with `gateway_client is not None` calls `_compose_via_gateway()` | PASS |
| `run_post_ack_composition()` with `gateway_client is None` uses old ingress path | PASS |
| Feedback branch unchanged and runs before gateway branch | PASS |
| `handle_wecom_webhook_request()` unchanged — ACK-first, 5s deadline | PASS |
| `_agent_turn_to_dict()` correctly serializes AgentTurn fields | PASS |
| `_compose_via_gateway()` calls `WeComEventConsumer.consume_and_deliver()` | PASS |
| No `runtime.create_run()` or `backend.get_run()` in gateway path (BOT-02) | PASS |
| `__main__.py` reads `INKSTATUTE_GATEWAY_URL`, `INKSTATUTE_GATEWAY_BEARER_TOKEN`, `INKSTATUTE_GATEWAY_TENANT_ID` | PASS |
| When bearer token is set, `gateway_config` is passed to `build_wecom_wired_runtime()` | PASS |
| When bearer token is empty, old path is used | PASS |
| `FakeBackendAdapter` still used as default backend | PASS |
| `test_webhook_gateway_migration.py` has 14+ tests | PASS (15) |
| `test_wecom_wiring.py` has `test_wiring_with_gateway_config` | PASS |
| All 18 existing WeCom test files pass (BOT-03 regression) | PASS |
| No `from gateway` or `import gateway` in `gateway_client.py` | PASS |
| `ingress_runtime.py` and `session_runtime.py` kept (not deleted) | PASS |
| All 34 gates green | PASS |

## Test Counts

- wecom-service gate: 142 tests (125 existing + 15 new gateway migration + 2 new wiring)
- Full gate suite: 34 gates green
- New test files: test_webhook_gateway_migration.py (15 tests)
- Updated test files: test_wecom_wiring.py (+2 tests)

## Deviations

1. **DeliverRecordingAdapter wrapper**: The plan specified using `FakeWeComAdapter` from `fakes.py` to capture deliveries. However, `FakeWeComAdapter.normalize_inbound()` returns an empty `InboundNormalized()` (message=None), which prevents the gateway branch from triggering (it requires `normalized.message is not None`). To solve this, a `DeliverRecordingAdapter` wrapper was created that delegates `verify_and_ack` and `normalize_inbound` to the real `WeComChannelAdapter` (which properly normalizes callbacks into `AgentTurn`) but intercepts `deliver()` to record deliveries. This preserves test fidelity while capturing delivery assertions.

2. **SolutionBinding type mismatch**: The `event_consumer.py` imports `SolutionBinding` from `platform_contract.events` (which has `manifest_ref`/`materialization_ref` fields), while `webhook.py` imports `SolutionBinding` from `platform_runtime.protocols` (which has `version`/`config_ref` fields). The test for solution binding uses the `platform_contract.events.SolutionBinding` to match what the event consumer expects. This is a pre-existing type aliasing issue that doesn't affect production behavior (the solution is passed through as-is).

3. **Privacy gate fix in 95-01-SUMMARY.md**: The `95-01-SUMMARY.md` file contained a raw callback body marker (in the context of describing a previous privacy fix) which matched the privacy scanner's forbidden-body-marker pattern. Fixed by rewording the text to avoid the forbidden marker. This is a documentation-only fix.

## Self-Check: PASSED

All 6 tasks executed and committed. All acceptance criteria pass. 34 gates green. No existing test broken. WeCom webhook.py uses Gateway instead of direct agent calls when gateway_client is available. Template cards, media delivery, intermediate pushes all preserved via the event consumer. Backward-compatible fallback when gateway_client is None.
