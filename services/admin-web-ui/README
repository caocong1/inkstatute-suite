# Admin Web UI

Server-side rendered operator dashboard for InkStatute V2.

Built on Python stdlib `http.server` with server-side HTML templates. All dynamic
content is rendered as HTML-escaped plaintext (`html.escape`) — never `innerHTML`.
A strict Content-Security-Policy header is set on every response.

## Feature Flag

Gated by `admin_web_ui_enabled` (default `False`). When disabled, the server
returns HTTP 503.

## RBAC

Access is enforced via the `rbac` package (Phase 51). Only `admin`/`operator`
roles may view operational endpoints (`/feedback`, `/health`, `/gates`);
`lawyer`/`viewer` roles see only case data (`/sessions`, `/tasks`).

## Endpoints

- `GET /` — Dashboard index with navigation
- `GET /sessions` — Session/task inspection (conversations)
- `GET /tasks` — Task inspection
- `GET /feedback` — Feedback review queue
- `GET /health` — Health monitoring
- `GET /gates` — Gate status display

All data is proxied from `admin_console_api.handle_admin_get` read endpoints.
