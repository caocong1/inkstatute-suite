---
phase: 91-unified-gateway
plan: 03
subsystem: gateway
tags: [upload, artifact, feedback, reference-first, tenant-isolation]
requires:
  - phase: 91-01
    provides: Gateway scaffold (GatewayApp, GatewayAuth, dispatch, 501 stubs)
  - phase: 91-02
    provides: SSE Last-Event-ID replay (RunEventBuffer, seq-based reconnection)
provides:
  - gateway.upload.GatewayUploadHandler (reference-first upload with SHA-256 hash, tenant isolation, filename sanitization)
  - gateway.upload.UploadResult (dataclass with tenant_id as first-class field)
  - gateway.upload.handle_upload_request (POST /v1/uploads endpoint handler)
  - gateway.artifacts.GatewayArtifactStore (in-memory artifact store with tenant isolation)
  - gateway.artifacts.ArtifactMetadata (dataclass wrapping ArtifactRecord with tenant_id)
  - gateway.artifacts.handle_get_artifact_request (GET /v1/artifacts/{id} endpoint handler, cross-tenant 404)
  - gateway.feedback.GatewayFeedbackHandler (feedback normalization: up/down/needs_fix/route_wrong)
  - gateway.feedback.FeedbackResult (dataclass with tenant_id as first-class field)
  - gateway.feedback.handle_submit_feedback_request (POST /v1/feedback endpoint handler)
  - GatewayApp updated (upload_handler, artifact_store, feedback_handler constructor params; 501 stubs replaced)
affects: [91-04, 91-05]
key-files:
  - services/gateway/src/gateway/upload.py
  - services/gateway/src/gateway/artifacts.py
  - services/gateway/src/gateway/feedback.py
  - services/gateway/src/gateway/app.py
  - services/gateway/tests/test_upload_artifact_feedback.py
  - services/gateway/tests/fixtures/upload_requests.json
  - services/gateway/tests/fixtures/feedback_requests.json
key-decisions:
  - "tenant_id is a first-class field in UploadResult and FeedbackResult (not in metadata as in lawyer-web-chat)"
  - "Cross-tenant artifact access returns 404 (not 403) to avoid leaking existence of artifacts belonging to other tenants"
  - "Cross-tenant upload access is invisible (get_upload returns None) — fail-safe tenant isolation"
  - "Raw content is never stored — only SHA-256 hash and references (payload_ref, content_ref)"
  - "Filename sanitization strips path components (prevents path traversal: ../../../etc/passwd → passwd)"
  - "SkillCandidate.requires_human_review is always True for route_wrong feedback; metadata.no_auto_modify is True"
  - "Handler parameters are optional in GatewayApp.__init__ with default instances — preserves backward compatibility"
  - "Feedback source changed from 'web_chat' to 'gateway' to reflect the new unified entry point"
  - "proposed_name for route_wrong SkillCandidate is 'gateway.route_review_candidate' (was 'web_chat.route_review_candidate')"
patterns-established:
  - "Reference-first upload: content_bytes hashed and discarded, only hash + refs stored"
  - "Cross-tenant 404 pattern: not-found and cross-tenant both return 404 (no existence leak)"
  - "Cross-tenant invisible pattern: get_upload returns None for wrong tenant (fail-safe)"
  - "Optional dependency injection: handler params default to new instances when None"
  - "Feedback normalization: action aliases mapped to canonical form (up/down/needs_fix/route_wrong)"
  - "Human-review enforcement: route_wrong always creates SkillCandidate with requires_human_review=True"
requirements-completed: [GW-04]
coverage: 103 tests (74 existing + 29 new: 8 TestUpload + 7 TestArtifacts + 10 TestFeedback + 4 TestFixtures)
duration: ~1.5h
completed: 2026-08-07
status: complete
---

# Plan 91-03 Summary — Upload, Artifact, and Feedback Endpoints

## What Was Done

Implemented three Gateway endpoints that absorb capabilities from `services/lawyer-web-chat`: `POST /v1/uploads` (reference-first file upload), `GET /v1/artifacts/{artifact_id}` (artifact download with auth + tenant check), and `POST /v1/feedback` (feedback normalization). These endpoints replace the 501 stubs from Plan 91-01 with full implementations. This satisfies GW-04: "附件上传与产物下载 reference-first（返回 `attachment_ref` / `artifact_id`，不落敏感全文），下载需鉴权 + 租户校验".

### Tasks Completed (6/6)

