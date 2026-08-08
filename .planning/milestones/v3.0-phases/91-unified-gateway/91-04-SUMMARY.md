---
phase: 91-unified-gateway
plan: 04
subsystem: gateway
tags: [skill-catalog, skill-search, verify-and-ack-optional, deprecation-header, pagination]
requires:
  - phase: 91-01
    provides: Gateway scaffold (GatewayApp, GatewayAuth, dispatch, 501 stubs)
  - phase: 91-03
    provides: Feedback handler (GatewayFeedbackHandler, handle_submit_feedback_request)
provides:
  - gateway.skills.GatewaySkillsHandler (proxy to skill-registry handle_get with auth + tenant checks)
  - gateway.skills.handle_skills_request (dispatcher for GET /v1/skills* paths)
  - GatewayApp updated (skills_handler constructor param, 501 stub replaced)
  - ChannelCapabilitySet.verify_and_ack_support field (additive, default False)
  - WebSseChannelAdapter verify_and_ack_support=False (GW-06)
  - QqBotChannelAdapter verify_and_ack_support=True
  - WeComChannelAdapter verify_and_ack_support=True
  - lawyer-web-chat deprecation headers (Deprecation, Sunset, Link)
  - lawyer-web-chat HTML deprecation notice
affects: [91-05]
key-files:
  - services/gateway/src/gateway/skills.py
  - services/gateway/src/gateway/app.py
  - packages/platform-runtime/src/platform_runtime/protocols.py
  - packages/channels/web_sse/src/inkstatute_channels_web_sse/adapter.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
  - packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py
  - packages/platform-runtime/src/platform_runtime/fakes.py
  - services/lawyer-web-chat/src/lawyer_web_chat/server.py
  - services/gateway/tests/test_skills.py
  - services/gateway/tests/test_verify_and_ack_optional.py
  - packages/channels/web_sse/tests/test_adapter_optional_verify.py
  - services/lawyer-web-chat/tests/test_deprecation_header.py
  - scripts/run_v2_gates.py
  - packages/contract-test-suite/fixtures/contract_freeze_baseline.json
key-decisions:
  - "Skills endpoint proxies to skill-registry's handle_get — no reimplementation, just auth + tenant checks + path translation (/v1 → /)"
  - "verify_and_ack_support is an additive field on ChannelCapabilitySet (default False) — Protocol not structurally changed"
  - "Web/SSE adapter declares verify_and_ack_support=False (first-party, no callback verification needed)"
  - "QQBot and WeCom adapters declare verify_and_ack_support=True (ED25519 and AES-CBC verification respectively)"
  - "Deprecation headers are additive — no response body or status code changed, lawyer-web-chat continues to function"
  - "Sunset date set to Wed, 31 Dec 2026 23:59:59 GMT (after Phase 95 completion)"
  - "Link header points to /v1/sessions as successor-version"
  - "skills_handler is optional in GatewayApp.__init__ (default None → 501, backward compatible)"
  - "Contract freeze baseline hash updated for protocols.py (additive field change)"
  - "Gateway gate PYTHONPATH extended with channel_core, qqbot, wecom paths for test_verify_and_ack_optional.py"
patterns-established:
  - "Proxy pattern: Gateway proxies to existing package read API, adding auth + tenant checks + path translation"
  - "Additive capability field: new bool field with default False on frozen dataclass — no existing code breaks"
  - "Deprecation via headers: Deprecation + Sunset + Link headers on all responses, HTML notice for browser users"
  - "Read-only enforcement: skills endpoint exposes only GET, no write API (write stays in admin-console)"
  - "Feature flag preservation: skill_registry_enabled default-off → 503 when disabled"
  - "Optional dependency injection: skills_handler=None preserves backward compatibility (returns 501)"
requirements-completed: [GW-05, GW-06]
coverage: 125 gateway tests (103 existing + 14 skills + 8 verify_and_ack) + 101 lawyer-web-chat tests (92 existing + 9 deprecation) + 30 web_sse tests (27 existing + 3 optional_verify)
duration: ~2h
completed: 2026-08-07
status: complete
---

# Plan 91-04 Summary — Skill Endpoints, Optional verify_and_ack, and lawyer-web-chat Deprecation

## What Was Done

