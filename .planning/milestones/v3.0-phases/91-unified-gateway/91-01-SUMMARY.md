---
phase: 91-unified-gateway
plan: 01
subsystem: gateway
tags: [gateway, unified-entry, auth-middleware, sse, gate-registration, tracer]
requires: []
provides:
  - services/gateway/ (unified multi-tenant HTTP+SSE Gateway)
  - gateway.config.GatewayConfig (with default_tenant_id, INKSTATUTE_GATEWAY_ENABLED)
  - gateway.auth.GatewayAuth (RBAC resolve_identity — Bearer + cookie + static-token fallback)
  - gateway.sessions.GatewaySessionManager (RBAC SessionStore with multi-device sync)
  - gateway.sse.GatewaySseStream (encode_sse_event from web_sse + output boundary)
  - gateway.app.GatewayApp (12-endpoint routing, 4 tracer handlers, 8 stubbed 501)
  - gateway.openapi.build_openapi_document (12 paths, Bearer+cookie security, Last-Event-ID)
  - gateway gate (31st gate in run_v2_gates.py)
affects: [91-02, 91-03, 91-04, 91-05]
key-files:
  - services/gateway/pyproject.toml
  - services/gateway/src/gateway/__init__.py
  - services/gateway/src/gateway/config.py
  - services/gateway/src/gateway/auth.py
  - services/gateway/src/gateway/sessions.py
  - services/gateway/src/gateway/sse.py
  - services/gateway/src/gateway/app.py
  - services/gateway/src/gateway/openapi.py
  - services/gateway/tests/test_app_tracer.py
  - services/gateway/tests/test_auth.py
  - services/gateway/tests/test_sessions.py
  - services/gateway/tests/test_sse.py
  - services/gateway/tests/fixtures/gateway_events.json
  - scripts/run_v2_gates.py
  - packages/contract-test-suite/tests/test_audit_v2_requirements.py
key-decisions:
  - "Upgrade platform_api → services/gateway (not a new service, a move + expansion)"
  - "Framework-free (stdlib http.server pattern, zero external dependencies)"
  - "SSE uses encode_sse_event from web_sse package (replaces platform_api custom SSE constants)"
  - "Auth uses RBAC resolve_identity() — Bearer token first, session cookie fallback, static-token for self-hosted"
  - "Output boundary enforced per event at Gateway (second enforcement point, first is ACP event bridge)"
  - "V3 event types normalized to V2 equivalents for DefaultAssistantOutputBoundary allowlist check"
  - "Auth middleware applied centrally in dispatch — no per-handler bypass possible"
  - "8 endpoints stubbed with 501 (to be implemented in Plans 91-02, 91-03, 91-04)"
  - "Gate registration purely additive — no existing gate modified"
patterns-established:
  - "Single gateway pattern: one HTTP+SSE entry point for all clients"
  - "Framework-free handlers: pure Python functions returning dicts or SSE frames"
  - "Auth unification: RBAC resolve_identity() handles both Bearer and cookie auth"
  - "SSE convergence: all SSE uses encode_sse_event from web_sse package"
  - "V3-to-V2 event type normalization for output boundary compatibility"
  - "tenant_id in all API responses (contract field not omitted)"
  - "Reference-first: contract logs prefer raw_payload_ref"
requirements-completed: []
coverage: 46 tests (13 tracer + 12 auth + 8 sessions + 12 SSE + 1 placeholder removed)
duration: ~2h
completed: 2026-08-07
status: complete
---

# Plan 91-01 Summary — Gateway Tracer

## What Was Done

Created `services/gateway/` — the unified multi-tenant HTTP+SSE Gateway for InkStatute, upgraded from `apps/platform_api/`. This plan implements the end-to-end tracer slice: `POST /v1/sessions` → `POST /v1/runs` → `GET /v1/runs/{id}/events` (SSE) → `DELETE /v1/runs/{id}`.

### Tasks Completed (10/10)

