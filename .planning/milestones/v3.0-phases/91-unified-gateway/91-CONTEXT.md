---
phase: 91
slug: unified-gateway
status: draft
created: 2026-08-07
skip_discuss: true
---

# Phase 91 — Unified Gateway

## Phase Goal

全项目只有一个面向客户端的入口——多租户 HTTP + SSE Gateway，`apps/platform_api` 与 `services/lawyer-web-chat` 的职责重叠被消除

## Requirements

- **GW-01**: 统一 Gateway HTTP API（`/v1/sessions`、`/v1/runs`、`/v1/runs/{id}/events` SSE、`/v1/runs/{id}/elicitation`、`/v1/runs/{id}/approvals`、`/v1/artifacts/{id}`、`/v1/uploads`、`/v1/feedback`、`/v1/skills`）
- **GW-02**: SSE 流式传输统一事件，支持 `Last-Event-ID` 按 `seq` 断线续传，不重复不丢失
- **GW-03**: 多租户鉴权与会话（延续 RBAC + 会话 cookie + Bearer token）；自用形态可用单租户默认值，但契约字段不省略
- **GW-04**: 附件上传与产物下载 reference-first（返回 `attachment_ref` / `artifact_id`，不落敏感全文），下载需鉴权 + 租户校验
- **GW-05**: 取代 `apps/platform_api` 与 `services/lawyer-web-chat` 的职责重叠，全项目单一网关
- **GW-06**: `ChannelAdapter.verify_and_ack` 降级为可选 capability，web / 桌面通道不实现亦合法

## Success Criteria

1. `services/gateway`（由 `apps/platform_api` 升级而来）提供全部端点：`/v1/sessions`、`/v1/sessions/{id}`、`/v1/sessions/{id}/runs`、`/v1/runs/{id}`、`/v1/runs/{id}/events`(SSE)、`/v1/runs/{id}/elicitation`、`/v1/runs/{id}/approvals`、`/v1/artifacts/{id}`、`/v1/uploads`、`/v1/feedback`、`/v1/skills`，且有 OpenAPI 文档
2. SSE 流式传输统一事件；客户端带 `Last-Event-ID` 重连后从正确 `seq` 续传，集成测试断言不重复不丢失
3. 鉴权可用：RBAC + 会话 cookie（web/桌面）与 Bearer token（bot/程序化）；租户校验生效；自用形态可用单租户默认值但契约字段不省略
4. 附件上传返回 `attachment_ref`、产物下载经 `artifact_id`，均 reference-first 且需鉴权 + 租户校验；跨租户访问被拒
5. `services/lawyer-web-chat` 的能力（SSE 编码、会话鉴权、多设备会话列表、上传、反馈）已在 Gateway 中等价可用，旧服务标记 deprecated
6. `ChannelAdapter.verify_and_ack` 已降级为可选 capability，不实现它的通道适配器仍能通过 Protocol 校验与 gate

## Existing Infrastructure

### apps/platform_api (framework-free, 5 endpoints)
- POST /v1/runs, GET /v1/runs/{id}, DELETE /v1/runs/{id}, POST /v1/runs/{id}/approvals, GET /v1/runs/{id}/events (SSE)
- Custom SSE frame constants (SSE_EVENT_RUN, SSE_EVENT_RUN_COMPLETED)
- OpenAPI 3.1 document builder with X-InkStatute-Token security scheme
- Zero external dependencies
- Default-off (INKSTATUTE_PLATFORM_API_ENABLED env var)
- NOT covered by existing gates

