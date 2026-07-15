# Phase 86: Product Polish - Pattern Map

**Mapped:** 2026-07-14
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `services/admin-web-ui/src/admin_web_ui/server.py` | controller | request-response | `services/admin-console-api/src/admin_console_api/server.py` | exact (same role, same data flow, same stdlib HTTP handler pattern) |
| `services/admin-web-ui/src/admin_web_ui/dashboard.py` | component | request-response | (self-modifying — `_page_template` is the existing shell) | exact (same file, extending existing pattern) |
| `.env.example` | config | file-I/O | `.env.example` (self-modifying — existing 85-line file) | exact (same file, adding missing entries) |
| `scripts/start-console.sh` | utility | file-I/O | `scripts/start-hindsight.sh` | role-match (bash startup script; different target — Python subprocesses vs Docker) |
| `services/admin-web-ui/tests/test_server.py` | test | request-response | `services/admin-web-ui/tests/test_server.py` (self-modifying — existing test classes) | exact (same file, adding TestErrorPages class) |
| `services/admin-web-ui/tests/test_dashboard.py` | test | request-response | `services/admin-web-ui/tests/test_dashboard.py` (self-modifying — existing test classes) | exact (same file, adding TestNavActiveState + TestResponsive) |
| `services/admin-web-ui/tests/test_env_docs.py` | test | file-I/O | `services/admin-web-ui/tests/test_dashboard.py` (unittest pattern + file-read assertions) | role-match (new test file, same unittest structure) |
| `services/admin-web-ui/tests/test_startup_script.py` | test | file-I/O | `services/admin-web-ui/tests/test_main.py` (unittest + entry-point testing) | role-match (new test file, same unittest structure) |

## Pattern Assignments

### `services/admin-web-ui/src/admin_web_ui/server.py` (controller, request-response)

**Analog:** `services/admin-console-api/src/admin_console_api/server.py`

This file is MODIFIED in-place. The key changes are:
1. Wrap `AdminWebUiServer._dispatch()` in try/except to catch uncaught exceptions and render a dedicated 500 page
2. Replace the 404 dashboard-error-block with a dedicated 404 error page using `_page_template`
3. Fix the 413 oversized-body handler to use `_page_template` instead of bare HTML

**Imports pattern** (lines 7-14 of analog — API server already imports `traceback` and `sys`):
```python
from __future__ import annotations

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
```

> **Note:** The UI server (`server.py`) currently does NOT import `traceback` or `sys`. Add these imports to support the 500 catch-all pattern.

**500 catch-all pattern** (lines 86-135 of analog — API server `_dispatch` try/except):
```python
def _dispatch(self, method: str, body: bytes) -> None:
    parsed = urlparse(self.path)
    path = parsed.path

    try:
        if method == "GET":
            status, response = self.server.handle_admin_get(...)
        else:  # PUT
            ...
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        status, response = 500, {
            "error": {
                "code": "internal_error",
                "message": "internal server error",
                "type": type(exc).__name__,
            }
        }

    self._send_json(status, response)
```

**How to adapt for UI server** — the UI `_dispatch` (currently at `server.py` L1959-1985) has NO try/except. Wrap the `handle_admin_web_ui_request(...)` call:
```python
# Adapted from admin-console-api/server.py L90-133
def _dispatch(self, method: str, body: bytes | None) -> None:
    try:
        status, html_body, headers = handle_admin_web_ui_request(
            self.path,
            dict(self.headers),
            feature_flags=self.server.feature_flags,
            # ... (all existing kwargs unchanged)
        )
    except Exception:
        traceback.print_exc(file=sys.stderr)
        html_body = render_error_page(
            500, "Internal Server Error",
            "An unexpected error occurred. Check server logs.",
            identity=None,
        )
        status = 500
        headers = {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Security-Policy": CSP_HEADER,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
    encoded = html_body.encode("utf-8")
    self.send_response(status)
    # ... (rest unchanged)
```

**Existing 404 handling** (lines 289-295 — to be replaced with dedicated error page):
```python
if section is None:
    body_html = render_dashboard(
        "index",
        {"error": {"code": "not_found", "message": f"Unknown route: {route_path}"}},
        identity=None,
    )
    return 404, body_html, response_headers
```

