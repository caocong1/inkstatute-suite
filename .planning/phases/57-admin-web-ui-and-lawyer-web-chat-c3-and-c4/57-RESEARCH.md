# Phase 57: Admin Web UI + Lawyer Web Chat (C3 + C4) - Research

**Researched:** 2026-07-06
**Domain:** Operator dashboard web UI, lawyer-facing web chat with SSE, session auth, output boundary enforcement for browser-facing surfaces
**Confidence:** HIGH

## Summary

Phase 57 introduces two new opt-in Python services that render browser-facing surfaces while enforcing the output boundary:

1. **`services/admin-web-ui/`** — a server-side rendered operator dashboard built on the Python stdlib `http.server`. It proxies read-only requests to the existing `admin-console-api` `handle_admin_get` handler, renders session/task inspection, a feedback review queue, gate status, and health monitoring as **escaped plaintext HTML** (never `innerHTML`), and sets a strict Content-Security-Policy. Access is gated by the `admin_web_ui_enabled` feature flag (default `False`) and RBAC (Phase 51) — only `admin`/`operator` roles may view operational endpoints; `lawyer`/`viewer` roles see only case data.

2. **`services/lawyer-web-chat/`** — a server-side rendered lawyer web chat built on the Python stdlib `http.server` with real Server-Sent Events streaming. It provides session authentication (RBAC `lawyer` role tokens), message history, file upload (reference-only, no raw legal payloads persisted), feedback submission (reusing the `web_sse` ChannelAdapter normalization), and multi-device sync via server-side session state. It is gated by the `lawyer_web_chat_enabled` feature flag (default `False`) and enforces the same output boundary as WeCom — no backend notices (gateway/meta/system/update/command) reach the lawyer.

Both services use **stdlib only** (`dependencies = []` invariant preserved) and reuse existing packages: `rbac`, `platform_runtime` (feature flags + output boundary), `inkstatute_channels_web_sse` (SSE encoding + channel adapter), `admin_console_api` (read endpoints), and `conversation_read_view` (read model). No frozen contract surfaces are modified. The two new feature flags (`admin_web_ui_enabled`, `lawyer_web_chat_enabled`) are added to `RuntimeFeatureFlags` — both default to `False` and are purely additive (the count-freeze test does not freeze `RuntimeFeatureFlags` field count, and the introspection-based default-False test passes automatically).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per `workflow.skip_discuss`. All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Claude's Discretion
- **Rendering technology:** The CONTEXT.md mentions "Preact + Tailwind (static bundle)". The codebase has no existing frontend framework (no React/Vue/Preact/Tailwind in any `package.json`/`pyproject.toml`). Per the operative task constraints ("Python backend services — use stdlib http.server or similar lightweight approach, with HTML templates. Do NOT introduce React/Vue/etc. unless already in the project"), both services are implemented as **Python stdlib `http.server` services with server-side HTML templates**. All backend content is rendered as **HTML-escaped plaintext** (via `html.escape`) — never `innerHTML` — satisfying the output-boundary success criterion ("escaped plaintext or DOMPurify-sanitized content — never innerHTML"). A strict CSP header (`default-src 'self'`) is set on every response. No secrets or raw legal payloads are placed in browser storage; session state is server-side.
- All other implementation choices follow codebase conventions.