| Task | Description | Commit |
|------|-------------|--------|
| 91-03-01 | Create upload.py — reference-first file upload handler with tenant isolation | `5f6f0df` |
| 91-03-02 | Create artifacts.py — artifact download with auth + tenant validation, cross-tenant 404 | `7061645` |
| 91-03-03 | Create feedback.py — feedback normalization with SkillCandidate human-review enforcement | `9ee1eb3` |
| 91-03-04 | Wire upload/artifact/feedback handlers into app.py — replace 501 stubs | `020bdd5` |
| 91-03-05 | Create test_upload_artifact_feedback.py with 29 tests and fixtures | `ee06bae` |
| 91-03-06 | Run gateway gate — verify all 103 tests and 31 gates green | (verification) |

### Key Decisions

1. **tenant_id as first-class field**: In `lawyer-web-chat`, `tenant_id` was stored in `metadata`. In the Gateway, `UploadResult.tenant_id` and `FeedbackResult.tenant_id` are explicit dataclass fields. This makes tenant isolation enforceable at the data structure level, not just via metadata lookup.

2. **Cross-tenant 404 (not 403) for artifacts**: The artifact handler returns 404 for both not-found and cross-tenant-denied cases. This prevents leaking the existence of artifacts belonging to other tenants. The plan specified this explicitly: "Cross-tenant access returns 404 (not 403) to avoid leaking the existence of artifacts belonging to other tenants."

3. **Cross-tenant invisible for uploads**: `get_upload` returns `None` when the tenant_id doesn't match — the upload is invisible to other tenants. This is fail-safe: no information about the upload's existence is leaked.

4. **Raw content never stored**: The upload handler computes a SHA-256 hash of the content bytes and immediately discards them. Only the hash and references (`payload_ref`, `content_ref`) are stored. This satisfies AGENTS.md: "Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads."

5. **Filename sanitization**: Path components are stripped from uploaded filenames (`../../../etc/passwd` → `passwd`). This prevents path traversal attacks. The sanitization follows the same pattern as `lawyer-web-chat`'s `FileUploadHandler`.

6. **Human-review enforcement**: For `route_wrong` feedback, a `SkillCandidate` is created with `requires_human_review=True` and `metadata.no_auto_modify=True`. The handler never auto-synthesizes or auto-modifies legal conclusion skills. Non-route_wrong feedback does not create a `SkillCandidate` at all.

7. **Optional dependency injection**: `upload_handler`, `artifact_store`, and `feedback_handler` are optional parameters in `GatewayApp.__init__` with default instances. This preserves backward compatibility — all 74 existing tests pass without modification.

### Test Coverage

- **TestUpload** (8 tests): returns_references, no_raw_content, filename_sanitization, tenant_isolation, payload_ref_format, via_dispatch, no_auth, tenant_id_in_response
- **TestArtifacts** (7 tests): register_and_get, cross_tenant_denied (404 not 403), not_found, no_raw_content, via_dispatch, no_auth, tenant_id_in_response
- **TestFeedback** (10 tests): up, down, needs_fix, route_wrong, route_wrong_human_review, invalid_action, via_dispatch, no_auth, tenant_id_in_response, no_auto_synthesize
- **TestFixtures** (4 tests): upload_fixtures_valid, feedback_fixtures_valid, upload_all_fixtures, feedback_all_fixtures
- **Total**: 29 new tests, all passing
- **Grand total**: 103 Gateway tests (74 existing + 29 new), all passing

### Gate Status

- 31 gates total (30 existing + 1 gateway gate from Plan 91-01)
- All gates green
- `python scripts/run_v2_gates.py --json-summary` outputs `{"passed": true}`
- No regression in Plan 91-01 tests (test_app_tracer, test_auth, test_sessions, test_sse)
- No regression in Plan 91-02 tests (test_event_buffer, test_sse_replay)

### Requirements Progress

- **GW-04** (complete): 附件上传与产物下载 reference-first（返回 `attachment_ref` / `artifact_id`，不落敏感全文），下载需鉴权 + 租户校验。Cross-tenant access rejected. All three endpoints require auth and include tenant_id in responses.

## Self-Check: PASSED

- [x] All tasks executed and committed (6/6)
- [x] All acceptance_criteria PASS
- [x] POST /v1/uploads — reference-first upload (returns upload_id, payload_ref, content_ref, content_hash; no raw content stored)
- [x] GET /v1/artifacts/{id} — auth + tenant check (cross-tenant returns 404, no existence leak)
- [x] POST /v1/feedback — feedback normalization (up/down/needs_fix/route_wrong with SkillCandidate)
- [x] Cross-tenant access rejected (upload invisible, artifact 404)
- [x] All tests pass (103 tests: 74 existing + 29 new)
- [x] 31 gates green
- [x] SUMMARY.md with Self-Check: PASSED
- [x] GW-04 marked complete in REQUIREMENTS.md
