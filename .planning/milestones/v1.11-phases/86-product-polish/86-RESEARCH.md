# Phase 86: Product Polish — Research

**Phase**: 86 (Product Polish)
**Requirements**: POLISH-01, POLISH-02, POLISH-03, POLISH-04, POLISH-05
**Researcher**: gsd-phase-researcher
**Date**: 2026-07-14

## User Constraints

> Copied verbatim from `86-CONTEXT.md`. Discuss phase was skipped (`workflow.skip_discuss: true`), so all implementation choices are at Claude's discretion.

### Decisions (Locked)

None — discuss phase was skipped. No locked decisions.

### Claude's Discretion

All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas

None — discuss phase skipped.

### Hard Project Constraints (from AGENTS.md + ROADMAP, non-negotiable)

- **stdlib-only**: `dependencies = []` in every `pyproject.toml`. No Flask/FastAPI/Django, no React/Vue SPA, no WebSocket/SSE libs, no `psutil`, no `celery`/`dramatiq`/`rq`, no TLS termination in-console, no process auto-restart watchdog. `[VERIFIED: AGENTS.md + ROADMAP.md L37]`
- **No new DB/queue/SPA**: Atomic JSON suffices; HTTP polling for logs. `[VERIFIED: AGENTS.md + ROADMAP.md L37]`
- **Privacy/scrubbing**: Never commit secrets, raw legal payloads, or stack traces to the browser. Contract logs prefer `raw_payload_ref`. `[VERIFIED: AGENTS.md L30-37]`
- **Gate honesty**: Automated gate results and probe/smoke evidence never claim Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ live acceptance. `[VERIFIED: REQUIREMENTS.md OBS-10, ROADMAP.md]`
- **All new feature flags default OFF**. `[VERIFIED: ROADMAP.md L37]`

## Project Constraints (from AGENTS.md)

| Directive | Source | Enforcement |
|-----------|--------|-------------|
| stdlib-only (`dependencies = []`) | AGENTS.md L44, ROADMAP.md L37 | No new third-party imports in any phase code |
| No new service/DB/queue/runtime dep | AGENTS.md L44 | Reuse existing admin-web-ui + admin-console-api |
| Never commit secrets/raw payloads | AGENTS.md L32 | Error pages must not leak stack traces or secrets |
| Keep changes scoped to active phase | AGENTS.md L41 | All edits within admin-web-ui, admin-console-api, scripts/, .env.example |
| Add tests with behavior changes | AGENTS.md L42 | New error pages, nav, startup script need unit tests |
| Update docs/GSD artifacts on decisions | AGENTS.md L45 | .env.example and runbook updates are in-scope |

## Standard Stack

> This phase introduces **no new libraries**. It polishes the existing stdlib SSR console. All work is within the existing stack.

| Component | Technology | Version | Source |
|-----------|-----------|---------|--------|
| Web UI server | `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` | Python ≥3.11 stdlib | `[VERIFIED: services/admin-web-ui/src/admin_web_ui/__main__.py L10]` |
| API server | `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` | Python ≥3.11 stdlib | `[VERIFIED: services/admin-console-api/src/admin_console_api/server.py L12]` |
| SSR rendering | `html.escape()` + f-string templates (no template engine) | stdlib | `[VERIFIED: services/admin-web-ui/src/admin_web_ui/dashboard.py L18-20]` |
| Test framework | `unittest` (not pytest) | stdlib | `[VERIFIED: scripts/run_v2_gates.py L144-150]` |
| Gate runner | `scripts/run_v2_gates.py` | project-specific | `[VERIFIED: scripts/run_v2_gates.py]` |
| Process orchestration | `subprocess.Popen` + `threading.Lock` | stdlib | `[VERIFIED: services/admin-console-api/src/admin_console_api/process_supervisor.py L13-16]` |
| Startup script | bash (`set -euo pipefail`) | system bash | `[VERIFIED: scripts/start-hindsight.sh pattern]` |

**No packages to install.** Package Legitimacy Audit is not applicable — this phase adds zero external dependencies.

## Architecture Patterns

### System Architecture Diagram

