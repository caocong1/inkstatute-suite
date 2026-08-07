---
phase: 91
status: complete
researched_at: 2026-08-07T17:00:00Z
---

# Phase 91 Research — Unified Gateway

## §1 Endpoint Inventory

### Current platform_api (5 endpoints)
1. POST /v1/runs — create_run (AgentTurn + SolutionBinding)
2. GET /v1/runs/{run_id} — poll_run
3. DELETE /v1/runs/{run_id} — cancel_run
4. POST /v1/runs/{run_id}/approvals — submit_approval
5. GET /v1/runs/{run_id}/events — stream_run (SSE)

### Current lawyer-web-chat (7 routes)
1. GET / — index page
2. POST /login — issue RBAC token
3. GET /sessions — list sessions
4. GET /history — message history
5. GET /stream — SSE streaming
6. POST /upload — file upload (reference-only)
7. POST /feedback — feedback normalization

### Gateway needs (11+ endpoints per GW-01)
1. POST /v1/sessions — create session
2. GET /v1/sessions/{id} — get session
3. GET /v1/sessions/{id}/runs — list runs for session
4. POST /v1/runs — create run
5. GET /v1/runs/{id} — get run
6. GET /v1/runs/{id}/events — SSE stream
7. POST /v1/runs/{id}/elicitation — submit elicitation response
8. POST /v1/runs/{id}/approvals — submit approval
9. GET /v1/artifacts/{id} — download artifact
10. POST /v1/uploads — upload file
11. POST /v1/feedback — submit feedback
12. GET /v1/skills — list/search skills

## §2 SSE & Last-Event-ID

### Current SSE
- platform_api: custom SSE frame constants (SSE_EVENT_RUN, SSE_EVENT_RUN_COMPLETED)
- lawyer-web-chat: uses encode_sse_event from web_sse package with output boundary

### Convergence
- Gateway uses encode_sse_event from web_sse package
- Output boundary applied per event before encoding
- Deterministic JSON (sort_keys, separators)

### Last-Event-ID Implementation
- In-memory event buffer per run_id (dict[run_id, list[RunEvent]])
- Buffer stores events with their seq numbers
- On reconnection with Last-Event-ID header:
  1. Parse last_event_id to get last seq number
  2. Find events with seq > last_seq
  3. Replay those events in seq order
  4. Continue streaming new events
- Buffer size limit: ~1000 events per run (sufficient for single-firm scale)
- Buffer cleanup: when run reaches terminal state, keep for 5 minutes then remove

### RunEvent.seq
- RunEvent has `seq` field (int) — sequence number within a run
- Events are ordered by seq
- Phase 88 added sort_events_by_seq and resume_from_seq helpers

## §3 Auth & Tenant

### RBAC resolve_identity()
- File: packages/rbac/src/rbac/identity.py
- Tries Bearer token first (Authorization: Bearer <token>)
- Falls back to session cookie (inkstatute_session)
- Returns Identity with role, tenant_id, user_id
- When rbac_enabled=False, falls back to v1.6 static-token

### Gateway Auth Middleware
- gateway/auth.py — wraps all endpoint handlers
- Calls resolve_identity() on every request
- Rejects unauthenticated requests with 401
- Adds identity to request context
- Tenant validation: compare identity.tenant_id with resource tenant_id

### Permission Matrix
- LAWYER: /v1/sessions, /v1/runs, /v1/uploads, /v1/feedback, /v1/skills (read)
- ADMIN: all endpoints + /v1/skills-write
- Bearer token: for bot/programmatic access
- Session cookie: for web/desktop access

### Tenant Isolation
- tenant_id required in all API responses (contract field)
- Default tenant_id for self-hosted: "default"
- Cross-tenant access: 403 Forbidden
- tenant_id from auth token/cookie claims

## §4 Session Management

### RBAC SessionStore Protocol
- File: packages/rbac/src/rbac/session.py
- Protocol: create(), get(), delete()
- InMemorySessionStore: MVP implementation
- Session fields: sid, role, tenant_id, created_at, expires_at
- TTL: 28800 seconds (8 hours)

### lawyer-web-chat Session Features
- Multi-device sync: devices[] field per session
- Session token: HMAC-SHA256 signed cookie
- Cookie: HttpOnly, Secure, SameSite=Strict
- TTL: 15 minutes (900 seconds) for token, 8 hours for session

### Merge Strategy
- Gateway uses RBAC SessionStore Protocol
- Add devices[] field to support multi-device sync
- Session creation: POST /v1/sessions → returns session + Set-Cookie
- Session retrieval: GET /v1/sessions/{id}
- Session listing: GET /v1/sessions (for current user/tenant)