**Existing 413 handler** (lines 1941-1955 — bypasses `_page_template`, needs fixing):
```python
if length < 0 or length > MAX_CHANNELS_POST_BYTES:
    body_html = (
        "<!DOCTYPE html><html><body>"
        "<p class=\"error\">Request body too large</p>"
        "</body></html>"
    )
    encoded = body_html.encode("utf-8")
    self.send_response(413)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Security-Policy", CSP_HEADER)
    self.send_header("Content-Length", str(len(encoded)))
    self.end_headers()
    self.wfile.write(encoded)
    return
```

**CSP header constant** (line 94 — already defined, reuse in error pages):
```python
CSP_HEADER = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
```

**Anti-pattern (CRITICAL):** Never include `str(exc)` or `traceback.format_exc()` in the HTML response body. The API server (L126-133) logs to stderr only and renders a generic message. The UI server must follow the same pattern — log full traceback to `sys.stderr`, render generic "Internal Server Error" in HTML.

---

### `services/admin-web-ui/src/admin_web_ui/dashboard.py` (component, request-response)

**Analog:** Self-modifying — `_page_template` is the existing shared HTML shell.

This file is MODIFIED in-place. The key changes are:
1. Add `active_path: str | None = None` optional parameter to `_page_template`
2. Add active-state CSS class + `aria-current="page"` to nav links
3. Add `render_error_page()` function for 404/500 dedicated pages
4. Audit/fix CSS for 1280px responsive target (no horizontal scroll)
5. Optionally make Login/Logout nav links auth-state-aware

**Existing `_page_template` signature** (line 68 — to be extended):
```python
def _page_template(title: str, body: str, identity: Identity | None = None) -> str:
```

**Existing nav_items list** (lines 71-87 — hardcoded, no active-state):
```python
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
```

**Existing nav_links rendering** (lines 88-91 — no active class, no aria-current):
```python
nav_links = "\n".join(
    f'      <a href="{_esc(href)}" class="nav-link">{_esc(label)}</a>'
    for href, label in nav_items
)
```

**Active-state pattern** (adapted from RESEARCH.md Pattern 2, based on existing L88-91):
```python
def _page_template(
    title: str,
    body: str,
    identity: Identity | None = None,
    active_path: str | None = None,  # NEW optional parameter
) -> str:
    # ... nav_items unchanged ...
    nav_links = "\n".join(
        f'      <a href="{_esc(href)}" class="nav-link{" active" if href == active_path else ""}'
        f'{" aria-current=\"page\"" if href == active_path else ""}>{_esc(label)}</a>'
        for href, label in nav_items
    )
```

> **CRITICAL — Pitfall 2:** `active_path` MUST be optional with default `None`. There are 16+ call sites across `channels.py`, `providers.py`, `logs.py`, `audit.py`, `auth.py`, `processes.py`, `catalog.py`, `vision.py`, and `render_dashboard` itself. Adding it as required would break all callers.

