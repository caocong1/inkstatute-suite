# Phase 78 — Research Notes

**Phase:** 78 — Console SSR, Docs & Gate Honesty  
**Research:** skipped (`--skip-research`); built from existing context, UI-SPEC, and codebase pattern mapping.  
**Date:** 2026-07-11

## User Constraints

Copied from `78-CONTEXT.md` (locked decisions):

- Extend `services/admin-web-ui` stdlib `http.server` + escaped HTML + CSP. Do **not** introduce React, Vite, Next, or shadcn (D-01).
- All mutating config routes (`/config/channels`, `/config/providers`, `/config/catalog`, `/config/vision`, `/config/providers/probe`) use signed, route-bound CSRF tokens (D-07).
- `/config/channels` upgrades from the Phase 75 placeholder random token to the signed pattern (D-10).
- Gate-honesty banner appears on every config page, `/`, and `/gates` with exact UI-SPEC copy (D-04).
- Gate Status page adds a “Carried human gates” card (D-05).
- Dashboard index adds config section cards and a gate-honesty card (D-06).
- Operator docs update `README.md`, `.env.example`, runbook, and `services/admin-web-ui/README.md` (D-16..D-19).
- No raw secrets, resolved values, store paths, probe bodies, or `api_key_ref` values rendered (D-13).
- Smoke/config evidence must never auto-claim Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ live acceptance (D-20, D-21).

## Standard Stack

- **Runtime:** Python 3.12+ stdlib (`http.server`, `html`, `urllib.parse`, `secrets`, `hmac`, `json`).
- **Templating:** Python `html.escape` string concatenation (no Jinja/React) `[ASSUMED]`.
- **Security:** `rbac` package for identity/role; `admin_web_ui.csrf` for nonce+HMAC-SHA256 tokens.
- **Config store:** `packages/operator-config` `OperatorConfigStore` (refs-only, no secret resolution).
- **Admin API:** `services/admin-console-api` `handle_admin_get` / `handle_admin_put` / `handle_config_probe`.

## Architecture Patterns

- **SSR page pattern:** `render_{section}_page(api_data, identity, csrf_token, ...)` wraps `_page_template(title, body, identity)` from `dashboard.py`.
- **Form pattern:** `render_{section}_form` returns the body HTML; includes hidden `csrf_token`, restart notice, fields, and primary CTA.
- **POST pattern:** `handle_admin_web_ui_request` dispatches → `_validate_post_csrf` → `parse_{section}_form` → `client.proxy_put` → re-render with flash/error.
- **Probe pattern:** separate `POST /config/providers/probe` form with its own route-bound CSRF token and `target`/`return_to` fields; re-renders provider or vision page.
- **Refs-only boundary:** UI stores and displays secret refs (`env:…`, `secret://…`) but never resolves them; `api_key_ref` is a text input.

## Don't Hand-Roll

- Do **not** implement a custom CSRF scheme — reuse `admin_web_ui/csrf.py` `[VERIFIED: codebase]`.
- Do **not** implement a new UI stack — reuse `dashboard._page_template` and existing CSS classes `[VERIFIED: codebase]`.
- Do **not** write a new admin config API — existing `admin_console_api` `/config/*` endpoints provide GET/PUT/probe `[VERIFIED: codebase]`.
- Do **not** resolve secret refs in the UI layer — use ref strings and trust the admin-console-api / host process to validate shapes only `[VERIFIED: codebase]`.

## Common Pitfalls

- **Cross-route token reuse:** a token issued for `/config/providers` must fail on `/config/catalog` or `/config/providers/probe`. `validate_csrf_token` binds `route` in the canonical payload.
- **Channels CSRF gap:** `channels.py` currently renders a random token and `server.py` `_handle_channels` does not call `validate_csrf_token`. Phase 78 must replace this.
- **HTML injection:** any API value placed in HTML must pass through `html.escape(str(value), quote=True)`. `AdminUiBoundary` only filters backend noise; explicit escaping is still required for form values.
- **Secret leakage in error/flash copy:** never echo the `csrf_token` in error messages; never include resolved secrets, base URLs, or probe response bodies in rendered text.
- **Gate-honesty wording drift:** never use “live wecom uat passed”, “lawyer trial acceptance complete”, “live qq openapi acceptance”, or “live provider reachability” in any output or docs.
- **Feature-flag disabled state:** when `operator_config_enabled` is OFF, the form should still render but submit buttons are disabled and a `.error` flash shows the flag-off copy.
- **Probe result color semantics:** success = `.status-ok`; failure = `.status-err`; routine “not configured” / “not required” = `.empty` (muted), not red.

## Code Examples

### Issuing a route-bound CSRF token

```python
# services/admin-web-ui/src/admin_web_ui/server.py
from admin_web_ui.csrf import issue_csrf_token

csrf_token = issue_csrf_token(identity, "/config/channels", signing_key=rbac_secret)
```

### Validating a CSRF token before proxying

```python
# services/admin-web-ui/src/admin_web_ui/server.py
from admin_web_ui.csrf import validate_csrf_token
from urllib.parse import parse_qs

text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body or "")
form_map = parse_qs(text, keep_blank_values=True)
raw_token = form_map.get("csrf_token")
token = raw_token[0] if isinstance(raw_token, list) and raw_token else str(raw_token or "")
if not validate_csrf_token(token, identity, "/config/channels", signing_key=rbac_secret):
    html_body = render_channels_page(
        {"error": {"code": "forbidden", "message": "..."}},
        identity=identity,
        csrf_token=issue_csrf_token(identity, "/config/channels", signing_key=rbac_secret),
    )
    return 403, html_body, response_headers
```

### Gate-honesty banner HTML

```html
<div class="notice-honesty" role="note" aria-label="Gate honesty notice">
  <p class="notice-honesty-heading">This console does not close live acceptance gates</p>
  <p class="notice-honesty-body">Saving config or running a probe does not claim Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ live acceptance. Smoke and probe evidence remains <code>not_live_acceptance</code>.</p>
</div>
```

### Rendering a config page with banner

```python
# services/admin-web-ui/src/admin_web_ui/channels.py
from admin_web_ui.dashboard import _page_template

body_parts = [
    _render_gate_honesty_banner(),
    _flash_html(error_message, kind="error"),
    _render_qqbot_panel(...),
    _render_wecom_panel(...),
    ...
]
body = "\n".join(body_parts)
return _page_template("Channel Config", body, identity)
```

## Out of Scope

- Hot-reload without restart (CFG-F01).
- New React/Next/Vite/SPA stack.
- Auto-closing carried human gates.
- Raw secret storage or in-console secret resolution.

## Assumptions / Low-Confidence Items

- No new external packages are required (`[ASSUMED]`).
- Existing `pytest` and `unittest` runner setup is sufficient for new tests (`[ASSUMED]`).