```
Operator (browser)
  │
  ├── HTTP GET/POST ──► AdminWebUiServer (ThreadingHTTPServer, port 8080)
  │                        │
  │                        ├── _page_template(title, body, identity)  ← shared nav + CSS
  │                        │     └── nav_items[] (hardcoded list, NO active-state)
  │                        │
  │                        ├── handle_admin_web_ui_request(path, ...)
  │                        │     ├── feature flag gate → 503 dashboard
  │                        │     ├── /login /logout → auth.py
  │                        │     ├── route lookup → _SECTION_MAP
  │                        │     │     └── unknown → 404 (dashboard error block)
  │                        │     ├── RBAC auth → 401
  │                        │     ├── RBAC guard → 403
  │                        │     └── section handlers → render_*_page()
  │                        │
  │                        └── AdminWebUiServer._dispatch()  ← NO try/except (GAP)
  │                              └── uncaught Exception → BaseHTTPRequestHandler
  │                                    → stderr stack trace + blank/default 500 (GAP)
  │
  └── start-console.sh (NEW)
       ├── source .env
       ├── python -m admin_console_api &  → API (port 8081)
       ├── python -m admin_web_ui &       → UI  (port 8080)
       ├── write PIDs → .inkstatute/console-pids.json
       └── trap EXIT → kill both children

AdminConsoleApiServer (ThreadingHTTPServer, port 8081)
  └── _dispatch()  ← HAS try/except (safe)
        └── Exception → JSON 500 {internal_error} + stderr traceback (no browser leak)
```

### Existing SSR Rendering Pattern (CRITICAL — all pages follow this)

Every page renderer calls `_page_template(title, body, identity)` from `dashboard.py`. This is the single shared HTML skeleton that produces the full `<!DOCTYPE html>` document with nav, CSS, and CSP. `[VERIFIED: services/admin-web-ui/src/admin_web_ui/dashboard.py L68-189]`

```python
# dashboard.py L68-189 — _page_template is the shared shell
def _page_template(title: str, body: str, identity: Identity | None = None) -> str:
    nav_items = [
        ("/", "Dashboard"),
        ("/sessions", "Sessions"),
        ("/tasks", "Tasks"),
        ("/feedback", "Feedback Review"),
        ("/health", "Health"),
        ("/gates", "Gates"),
        ("/reports", "Reports"),
        ("/logs", "Logs"),
        ("/audit", "Audit Trail"),
        ("/config/channels", "Channel Config"),
        ("/config/providers", "Provider Config"),
        ("/config/catalog", "Model Catalog"),
        ("/config/vision", "Vision Config"),
        ("/login", "Login"),
        ("/logout", "Logout"),
    ]
    nav_links = "\n".join(
        f'      <a href="{_esc(href)}" class="nav-link">{_esc(label)}</a>'
        for href, label in nav_items
    )
    # ... <style> block, <div class="nav">{nav_links}</div>, <div class="main">{body}</div>
```

**Key observations:**
1. `nav_items` is a hardcoded list — no active-state CSS class, no `aria-current="page"`. `[VERIFIED: dashboard.py L71-91]`
2. All pages already share this nav (channels.py, providers.py, logs.py, audit.py, auth.py all import `_page_template`). `[VERIFIED: channels.py L16, providers.py L22, logs.py L15, audit.py L16, auth.py L26]`
3. Login/Logout are always in nav regardless of auth state. `[VERIFIED: dashboard.py L85-86]`
4. CSS is inline in `<style>` — CSP allows `style-src 'self' 'unsafe-inline'`. `[VERIFIED: server.py L94]`
5. Viewport meta tag already present: `<meta name="viewport" content="width=device-width, initial-scale=1">`. `[VERIFIED: dashboard.py L102]`

### Existing Error Handling (GAP for POLISH-01)

| Scenario | Current Behavior | File:Line | Gap |
|----------|-----------------|-----------|-----|
| Unknown route (404) | Renders dashboard with `{"error": {"code": "not_found", ...}}` inside `_page_template` — has nav but is not a dedicated 404 page | `server.py L289-295` | Not a dedicated 404 page with "back to dashboard" CTA; message includes raw route path (escaped, safe) |
| Uncaught exception in UI (500) | **No try/except in `AdminWebUiServer._dispatch()`** — `BaseHTTPRequestHandler` prints stack trace to stderr and sends default 500 with no HTML body | `server.py L1959-1985` | **Major gap**: blank/default 500 response, potential stack trace leak via stderr (not browser, but no proper error page) |
| Uncaught exception in API (500) | `AdminConsoleApiServer._dispatch()` has try/except → JSON `{"error": {"code": "internal_error", ...}}` + `traceback.print_exc(file=sys.stderr)` | `server.py L125-133` (API) | Already safe — no stack trace to browser, generic message. But UI proxy failures render as dashboard error blocks, not dedicated 500 pages |
| Feature flag off (503) | Renders dashboard with `admin_web_ui_disabled` error | `server.py L243-251` | Works but not a dedicated error page |
| Auth failure (401) | Renders dashboard with `unauthorized` error | `server.py L328-335` | Works but not a dedicated error page |
| Forbidden (403) | Renders section-specific page with `forbidden` error | `server.py L348-378` | Works but inconsistent across sections |
| Oversized POST (413) | Inline HTML `<p class="error">Request body too large</p>` — NOT using `_page_template` | `server.py L1943-1954` | No nav, no CSP on this response, inconsistent with rest of UI |

