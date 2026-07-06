# Plan 57-01 Summary: Admin Web UI + Lawyer Web Chat (C3 + C4)

## Objective

Implement two new opt-in Python services that render browser-facing surfaces while enforcing the output boundary:
1. **`services/admin-web-ui/`** — server-side rendered operator dashboard with session/task inspection, feedback review queue, gate status, and health monitoring, backed by admin-console-api endpoints with RBAC enforcement.
2. **`services/lawyer-web-chat/`** — server-side rendered lawyer web chat with real SSE streaming, session auth, message history, file upload, feedback submission, and multi-device sync, enforcing the output boundary.

## Tasks Completed

### Task 1: Add feature flags to RuntimeFeatureFlags

**Files modified:**
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — Added `admin_web_ui_enabled: bool = False` and `lawyer_web_chat_enabled: bool = False` to `RuntimeFeatureFlags`. Both default to `False`. The introspection test `test_all_flags_default_to_false_via_introspection` passes automatically. The count-freeze test does not freeze `RuntimeFeatureFlags` field count.

**Commit:** `1757aaf` — `feat(57-01): add admin_web_ui_enabled and lawyer_web_chat_enabled feature flags`

### Task 2: Create Admin Web UI service

**Files created:**
- `services/admin-web-ui/pyproject.toml` — Package config with `dependencies = []`, stdlib only.
- `services/admin-web-ui/README.md` — Service documentation.
- `services/admin-web-ui/src/admin_web_ui/__init__.py` — Exports `AdminWebUiServer`, `handle_admin_web_ui_request`, `render_dashboard`, `AdminApiClient`, `AdminUiBoundary`, `CSP_HEADER`.
- `services/admin-web-ui/src/admin_web_ui/boundary.py` — `AdminUiBoundary` wrapping `DefaultAssistantOutputBoundary.apply()` with `html.escape` on visible text. Blocks model names, API error traces, function call internals. Rewrites backend lifecycle notices to owned service notices.
- `services/admin-web-ui/src/admin_web_ui/api_client.py` — `AdminApiClient.proxy()` delegates to `admin_console_api.handle_admin_get` with identity and auth context.
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` — `render_dashboard()` produces HTML with `html.escape` on all dynamic content — never `innerHTML`. Renders sessions, tasks, feedback review queue, gate status, and health monitoring sections.
- `services/admin-web-ui/src/admin_web_ui/server.py` — `AdminWebUiServer(BaseHTTPRequestHandler)` with feature flag gate (503 when disabled), RBAC enforcement via `resolve_identity` + `RbacGuard.check`, CSP header on every response.
- `services/admin-web-ui/tests/test_boundary.py` — 9 tests: allows business text + escapes HTML, blocks model name/API error/function call/secret patterns, rewrites backend lifecycle/debug/rate limit, escape_value, None text.
- `services/admin-web-ui/tests/test_api_client.py` — 4 tests: proxy passes path, passes auth header, works without auth header, passes feedback queue.
- `services/admin-web-ui/tests/test_dashboard.py` — 12 tests: index navigation, sessions/tasks/feedback/health/gates rendering, error response, HTML escape in items, identity display, empty items, no identity, no innerHTML/onclick/onerror.
- `services/admin-web-ui/tests/test_server.py` — 12 tests: disabled flag 503, admin token 200, operator token 200, lawyer forbidden on feedback, lawyer allowed on sessions, invalid token 401, missing token 401, CSP header, security headers, unknown route 404, index maps to sessions API, output boundary filters backend noise.

**Commit:** `f9de913` — `feat(57-01): add Admin Web UI service with RBAC, output boundary, and server-side HTML rendering`
**Fix commit:** `6bdca43` — `fix(57-01): remove stray truncated files from admin-web-ui`

### Task 3: Create Lawyer Web Chat service

**Files created:**
- `services/lawyer-web-chat/pyproject.toml` — Package config with `dependencies = []`, stdlib only.
- `services/lawyer-web-chat/README.md` — Service documentation.
- `services/lawyer-web-chat/src/lawyer_web_chat/__init__.py` — Exports `LawyerWebChatServer`, `handle_lawyer_chat_request`, `SessionStore`, `SseStream`, `MessageHistory`, `FileUploadHandler`, `FeedbackHandler`, `ChatBoundary`, `CSP_HEADER`, etc.
- `services/lawyer-web-chat/src/lawyer_web_chat/boundary.py` — `ChatBoundary` wrapping `DefaultAssistantOutputBoundary.apply()` with `html.escape` on visible text.
- `services/lawyer-web-chat/src/lawyer_web_chat/session.py` — `SessionStore` with `create_session`, `issue_session_token`, `verify_session_token`, `add_device` (multi-device sync), `get_sessions_for_conversation`, `cleanup_expired`. Cookie helpers with `HttpOnly; Secure; SameSite=Strict`.
- `services/lawyer-web-chat/src/lawyer_web_chat/sse.py` — `SseStream` wrapping `encode_sse_event` from `inkstatute_channels_web_sse` with output boundary applied per event. Blocked events are dropped.
- `services/lawyer-web-chat/src/lawyer_web_chat/history.py` — `MessageHistory` in-memory store. Content is boundary-filtered before storage. Reference-only (no raw payloads).
- `services/lawyer-web-chat/src/lawyer_web_chat/upload.py` — `FileUploadHandler` storing `payload_ref`/`content_ref` only. SHA-256 content hash. Filename sanitization (no path traversal). No raw content stored.
- `services/lawyer-web-chat/src/lawyer_web_chat/feedback.py` — `FeedbackHandler` normalizing feedback via `WebSseChannelAdapter` pattern. Produces `FeedbackEvent` with proper action classification (up/down/needs_fix/route_wrong) and skill candidate detection for route mismatches.
- `services/lawyer-web-chat/src/lawyer_web_chat/server.py` — `LawyerWebChatServer(BaseHTTPRequestHandler)` with feature flag gate, `/login` (RBAC token + HttpOnly cookie), `/sessions`, `/history`, `/stream` (SSE), `/upload`, `/feedback`. CSP header on every response.
- `services/lawyer-web-chat/tests/test_boundary.py` — 11 tests.
- `services/lawyer-web-chat/tests/test_session.py` — 15 tests (session creation, token issue/verify, multi-device sync, cookie helpers).
- `services/lawyer-web-chat/tests/test_sse.py` — 7 tests (encoding, blocking, rewriting, HTML escaping, stream response).
- `services/lawyer-web-chat/tests/test_history.py` — 9 tests (add message, filtering, HTML escape, pagination, reference-only, clear).
- `services/lawyer-web-chat/tests/test_upload.py` — 9 tests (references, no raw content, filename sanitization, size, metadata, hash determinism).
- `services/lawyer-web-chat/tests/test_feedback.py` — 10 tests (thumbs up/down, needs_fix, route mismatch, invalid action, metadata, source, status).
- `services/lawyer-web-chat/tests/test_server.py` — 16 tests (feature flag, login, auth, sessions, history, stream, upload, feedback, CSP, security headers, unknown route, output boundary, no innerHTML, multi-device sync).

**Commit:** `c3b4e09` — `feat(57-01): add Lawyer Web Chat service with SSE, session auth, file upload, feedback, and output boundary`

### Task 4: Add V2 gates for both new services

**Files modified:**
- `scripts/run_v2_gates.py` — Added `admin-web-ui` and `lawyer-web-chat` gate entries with appropriate PYTHONPATH. The `admin_web_ui_src` and `lawyer_web_chat_src` path variables and compileall entries were already present.
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — Updated gate count assertion from 24 to 26, added `admin-web-ui` and `lawyer-web-chat` to the gate name assertions.

**Commits:** `551e3a3` — `feat(57-01): add V2 gates for admin-web-ui and lawyer-web-chat services`, `6697a1d` — `fix(57-01): update V2 gate count test for admin-web-ui and lawyer-web-chat gates`

## Deviations

- **[Stray truncated files]** The initial commit for admin-web-ui accidentally included stray truncated files (e.g., `README` without `.md`, `__init` without `.py`). These were removed in a follow-up commit (`6bdca43`). The `git add` command was refined to use explicit file paths for subsequent commits.
- **[Gate count test]** The `test_v2_gates_includes_traceability_gate` test in `test_audit_v2_requirements.py` asserted a gate count of 24. Adding 2 new gates (admin-web-ui, lawyer-web-chat) increased the count to 26. The test was updated to assert 26 and include the new gate names.

## Test Results

- **Admin Web UI tests:** 37 tests pass
  - `python3 -m unittest discover -s services/admin-web-ui/tests -v` — OK
- **Lawyer Web Chat tests:** 77 tests pass
  - `python3 -m unittest discover -s services/lawyer-web-chat/tests -v` — OK
- **V2 gate suite:** All 26 gates pass, exit code 0
  - `python3 scripts/run_v2_gates.py` — OK (all gates green)

## FROZEN Contract Surfaces Verified

- `BackendAdapter` Protocol: 9 methods (unchanged)
- `ChannelAdapter` Protocol: 6 methods (unchanged)
- `RunEvent` dataclass: unchanged
- `RunEventType` enum: unchanged
- `admin_console_api.handle_admin_get` signature: consumed, not modified
- `rbac` public API: consumed, not modified
- `encode_sse_event` signature: consumed, not modified
- `WebSseChannelAdapter`: consumed, not modified
- `dependencies = []` invariant preserved — no new external imports at module top level

## Key Design Decisions

1. **Server-side HTML rendering with stdlib `http.server`** — No frontend framework (React/Vue/Preact/Tailwind) introduced. All HTML is generated server-side with `html.escape` on all dynamic content.
2. **Strict CSP header** — `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'` on every response, blocking inline scripts/styles and external resources.
3. **Security headers** — `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` on every response.
4. **RBAC enforcement** — Admin Web UI uses `resolve_identity` + `RbacGuard.check` for role-based access. Lawyer Web Chat uses RBAC `lawyer` role tokens with `HttpOnly; Secure; SameSite=Strict` cookies.
5. **Output boundary reuse** — Both services wrap `DefaultAssistantOutputBoundary.apply()` with `html.escape` on the resulting visible text. Blocked content is dropped; rewritten content uses the owned service notice.
6. **SSE encoding reuse** — Lawyer Web Chat reuses `encode_sse_event` from `inkstatute_channels_web_sse` for SSE frame encoding, with the output boundary applied per event.
7. **File upload reference-only** — `FileUploadHandler` stores `payload_ref`/`content_ref` and SHA-256 hash only. No raw legal text is persisted.
8. **Feedback normalization** — `FeedbackHandler` reuses the `WebSseChannelAdapter` normalization pattern, producing `FeedbackEvent` records with proper action classification and skill candidate detection.
9. **Multi-device sync** — `SessionStore` supports adding devices to existing sessions and listing sessions per conversation, enabling multi-device sync via shared session_id.
