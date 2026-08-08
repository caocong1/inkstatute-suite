---
phase: 91-unified-gateway
plan: 05
subsystem: gateway
tags: [openapi, integration-tests, deprecation, e2e, phase-completion]
requires:
  - phase: 91-01
    provides: Gateway scaffold (GatewayApp, GatewayAuth, dispatch, 501 stubs, OpenAPI builder)
  - phase: 91-02
    provides: SSE Last-Event-ID replay (RunEventBuffer, replay logic)
  - phase: 91-03
    provides: Upload/artifact/feedback handlers (reference-first, tenant isolation)
  - phase: 91-04
    provides: Skills endpoint, verify_and_ack optional, lawyer-web-chat deprecation
provides:
  - gateway.openapi.build_openapi_document (full 12-endpoint OpenAPI 3.1 with security, schemas, examples)
  - gateway.openapi.validate_openapi_document (basic OpenAPI validation function)
  - gateway.openapi.render_openapi_json (deterministic, byte-stable JSON rendering)
  - services/gateway/tests/test_openapi.py (18 OpenAPI document validation tests)
  - services/gateway/tests/test_integration.py (17 end-to-end integration tests)
  - services/gateway/tests/fixtures/integration_run_events.json (15-event lifecycle fixture)
  - services/gateway/tests/fixtures/integration_upload.json (upload request fixture)
  - services/gateway/tests/fixtures/integration_feedback.json (feedback request fixture)
  - Phase 91 verification report (all 31 gates green, all 6 success criteria met)
affects: [92-unified-ui]
key-files:
  - services/gateway/src/gateway/openapi.py
  - services/gateway/tests/test_openapi.py
  - services/gateway/tests/test_integration.py
  - services/gateway/tests/fixtures/integration_run_events.json
  - services/gateway/tests/fixtures/integration_upload.json
  - services/gateway/tests/fixtures/integration_feedback.json
  - scripts/run_v2_gates.py
key-decisions:
  - "Security requirements applied to all 13 operations via post-processing in build_openapi_document (BearerAuth + SessionCookie)"
  - "validate_openapi_document performs basic validation: paths have operations, operationId present, responses present, $ref pointers resolve"
  - "SkillDescriptor schema added to components for SkillsListResponse items array"
  - "reference_only: true added to upload request/response and artifact response examples and schemas"
  - "Integration tests use INKSTATUTE_GATE_RUNNING env var to skip nested gate execution (prevents recursive timeout)"
  - "Gate runner sets INKSTATUTE_GATE_RUNNING=1 on child processes to break recursion"
  - "lawyer_web_chat_src added to gateway gate PYTHONPATH for SC-5 deprecation header test"
  - "SSE seq numbers parsed from data JSON payload (not id: field, which contains event_id)"
  - "Output boundary test uses patterns matching actual boundary rules (stack trace, admin_notice)"
  - "Shared session store between auth and session manager for cookie auth testing"
patterns-established:
  - "OpenAPI document is deterministic (sort_keys, indent=2, ensure_ascii=True) — byte-stable for SDK generation"
  - "Integration tests cover all 6 success criteria end-to-end with FakeRunRuntime (no network, no external services)"
  - "Gate runner env var prevents recursive gate execution when tests run gates as subprocesses"
  - "All response schemas include tenant_id (GW-03: contract field not omitted)"
  - "All operations have security requirements (BearerAuth + SessionCookie)"
requirements-completed: [GW-01, GW-03]
coverage: 160 gateway tests (125 existing + 18 OpenAPI + 17 integration) + 31 gates green
duration: ~2h
completed: 2026-08-07
status: complete
---

# Plan 91-05 Summary — Full OpenAPI Document, Integration Tests, and Phase 91 Verification

## What Was Done

Completed Phase 91 with three final deliverables:

1. **Full OpenAPI 3.1 document** — expanded the OpenAPI builder from Plan 91-01 with complete schemas, examples, security schemes, and the `Last-Event-ID` header parameter for all 12 endpoints. Added `validate_openapi_document()` function for basic validation. The document is deterministic (byte-stable) and valid.

2. **End-to-end integration tests** — 17 comprehensive tests that exercise the full Gateway surface: create session → create run → stream events with Last-Event-ID reconnection → upload → download artifact → submit feedback → list skills. Tests verify all 6 Phase 91 Success Criteria and all binding constraints from AGENTS.md.

3. **Phase 91 verification** — all 31 gates green, all 6 success criteria verified, all 6 requirements (GW-01..06) satisfied.

### Tasks Completed (4/4)

| Task | Description | Commit |
|------|-------------|--------|
| 91-05-01 | Expand openapi.py — full schemas, security, validate_openapi_document | `e3e9537` |
| 91-05-02 | Create test_openapi.py — 18 OpenAPI document validation tests | `085ef9b` |
| 91-05-03 | Create integration fixtures and test_integration.py — 17 e2e tests | `5f1e318` |
| 91-05-04 | Run full gate suite and verify Phase 91 success criteria | (verification only) |

### Key Decisions

1. **Security post-processing**: Security requirements (`BearerAuth` + `SessionCookie`) are applied to all 13 operations via a post-processing step in `build_openapi_document()`, rather than modifying each operation function individually. This ensures no operation is missed.

