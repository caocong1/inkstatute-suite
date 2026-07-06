# Lawyer Web Chat

Server-side rendered lawyer web chat with real SSE streaming for InkStatute V2.

Built on Python stdlib `http.server` with server-side HTML templates and real
Server-Sent Events. All dynamic content is rendered as HTML-escaped plaintext
(`html.escape`) — never `innerHTML`. A strict Content-Security-Policy header
is set on every response.

## Feature Flag

Gated by `lawyer_web_chat_enabled` (default `False`). When disabled, the server
returns HTTP 503.

## Features

- **Session authentication** — RBAC `lawyer` role tokens (HMAC-SHA256 signed)
  set as `HttpOnly; Secure; SameSite=Strict` cookies
- **Real SSE streaming** — uses `encode_sse_event` from `inkstatute_channels_web_sse`
  with output boundary applied per event
- **Message history** — in-memory server-side store (reference-only)
- **File upload** — stores `payload_ref`/`content_ref` only (no raw legal payloads)
- **Feedback submission** — normalizes feedback via `WebSseChannelAdapter` pattern
- **Multi-device sync** — server-side session state shared via session_id

## Output Boundary

Enforces the same output boundary as WeCom — no backend notices
(gateway/meta/system/update/command) reach the lawyer. All text is filtered
through `DefaultAssistantOutputBoundary` before rendering.

## Endpoints

- `GET /` — Chat interface (login form + chat UI)
- `POST /login` — Issue RBAC token, set HttpOnly cookie
- `GET /history` — Message history for the authenticated session
- `GET /stream` — SSE streaming endpoint
- `POST /upload` — File upload (reference-only)
- `POST /feedback` — Feedback submission
- `GET /sessions` — Session list (multi-device sync)