**POLISH-01 requires:** Dedicated 404 and 500 SSR pages that:
- Use `_page_template` (so they have nav with "back to dashboard")
- Escape all dynamic content
- Never include stack traces or secrets
- Wrap `AdminWebUiServer._dispatch()` in try/except to catch uncaught exceptions

### Existing Entry Points (for POLISH-04 startup script)

Both services have `__main__.py` entry points from Phase 79: `[VERIFIED: __main__.py files]`

| Service | Entry Command | Host Env | Port Env | Default Port |
|---------|--------------|----------|----------|--------------|
| admin-web-ui | `python -m admin_web_ui` | `ADMIN_WEB_UI_HOST` | `ADMIN_WEB_UI_PORT` | 8080 |
| admin-console-api | `python -m admin_console_api` | `ADMIN_CONSOLE_API_HOST` | `ADMIN_CONSOLE_API_PORT` | 8081 |

Both use `ThreadingHTTPServer`, `signal.SIGINT`/`SIGTERM` graceful shutdown, and `RuntimeFeatureFlags.require_enabled()` flag gates. `[VERIFIED: admin-web-ui/__main__.py L132-153, admin-console-api/__main__.py L23-46]`

**Existing bash script pattern** (`scripts/start-hindsight.sh`): `[VERIFIED: scripts/start-hindsight.sh]`
- `set -euo pipefail`
- `set -a; source "$ENV_FILE"; set +a` for env loading
- Health-check polling loop with timeout
- Docker-based (not applicable — our services are Python subprocesses)

**No `start-console.sh` exists yet.** `[VERIFIED: ls scripts/ — only start-hindsight.sh, smoke_test.py, run_v2_gates.py, audit scripts]`

### Existing Env Vars (for POLISH-05 .env.example completion)

The `.env.example` file exists (85 lines) but is **missing Phase 85 auth env vars**. `[VERIFIED: .env.example + grep for ADMIN_USERNAME/ADMIN_PASSWORD/SESSION_TTL/SECURE_COOKIE → no matches]`

**Missing from .env.example (introduced in Phase 85):** `[VERIFIED: services/admin-web-ui/src/admin_web_ui/auth.py L54-58, server.py L1902-1914]`

| Env Var | Default | Purpose | Source |
|---------|---------|---------|--------|
| `ADMIN_USERNAME` | `admin` | Login username for session auth | `auth.py L57` |
| `ADMIN_PASSWORD` | (empty = login disabled) | Login password for session auth | `auth.py L58-59` |
| `SESSION_TTL_SECONDS` | `DEFAULT_SESSION_TTL_SECONDS` (from rbac package) | Session cookie TTL in seconds (min 60) | `server.py L1902-1908` |
| `ADMIN_WEB_UI_SECURE_COOKIE` | `false` | Set Secure attribute on session cookie | `server.py L1911-1914` |

**Already documented in .env.example:** `[VERIFIED: .env.example L1-85]`
- Feature flags (`INKSTATUTE_ADMIN_WEB_UI_ENABLED`, `INKSTATUTE_ADMIN_API_ENABLED`, `INKSTATUTE_OPERATOR_CONFIG_ENABLED`, etc.)
- Ports (`ADMIN_WEB_UI_HOST/PORT`, `ADMIN_CONSOLE_API_HOST/PORT`)
- Secrets (`RBAC_TOKEN_SECRET`, `ADMIN_CONSOLE_API_TOKEN`, `ADMIN_WEB_UI_SECRET`)
- Paths (`INKSTATUTE_CONTRACT_LOG_PATH`, `INKSTATUTE_FEEDBACK_QUEUE_PATH`, `INKSTATUTE_OPERATOR_CONFIG_PATH`)
- Reports (`REPORTS_MAX_SCAN_LINES`, `REPORTS_SCAN_LOOKBACK_SECONDS`, `REPORTS_LONG_TASK_THRESHOLD_SECONDS`, `INKSTATUTE_REPORT_DISPLAY_TZ`)
- Process orchestration (`INKSTATUTE_PROCESS_STATE_PATH`, `INKSTATUTE_PROCESS_LOG_DIR`)
- Log viewing (`INKSTATUTE_RUNTIME_AUDIT_PATH`, `LOG_VIEWER_MAX_LINES`)
- QQBot/WeCom host configs
- Provider/vision configs

