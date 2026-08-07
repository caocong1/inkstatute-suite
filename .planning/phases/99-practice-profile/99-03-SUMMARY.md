# Plan 99-03 Summary — Gateway Endpoints + E2E + Phase Completion

**Phase:** 99 — Practice Profile
**Plan:** 99-03 (Wave 3, depends on 99-02)
**Requirements:** PROF-01, PROF-02, PROF-03
**Status:** COMPLETE
**Date:** 2026-08-11

## What Was Built

### GatewayPracticeProfileHandler (`services/gateway/src/gateway/practice_profile.py`)

Created the handler class for 3 practice profile endpoints:

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| `handle_get_profile` | `GET /v1/practice-profile` | All authenticated roles | Returns tenant's profile(s), optionally filtered by `?plugin=X` |
| `handle_put_profile` | `PUT /v1/practice-profile` | ADMIN/OPERATOR only | Updates tenant's profile (validates no secrets, uses `ctx.tenant_id`) |
| `handle_start_interview` | `POST /v1/practice-profile/interview` | ADMIN/OPERATOR only | Starts cold-start interview, returns first `ElicitationRequestedPayload` |
| `submit_interview_answers` | `POST /v1/practice-profile/interview/answers` | ADMIN/OPERATOR only | Submits answers for current step, advances or finalizes |

Key design decisions:
- **Cross-tenant prevention**: All methods use `ctx.tenant_id` from the auth context — the tenant_id is never read from the request body
- **RBAC enforcement**: Uses `check_read_access`/`check_write_access` from `rbac_check.py`; raises `GatewayAuthError` (403) for unauthorized roles
- **Secret guard**: `handle_put_profile` calls `validate_no_secrets(body)` before constructing the `PracticeProfile` — raises 400 on secret detection
- **No event log**: The handler does NOT log profile content to the contract event log — profile data is runtime-only
- **Multi-round interview**: In-progress interview states are stored in-memory keyed by `(tenant_id, plugin)`

### Gateway Route Registration (`services/gateway/src/gateway/app.py`)

- Added 4 new operation constants: `OPERATION_GET_PROFILE`, `OPERATION_PUT_PROFILE`, `OPERATION_START_INTERVIEW`, `OPERATION_SUBMIT_INTERVIEW_ANSWERS`
- Added route patterns in `_parse_route` for the 4 new endpoints
- Added `practice_profile_handler` parameter to `GatewayApp.__init__`
- Added dispatch logic for all 4 operations
- Updated `OPERATIONS` tuple from 14 to 18 operations
- Updated `__all__` exports

### OpenAPI Document Updates (`services/gateway/src/gateway/openapi.py`)

- Added 3 new paths (15 total, was 12):
  - `/v1/practice-profile` (GET + PUT)
  - `/v1/practice-profile/interview` (POST)
  - `/v1/practice-profile/interview/answers` (POST)
- Added "PracticeProfile" tag (10 tags total, was 9)
- Added 7 new schema definitions: `PracticeProfile`, `PracticeProfileResponse`, `PracticeProfileUpdateResponse`, `StartInterviewRequest`, `SubmitInterviewAnswersRequest`, `ElicitationPayload`
- Added example functions: `_practice_profile_example`, `_elicitation_example`

### Gate PYTHONPATH Update (`scripts/run_v2_gates.py`)

- Added `practice_profile_src` to the `gateway` gate's PYTHONPATH tuple so the handler can import from `inkstatute_practice_profile`
- Gate registration for `practice-profile` was already done in Plan 99-01 (37 gates)

### Test Files Created

| File | Tests | Coverage |
|------|-------|----------|
| `services/gateway/tests/test_practice_profile.py` | 16 | GET all roles, GET with plugin, GET missing 404, GET all plugins, PUT admin/operator, PUT lawyer/viewer denied 403, PUT secret rejected 400, PUT success + retrievable, PUT tenant_id from ctx, POST interview admin/operator, POST interview lawyer/viewer denied 403, POST interview returns elicitation, POST interview requires auth, tenant isolation, tenant isolation PUT uses ctx |
| `services/gateway/tests/test_practice_profile_e2e.py` | 4 | Full 5-step interview flow via Gateway, validate_question_count all steps, cannot finalize before complete, all 5 steps completed |
| `packages/practice-profile/tests/test_phase99_success_criteria.py` | 6 | Criterion 1: profile modeled + stored, Criterion 2: context injection covers dependent skills, Criterion 3: temporary mode tagged, Criterion 4: cold-start interview via elicitation, Criterion 5: RBAC authorized, Criterion 6: no secrets + no event log |