| Task | Description | Commit |
|------|-------------|--------|
| 91-01-01 | Scaffold services/gateway package, port config, register gate (31 gates) | `433282e` |
| 91-01-02 | Create auth.py — RBAC resolve_identity() middleware with Bearer + cookie fallback | `9fc857d` |
| 91-01-03 | Create sessions.py — RBAC SessionStore with multi-device sync | `1359d30` |
| 91-01-04 | Create sse.py — encode_sse_event from web_sse with output boundary | `616c7b0` |
| 91-01-05 | Create app.py — GatewayApp with 12-endpoint routing, tracer handlers, auth middleware | `33476aa` |
| 91-01-06 | Create openapi.py — OpenAPI 3.1 builder with 12 paths, Bearer+cookie security | `1197e4e` |
| 91-01-07 | Create test fixtures and test_app_tracer.py — 13 end-to-end tracer tests | `9b589cf` |
| 91-01-08 | Create test_auth.py (12 tests) and test_sessions.py (8 tests) | `3419e69` |
| 91-01-09 | Create test_sse.py — 12 SSE encoding with output boundary tests | `e3189e6` |
| 91-01-10 | Remove placeholder test, verify all 31 gates green | `eccb2df` |

### Key Decisions

1. **V3-to-V2 event type normalization**: The `DefaultAssistantOutputBoundary` checks `event_type` against a V2 allowlist. V3 event types (e.g., `message.delta`) are normalized to V2 equivalents (e.g., `message_delta`) before passing to the boundary. Unknown V3 types return `None` so the event-type check is skipped and text-based rules still apply.

2. **Auth applied centrally**: The `dispatch` method calls `auth.require_auth(headers)` BEFORE routing to any handler. No endpoint bypasses auth. The `stream` method also calls `auth.require_auth(headers)` before yielding any SSE frames.

3. **8 endpoints stubbed with 501**: The tracer-critical endpoints (create_session, create_run, stream_run, cancel_run) are fully implemented. The remaining 8 endpoints (get_session, list_session_runs, get_run, submit_elicitation, submit_approval, get_artifact, upload, submit_feedback, list_skills) return 501 not-implemented — to be implemented in Plans 91-02, 91-03, and 91-04.

4. **Gate registration purely additive**: The `gateway` gate was added after `acp-event-bridge` in `scripts/run_v2_gates.py`. No existing gate entry was modified. The `compileall` gate path list was extended with `services/gateway/src`. The gate count assertion in `test_audit_v2_requirements.py` was updated from 30 to 31.

### Test Coverage

- **test_app_tracer.py**: 13 tests (end-to-end tracer slice, auth, SSE, stubs, 404, tenant_id)
- **test_auth.py**: 12 tests (static-token, RBAC Bearer, session cookie, role check, tenant check, no auto-approve)
- **test_sessions.py**: 8 tests (create, get, list, add_device, delete, cookie header, multi-device sync)
- **test_sse.py**: 12 tests (encode, forbidden keys, boundary block/rewrite, format match, Last-Event-ID)
- **Total**: 46 tests, all passing

### Gate Status

- 31 gates total (30 existing + 1 new `gateway` gate)
- All gates green
- `gate-coverage-meta-test` confirms `services/gateway/src` is covered
- `compileall` gate includes `services/gateway/src`

### Requirements Progress (all partial)

- **GW-01** (partial): 12 endpoint paths scaffolded, 4 tracer handlers implemented, 8 stubbed with 501
- **GW-03** (partial): Auth middleware using RBAC resolve_identity() with Bearer + cookie + static-token fallback; tenant_id in all responses; default_tenant_id for self-hosted
- **GW-05** (partial): services/gateway created from apps/platform_api; apps/platform_api preserved during transition

## Self-Check: PASSED

- [x] All tasks executed and committed (10/10)
- [x] All acceptance_criteria PASS
- [x] services/gateway/ created (moved from apps/platform_api/)
- [x] 12 endpoint handlers scaffolded (4 implemented, 8 stubbed 501)
- [x] Auth middleware using RBAC resolve_identity()
- [x] SSE using encode_sse_event from web_sse
- [x] Gate registered (31 gates total)
- [x] All tests pass (46 tests)
- [x] 31 gates green
- [x] SUMMARY.md with Self-Check: PASSED
- [x] STATE.md, ROADMAP.md updated