### Deferred Ideas (OUT OF SCOPE)
- Preact/Tailwind static bundle (no existing frontend framework in repo; stdlib server-side rendering chosen instead — equivalent output-boundary guarantees).
- New admin-console-api route branches (`/mcp-servers`, `/model-gateway/health`, `/skills`, `/tenants`) — these are additive read endpoints; the Admin Web UI consumes the **existing** `/sessions`, `/tasks`, `/feedback`, `/health`, `/gates` endpoints which already cover session/task inspection, feedback review, gate status, and health monitoring. Adding new route branches is out of scope for the phase goal as stated in the operative success criteria.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADMINUI-01 | Admin Web UI renders operator dashboard with session/task inspection, feedback review queue, gate status, and health monitoring — backed by admin-console-api endpoints with RBAC enforcement; `admin_web_ui_enabled` defaults `False` | §Architecture (AdminWebUiServer proxies handle_admin_get), §Code Examples (RBAC guard reuse), §Feature Flags |
| LAWYERCHAT-01 | Lawyer Web Chat provides web chat with real SSE streaming, session auth, message history, file upload, feedback submission, multi-device sync — enforcing output boundary; `lawyer_web_chat_enabled` defaults `False` | §Architecture (LawyerWebChatServer + SSE + sessions), §Code Examples (encode_sse_event reuse, web_sse adapter reuse), §Feature Flags |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.** File upload stores references only (`payload_ref`, `content_ref`), never raw legal text. Session tokens are HMAC-signed RBAC tokens, not raw secrets. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it.** Two new services are explicitly required by the phase goal. Both use stdlib `http.server` + existing packages only. `dependencies = []` preserved. [VERIFIED: AGENTS.md §Coding Rules]
- **Backend/gateway/system notices are not user-facing.** Both UIs enforce the output boundary — `DefaultAssistantOutputBoundary` filters backend noise; HTML rendering uses `html.escape` (never `innerHTML`). [VERIFIED: AGENTS.md §Safety And Privacy]
- **Keep changes scoped to the active GSD phase.** No frozen contract surfaces modified. [VERIFIED: AGENTS.md §Coding Rules]
- **Add tests before or with behavior changes.** Each service gets unit tests covering rendering, RBAC, SSE, sessions, history, upload, feedback, and output boundary. [VERIFIED: AGENTS.md §Coding Rules]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Admin Web UI HTTP server | `services/admin-web-ui/` (server.py) | — | New service owns HTTP dispatch + CSP headers |
| Admin dashboard rendering | `services/admin-web-ui/` (dashboard.py) | — | Server-side HTML templates with html.escape |
| Admin API proxy | `services/admin-web-ui/` (api_client.py) | `admin_console_api.handle_admin_get` | Reuses existing read endpoints + RBAC |
| Lawyer Web Chat HTTP server | `services/lawyer-web-chat/` (server.py) | — | New service owns HTTP dispatch + SSE |
| Lawyer session auth | `services/lawyer-web-chat/` (session.py) | `rbac` package | Reuses RBAC token issue/verify (lawyer role) |
| Lawyer SSE streaming | `services/lawyer-web-chat/` (sse.py) | `inkstatute_channels_web_sse.encode_sse_event` | Reuses SSE frame encoding |
| Lawyer message history | `services/lawyer-web-chat/` (history.py) | — | In-memory server-side store (reference-only) |
| Lawyer file upload | `services/lawyer-web-chat/` (upload.py) | — | Stores payload_ref/content_ref only |
| Lawyer feedback | `services/lawyer-web-chat/` (feedback.py) | `inkstatute_channels_web_sse.WebSseChannelAdapter` | Reuses feedback normalization |
| Output boundary (both) | `platform_runtime.output_boundary` | per-service boundary.py | Reuse DefaultAssistantOutputBoundary + html.escape |

## Architecture Patterns

### Admin Web UI request flow
```
Browser --HTTP--> AdminWebUiServer
  -> feature flag gate (admin_web_ui_enabled)
  -> RBAC token verify (rbac.verify_token) -> Identity(role, tenant_id)
  -> RbacGuard.check(role, endpoint)  # admin/operator for ops; lawyer/viewer for case data
  -> api_client.proxy(handle_admin_get, path, identity)  # reuses admin-console-api
  -> dashboard.render(escaped_plaintext)  # html.escape, never innerHTML
  -> response with CSP header: default-src 'self'
```

### Lawyer Web Chat request flow
```
Browser --HTTP--> LawyerWebChatServer
  -> feature flag gate (lawyer_web_chat_enabled)
  -> /login: issue RBAC token (lawyer role, tenant_id) -> Set-Cookie httpOnly
  -> /sessions: server-side session store (multi-device sync via shared session_id)
  -> /history: message history (reference-only)
  -> /stream: SSE via encode_sse_event, output boundary applied per event
  -> /upload: file upload -> payload_ref/content_ref only (no raw legal text)
  -> /feedback: WebSseChannelAdapter.normalize_inbound -> FeedbackEvent
  -> all responses: CSP header, html.escape rendering
```

### Output boundary enforcement (both UIs)
- **Server-side:** `DefaultAssistantOutputBoundary.apply()` filters backend noise (model names, API error traces, function call internals, gateway/meta/system notices) before any text is rendered.
- **Rendering:** All dynamic content passed through `html.escape()` and inserted as HTML text content — never `innerHTML`, never string interpolation into raw HTML.
- **CSP:** Every HTTP response carries `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'` — blocks inline scripts/styles and external resources.
- **Cookies:** Session tokens set as `HttpOnly; Secure; SameSite=Strict` — not accessible to JS.
- **No browser storage of secrets/raw payloads:** Session state is server-side; file uploads store references only.