**Total new tests in 99-03**: 26 (16 handler + 4 e2e + 6 success criteria)
**Total tests in practice-profile package**: 152 (146 from 99-01/02 + 6 success criteria)
**Total tests in gateway**: 193 + 20 new = 213

### Existing Tests Updated

| File | Change |
|------|--------|
| `test_app_tracer.py` | Operation count 14 → 18 |
| `test_integration.py` | Operation count 14 → 18, path count 12 → 15, gate count 36 → 37 |
| `test_openapi.py` | Path count 12 → 15, tag count 9 → 10, added 3 new paths + PracticeProfile tag |

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | `106e454` | feat(99-03): GatewayPracticeProfileHandler — 3 endpoints (GET/PUT profile, POST interview) with RBAC + secret guard |
| 2 | `4ffce5c` | feat(99-03): register 4 practice-profile routes in Gateway + OpenAPI paths + update test counts (14→18 ops, 12→15 paths, 36→37 gates) |
| 3 | `d20c02a` | fix(99-03): add practice_profile_src to gateway gate PYTHONPATH so handler imports resolve |
| 4 | `c32721a` | test(99-03): 16 Gateway handler unit tests — RBAC, secret rejection, tenant isolation, all 3 endpoints |
| 5 | `ea60a3c` | test(99-03): e2e cold-start interview flow — 5 steps via Gateway, finalize, verify profile stored |
| 6 | `d7ea855` | test(99-03): phase 99 success criteria verification — 6 tests asserting all 6 ROADMAP criteria |
| 7 | (this commit) | docs(99-03): mark PROF-01/02/03 complete + Phase 99 complete + SUMMARY.md + STATE.md + ROADMAP.md updates |

## Acceptance Criteria Results

### Task 99-03-01: GatewayPracticeProfileHandler — ALL PASS
- [x] `GatewayPracticeProfileHandler` has methods `handle_get_profile`, `handle_put_profile`, `handle_start_interview`
- [x] `handle_get_profile(ctx, plugin)` returns the tenant's profile as JSON — all profiles when plugin is None, specific profile or 404 when plugin is specified
- [x] `handle_get_profile` allows all authenticated roles (LAWYER, VIEWER, OPERATOR, ADMIN)
- [x] `handle_put_profile(ctx, body)` enforces ADMIN/OPERATOR role via `check_write_access` — raises 403 for LAWYER/VIEWER
- [x] `handle_put_profile` calls `validate_no_secrets(body)` before constructing `PracticeProfile` — raises 400 on secret detection
- [x] `handle_put_profile` constructs `PracticeProfile.from_json(body)` with `tenant_id=ctx.tenant_id` and calls `store.upsert`
- [x] `handle_put_profile` returns `{"status": "updated", "tenant_id": ctx.tenant_id, "plugin": profile.plugin}`
- [x] `handle_start_interview(ctx, body)` enforces ADMIN/OPERATOR role — raises 403 for LAWYER/VIEWER
- [x] `handle_start_interview` calls `orchestrator.start(ctx.tenant_id, body.get("plugin", "commercial-legal"))` and returns the initial elicitation payload as JSON
- [x] All handler methods use `ctx.tenant_id` from the auth context — cross-tenant access is structurally prevented
- [x] The handler does NOT log profile content to the contract event log

### Task 99-03-02: Gateway route registration — ALL PASS
- [x] `GET /v1/practice-profile` route is registered and calls `handler.handle_get_profile(ctx, plugin_query_param)`
- [x] `PUT /v1/practice-profile` route is registered and calls `handler.handle_put_profile(ctx, request_body)`
- [x] `POST /v1/practice-profile/interview` route is registered and calls `handler.handle_start_interview(ctx, request_body)`
- [x] All 3 routes call `require_auth(headers)` before processing — unauthenticated requests get 401
- [x] The `GatewayPracticeProfileHandler` is instantiated at Gateway startup with an `InMemoryPracticeProfileStore` and `ColdStartInterviewOrchestrator`
- [x] The `?plugin=X` query parameter is correctly parsed and passed to `handle_get_profile`
- [x] The routes return JSON responses with appropriate HTTP status codes (200, 400, 403, 404)
- [x] Existing Gateway routes and handlers are not affected (no regression)

