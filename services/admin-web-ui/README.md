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
roles may view operational endpoints (`/feedback`, `/health`, `/gates`) and
channel config (`/config/channels`); `lawyer`/`viewer` roles see only case data
(`/sessions`, `/tasks`).

## Endpoints

- `GET /` — Dashboard index with navigation
- `GET /sessions` — Session/task inspection (conversations)
- `GET /tasks` — Task inspection
- `GET /feedback` — Feedback review queue
- `GET /health` — Health monitoring
- `GET /gates` — Gate status display
- `GET /config/channels` — Incremental Channel Config SSR form (QQ + WeCom)
- `POST /config/channels` — Save channel section via `handle_admin_put` proxy

Operational routes remain GET-only. Config mutate is limited to
`POST /config/channels` in this milestone slice.

## Channel Config (Phase 75 incremental)

The Channel Config page shows dual-knob enablement (platform flag read-only +
host `enabled` editable + derived effective) and secret-**ref** text fields only
(`env:…` / `secret://…`). It never resolves secrets and never offers a single
bypass toggle.

**Apply semantics (MVP):** saving persists to the operator config store.
Channel hosts read config at startup — **restart QQ/WeCom hosts to apply**.
There is no hot-reload claim in this UI.

**CSRF:** forms include a `csrf_token` hidden field. Complete CSRF-protected SSR
surface verification and honesty docs are owned by **Phase 78** — this
incremental form does **not** claim CSRF-complete coverage.

**Human gates:** saving channel config does **not** close carried live WeCom /
lawyer-trial / QQ `--live` acceptance gates.

## Data path

Read data is proxied from `admin_console_api.handle_admin_get`. Channel Config
POST proxies `admin_console_api.handle_admin_put` for `/config/channels` only.