### Existing Page Structure (Phases 79–85)

All pages are rendered through `_page_template` and share the same nav + CSS: `[VERIFIED: dashboard.py L68-189 + imports across all render modules]`

| Page | Route | Renderer | Phase |
|------|-------|----------|-------|
| Dashboard | `/` | `dashboard.render_dashboard("index", ...)` | v1.7 (57) |
| Sessions | `/sessions` | `dashboard.render_dashboard("sessions", ...)` | v1.6 (42) |
| Tasks | `/tasks` | `dashboard.render_dashboard("tasks", ...)` | v1.6 (42) |
| Feedback | `/feedback` | `dashboard.render_dashboard("feedback", ...)` | v1.6 (42) |
| Health | `/health` | `dashboard.render_dashboard("health", ...)` | v1.11 (84) |
| Gates | `/gates` | `dashboard.render_dashboard("gates", ...)` | v1.6 (42) |
| Reports | `/reports` | `dashboard.render_dashboard("reports", ...)` | v1.11 (81) |
| Logs | `/logs`, `/logs/<source>` | `logs.render_logs_page(...)` | v1.11 (82) |
| Audit | `/audit`, `/audit/<trace_id>` | `audit.render_audit_page(...)` / `render_trace_page(...)` | v1.11 (83) |
| Processes | `/processes` | `processes.render_processes_page(...)` | v1.11 (80) |
| Channel Config | `/config/channels` | `channels.render_channels_page(...)` | v1.10 (75) |
| Provider Config | `/config/providers` | `providers.render_providers_page(...)` | v1.10 (76) |
| Model Catalog | `/config/catalog` | `catalog.render_catalog_page(...)` | v1.10 (76) |
| Vision Config | `/config/vision` | `vision.render_vision_page(...)` | v1.10 (77) |
| Login | `/login` | `auth.render_login_page(...)` | v1.11 (85) |
| Logout | `/logout` | `auth.render_logout_page(...)` | v1.11 (85) |