Implemented three changes that complete the Gateway's capability coverage and the channel protocol evolution:

1. **`GET /v1/skills` endpoint** — proxies to the existing `skill-registry` read API (`handle_get`), adding auth and tenant checks. Supports list (`/v1/skills`), search (`/v1/skills/search`), and get-single (`/v1/skills/{id}`). Read-only (no write API exposed). Feature flag preserved (`skill_registry_enabled` default-off → 503). This replaces the 501 stub from Plan 91-01.

2. **`ChannelAdapter.verify_and_ack` optional capability** — added `verify_and_ack_support: bool = False` field to `ChannelCapabilitySet` (additive, default False). Updated all channel adapters to declare their support level: Web/SSE = False, QQBot = True, WeCom = True, Fake = False. The Protocol is not structurally changed — the flag declares whether the adapter's `verify_and_ack` is semantically required. Adapters without `verify_and_ack_support` still pass Protocol validation (GW-06 verified).

3. **`lawyer-web-chat` deprecation headers** — added `Deprecation: true`, `Sunset: Wed, 31 Dec 2026 23:59:59 GMT`, and `Link: </v1/sessions>; rel="successor-version"` headers to all `lawyer-web-chat` responses. Added deprecation notice `<div>` to HTML pages (error, login, chat). JSON response bodies are unchanged — only headers are added. `lawyer-web-chat` continues to function during the transition period (removal in Phase 104).

### Tasks Completed (8/8)

| Task | Description | Commit |
|------|-------------|--------|
| 91-04-01 | Add verify_and_ack_support field to ChannelCapabilitySet | `86000c5` |
| 91-04-02 | Update channel adapters to declare verify_and_ack_support level | `1e37e43` |
| 91-04-03 | Create skills.py — proxy to skill-registry read API | `e753739` |
| 91-04-04 | Wire skills endpoint into app.py and replace 501 stub | `87f33e5` |
| 91-04-05 | Add deprecation headers to lawyer-web-chat responses | `18dad64` |
| 91-04-06 | Create test_skills.py — 14 tests for skills endpoint | `a8ff822` |
| 91-04-07 | Create test_verify_and_ack_optional.py, test_adapter_optional_verify.py, test_deprecation_header.py | `4ea3c52` |
| 91-04-08 | Run full gate suite — update gate PYTHONPATH and contract freeze baseline | `2d2cce9` |

### Key Decisions

1. **Proxy pattern for skills**: The Gateway does not reimplement the skill listing logic. It imports `handle_get` from `inkstatute_skill_registry.api` and proxies requests, translating the `/v1/skills` path prefix to `/skills` by stripping `/v1`. Auth and tenant checks are added on top. The `skill_registry_enabled` feature flag is preserved (default-off → 503).

2. **Additive capability field**: `verify_and_ack_support: bool = False` is added to `ChannelCapabilitySet` after `idempotency_strategy` and before `metadata`. The default `False` means existing code that constructs `ChannelCapabilitySet` without this field continues to work. The `ChannelAdapter` Protocol is not structurally changed — `verify_and_ack` remains a method on the Protocol, but the flag declares whether it is semantically required.

3. **Deprecation via headers only**: JSON response bodies are unchanged — deprecation is communicated via `Deprecation`, `Sunset`, and `Link` headers for API clients, and via a `<div class="deprecation-notice">` element in HTML pages for browser users. The `Sunset` date is set to `Wed, 31 Dec 2026 23:59:59 GMT` (after Phase 95 completion).

4. **Optional skills_handler injection**: `skills_handler: GatewaySkillsHandler | None = None` in `GatewayApp.__init__`. When `None`, the skills endpoint returns 501 (backward compatible with all 103 existing tests). When provided, it returns 200/404/503 based on the skill registry state.

5. **Contract freeze baseline update**: The SHA-256 hash for `protocols.py` in `contract_freeze_baseline.json` was updated to reflect the additive `verify_and_ack_support` field. This is a one-way-door change — the baseline is now locked at the new hash.

6. **Gateway gate PYTHONPATH extension**: Added `channel_core_src`, `qqbot_src`, `wecom_channel_src`, `wecom_src` to the gateway gate's PYTHONPATH so that `test_verify_and_ack_optional.py` can import `QQBotChannelAdapter` and `WeComChannelAdapter` to verify their `verify_and_ack_support` values.