## §5 Upload & Artifacts

### Upload (from lawyer-web-chat)
- POST /v1/uploads
- FileUploadHandler stores references only
- Returns: upload_id, payload_ref, content_ref, content_hash, filename, size_bytes, mime_type
- Safety: raw content never stored, only hash and references
- Reference format: ref://{tenant}/{conversation}/{upload_id}/payload

### Artifact Download
- GET /v1/artifacts/{artifact_id}
- Auth required + tenant check
- Returns artifact metadata + content_ref (not raw content)
- Cross-tenant access: 403 Forbidden
- Reference-first: artifact_id is the key, content_ref points to storage

## §6 Skills Endpoint

### skill-registry Read API
- File: packages/skill-registry/src/inkstatute_skill_registry/api.py
- handle_get(): GET /skills, GET /skills/search, GET /skills/{skill_id}
- Feature flag: skill_registry_enabled (default-off)

### Gateway Integration
- Import handle_get from skill-registry
- Expose under /v1/skills prefix
- Add auth and tenant checks
- Keep skill-registry feature flag
- No write API in Gateway (write API stays in admin-console)

## §7 ChannelAdapter.verify_and_ack

### Current Protocol
- File: packages/platform-runtime/src/platform_runtime/protocols.py
- ChannelAdapter Protocol has 6 methods including verify_and_ack
- ChannelCapabilitySet: channel_id_support, stream_event_support, etc.

### Making verify_and_ack Optional
- Add `verify_and_ack_support: bool = False` to ChannelCapabilitySet
- Web/desktop adapters: verify_and_ack_support = False
- Bot adapters (qqbot, wecom): verify_and_ack_support = True
- Protocol check: adapters without verify_and_ack_support skip the method
- Gate: test that adapters without verify_and_ack still pass Protocol validation

### Adapters to Update
- packages/channels/web_sse: set verify_and_ack_support = False
- packages/channels/qqbot: keep verify_and_ack_support = True
- packages/channels/wecom: keep verify_and_ack_support = True

## §8 Gate Registration

### Current Gates: 30

### New Gate
```python
gateway_src = repo_root / "services" / "gateway" / "src"

Gate(
    "gateway",
    (py, "-m", "unittest", "discover", "-s", "services/gateway/tests"),
    (gateway_src, platform_src, platform_runtime_src, rbac_src, web_sse_src, skill_registry_src),
),
```

### compileall
Add `"services/gateway/src"` to compileall paths.

### gate-coverage-meta-test
Add `"services/gateway/src"` to coverage paths.

### lawyer-web-chat gate
Keep gate #28 during transition. Remove after Phase 95.

### platform_api
platform_api has NO gate currently. After upgrade to services/gateway, the gateway gate covers it.

## §9 OpenAPI

### Current OpenAPI Builder
- File: apps/platform_api/src/platform_api/openapi.py
- Generates deterministic OpenAPI 3.1 document
- Security scheme: X-InkStatute-Token (apiKey type)

### Expansion
- Add all 12 endpoints to OpenAPI document
- Add tags: Sessions, Runs, Elicitation, Approvals, Artifacts, Uploads, Feedback, Skills
- Update security schemes: Bearer token + session cookie
- Add tenant_id to all response schemas
- Add Last-Event-ID header parameter for SSE endpoint
- Keep deterministic JSON generation

## §10 Deprecation Strategy

### lawyer-web-chat Deprecation
- Add `Deprecation: true` header to all lawyer-web-chat responses
- Add `Sunset: <date>` header (RFC 8594) — set to Phase 95 completion date
- Add deprecation notice in response body for HTML responses
- Keep service running during transition
- Remove after Phase 95 (Bot Channel Degradation) verifies Gateway covers all capabilities
- lawyer-web-chat gate stays green during transition

### platform_api
- apps/platform_api/ is upgraded to services/gateway/
- Old apps/platform_api/ directory removed after upgrade
- No deprecation needed — it's a move, not a parallel service

## §11 Risk Assessment

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | Session merge breaks multi-device sync | Medium | Comprehensive session tests, keep lawyer-web-chat as fallback during transition |
| 2 | Last-Event-ID replay misses events | Medium | Integration test with reconnection scenario, seq-based replay verification |
| 3 | Protocol change breaks existing channel adapters | Medium | Additive change (new field with default), test all adapters pass |
| 4 | Auth middleware blocks legitimate requests | Low | RBAC resolve_identity() is proven, fallback for rbac_enabled=False |
| 5 | SSE convergence breaks existing clients | Low | encode_sse_event is already used by lawyer-web-chat, same format |
| 6 | Gate count change breaks meta-test | Low | Update gate count assertion (30 → 31) |