### Task 99-03-03: Gate registration — ALL PASS (no-op, done in 99-01)
- [x] `practice_profile_src` path variable already exists (added in 99-01)
- [x] `Gate("practice-profile", ...)` entry already exists (added in 99-01)
- [x] `packages/practice-profile/src` already in compileall (added in 99-01)
- [x] `python scripts/run_v2_gates.py --list` includes `practice-profile` in the output
- [x] Total gate count is 37
- [x] Added `practice_profile_src` to gateway gate's PYTHONPATH (new in 99-03)
- [x] All 36 pre-existing gates remain green

### Task 99-03-04: Gateway handler unit tests — ALL PASS
- [x] `test_get_profile_all_roles` — GET profile succeeds for all 4 roles
- [x] `test_get_profile_with_plugin` — GET with `?plugin=commercial-legal` returns only that plugin's profile
- [x] `test_get_profile_missing` — GET for a non-existent profile returns 404
- [x] `test_put_profile_admin_operator` — PUT succeeds for ADMIN and OPERATOR roles
- [x] `test_put_profile_lawyer_viewer_denied` — PUT returns 403 for LAWYER and VIEWER roles
- [x] `test_put_profile_secret_rejected` — PUT with `api_key` or `password` returns 400
- [x] `test_put_profile_success` — PUT with valid data returns `{"status": "updated", ...}` and is retrievable via GET
- [x] `test_start_interview_admin_operator` — POST interview succeeds for ADMIN and OPERATOR
- [x] `test_start_interview_lawyer_viewer_denied` — POST interview returns 403 for LAWYER and VIEWER
- [x] `test_start_interview_returns_elicitation` — POST interview returns JSON with `interrupt_id`, `intro`, and 2-4 `questions`
- [x] `test_tenant_isolation` — profile created by tenant "t1" is NOT accessible to tenant "default"
- [x] All 16 tests pass

### Task 99-03-05: E2e interview flow test — ALL PASS
- [x] The test starts an interview via `handle_start_interview` and receives the first elicitation payload
- [x] The test verifies the first elicitation has `interrupt_id`, `intro`, and 2-4 `questions`
- [x] The test simulates answer submission for all 5 steps (identity-team → review-stance → escalation-rules → document-style → jurisdiction-profile)
- [x] After all 5 steps, the test verifies a `PracticeProfile` is stored (status: "finalized")
- [x] The test verifies the stored profile is retrievable via `handle_get_profile` with `temporary_mode=False`
- [x] The test verifies the stored profile contains data from the interview answers
- [x] The test verifies `validate_question_count` passes for every step's elicitation (2-4 questions)
- [x] The test verifies the interview cannot be finalized before all 5 steps are complete (raises ValueError)

### Task 99-03-06: Phase 99 success criteria verification — ALL PASS
- [x] `test_criterion_1_profile_modeled_and_stored` — verifies PracticeProfile models 审查立场, 升级矩阵, 文书风格, 管辖识别; verifies InMemoryPracticeProfileStore stores per-tenant
- [x] `test_criterion_2_context_injection_covers_all_dependent_skills` — verifies PracticeProfileInjector injects context for skills with `practice_profile_dependency=True`
- [x] `test_criterion_3_temporary_mode_tagged` — verifies temporary mode with `[临时模式]` tag present and never omitted
- [x] `test_criterion_4_cold_start_interview_via_elicitation` — verifies ColdStartInterviewOrchestrator emits ElicitationRequestedPayload with 2-4 questions, 5 rounds, answers written back
- [x] `test_criterion_5_rbac_authorized` — verifies check_read_access allows all roles, check_write_access allows only ADMIN/OPERATOR, check_tenant_access denies cross-tenant
- [x] `test_criterion_6_no_secrets_no_event_log` — verifies validate_no_secrets rejects secret patterns; verifies injector and orchestrator do NOT create RunEvent objects

### Task 99-03-07: All gates green — ALL PASS
- [x] `python scripts/run_v2_gates.py` exits with code 0 (all 37 gates pass)
- [x] The output includes `==> practice-profile` followed by a passing test run (152 tests, 2 skipped)
- [x] Total gate count is 37
- [x] All 36 pre-existing gates are green (no regression)
- [x] The `gate-coverage-meta-test` passes
- [x] The `compileall` gate passes (includes `packages/practice-profile/src`)
- [x] The `gateway` gate passes (213 tests including 20 new practice-profile tests)

