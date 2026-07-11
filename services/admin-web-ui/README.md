# Admin Web UI

Server-side rendered operator dashboard and config console for InkStatute V2.

Built on Python stdlib `http.server` with server-side HTML templates. All dynamic
content is rendered as HTML-escaped plaintext (`html.escape`) — never `innerHTML`.
A strict Content-Security-Policy header (`default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`)
is set on every response.

## Feature Flag

Gated by `admin_web_ui_enabled` (default `False`). When disabled, the server
returns HTTP 503.

## RBAC

Access is enforced via the `rbac` package (Phase 51). Only `admin`/`operator`
roles may view operational endpoints (`/feedback`, `/health`, `/gates`) and all
config pages (`/config/*`); `lawyer`/`viewer` roles see only case data
(`/sessions`, `/tasks`).

## Endpoints

- `GET /` — Dashboard index with navigation and config section cards
- `GET /sessions` — Session/task inspection (conversations)
- `GET /tasks` — Task inspection
- `GET /feedback` — Feedback review queue
- `GET /health` — Health monitoring
- `GET /gates` — Gate status display with carried human gates card
- `GET /config/channels` — Channel Config SSR form (QQ + WeCom)
- `POST /config/channels` — Save channel section via `handle_admin_put` proxy
- `GET /config/providers` — Provider Config SSR form (built-in + custom providers)
- `POST /config/providers` — Save provider registry
- `POST /config/providers/probe` — Non-destructive connectivity probe
- `GET /config/catalog` — Model Catalog SSR form (main model selection)
- `POST /config/catalog` — Save catalog selection
- `GET /config/vision` — Vision Config SSR form (routing mode + vision model)
- `POST /config/vision` — Save vision config

Operational routes remain GET-only. Config mutate is limited to `POST /config/*`
with a valid, signed, route-bound CSRF token.

## Security Model

- Pages are server-side rendered with Python `html.escape` on every dynamic value.
- Every mutating config form (`/config/channels`, `/config/providers`, `/config/catalog`, `/config/vision`, `/config/providers/probe`) includes a hidden `csrf_token`.
- CSRF tokens are signed with HMAC-SHA256 and bound to the caller identity (`role` + `tenant`) and the exact route via `admin_web_ui/csrf.py`. A token issued for one route fails on another.
- `admin_web_ui/csrf.py` provides `issue_csrf_token` and `validate_csrf_token`; callers pass the shared `RBAC_TOKEN_SECRET` as the signing key for cross-process validity.
- Secrets are accepted and displayed as refs only (`env:NAME`, `secret://path/segments`). The UI never resolves or stores raw secret values.
- Probe and save actions do not claim live acceptance. The UI is not a substitute for Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ `--live` acceptance.

## Gate Honesty

Every config page and the dashboard index render a gate-honesty notice:

> This console does not close live acceptance gates.
> Saving config or running a probe does not claim Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ live acceptance. Smoke and probe evidence remains `not_live_acceptance`.

The Gate Status page (`/gates`) also adds a "Carried human gates" card with the same message.

## Config Console

- **Channel Config** — dual-knob enablement (platform flag read-only, host `enabled` editable, effective derived), secret-ref fields.
- **Provider Config** — built-in vendor profiles (OpenAI, Anthropic) with read-only canonical URLs and custom OpenAI-compatible endpoints with editable URL and allowlist.
- **Model Catalog** — main model selection from the built-in catalog; `supports_vision` badges drive Phase 77 routing.
- **Vision Config** — routing mode (`auto`, `always_preprocess`, `main_only`) and optional dedicated vision provider/model.

**Apply semantics (MVP):** saving persists to the operator config store. Runtime reads config at startup — **restart the runtime to apply**. There is no hot-reload claim in this UI.

See [`runbook/OPERATOR_CONFIG_RUNBOOK.md`](../runbook/OPERATOR_CONFIG_RUNBOOK.md) for operator step-by-step instructions.

## Data Path

Read data is proxied from `admin_console_api.handle_admin_get`. Config POSTs
proxy `admin_console_api.handle_admin_put` for the relevant `/config/*` section.
