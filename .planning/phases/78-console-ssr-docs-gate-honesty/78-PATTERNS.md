# Phase 78: Console SSR, Docs & Gate Honesty - Pattern Map

**Mapped:** 2026-07-11
**Files analyzed:** 11
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `services/admin-web-ui/src/admin_web_ui/dashboard.py` | view | request-response | `services/admin-web-ui/src/admin_web_ui/dashboard.py` (existing) | exact |
| `services/admin-web-ui/src/admin_web_ui/channels.py` | view | request-response | `services/admin-web-ui/src/admin_web_ui/providers.py` | role-match |
| `services/admin-web-ui/src/admin_web_ui/server.py` | controller | request-response | `services/admin-web-ui/src/admin_web_ui/server.py` (existing `_handle_providers`, `_handle_catalog`, `_handle_vision`) | exact |
| `services/admin-web-ui/src/admin_web_ui/providers.py` | view | request-response | `services/admin-web-ui/src/admin_web_ui/providers.py` (existing) | exact |
| `services/admin-web-ui/src/admin_web_ui/catalog.py` | view | request-response | `services/admin-web-ui/src/admin_web_ui/catalog.py` (existing) | exact |
| `services/admin-web-ui/src/admin_web_ui/vision.py` | view | request-response | `services/admin-web-ui/src/admin_web_ui/vision.py` (existing) | exact |
| `services/admin-web-ui/tests/test_dashboard.py` | test | request-response | `services/admin-web-ui/tests/test_dashboard.py` (existing) | exact |
| `services/admin-web-ui/tests/test_channels_form.py` | test | request-response | `services/admin-web-ui/tests/test_providers_form.py` | role-match |
| `README.md` | doc | static | `README.md` (existing) | exact |
| `.env.example` | config | static | `.env.example` (existing) | exact |
| `runbook/OPERATOR_CONFIG_RUNBOOK.md` | doc | static | `runbook/SMOKE_TEST_RUNBOOK.md` | role-match |

## Pattern Assignments

### `services/admin-web-ui/src/admin_web_ui/dashboard.py` (view, request-response)

**Analog:** `services/admin-web-ui/src/admin_web_ui/dashboard.py` (current code)

**Imports pattern** (lines 1-16):
```python
import html
from typing import Any, Mapping

from rbac import Identity

from .boundary import AdminUiBoundary
```

**Page chrome pattern** (lines 68-165):
```python
def _page_template(title: str, body: str, identity: Identity | None = None) -> str:
    ...
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  ...
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; padding: 0; background: #f5f5f5; color: #222; }}
    .header {{ background: #1a1a2e; color: #fff; padding: 1rem 2rem; }}
    .header h1 {{ margin: 0; font-size: 1.25rem; }}
    .nav {{ background: #16213e; padding: 0.5rem 2rem; display: flex; gap: 1rem; flex-wrap: wrap; }}
    .nav-link {{ color: #aaccff; text-decoration: none; font-size: 0.9rem; }}
    ...
  </style>
</head>
<body>
  ...
</body>
</html>"""
```

**Section rendering pattern** (lines 168-220):
```python
def render_dashboard(section: str, data: dict[str, Any], identity: Identity | None = None, boundary: AdminUiBoundary | None = None) -> str:
    if boundary is None:
        boundary = AdminUiBoundary()
    title = title_map.get(section, "Admin Dashboard")
    if "error" in data:
        ...
    if section == "index":
        body = _render_index(data, boundary)
    elif section == "gates":
        body = _render_gates_section(data, boundary)
    ...
    return _page_template(title, body, identity)
```

**Key excerpts for Phase 78 changes:**
- Update `.header h1` style to `font-size: 1.25rem; font-weight: 600; line-height: 1.2;`.
- Update `.section h2` and `.card h3` to `font-size: 1.125rem; font-weight: 600; line-height: 1.2;`.
- Update `.nav-link` to `font-size: 0.875rem; font-weight: 600;`.
- Update `.identity` to `font-size: 0.875rem; font-weight: 600;`.
- Update `.data-table` to `font-size: 0.875rem;`.
- Add `.notice-honesty` CSS: `background: #f5f8ff; border: 1px solid #aaccff; border-radius: 6px; padding: 16px; margin-bottom: 16px;`.
- Add `_render_gate_honesty_banner` helper and `_render_carried_human_gates_card` helper.
- Update `_render_index` to include config cards and a gate-honesty card.
- Update `_render_gates_section` to include the “Carried human gates” card.