### Task 99-03-08: Phase completion — ALL PASS
- [x] `.planning/REQUIREMENTS.md` has PROF-01, PROF-02, PROF-03 marked as `- [x]`
- [x] `.planning/REQUIREMENTS.md` Traceability table shows PROF-01/02/03 as "Complete ✅" with Phase 99
- [x] `.planning/ROADMAP.md` has Phase 99 marked as `- [x]` with `✅ COMPLETE`
- [x] `.planning/STATE.md` updated: `completed_phases: 12`, `completed_plans: 54`, `percent: 71`
- [x] `.planning/STATE.md` current focus updated to Phase 100
- [x] `.planning/STATE.md` next command updated to `/gsd-plan 100`
- [x] `99-03-SUMMARY.md` exists and documents all work
- [x] No human gates are auto-closed (HG-1, HG-2, HG-3, HG-4 remain unchanged)

## Gate Results

- **37 gates green** (all existing gates preserved)
- `practice-profile` gate: 152 tests, OK (2 skipped — real index not available)
- `gateway` gate: 213 tests, OK (20 new practice-profile tests)
- `gate-coverage-meta-test`: OK (all `packages/*/src` covered)
- `compileall`: OK (includes `packages/practice-profile/src`)
- `contract-test-suite`: 369 tests, OK
- `phase7-privacy-boundary`: 13 tests, OK

## Phase 99 Success Criteria Verification

All 6 success criteria from ROADMAP.md are verified by `test_phase99_success_criteria.py`:

1. ✅ 执业配置在平台侧建模并按租户存储 — `test_criterion_1_profile_modeled_and_stored`
2. ✅ 执行时执业配置被注入 skill 上下文 — `test_criterion_2_context_injection_covers_all_dependent_skills`
3. ✅ 未配置时降级"临时模式" — `test_criterion_3_temporary_mode_tagged`
4. ✅ 冷启动访谈可通过 elicitation.requested 完成 — `test_criterion_4_cold_start_interview_via_elicitation`
5. ✅ 执业配置的读写经 RBAC 授权 — `test_criterion_5_rbac_authorized`
6. ✅ 执业配置不含 secrets，且不进入契约事件日志 — `test_criterion_6_no_secrets_no_event_log`

## Deviations

1. **Added `submit_interview_answers` endpoint (4th route)**: The plan specified 3 endpoints (GET, PUT, POST interview). A 4th endpoint `POST /v1/practice-profile/interview/answers` was added to support multi-round interview answer submission via the Gateway. This is a natural extension of the interview endpoint — the handler stores in-progress interview states in-memory and the answers endpoint advances or finalizes the interview. The plan's Task 99-03-05 e2e test requires multi-round answer submission, which this endpoint enables.

2. **Gate registration was a no-op**: The plan's Task 99-03-03 specified adding the `practice-profile` gate to `run_v2_gates.py`. This was already done in Plan 99-01 (Deviation #2 in 99-01-SUMMARY.md). The only change needed was adding `practice_profile_src` to the `gateway` gate's PYTHONPATH so the handler can import from `inkstatute_practice_profile`.

3. **Updated existing test counts**: Several existing Gateway tests had hardcoded counts (14 operations, 12 OpenAPI paths, 36 gates) that needed updating to reflect the new endpoints (18 operations, 15 paths, 37 gates). These were updated in `test_app_tracer.py`, `test_integration.py`, and `test_openapi.py`.

## Self-Check: PASSED

- [x] All tasks executed and committed
- [x] All acceptance_criteria PASS
- [x] GatewayPracticeProfileHandler created (3 endpoints + 1 answers endpoint)
- [x] Routes registered in Gateway (4 routes in app.py + 3 paths in OpenAPI)
- [x] E2e interview flow test passes (4 tests, full 5-step flow)
- [x] All 6 success criteria verified by test_phase99_success_criteria.py
- [x] All 37 gates green
- [x] PROF-01, PROF-02, PROF-03 marked complete in REQUIREMENTS.md
- [x] Phase 99 marked complete in STATE.md and ROADMAP.md
- [x] SUMMARY.md with Self-Check: PASSED
- [x] No human gates auto-closed