### services/lawyer-web-chat (stdlib http.server, 7 routes)
- GET /, POST /login, GET /sessions, GET /history, GET /stream (SSE), POST /upload, POST /feedback
- Uses encode_sse_event from web_sse package
- RBAC session cookies (HttpOnly, Secure, SameSite=Strict)
- Multi-device session sync
- Reference-only upload (payload_ref, content_ref, content_hash)
- Feedback normalization (up/down/needs_fix/route_wrong)
- Output boundary per event before SSE encoding
- IS covered by existing gates (gate #28)

### packages/rbac (auth infrastructure)
- Token-based: HMAC-SHA256 signed tokens (role, tenant_id, iat, exp)
- Session-based: SessionStore Protocol + InMemorySessionStore
- Identity resolution: Bearer token first, session cookie fallback
- Roles: ADMIN, OPERATOR, LAWYER, VIEWER
- Permission matrix per endpoint

### packages/channels/web_sse (SSE encoder)
- encode_sse_event() function: id, event, data format
- Deterministic JSON (sort_keys, separators)
- Forbidden payload key check (rawpayload, rawbody, callbackbody)
- Used by lawyer-web-chat

### packages/skill-registry (skills API)
- Read API: GET /skills, GET /skills/search, GET /skills/{skill_id}
- Write API: POST /skills-write/create, etc. (ADMIN only)
- Feature-flagged (skill_registry_enabled)

### ChannelAdapter Protocol (packages/platform-runtime)
- 6 methods: channel_id, capabilities, verify_and_ack, normalize_inbound, deliver, health
- verify_and_ack implemented by qqbot (ED25519) and wecom (WeCom callback)
- web_sse adapter also implements it

## Key Decisions (Auto-Selected)

### 1. Upgrade platform_api → services/gateway

[auto] Q: "Should the Gateway be a new service or an upgrade of platform_api?" → Selected: "Upgrade apps/platform_api to services/gateway" (recommended)

**Rationale:** ROADMAP says "由 apps/platform_api 升级而来". Move platform_api from apps/ to services/gateway/, expand its endpoints, and absorb lawyer-web-chat's capabilities. This preserves the existing framework-free design while adding the missing endpoints.

### 2. Framework-free (stdlib http.server pattern)

[auto] Q: "Should Gateway use a framework (FastAPI/Starlette)?" → Selected: "Framework-free, matching existing pattern" (recommended)

**Rationale:** Both platform_api and lawyer-web-chat are framework-free with zero external dependencies. The Gateway should maintain this pattern — pure Python handlers that return plain dictionaries or SSE frames. This keeps the codebase consistent and dependency-free.

### 3. SSE: Converge on encode_sse_event from web_sse

[auto] Q: "Which SSE encoder should the Gateway use?" → Selected: "encode_sse_event from web_sse package" (recommended)

**Rationale:** lawyer-web-chat already uses encode_sse_event which has forbidden payload key checks and deterministic JSON. platform_api's custom SSE constants should be replaced with the web_sse encoder for consistency.

### 4. Last-Event-ID: In-memory event buffer per run_id

[auto] Q: "How to implement Last-Event-ID reconnection?" → Selected: "In-memory event buffer per run_id with seq-based replay" (recommended)

**Rationale:** For single-firm scale (≤50 lawyers), in-memory event buffering is sufficient. The buffer stores events per run_id with their seq numbers. On reconnection with Last-Event-ID, the gateway replays events with seq > last_event_id. Future phases can add persistent storage.

### 5. Auth: RBAC resolve_identity() pattern (Bearer + cookie)

[auto] Q: "How should auth work in the Gateway?" → Selected: "RBAC resolve_identity() — Bearer token first, session cookie fallback" (recommended)

**Rationale:** RBAC already has resolve_identity() which tries Bearer token first, then falls back to session cookie. This supports both web/desktop (cookie) and bot/programmatic (Bearer token) access patterns. Tenant_id is always in the token/cookie claims.

### 6. Session management: RBAC SessionStore Protocol

[auto] Q: "Which session store should the Gateway use?" → Selected: "RBAC SessionStore Protocol with InMemorySessionStore" (recommended)

**Rationale:** RBAC SessionStore is Protocol-based and extensible. lawyer-web-chat's session store can migrate to it. The Gateway uses RBAC sessions for web/desktop auth, with multi-device sync support.

### 7. Skills: Import and reuse skill-registry handlers

[auto] Q: "How should /v1/skills work?" → Selected: "Import and reuse skill-registry read API handlers" (recommended)

**Rationale:** skill-registry already has a complete read API. The Gateway imports and exposes these handlers under /v1/skills, adding auth and tenant checks. No need to reimplement.

### 8. ChannelAdapter.verify_and_ack: Optional capability

[auto] Q: "How to make verify_and_ack optional?" → Selected: "Add ChannelCapabilitySet.verify_and_ack_support field, default False" (recommended)

**Rationale:** GW-06 requires verify_and_ack to be optional. Add a boolean field to ChannelCapabilitySet. Web/desktop adapters set it to False. The Protocol check and gate verify that adapters without verify_and_ack_support still pass Protocol validation.

### 9. Deprecation: Mark lawyer-web-chat deprecated, keep for transition

[auto] Q: "How to deprecate lawyer-web-chat?" → Selected: "Mark deprecated with deprecation header, keep for transition period" (recommended)

**Rationale:** Don't remove lawyer-web-chat immediately. Add a deprecation header to its responses. Remove after Phase 95 (Bot Channel Degradation) verifies the Gateway covers all capabilities.

### 10. Multi-tenant: tenant_id required in contract, default for self-hosted

[auto] Q: "How to handle multi-tenancy?" → Selected: "tenant_id required in contract fields, default value for self-hosted" (recommended)

**Rationale:** GW-03 says "自用形态可用单租户默认值，但契约字段不省略". All API responses include tenant_id in the contract. For self-hosted single-tenant deployments, a default tenant_id is used. Cross-tenant access is rejected.

## Key Files

### New Service (upgraded from platform_api)
- `services/gateway/` — Unified Gateway service
  - `src/gateway/` — Main source
    - `app.py` — All endpoint handlers (expanded from platform_api)
    - `sse.py` — SSE encoding using web_sse's encode_sse_event + Last-Event-ID replay
    - `auth.py` — Auth middleware using RBAC resolve_identity()
    - `sessions.py` — Session management using RBAC SessionStore
    - `upload.py` — Upload handler (reference-only, from lawyer-web-chat)
    - `feedback.py` — Feedback handler (from lawyer-web-chat)
    - `skills.py` — Skills endpoint (proxy to skill-registry)
    - `openapi.py` — OpenAPI document builder (expanded)
    - `config.py` — Configuration
  - `tests/` — Test suite
  - `pyproject.toml` — Package configuration

### Existing Files to Reference
- `apps/platform_api/src/platform_api/app.py` — Current 5 endpoints (to be expanded)
- `apps/platform_api/src/platform_api/openapi.py` — OpenAPI builder
- `services/lawyer-web-chat/src/lawyer_web_chat/server.py` — 7 routes (capabilities to absorb)
- `services/lawyer-web-chat/src/lawyer_web_chat/sse.py` — SSE with output boundary
- `services/lawyer-web-chat/src/lawyer_web_chat/session.py` — Session management
- `services/lawyer-web-chat/src/lawyer_web_chat/upload.py` — Upload handler
- `services/lawyer-web-chat/src/lawyer_web_chat/feedback.py` — Feedback handler
- `packages/rbac/src/rbac/identity.py` — resolve_identity()
- `packages/rbac/src/rbac/session.py` — SessionStore Protocol
- `packages/channels/web_sse/src/inkstatute_channels_web_sse/sse.py` — encode_sse_event()
- `packages/skill-registry/src/inkstatute_skill_registry/api.py` — Skills read API
- `packages/platform-runtime/src/platform_runtime/protocols.py` — ChannelAdapter Protocol
- `scripts/run_v2_gates.py` — Gate registration (add gateway gate, update platform_api gate)

## Patterns Established

- **Single gateway pattern:** One HTTP+SSE entry point for all clients (web, desktop, bot, programmatic)
- **Framework-free handlers:** Pure Python functions returning dicts or SSE frames
- **Auth unification:** RBAC resolve_identity() handles both Bearer and cookie auth
- **SSE convergence:** All SSE uses encode_sse_event from web_sse package
- **Last-Event-ID replay:** In-memory event buffer per run_id, seq-based replay
- **Reference-first:** Uploads and artifacts return references, not full content
- **Deprecation path:** Old services marked deprecated, kept for transition