### `services/admin-web-ui/src/admin_web_ui/channels.py` (view, request-response)

**Analog:** `services/admin-web-ui/src/admin_web_ui/providers.py` (signed CSRF + form render)

**Imports pattern** (lines 1-22):
```python
from __future__ import annotations

import html
from typing import Any, Mapping
from urllib.parse import parse_qs

from rbac import Identity

from .boundary import AdminUiBoundary
from .dashboard import _page_template
```

**Form render pattern** (lines 255-303 in channels.py; lines 374-442 in providers.py):
```python
def render_channels_form(
    api_data: Mapping[str, Any],
    *,
    csrf_token: str | None = None,
    read_only: bool = False,
    flash: str | None = None,
    flash_kind: str = "success",
    error_message: str | None = None,
) -> str:
    ...
    parts.append(f'    <form method="post" action="/config/channels" class="channels-form">')
    token = csrf_token or ""
    parts.append(f'      <input type="hidden" name="csrf_token" value="{html.escape(token, quote=True)}">')
    ...
```

**Key changes for Phase 78:**
- Import `_render_gate_honesty_banner` from `dashboard.py` and insert it at the top of `render_channels_form` before flash/error.
- Update `ERROR_VALIDATION` to use the exact UI-SPEC error: “Invalid config. Check the fields and try again.”.
- Add `ERROR_CSRF` constant: “Request could not be verified. Refresh the page and try again.”.
- Keep ref-input escaping and refs-only behavior.
- Consider changing `_bool_status(False)` from `status-err` to `empty` per UI-SPEC (routine OFF should be muted).

### `services/admin-web-ui/src/admin_web_ui/server.py` (controller, request-response)

**Analog:** `services/admin-web-ui/src/admin_web_ui/server.py` `_handle_providers` (lines 665-804) and `_handle_catalog` (lines 979-1087)

**CSRF token issue/validate pattern** (lines 684-690, 998-1003):
```python
save_token = issue_csrf_token(identity, _PROVIDERS_PATH, signing_key=rbac_secret)
probe_token = issue_csrf_token(identity, _PROBE_PATH, signing_key=rbac_secret)

if http_method == "POST":
    valid, form_map = _validate_post_csrf(body, identity, _PROVIDERS_PATH, rbac_secret=rbac_secret)
    if not valid:
        html_body = render_providers_page(
            {"error": {"code": "forbidden", "message": PROVIDERS_ERROR_FORBIDDEN}},
            identity=identity,
            csrf_token=save_token,
            probe_csrf_token=probe_token,
        )
        return 403, html_body, response_headers
```

**Key change for `_handle_channels`:**
- Replace `csrf_token = secrets.token_urlsafe(16)` with `save_token = issue_csrf_token(identity, _CHANNELS_PATH, signing_key=rbac_secret)`.
- On POST, call `_validate_post_csrf(body, identity, _CHANNELS_PATH, rbac_secret=rbac_secret)` before `parse_channels_form`.
- On CSRF failure, render `render_channels_page` with `error_message=ERROR_CSRF` and a fresh token.
- Keep the `_channels_post_body_usable` check and metadata preservation.

### `services/admin-web-ui/src/admin_web_ui/providers.py` (view, request-response)

**Analog:** `services/admin-web-ui/src/admin_web_ui/providers.py` (existing code)

**Form render pattern** (lines 374-442):
```python
def render_providers_form(
    api_data: Mapping[str, Any],
    *,
    csrf_token: str | None = None,
    probe_csrf_token: str | None = None,
    read_only: bool = False,
    flash: str | None = None,
    flash_kind: str = "success",
    error_message: str | None = None,
    probe_result: Mapping[str, Any] | None = None,
) -> str:
    ...
```

**Key change for Phase 78:**
- Import `_render_gate_honesty_banner` from `dashboard.py` and insert it at the top of `render_providers_form`.
- Optionally update empty/error copy to exact UI-SPEC strings.

### `services/admin-web-ui/src/admin_web_ui/catalog.py` (view, request-response)

**Analog:** `services/admin-web-ui/src/admin_web_ui/catalog.py` (existing code)

**Form render pattern** (lines 159-227):
```python
def render_catalog_form(
    api_data: Mapping[str, Any],
    *,
    csrf_token: str | None = None,
    read_only: bool = False,
    flash: str | None = None,
    flash_kind: str = "success",
    error_message: str | None = None,
) -> str:
    ...
```