## Code Examples

### Feature flag addition (platform_runtime/feature_flags.py)
```python
@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    # ... existing flags ...
    admin_web_ui_enabled: bool = False      # NEW — Phase 57
    lawyer_web_chat_enabled: bool = False   # NEW — Phase 57
```
The introspection test `test_all_flags_default_to_false_via_introspection` iterates `fields(RuntimeFeatureFlags)` and asserts each defaults to `False` — new flags pass automatically. The count-freeze test does **not** freeze `RuntimeFeatureFlags`.

### RBAC token issue/verify (rbac package — Phase 51)
```python
from rbac import issue_token, verify_token, Role, RbacGuard
token = issue_token(secret, role=Role.LAWYER, tenant_id="tenant-1")
claims = verify_token(token, secret)  # -> RbacTokenClaims(role, tenant_id, iat, exp)
guard = RbacGuard()
guard.check(Role.OPERATOR, "/feedback")  # True
guard.check(Role.LAWYER, "/feedback")    # False (default-deny)
```

### SSE encoding reuse (inkstatute_channels_web_sse — Phase 46)
```python
from inkstatute_channels_web_sse import encode_sse_event
frame = encode_sse_event({"event_id": "e1", "event_type": "message_delta", ...})
# -> "id: e1\nevent: message_delta\ndata: {...}\n\n"
```

### Output boundary reuse (platform_runtime — Phase 7/46)
```python
from platform_runtime.output_boundary import DefaultAssistantOutputBoundary, BoundaryAction
boundary = DefaultAssistantOutputBoundary()
decision = boundary.apply("web", text=event_text, event_type=event_type)
if decision.action == BoundaryAction.ALLOW:
    visible = decision.visible_text
elif decision.action == BoundaryAction.REWRITE:
    visible = decision.visible_text  # owned service notice
else:  # BLOCK
    visible = None  # dropped
```

## Feature Flags

| Flag | Default | Owner | Purpose |
|------|---------|-------|---------|
| `admin_web_ui_enabled` | `False` | `services/admin-web-ui/` | Opt-in for Admin Web UI service |
| `lawyer_web_chat_enabled` | `False` | `services/lawyer-web-chat/` | Opt-in for Lawyer Web Chat service |
| `admin_api_enabled` | `False` (existing) | `admin-console-api` | Required by Admin Web UI backend |
| `web_sse_channel_enabled` | `False` (existing) | `inkstatute_channels_web_sse` | Required by Lawyer Web Chat SSE |
| `rbac_enabled` | `False` (existing) | `rbac` | Required for session auth + role enforcement |

## Dependencies On Prior Phases

| Phase | Dependency | How Used |
|-------|-----------|----------|
| 51 (RBAC) | `rbac` package | Token issue/verify, RbacGuard, Role, Identity |
| 56 (Multi-Tenant) | `tenant_id` scoping | Session/auth carry tenant_id |
| 50 (MCP Registry) | — | Not directly consumed by UI surfaces (read endpoints exist in admin-console-api scope) |
| 54 (Model Gateway) | — | Health monitoring surfaces gateway health via `/health` endpoint |
| 46 (Streaming) | `encode_sse_event`, RunEvent | Lawyer Web Chat SSE streaming |
| 47 (Artifact Return) | artifact refs | File upload + artifact reference rendering |

## FROZEN Contract Surfaces (NOT modified)

- `BackendAdapter` Protocol (9 methods)
- `AdapterCapabilitySet` (14 fields)
- `ChannelAdapter` Protocol (6 methods)
- `RunEvent` dataclass
- `RunEventType` enum
- `platform_contract.events` dataclasses
- `admin_console_api.handle_admin_get` signature (consumed, not modified)
- `rbac` public API (consumed, not modified)
- `encode_sse_event` signature (consumed, not modified)

## Risks And Mitigations

| Risk | Mitigation |
|------|-----------|
| XSS via backend content | `html.escape` on all dynamic content; never `innerHTML`; strict CSP header |
| Session token leakage | HttpOnly + Secure + SameSite=Strict cookies; HMAC-signed RBAC tokens with expiry |
| Raw legal payloads in browser | File upload stores references only; no localStorage/sessionStorage of payloads |
| Feature flag bypass | Both services gate on flag before any rendering; disabled returns 503 |
| Stray untracked files in repo | Only `git add` explicit phase-57 paths; never `git add -A` |