2. **Gate runner recursion prevention**: The gate runner now sets `INKSTATUTE_GATE_RUNNING=1` on child processes. Integration tests that run the gate suite as a subprocess (`test_all_gates_green`, `test_gate_count_is_31`) are skipped when this env var is set, preventing recursive gate execution and timeouts.

3. **SSE seq parsing**: The `_parse_sse_event_ids` helper extracts `seq` from the SSE `data:` JSON payload, not from the `id:` field (which contains `event_id` like "evt-008", not the seq number).

4. **Output boundary test patterns**: The `FakeNoisyRuntime` uses patterns that the `DefaultAssistantOutputBoundary` actually blocks ("stack trace", "admin_notice") rather than patterns like "[gateway]" or "[system]" which are not in the boundary's block rules.

5. **Shared session store**: The `_make_gateway` helper shares the same `InMemorySessionStore` between `GatewayAuth` and `GatewaySessionManager` so that cookies issued by the session manager can be verified by the auth middleware.

### Test Coverage

- **test_openapi.py** (18 tests): OpenAPI version, API title, all 12 paths, operationId presence, responses presence, tenant_id in response schemas, security schemes, security on all operations, Last-Event-ID parameter, all 9 tags, deterministic rendering, valid JSON, validation passes, sanitized examples, upload/artifact reference_only, all $ref resolve, no duplicate operationIds
- **test_integration.py** (17 tests, 2 skipped when nested): SC-1 endpoints + OpenAPI, SC-2 SSE reconnect, SC-3 Bearer + cookie auth + tenant_id, SC-4 upload reference-first + artifact cross-tenant, SC-5 deprecation, SC-6 verify_and_ack optional, full lifecycle, output boundary, no second HTTP surface, gates green, gate count 31, no external deps, no auto-approve, reference-first logs
- **Gateway total**: 160 tests (125 existing + 18 OpenAPI + 17 integration)
- **All 31 gates green**

### Gate Status

- 31 gates total (30 existing + 1 gateway gate from Plan 91-01)
- All gates green: `python scripts/run_v2_gates.py --json-summary` → `{"passed": true}`
- Gate count verified: `python scripts/run_v2_gates.py --list` → 31 lines
- `gate-coverage-meta-test` confirms `services/gateway/src` is covered
- `compileall` gate includes `services/gateway/src`
- No regression in any pre-existing gate

### Requirements Progress

- **GW-01** (complete): 统一 Gateway HTTP API — all 12 endpoints available with OpenAPI document. Verified by `test_success_criteria_1_all_endpoints_available` and `test_success_criteria_1_openapi_document`.
- **GW-03** (complete): 多租户鉴权与会话 — RBAC + session cookie + Bearer token, tenant_id in all contract responses, cross-tenant access denied. Verified by `test_success_criteria_3_auth_bearer_and_cookie` and `test_success_criteria_3_tenant_id_in_contract`.

### Phase 91 Complete

All 6 requirements (GW-01..06) are now complete:
- GW-01: All 12 endpoints with OpenAPI document ✓
- GW-02: SSE Last-Event-ID replay ✓ (Plan 91-02)
- GW-03: Multi-tenant auth, tenant_id in contract ✓
- GW-04: Upload/artifact reference-first ✓ (Plan 91-03)
- GW-05: Single gateway, lawyer-web-chat deprecated ✓ (Plan 91-04)
- GW-06: verify_and_ack optional ✓ (Plan 91-04)

All 6 success criteria verified:
- SC-1: All 12 endpoints + OpenAPI document ✓
- SC-2: SSE Last-Event-ID reconnection, no duplicates, no loss ✓
- SC-3: Auth (RBAC + cookie + Bearer), tenant validation, tenant_id in contract ✓
- SC-4: Upload reference-first, artifact download with auth + tenant, cross-tenant denied ✓
- SC-5: lawyer-web-chat deprecated ✓
- SC-6: verify_and_ack optional ✓

## Self-Check: PASSED

- [x] All tasks executed and committed (4/4)
- [x] All acceptance_criteria PASS
- [x] OpenAPI 3.1 spec complete with all 12 endpoints
- [x] End-to-end integration test passing (17 tests, 15 active + 2 skipped when nested)
- [x] All response schemas include tenant_id (GW-03)
- [x] Security schemes include BearerAuth and SessionCookie
- [x] All operations have security requirements
- [x] streamRun has Last-Event-ID header parameter
- [x] All 9 tags defined with descriptions
- [x] OpenAPI document is deterministic (byte-stable)
- [x] validate_openapi_document returns empty list (no errors)
- [x] All $ref pointers resolve
- [x] No duplicate operationIds
- [x] Upload and artifact examples include reference_only: true
- [x] All tests pass (160 gateway tests)
- [x] 31 gates green
- [x] No regressions in any pre-existing gate
- [x] No external dependencies (framework-free)
- [x] No auto-approval fields in Gateway code
- [x] Output boundary enforced at Gateway
- [x] Single client-facing entry point (no second HTTP/SSE surface)
- [x] GW-01 and GW-03 marked complete
- [x] Phase 91 marked complete in STATE.md and ROADMAP.md
- [x] SUMMARY.md with Self-Check: PASSED