**Key change for Phase 78:**
- Import `_render_gate_honesty_banner` from `dashboard.py` and insert it at the top of `render_catalog_form`.

### `services/admin-web-ui/src/admin_web_ui/vision.py` (view, request-response)

**Analog:** `services/admin-web-ui/src/admin_web_ui/vision.py` (existing code)

**Form render pattern** (lines 357-442):
```python
def render_vision_form(
    api_data: Mapping[str, Any],
    *,
    csrf_token: str | None = None,
    probe_csrf_token: str | None = None,
    read_only: bool = False,
    flash: str | None = None,
    flash_kind: str = "success",
    error_message: str | None = None,
    probe_result: Mapping[str, Any] | None = None,
) -> str:
    ...
```

**Key change for Phase 78:**
- Import `_render_gate_honesty_banner` from `dashboard.py` and insert it at the top of `render_vision_form`.

### `services/admin-web-ui/tests/test_channels_form.py` (test, request-response)

**Analog:** `services/admin-web-ui/tests/test_providers_form.py` (existing CSRF/form tests)

**Test patterns to copy:**
- Use `csrf = _try_import_csrf()` and `csrf.issue_csrf_token(identity, route, signing_key=self.SECRET)`.
- Send `csrf_token` in POST form body.
- Assert `put_calls` is populated when valid, empty when token is missing/malformed/cross-route.
- Assert 403 response and the exact CSRF error copy when token is invalid.

**Key additions for Phase 78:**
- Update `test_post_proxies_put_and_shows_restart_flash` to use a valid CSRF token.
- Add `test_post_rejects_missing_csrf_token`.
- Add `test_post_rejects_invalid_csrf_token`.
- Add `test_post_rejects_cross_route_csrf_token`.
- Add `test_page_contains_gate_honesty_banner`.

### `services/admin-web-ui/tests/test_dashboard.py` (test, request-response)

**Analog:** `services/admin-web-ui/tests/test_dashboard.py` (existing)

**Key additions for Phase 78:**
- `test_index_contains_gate_honesty_banner`.
- `test_index_contains_config_cards`.
- `test_gates_contains_carried_human_gates_card`.
- `test_gate_honesty_forbidden_phrases_absent`.

### `README.md`, `.env.example`, `services/admin-web-ui/README.md`, `runbook/OPERATOR_CONFIG_RUNBOOK.md`

**Analog:** `runbook/SMOKE_TEST_RUNBOOK.md` (existing gate-honesty / operator docs)

**Key pattern:**
- Use exact gate-honesty wording.
- Document env/ref keys only, not values.
- Reference `not_live_acceptance` and carried human gates.
- Avoid forbidden phrases listed in `78-UI-SPEC.md`.

## Shared Patterns

### Authentication / Authorization

- `handle_admin_web_ui_request` resolves `identity` via `rbac.resolve_identity` and checks `RbacGuard.check(role, _guard_path(route_path))`.
- `/config/*` guard path is `/config`; only `ADMIN` and `OPERATOR` roles may GET/PUT; `LAWYER`/`VIEWER` are denied.

### CSRF

- `issue_csrf_token(identity, route, signing_key=rbac_secret)` returns `nonce.signature`.
- `validate_csrf_token(token, identity, route, signing_key=rbac_secret)` uses `hmac.compare_digest`.
- `_validate_post_csrf` parses the form body, extracts the `csrf_token` field, and validates before any proxy.

### Error Handling

- `error` dicts from `handle_admin_put` are mapped to UI copy:
  - `code == "forbidden"` → permission error
  - `code == "operator_config_disabled"` → flag-off error
  - `code == "invalid_config"` → validation error
  - otherwise → generic error
- Form is re-rendered with the current API data and error message.

### HTML Escaping

- `_esc(value)` = `html.escape(str(value), quote=True)` is used in all form modules.
- `AdminUiBoundary` filters backend noise before rendering in dashboard contexts.

### Testing

- Tests use `tempfile` for `OperatorConfigStore`, `rbac.issue_token` for auth, `RuntimeFeatureFlags`, and fake `handle_admin_get`/`handle_admin_put`/`handle_config_probe` callables.
- PYTHONPATH includes `services/admin-web-ui/src`, `services/admin-console-api/src`, `packages/rbac/src`, `packages/platform-runtime/src`, `packages/operator-config/src`, `packages/platform-contract/src`, `services/conversation-read-view/src`, `services/feedback-service/src`.