### Test Coverage

- **test_skills.py** (14 tests): list_skills, search_skills, get_single_skill, get_skill_not_found, skills_require_auth, skills_via_dispatch, skills_tenant_id_in_response, skills_feature_flag_disabled, skills_feature_flag_enabled, skills_read_only, skills_search_via_dispatch, skills_get_single_via_dispatch, skills_get_not_found_via_dispatch, skills_no_handler_returns_501
- **test_verify_and_ack_optional.py** (8 tests): channel_capability_set_has_verify_and_ack_support, default_verify_and_ack_support_is_false, web_sse_adapter_verify_and_ack_support_false, qqbot_adapter_verify_and_ack_support_true, wecom_adapter_verify_and_ack_support_true, fake_adapter_verify_and_ack_support_false, adapter_without_verify_and_ack_support_passes_protocol, adapter_with_verify_and_ack_support_true
- **test_adapter_optional_verify.py** (3 tests): web_sse_verify_and_ack_support_is_false, web_sse_adapter_passes_protocol_check, web_sse_verify_and_ack_is_noop_when_support_false
- **test_deprecation_header.py** (9 tests): index_page_has_deprecation_header, login_has_deprecation_header, all_routes_have_deprecation_header, deprecation_notice_in_html, link_header_points_to_gateway, json_responses_unchanged, sunset_header_is_future_date, error_page_has_deprecation_notice, disabled_flag_response_has_deprecation_header
- **Total new tests**: 34 (14 + 8 + 3 + 9)
- **Gateway total**: 125 tests (103 existing + 14 skills + 8 verify_and_ack)
- **lawyer-web-chat total**: 101 tests (92 existing + 9 deprecation)
- **web_sse total**: 30 tests (27 existing + 3 optional_verify)

### Gate Status

- 31 gates total (30 existing + 1 gateway gate from Plan 91-01)
- All gates green
- `python scripts/run_v2_gates.py --json-summary` outputs `{"passed": true}`
- No regression in any previous plan's tests
- Contract freeze baseline updated for protocols.py

### Requirements Progress

- **GW-05** (complete): 取代 `apps/platform_api` 与 `services/lawyer-web-chat` 的职责重叠，全项目单一网关. The skills endpoint is now accessible through the unified Gateway (`GET /v1/skills`). `lawyer-web-chat` is marked deprecated with `Deprecation: true`, `Sunset`, and `Link` headers on all responses.

- **GW-06** (complete): `ChannelAdapter.verify_and_ack` 降级为可选 capability，web / 桌面通道不实现亦合法. `ChannelCapabilitySet` has `verify_and_ack_support: bool = False` field. `WebSseChannelAdapter` declares `False`. Adapters without `verify_and_ack_support` still pass Protocol validation (verified by `test_adapter_without_verify_and_ack_support_passes_protocol`).

## Self-Check: PASSED

- [x] All tasks executed and committed (8/8)
- [x] All acceptance_criteria PASS
- [x] GET /v1/skills — catalog listing with pagination (proxies to skill-registry handle_get)
- [x] GET /v1/skills/{id} — skill detail
- [x] GET /v1/skills/search — skill search (tag/category/name query params)
- [x] Skills endpoint is read-only (no POST/PUT/DELETE on /v1/skills)
- [x] skill_registry_enabled feature flag preserved (default-off → 503)
- [x] ChannelCapabilitySet has verify_and_ack_support: bool = False (additive)
- [x] WebSseChannelAdapter declares verify_and_ack_support = False
- [x] QqBotChannelAdapter and WeComChannelAdapter declare verify_and_ack_support = True
- [x] Adapters without verify_and_ack_support pass Protocol validation (GW-06 verified)
- [x] All lawyer-web-chat responses include Deprecation: true and Sunset headers
- [x] lawyer-web-chat HTML pages include deprecation notice
- [x] lawyer-web-chat JSON response bodies unchanged (only headers added)
- [x] lawyer-web-chat gate stays green (deprecation headers are additive)
- [x] All tests pass (125 gateway + 101 lawyer-web-chat + 30 web_sse)
- [x] 31 gates green
- [x] SUMMARY.md with Self-Check: PASSED
- [x] GW-05 and GW-06 marked complete