**Error page rendering pattern** (new function, based on existing `_page_template` + `_esc`):
```python
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

**Existing CSS responsive elements** (lines 104-172 — already partially responsive):
```css
.main { padding: 2rem; max-width: 1200px; margin: 0 auto; }
.nav { background: #16213e; padding: 0.5rem 2rem; display: flex; gap: 1rem; flex-wrap: wrap; }
```

**CSS gap to fix** (line 116 — fixed 200px width on key column can cause 1280px overflow):
```css
.data-table td.key { font-weight: 600; color: #555; white-space: nowrap; width: 200px; }
```

> **Pitfall 3:** Change `width: 200px` to `max-width: 200px` or `width: 200px; min-width: 120px; max-width: 200px;`. Add `overflow-wrap: break-word` on `.data-table td.val` (currently `word-break: break-all` at L117 which is acceptable but should be verified).

**Existing viewport meta** (line 102 — already present, no change needed):
```html
<meta name="viewport" content="width=device-width, initial-scale=1">
```

**Existing `_esc` helper** (lines 18-20 — reuse in error pages):
```python
def _esc(value: Any) -> str:
    """HTML-escape a value for safe rendering."""
    return html.escape(str(value))
```

**Existing `.btn-primary` CSS** (lines 142-146 — reuse for "Back to Dashboard" link):
```css
.btn-primary {
    background: #1a1a2e; color: #fff; border: none; border-radius: 6px;
    padding: 8px 16px; min-height: 44px; font-size: 1rem; cursor: pointer;
}
```

**Existing `.error` CSS** (line 125 — reuse in error pages):
```css
.error { color: #c0392b; font-weight: 600; }
```

**Existing `.nav-link` CSS** (lines 109-110 — add `.nav-link.active` rule):
```css
.nav-link { color: #aaccff; text-decoration: none; font-size: 0.875rem; font-weight: 600; }
.nav-link:hover { color: #fff; }
```

> Add: `.nav-link.active { color: #fff; border-bottom: 2px solid #aaccff; }`

**`render_dashboard` call site** (lines 192-251 — passes through to `_page_template`, needs `active_path` threading):
```python
def render_dashboard(
    section: str,
    data: dict[str, Any],
    identity: Identity | None = None,
    boundary: AdminUiBoundary | None = None,
) -> str:
    # ... title_map, error handling, section rendering ...
    return _page_template(title, body, identity)
```

> The `render_dashboard` function should accept an optional `active_path` and pass it through, OR derive it from the `section` name via a reverse-lookup map.

---

### `.env.example` (config, file-I/O)

**Analog:** Self-modifying — existing 85-line file.

This file is MODIFIED in-place. The key change is adding Phase 85 auth env vars that are currently missing.

**Existing file structure** (lines 1-25 — section-based with `# ---` headers and inline comments):
```
# InkStatute local env example — copy to `.env` (gitignored). Never commit real secrets.
# Refs vs values: production hosts prefer *_REF; smoke --live uses value vars. See runbook/.

# --- Feature flags (all default OFF unless set) ---
# INKSTATUTE_QQBOT_CHANNEL_ENABLED=false
...

# --- Admin Web UI and Admin Console API (Operator Config Console) ---
# INKSTATUTE_ADMIN_WEB_UI_ENABLED=false
# ADMIN_WEB_UI_HOST=127.0.0.1
# ADMIN_WEB_UI_PORT=8080
# ADMIN_WEB_UI_SECRET=replace-me-admin-web-ui-secret
# ADMIN_CONSOLE_API_HOST=127.0.0.1
# ADMIN_CONSOLE_API_PORT=8081
...
```

**Missing auth env vars** (from `auth.py` L57-58, `server.py` L1901-1914):

| Env Var | Default | Purpose | Source |
|---------|---------|---------|--------|
| `ADMIN_USERNAME` | `admin` | Login username for session auth | `auth.py` L57 |
| `ADMIN_PASSWORD` | (empty = login disabled) | Login password for session auth | `auth.py` L58-59 |
| `SESSION_TTL_SECONDS` | `DEFAULT_SESSION_TTL_SECONDS` (from rbac package) | Session cookie TTL in seconds (min 60) | `server.py` L1902-1908 |
| `ADMIN_WEB_UI_SECURE_COOKIE` | `false` | Set Secure attribute on session cookie | `server.py` L1911-1914 |

**Pattern to follow** (existing inline comment style from L27-31):
```
# --- Reports dashboard (bounded tail-scan aggregation) ---
# REPORTS_MAX_SCAN_LINES=10000
# REPORTS_SCAN_LOOKBACK_SECONDS=86400
# REPORTS_LONG_TASK_THRESHOLD_SECONDS=60
# INKSTATUTE_REPORT_DISPLAY_TZ=UTC
```

**New section to add** (after the Admin Web UI section, ~L25):
```
# --- Session auth (Phase 85) ---
# ADMIN_USERNAME=admin
# ADMIN_PASSWORD=               # empty = login disabled; set to enable browser session auth
# SESSION_TTL_SECONDS=3600      # session cookie TTL in seconds (min 60; default from rbac package)
# ADMIN_WEB_UI_SECURE_COOKIE=false  # set true to add Secure attribute (requires HTTPS)
```

> **Pitfall 6:** Each new entry must have an inline comment explaining: purpose, default when unset, and constraints. Follow the existing `# ---` section header pattern.

---

### `scripts/start-console.sh` (utility, file-I/O)

**Analog:** `scripts/start-hindsight.sh`

This file is NEW. It launches admin-web-ui + admin-console-api as Python subprocesses with env loading and PID tracking.

**Bash script pattern** (lines 1-25 of analog — `set -euo pipefail` + env loading):
```bash
#!/usr/bin/env bash
# Start Hindsight memory backend for InkStatute.
#
# Usage:
#   ./scripts/start-hindsight.sh              # Gemini LLM (default)
#   ./scripts/start-hindsight.sh --ollama     # Full Ollama backend (offline mode)

set -euo pipefail

ENV_FILE="${HOME}/.config/inkstatute/hindsight.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found." >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a
```

**Health-check polling pattern** (lines 86-104 of analog — timeout loop):
```bash
TIMEOUT="${HEALTH_TIMEOUT:-180}"
echo "Waiting for Hindsight to start (timeout: ${TIMEOUT}s)..."
for i in $(seq 1 "$TIMEOUT"); do
  if curl -sf http://localhost:8888/health >/dev/null 2>&1; then
    echo "Hindsight is healthy (after ${i}s)."
    exit 0
  fi
  if [ $((i % 15)) -eq 0 ]; then
    echo "  ...still waiting (${i}s)"
  fi
  sleep 1
done
echo "ERROR: did not become healthy within ${TIMEOUT}s." >&2
exit 1
```

**PID tracking pattern** (from `process_supervisor.py` L52-56 — JSON state file, not `.pid` files):
```python
def _resolve_state_path(self) -> Path:
    raw = self._env.get("INKSTATUTE_PROCESS_STATE_PATH")
    if raw:
        return Path(raw)
    return Path.home() / ".inkstatute" / "process-state.json"
```

> **Pitfall 4:** `.gitignore` L14 ignores `*.pid` files. Use a JSON PID file (e.g., `${HOME}/.inkstatute/console-pids.json`) instead of `.pid` files, mirroring the ProcessSupervisor pattern. The `~/.inkstatute/` directory is the conventional runtime state location.

**ProcessRecord dataclass** (from `process_registry.py` L10-22 — JSON-serializable structure for PID tracking):
```python
@dataclass
class ProcessRecord:
    name: str
    status: str = "stopped"
    pid: int | None = None
    started_at: str | None = None
    last_exit_code: int | None = None
    host: str = "127.0.0.1"
    port: int = 0
    log_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
```

**Entry point commands** (from RESEARCH.md L156-159, verified in `__main__.py` files):
```bash
# admin-web-ui entry: python -m admin_web_ui (port 8080, env: ADMIN_WEB_UI_HOST/PORT)
# admin-console-api entry: python -m admin_console_api (port 8081, env: ADMIN_CONSOLE_API_HOST/PORT)
```

**PYTHONPATH pattern** (from `process_supervisor.py` L92-111 — canonical source-root PYTHONPATH):
```python
repo_root = Path(__file__).resolve().parents[4]
paths = [
    repo_root,
    repo_root / "services" / "wecom-service" / "src",
    repo_root / "packages" / "platform-runtime" / "src",
    repo_root / "packages" / "platform-contract" / "src",
    # ... etc
]
```

> The startup script must set `PYTHONPATH` to include all source roots so `python -m admin_web_ui` and `python -m admin_console_api` can resolve imports. Mirror the `_default_pythonpath()` pattern or source from `scripts/run_v2_gates.py` L150.

**Adapted script structure** (combining analog patterns):
```bash
#!/usr/bin/env bash
# One-click startup for InkStatute Admin Console (UI + API).
set -euo pipefail

# Env loading (from start-hindsight.sh L18-25)
ENV_FILE="${1:-.env}"
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi

# PYTHONPATH (from process_supervisor.py _default_pythonpath pattern)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${REPO_ROOT}/services/admin-web-ui/src:${REPO_ROOT}/services/admin-console-api/src:${REPO_ROOT}/packages/rbac/src:..."

# Launch subprocesses
python -m admin_web_ui &
UI_PID=$!
python -m admin_console_api &
API_PID=$!

# PID tracking (JSON file, from process_supervisor.py pattern)
PID_FILE="${HOME}/.inkstatute/console-pids.json"
mkdir -p "$(dirname "$PID_FILE")"
echo "{\"ui\": ${UI_PID}, \"api\": ${API_PID}}" > "$PID_FILE"

# Cleanup on exit (trap pattern)
trap 'kill ${UI_PID} ${API_PID} 2>/dev/null || true; rm -f "$PID_FILE"' EXIT
wait
```

---

### `services/admin-web-ui/tests/test_server.py` (test, request-response)

**Analog:** Self-modifying — existing test file with `AdminWebUiServerTests` class.

This file is MODIFIED in-place. Add a new `TestErrorPages` class covering POLISH-01.

**Existing test class pattern** (lines 37-57 — unittest TestCase with setUp, handle_admin_web_ui_request direct call):
```python
class AdminWebUiServerTests(unittest.TestCase):
    SECRET = "test-secret-key"

    def setUp(self) -> None:
        self.handle_admin_get = _make_fake_handle_admin_get()
        self.read_model = None
        self.feedback_queue: list[dict[str, Any]] = []

    def test_disabled_feature_flag_returns_503(self) -> None:
        flags = RuntimeFeatureFlags(admin_web_ui_enabled=False)
        status, body, headers = handle_admin_web_ui_request(
            "/",
            {},
            feature_flags=flags,
            handle_admin_get=self.handle_admin_get,
            read_model=self.read_model,
            feedback_queue=self.feedback_queue,
            rbac_secret=self.SECRET,
        )
        self.assertEqual(status, 503)
        self.assertIn("admin_web_ui_disabled", body)
```

**Existing 404 test** (lines 175-187 — pattern to extend for dedicated 404 page):
```python
def test_unknown_route_returns_404(self) -> None:
    flags = RuntimeFeatureFlags(admin_web_ui_enabled=True, admin_api_enabled=True)
    token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="tenant-1")
    status, body, headers = handle_admin_web_ui_request(
        "/unknown",
        {"Authorization": f"Bearer {token}"},
        feature_flags=flags,
        handle_admin_get=self.handle_admin_get,
        read_model=self.read_model,
        feedback_queue=self.feedback_queue,
        rbac_secret=self.SECRET,
    )
    self.assertEqual(status, 404)
```

**New TestErrorPages class** (follow existing pattern — direct `handle_admin_web_ui_request` calls, assert status + body content):
```python
class TestErrorPages(unittest.TestCase):
    """POLISH-01: dedicated 404/500 error pages with nav, no stack trace leak."""

    SECRET = "test-secret-key"

    def setUp(self) -> None:
        self.handle_admin_get = _make_fake_handle_admin_get()
        self.read_model = None
        self.feedback_queue: list[dict[str, Any]] = []

    def test_404_dedicated_page(self) -> None:
        # Assert: status 404, body contains _page_template nav, "Back to Dashboard", escaped route
        ...

    def test_500_on_uncaught_exception(self) -> None:
        # Use a handle_admin_get that raises; assert 500 page renders with nav
        ...

    def test_500_no_stack_trace_leak(self) -> None:
        # Assert: body does NOT contain str(exc) or "Traceback" or file paths
        ...
```

**Fake handle_admin_get that raises** (adapt from `_make_fake_handle_admin_get` L18-34):
```python
def _make_handle_admin_get_that_raises(exc: Exception = RuntimeError("secret-path-leak")):
    def handle_admin_get(*args, **kwargs):
        raise exc
    return handle_admin_get
```

---

### `services/admin-web-ui/tests/test_dashboard.py` (test, request-response)

**Analog:** Self-modifying — existing test file with `DashboardRenderingTests` class.

This file is MODIFIED in-place. Add `TestNavActiveState` and `TestResponsive` classes.

**Existing test class pattern** (lines 16-30 — unittest TestCase, `render_dashboard` direct call, `assertIn` on HTML content):
```python
class DashboardRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = AdminUiBoundary()
        self.identity = Identity(role=Role.ADMIN, tenant_id="tenant-1")

    def test_render_index_contains_navigation(self) -> None:
        html_doc = render_dashboard("index", {}, identity=self.identity, boundary=self.boundary)
        self.assertIn("InkStatute Admin Dashboard", html_doc)
        self.assertIn("/sessions", html_doc)
        self.assertIn("/feedback", html_doc)
```

**Existing source-file read pattern** (lines 13-14, 63-68 — read dashboard.py source for forbidden-phrase assertions):
```python
_DASHBOARD_SRC = Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "dashboard.py"

def test_gate_honesty_forbidden_phrases_absent(self) -> None:
    src = _DASHBOARD_SRC.read_text(encoding="utf-8").lower()
    self.assertNotIn("lawyer trial acceptance complete", src)
```

> **Reuse this pattern** for `TestResponsive.test_no_fixed_width_exceeds_1280` — read the CSS from `_DASHBOARD_SRC` and assert no `width: Npx` where N + padding > 1280, or assert `max-width` is used instead of fixed `width` on table cells.

**New test classes** (follow existing pattern):
```python
class TestNavActiveState(unittest.TestCase):
    """POLISH-02: nav active-state indication with aria-current."""

    def test_active_link_has_aria_current(self) -> None:
        # render_dashboard with active_path="/sessions" → assert 'aria-current="page"' on /sessions link
        ...

    def test_nav_consistent_across_pages(self) -> None:
        # Render multiple sections, extract nav_items, assert identical
        ...

class TestResponsive(unittest.TestCase):
    """POLISH-03: no horizontal scroll at 1280px."""

    def test_no_fixed_width_exceeds_1280(self) -> None:
        # Read dashboard.py source, audit CSS for fixed widths
        src = _DASHBOARD_SRC.read_text(encoding="utf-8")
        # Assert .data-table td.key uses max-width not fixed width, etc.
        ...
```

---

### `services/admin-web-ui/tests/test_env_docs.py` (test, file-I/O)

**Analog:** `services/admin-web-ui/tests/test_dashboard.py` (unittest + file-read assertions)

This file is NEW. It reads `.env.example` and asserts that Phase 85 auth env vars are documented with inline comments.

**File-read pattern** (from `test_dashboard.py` L13-14 — Path resolution to source files):
```python
_DASHBOARD_SRC = Path(__file__).resolve().parents[1] / "src" / "admin_web_ui" / "dashboard.py"
```

**Adapted for .env.example** (resolve to repo root `.env.example`):
```python
_ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"
# test_env_docs.py is at: services/admin-web-ui/tests/test_env_docs.py
# parents[0] = tests/, parents[1] = admin-web-ui/, parents[2] = services/, parents[3] = repo root
```

**Test class pattern** (follow existing unittest structure):
```python
class TestEnvDocs(unittest.TestCase):
    """POLISH-05: .env.example documents all auth env vars with inline comments."""

    def setUp(self) -> None:
        self.content = _ENV_EXAMPLE.read_text(encoding="utf-8")

    def test_auth_vars_documented(self) -> None:
        self.assertIn("ADMIN_USERNAME", self.content)
        self.assertIn("ADMIN_PASSWORD", self.content)
        self.assertIn("SESSION_TTL_SECONDS", self.content)
        self.assertIn("ADMIN_WEB_UI_SECURE_COOKIE", self.content)

    def test_inline_comments_present(self) -> None:
        # Each new var should have a # comment on the same line or line above
        for var in ("ADMIN_USERNAME", "ADMIN_PASSWORD", "SESSION_TTL_SECONDS", "ADMIN_WEB_UI_SECURE_COOKIE"):
            # Assert there's a # comment associated with the var
            ...
```

---

### `services/admin-web-ui/tests/test_startup_script.py` (test, file-I/O)

**Analog:** `services/admin-web-ui/tests/test_main.py` (unittest + entry-point testing)

This file is NEW. It validates the `start-console.sh` script logic and PID tracking.

**Existing test_main.py pattern** (unittest, tests entry points and server creation):
```python
# test_main.py tests the __main__.py entry point, create_server, signal handling
```

**Test class pattern** (follow existing unittest structure, read script file):
```python
_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "start-console.sh"

class TestStartupScript(unittest.TestCase):
    """POLISH-04: start-console.sh launches both services with env loading + PID tracking."""

    def setUp(self) -> None:
        self.content = _SCRIPT_PATH.read_text(encoding="utf-8")

    def test_script_has_set_euo_pipefail(self) -> None:
        self.assertIn("set -euo pipefail", self.content)

    def test_script_sources_env(self) -> None:
        self.assertIn("source", self.content)

    def test_script_launches_both_services(self) -> None:
        self.assertIn("admin_web_ui", self.content)
        self.assertIn("admin_console_api", self.content)

    def test_script_writes_pid_file(self) -> None:
        self.assertIn("console-pids.json", self.content)
        self.assertIn(".inkstatute", self.content)

    def test_script_has_trap_cleanup(self) -> None:
        self.assertIn("trap", self.content)
        self.assertIn("kill", self.content)
```

> **Alternative:** Integration test via `bash scripts/start-console.sh --dry-run` — but `--dry-run` support must be added to the script itself. The unit-test-reads-script approach is safer for CI gates and doesn't require port binding.

---

## Shared Patterns

### Error Handling (500 catch-all)
**Source:** `services/admin-console-api/src/admin_console_api/server.py` L90-133
**Apply to:** `services/admin-web-ui/src/admin_web_ui/server.py` — `AdminWebUiServer._dispatch()`
```python
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
> **UI adaptation:** Replace JSON response with `render_error_page(500, ...)` HTML. Never include `str(exc)` or `traceback.format_exc()` in the HTML body.

### HTML Escaping (XSS prevention)
**Source:** `services/admin-web-ui/src/admin_web_ui/dashboard.py` L18-20
**Apply to:** All error page rendering, 404 route path display, 500 message
```python
def _esc(value: Any) -> str:
    """HTML-escape a value for safe rendering."""
    return html.escape(str(value))
```

### CSP Header (security)
**Source:** `services/admin-web-ui/src/admin_web_ui/server.py` L94
**Apply to:** All error page responses (404, 500, 413)
```python
CSP_HEADER = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
```
> All error pages MUST go through `_page_template` which includes the CSP header. The 413 handler currently bypasses this — fix it.

### Env Loading in Bash
**Source:** `scripts/start-hindsight.sh` L18-25
**Apply to:** `scripts/start-console.sh`
```bash
set -euo pipefail
set -a; source "$ENV_FILE"; set +a
```

### PID File Tracking (JSON, not .pid)
**Source:** `services/admin-console-api/src/admin_console_api/process_supervisor.py` L52-56
**Apply to:** `scripts/start-console.sh`
```python
return Path.home() / ".inkstatute" / "process-state.json"
```
> Use `~/.inkstatute/console-pids.json` — mirrors ProcessSupervisor pattern, avoids `.gitignore` `*.pid` conflict.

### Test Structure (unittest, direct function calls)
**Source:** `services/admin-web-ui/tests/test_server.py` L37-57
**Apply to:** All new/modified test files
```python
class TestXxx(unittest.TestCase):
    def setUp(self) -> None:
        # Initialize fixtures
        ...

    def test_xxx(self) -> None:
        status, body, headers = handle_admin_web_ui_request(...)
        self.assertEqual(status, ...)
        self.assertIn("expected content", body)
```

## No Analog Found

None — all 8 files have close analogs in the codebase. The two NEW test files (`test_env_docs.py`, `test_startup_script.py`) follow the existing unittest + file-read pattern established in `test_dashboard.py` L13-14.

## Metadata

**Analog search scope:**
- `services/admin-console-api/src/admin_console_api/server.py` (full read, 243 lines)
- `services/admin-console-api/src/admin_console_api/process_supervisor.py` (full read, 420 lines)
- `services/admin-console-api/src/admin_console_api/process_registry.py` (full read, 57 lines)
- `services/admin-web-ui/src/admin_web_ui/server.py` (targeted reads: L1-99, L200-299, L1895-1996)
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` (full read, 550 lines)
- `services/admin-web-ui/src/admin_web_ui/auth.py` (L1-70)
- `services/admin-web-ui/src/admin_web_ui/__main__.py` (full read, 157 lines)
- `services/admin-web-ui/tests/test_server.py` (L1-80, L175-203)
- `services/admin-web-ui/tests/test_dashboard.py` (L1-80)
- `scripts/start-hindsight.sh` (full read, 105 lines)
- `.env.example` (full read, 85 lines)

**Files scanned:** 11 source files + 2 test files + 1 config file + 1 bash script = 15 files
**Pattern extraction date:** 2026-07-14