**Nav consistency:** All 16 pages already use `_page_template` → they share the same nav. The gap is **active-state indication** (no `aria-current` or `.active` CSS class on the current page's nav link). `[VERIFIED: dashboard.py L88-91 — nav_links have no active class]`

### Recommended Project Structure

```
services/admin-web-ui/src/admin_web_ui/
├── dashboard.py          # MODIFY: _page_template — add active-state, responsive CSS, error pages
├── server.py             # MODIFY: _dispatch() — add try/except for 500 page; 404 dedicated page
├── auth.py               # no change (login/logout already use _page_template)
├── channels.py           # no change (already uses _page_template)
├── providers.py          # no change
├── catalog.py            # no change
├── vision.py             # no change
├── logs.py               # no change
├── audit.py              # no change
├── processes.py          # no change
└── __main__.py           # no change (entry point stable)

services/admin-web-ui/tests/
├── test_server.py        # MODIFY: add 404/500 error page tests
├── test_dashboard.py     # MODIFY: add active-state, responsive, error page tests
└── (new test files for polish features)

scripts/
└── start-console.sh      # NEW: one-click startup with env loading + PID tracking

.env.example              # MODIFY: add Phase 85 auth env vars + any new polish vars
```

### Pattern 1: Dedicated Error Page Rendering

**What:** Render 404 and 500 as dedicated SSR pages using `_page_template` with a "Back to Dashboard" link.
**When to use:** Every 404 (unknown route) and every 500 (uncaught exception in `_dispatch`).
**Example:**
```python
# Source: existing _page_template pattern (dashboard.py L68)
def render_error_page(
    status_code: int,
    title: str,
    message: str,
    identity: Identity | None = None,
) -> str:
    """Render a dedicated error page with nav and back-to-dashboard link."""
    body = (
        f'    <p class="error">Error {status_code}: {_esc(title)}</p>\n'
        f'    <p>{_esc(message)}</p>\n'
        f'    <p><a href="/" class="btn-primary">Back to Dashboard</a></p>'
    )
    return _page_template(title, body, identity)
```

### Pattern 2: Active-State Nav Indication

**What:** Pass the current route to `_page_template` so the active nav link gets `aria-current="page"` and an `.active` CSS class.
**When to use:** Every page render.
**Example:**
```python
# Source: existing nav_items pattern (dashboard.py L71-91)
def _page_template(
    title: str,
    body: str,
    identity: Identity | None = None,
    active_path: str | None = None,  # NEW parameter
) -> str:
    nav_links = "\n".join(
        f'      <a href="{_esc(href)}" class="nav-link{" active" if href == active_path else ""}'
        f'{" aria-current=\"page\"" if href == active_path else ""}>{_esc(label)}</a>'
        for href, label in nav_items
    )
```

### Pattern 3: 500 Catch-All in _dispatch

**What:** Wrap `handle_admin_web_ui_request` in try/except to catch uncaught exceptions and render a dedicated 500 page.
**When to use:** `AdminWebUiServer._dispatch()`.
**Example:**
```python
# Source: admin-console-api/server.py L125-133 (API already does this)
def _dispatch(self, method: str, body: bytes | None) -> None:
    try:
        status, html_body, headers = handle_admin_web_ui_request(...)
    except Exception:
        # Log to stderr (not browser), render safe 500 page
        traceback.print_exc(file=sys.stderr)
        html_body = render_error_page(500, "Internal Server Error",
            "An unexpected error occurred. Check server logs.", identity=None)
        status = 500
        headers = {"Content-Type": "text/html; charset=utf-8",
                   "Content-Security-Policy": CSP_HEADER}
    # ... send response
```

### Anti-Patterns to Avoid

- **Never include `str(exc)` or `traceback.format_exc()` in the HTML response** — stack traces may contain file paths, env var names, or secret values. Log to stderr only. `[VERIFIED: admin-console-api/server.py L126 — API already follows this]`
- **Never bypass `_page_template` for error responses** — the 413 handler at `server.py L1943-1954` bypasses it and produces an inconsistent page with no nav. Fix this too.
- **Never add a third-party CSS framework** (Bootstrap, Tailwind) — stdlib-only constraint. Inline `<style>` is the existing pattern and CSP allows `style-src 'self' 'unsafe-inline'`.
- **Never add JavaScript for responsive behavior** — CSS media queries suffice for the 1280px target. CSP `script-src 'self'` blocks inline JS anyway.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML escaping | Custom escaper | `html.escape()` (stdlib) | Existing `_esc()` in dashboard.py already uses it; XSS-safe |
| HTTP server | Custom socket server | `ThreadingHTTPServer` (stdlib) | Already in place from Phase 79 |
| Process spawning | Custom fork/exec | `subprocess.Popen` (stdlib) | Already used by ProcessSupervisor |
| PID file tracking | Custom PID database | JSON file write (atomic) | ProcessSupervisor already uses `INKSTATUTE_PROCESS_STATE_PATH` pattern; startup script can mirror this |
| Env loading in bash | Custom parser | `set -a; source .env; set +a` | Existing pattern in `start-hindsight.sh` |

**Key insight:** This phase is pure polish of existing patterns — no new infrastructure. Every change extends `_page_template`, `handle_admin_web_ui_request`, or `.env.example`.

## Common Pitfalls

### Pitfall 1: Stack Trace Leak in 500 Page
**What goes wrong:** Including `str(exc)` or `traceback.format_exc()` in the HTML 500 page leaks file paths, env var names, or partial secret values to the browser.
**Why it happens:** Developer thinks the error message helps debugging; but the browser is an untrusted client.
**How to avoid:** Log full traceback to stderr only; render a generic "Internal Server Error" message in HTML. Mirror the API server's existing pattern (`server.py L126-133`).
**Warning signs:** Any test that asserts `str(exc)` content appears in the HTML body.

### Pitfall 2: Breaking _page_template Signature for All Callers
**What goes wrong:** Adding `active_path` as a required parameter to `_page_template` breaks all 16+ call sites across channels.py, providers.py, logs.py, audit.py, auth.py, etc.
**Why it happens:** `_page_template` is called from every renderer.
**How to avoid:** Add `active_path` as an optional parameter with default `None`. Pass it through from each renderer. Alternatively, derive active state from the title or a new optional param on `render_dashboard`.
**Warning signs:** Import errors or `TypeError: missing required argument` after the change.

### Pitfall 3: 1280px Horizontal Scroll from Fixed-Width Tables
**What goes wrong:** `.data-table td.key { white-space: nowrap; width: 200px; }` combined with long values can exceed 1280px viewport.
**Why it happens:** Fixed 200px key column + unbounded value column + `max-width: 1200px` on `.main` leaves no margin for padding on 1280px.
**How to avoid:** Audit CSS for fixed widths. Use `max-width` instead of `width` on table cells. Add `overflow-wrap: break-word` on value cells. Test with a headless browser width assertion or CSS review at 1280px.
**Warning signs:** Any `white-space: nowrap` on cells with dynamic content; any `width: Npx` that doesn't have a responsive fallback.

### Pitfall 4: Startup Script PID File Conflicts with .gitignore
**What goes wrong:** The startup script writes `*.pid` files, but `.gitignore` ignores `*.pid` — so the file exists but is invisible to git status.
**Why it happens:** `.gitignore` L14 has `*.pid`.
**How to avoid:** Use a JSON PID file (e.g., `.inkstatute/console-pids.json`) instead of `.pid` files, mirroring the ProcessSupervisor pattern (`INKSTATUTE_PROCESS_STATE_PATH`). Or write to a path under `~/.inkstatute/` which is already the runtime state directory. `[VERIFIED: .gitignore L14, process_supervisor.py L52-56]`
**Warning signs:** PID file exists but `git status` doesn't show it — not a problem if intentional, but document it.

### Pitfall 5: Login/Logout Nav Links Shown When Already Authenticated
**What goes wrong:** Nav always shows both "Login" and "Logout" regardless of auth state, which is confusing.
**Why it happens:** `nav_items` is a static list with no conditional logic. `[VERIFIED: dashboard.py L85-86]`
**How to avoid:** Conditionally render Login (when `identity is None` or anonymous) vs Logout (when `identity is not None`). This is a discretion decision — the success criteria says "consistent navigation" not "auth-aware navigation", but showing both is poor UX.
**Warning signs:** Both Login and Logout visible simultaneously.

### Pitfall 6: .env.example Comments Don't Explain Defaults
**What goes wrong:** New env vars are listed but without explaining the default behavior when unset.
**Why it happens:** Rushing the documentation.
**How to avoid:** Each new entry should have an inline comment explaining: purpose, default when unset, and any constraints (e.g., "min 60 seconds"). Follow the existing pattern in `.env.example` (e.g., L28-31 for reports).
**Warning signs:** Any env var line without a `#` comment above or beside it.

## Code Examples

### Existing 404 Handling (to be replaced)
```python
# Source: services/admin-web-ui/src/admin_web_ui/server.py L289-295
if section is None:
    body_html = render_dashboard(
        "index",
        {"error": {"code": "not_found", "message": f"Unknown route: {route_path}"}},
        identity=None,
    )
    return 404, body_html, response_headers
```

### Existing API 500 Handling (pattern to mirror in UI)
```python
# Source: services/admin-console-api/src/admin_console_api/server.py L125-133
except Exception as exc:
    traceback.print_exc(file=sys.stderr)
    status, response = 500, {
        "error": {
            "code": "internal_error",
            "message": "internal server error",
            "type": type(exc).__name__,
        }
    }
```

### Existing CSS Responsive Elements (already present)
```css
/* Source: services/admin-web-ui/src/admin_web_ui/dashboard.py L104-172 */
.main { padding: 2rem; max-width: 1200px; margin: 0 auto; }
.nav { background: #16213e; padding: 0.5rem 2rem; display: flex; gap: 1rem; flex-wrap: wrap; }
/* viewport meta already set: width=device-width, initial-scale=1 */
```

### Existing Startup Script Pattern (bash)
```bash
# Source: scripts/start-hindsight.sh L18-25
set -euo pipefail
ENV_FILE="${HOME}/.config/inkstatute/hindsight.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found." >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-threaded `HTTPServer` | `ThreadingHTTPServer` | Phase 79 (v1.11) | Blocking ops don't freeze UI; all shared state guarded by locks |
| Bearer-token-only auth | Bearer + session cookie (HMAC-signed) | Phase 85 (v1.11) | Browser sessions work without JS token management |
| Dashboard error blocks | Dedicated error pages (this phase) | Phase 86 | Product-grade error UX with nav and CTA |
| Manual service startup | One-click `start-console.sh` (this phase) | Phase 86 | Operator runs single command instead of two `python -m` invocations |

**Deprecated/outdated:**
- None in this phase — all patterns are current within the v1.11 milestone.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DEFAULT_SESSION_TTL_SECONDS` is exported from `rbac` package | Standard Stack | Low — `server.py L25` imports it directly |
| A2 | 1280px is the only width that must not scroll (mobile not required) | Success Criteria | None — explicitly stated in POLISH-03 |
| A3 | `.inkstatute/` directory is the conventional runtime state location | Pitfall 4 | Low — ProcessSupervisor already uses `Path.home() / ".inkstatute"` |
| A4 | `unittest` is the test framework (not pytest) | Validation Architecture | None — verified by `run_v2_gates.py` |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions (RESOLVED)

1. **Should Login/Logout nav links be auth-state-aware?**
   - What we know: Currently both are always shown. Success criteria says "consistent navigation" but doesn't specify auth-awareness.
   - What's unclear: Whether "consistent" means "identical on every page" or "consistent but context-aware".
   - Recommendation: Make them auth-state-aware (show Login when anonymous, Logout when authenticated) — this is product-grade UX and the success criteria says "product-grade". This is a discretion decision per CONTEXT.md.
   - RESOLVED: Yes — make auth-state-aware. Implemented in Plan 02 Task 1, action step 4 (conditional Login/Logout based on identity parameter).

2. **Should the 413 oversized-body handler be updated to use _page_template?**
   - What we know: `server.py L1943-1954` renders a bare HTML string without nav or CSP.
   - What's unclear: Whether POLISH-01's "proper error pages" scope includes 413.
   - Recommendation: Yes — fix it for consistency. It's a 2-line change to use `render_error_page`.
   - RESOLVED: Yes — update 413 handler to use render_error_page. Implemented in Plan 01 Task 2, action step 5 (replace bare HTML with render_error_page(413, ...)).

3. **Should the startup script start channel host processes too?**
   - What we know: POLISH-04 says "launches admin-web-ui + admin-console-api". Channel hosts (WeCom/QQBot) are orchestrated via the console UI (ProcessSupervisor).
   - What's unclear: Whether the script should also start channel hosts.
   - Recommendation: No — the script launches only the console (UI + API). Channel hosts are started on-demand from the UI, which is the existing Phase 80 design. Document this in the script help text.
   - RESOLVED: No — launch only UI + API. Implemented in Plan 03 Task 1, action step 2 (usage comment documents that channel hosts are started on-demand from the console UI, not by this script).

## Environment Availability

> This phase has no external dependencies — all work is stdlib + existing project code.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python ≥3.11 | All code | ✓ | 3.14.6 (pyenv) | — |
| bash | start-console.sh | ✓ | system | — |
| admin-console-api | admin-web-ui proxy | ✓ | v0.1.0 | — |
| rbac package | session auth | ✓ | v0.1.0 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `unittest` (stdlib, not pytest) |
| Config file | none — gates use `python -m unittest discover` |
| Quick run command | `python -m unittest discover -s services/admin-web-ui/tests -v` (with PYTHONPATH set) |
| Full suite command | `python scripts/run_v2_gates.py` |

**PYTHONPATH for admin-web-ui tests** (from `run_v2_gates.py L150`):
```
services/admin-web-ui/src
services/admin-console-api/src
packages/rbac/src
services/conversation-read-view/src
services/feedback-service/src
packages/platform-contract/src
packages/platform-runtime/src
packages/operator-config/src
```

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| POLISH-01 | 404 page renders with nav + back-to-dashboard, escaped, no stack trace | unit | `python -m unittest services.admin-web_ui.tests.test_server.TestErrorPages.test_404_dedicated_page -v` | ❌ Wave 0 |
| POLISH-01 | 500 page renders on uncaught exception, no stack trace leak | unit | `python -m unittest services.admin_web_ui.tests.test_server.TestErrorPages.test_500_on_uncaught_exception -v` | ❌ Wave 0 |
| POLISH-01 | 500 page does not contain str(exc) or traceback | unit | `python -m unittest services.admin_web_ui.tests.test_server.TestErrorPages.test_500_no_stack_trace_leak -v` | ❌ Wave 0 |
| POLISH-02 | Nav renders on all pages with active-state indication | unit | `python -m unittest services.admin_web_ui.tests.test_dashboard.TestNavActiveState.test_active_link_has_aria_current -v` | ❌ Wave 0 |
| POLISH-02 | Nav is consistent (same nav_items on every page) | unit | `python -m unittest services.admin_web_ui.tests.test_dashboard.TestNavActiveState.test_nav_consistent_across_pages -v` | ❌ Wave 0 |
| POLISH-03 | No horizontal scroll at 1280px (CSS audit — no fixed widths exceeding viewport) | unit | `python -m unittest services.admin_web_ui.tests.test_dashboard.TestResponsive.test_no_fixed_width_exceeds_1280 -v` | ❌ Wave 0 |
| POLISH-04 | start-console.sh launches both services with env loading | integration | `bash scripts/start-console.sh --dry-run` (or unit test of script logic) | ❌ Wave 0 |
| POLISH-04 | start-console.sh writes PID file | integration | `bash scripts/start-console.sh --dry-run && test -f .inkstatute/console-pids.json` | ❌ Wave 0 |
| POLISH-05 | .env.example documents ADMIN_USERNAME, ADMIN_PASSWORD, SESSION_TTL_SECONDS, ADMIN_WEB_UI_SECURE_COOKIE | unit | `python -m unittest services.admin_web_ui.tests.test_env_docs.test_auth_vars_documented -v` | ❌ Wave 0 |
| POLISH-05 | .env.example has inline comments for all new vars | unit | `python -m unittest services.admin_web_ui.tests.test_env_docs.test_inline_comments_present -v` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m unittest discover -s services/admin-web-ui/tests -v` (with PYTHONPATH)
- **Per wave merge:** `python scripts/run_v2_gates.py` (full gate suite — all gates must be green)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `services/admin-web-ui/tests/test_server.py` — add `TestErrorPages` class covering POLISH-01 (404/500 dedicated pages, no stack trace leak)
- [ ] `services/admin-web-ui/tests/test_dashboard.py` — add `TestNavActiveState` and `TestResponsive` classes covering POLISH-02, POLISH-03
- [ ] `services/admin-web-ui/tests/test_env_docs.py` — NEW file covering POLISH-05 (.env.example completeness)
- [ ] `services/admin-web-ui/tests/test_startup_script.py` — NEW file covering POLISH-04 (script logic, PID tracking) — or integration test via bash

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (existing) | env-based username/password (Phase 85, unchanged) |
| V3 Session Management | yes (existing) | HMAC-signed cookies, HttpOnly + SameSite (Phase 85, unchanged) |
| V4 Access Control | yes (existing) | RBAC guard pipeline (unchanged) |
| V5 Input Validation | yes | `html.escape()` on all dynamic content in error pages; route path escaped in 404 |
| V6 Cryptography | no | No new crypto in this phase |
| V7 Error Handling | yes | **This phase's core security concern** — error pages must not leak stack traces or secrets |
| V12 Files & Resources | no | No file handling changes |

### Known Threat Patterns for stdlib SSR error pages

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stack trace in 500 page → path/secret disclosure | Information Disclosure | Log to stderr only; render generic message in HTML; never `str(exc)` in response body |
| Reflected route path in 404 → XSS | Cross-Site Scripting | `html.escape()` on route path (existing pattern in `_esc()`) |
| Error page bypasses CSP | Security Misconfiguration | All error pages must go through `_page_template` which sets CSP header |
| Oversized body 413 without CSP | Security Misconfiguration | Fix 413 handler to use `_page_template` (currently bypasses it) |

## Sources

### Primary (HIGH confidence)
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` — `_page_template`, nav_items, CSS, render_dashboard (read in full)
- `services/admin-web-ui/src/admin_web_ui/server.py` — `handle_admin_web_ui_request`, `AdminWebUiServer._dispatch`, error handling, auth flow (read in full)
- `services/admin-console-api/src/admin_console_api/server.py` — `AdminConsoleApiServer._dispatch` try/except pattern (read in full)
- `services/admin-web-ui/src/admin_web_ui/__main__.py` — entry point, create_server, env vars (read in full)
- `services/admin-console-api/src/admin_console_api/__main__.py` — entry point (read in full)
- `services/admin-web-ui/src/admin_web_ui/auth.py` — login/logout, ADMIN_USERNAME/PASSWORD, session TTL (read in full)
- `.env.example` — existing env documentation (read in full, 85 lines)
- `scripts/start-hindsight.sh` — existing bash startup pattern (read in full)
- `scripts/run_v2_gates.py` — gate runner, test commands, PYTHONPATH (read relevant sections)
- `.planning/config.json` — nyquist_validation: true, skip_discuss: true
- `AGENTS.md` — project constraints (read in full)
- `.planning/REQUIREMENTS.md` — POLISH-01..05 definitions (read in full)
- `.planning/ROADMAP.md` — Phase 86 details, stack constraints (read relevant sections)

### Secondary (MEDIUM confidence)
- `services/admin-console-api/src/admin_console_api/process_supervisor.py` — PID tracking pattern, state path resolution
- `services/admin-console-api/src/admin_console_api/process_registry.py` — ProcessRecord dataclass
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — flag env var naming convention
- `.gitignore` — `*.pid` ignored, `.inkstatute/` runtime state

### Tertiary (LOW confidence)
- None — all research was codebase-internal verification.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all verified by reading source files directly
- Architecture patterns: HIGH — all verified by reading source files directly
- Error handling gaps: HIGH — verified by grep + reading _dispatch method
- Env var gaps: HIGH — verified by grep of .env.example against auth.py/server.py
- Startup script design: HIGH — based on existing start-hindsight.sh pattern + entry points
- Responsive CSS: MEDIUM — CSS reviewed but 1280px behavior not tested in a browser (test plan covers this)

**Thinking models applied:** None — this is codebase-only research (per thinking-models-research.md: "Codebase-only research — structured reasoning models add no value. Use grep and read the code."). No external library evaluation, no contested recommendations.

**Research type:** Codebase-only (no external dependencies, no library evaluation, no web search needed). All claims verified by reading project source files.
