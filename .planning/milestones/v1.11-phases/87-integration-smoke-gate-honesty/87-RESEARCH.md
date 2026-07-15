# Phase 87: Integration, Smoke & Gate Honesty — Research

**Phase**: 87 (Integration, Smoke & Gate Honesty)
**Requirements**: no direct requirement mapping — verifies ENTRY-01..POLISH-05 end-to-end
**Researcher**: gsd-phase-researcher
**Date**: 2026-07-15

## 1. User Constraints

Copied from `AGENTS.md` and `PROJECT.md` key constraints. These are non-negotiable and enforced every phase.

### Hard Project Constraints (from AGENTS.md + ROADMAP.md)

- **stdlib-only**: `dependencies = []` in every `pyproject.toml`. No Flask/FastAPI/Django, no React/Vue SPA, no WebSocket/SSE libs, no `psutil`, no `celery`/`dramatiq`/`rq`, no TLS termination in-console, no process auto-restart watchdog. `[VERIFIED: AGENTS.md L44, ROADMAP.md L37]`
- **No new DB/queue/SPA**: Atomic JSON suffices; HTTP polling for logs. `[VERIFIED: AGENTS.md L44, ROADMAP.md L37]`
- **Never commit secrets/raw payloads**: Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads. Contract logs prefer `raw_payload_ref` and must not store sensitive full text by default. `[VERIFIED: AGENTS.md L32-34]`
- **Gate honesty**: Automated gate results and probe/smoke evidence never claim Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ `--live` acceptance. `not_live_acceptance` must be preserved across all new surfaces. `[VERIFIED: REQUIREMENTS.md OBS-10, ROADMAP.md L186, STATE.md L50]`
- **All new feature flags default OFF**: every new flag on `RuntimeFeatureFlags` defaults to `False`. `[VERIFIED: ROADMAP.md L37, packages/platform-runtime/src/platform_runtime/feature_flags.py L16-46]`
- **Keep changes scoped to the active GSD phase**: all edits must be within the active phase's plan scope. `[VERIFIED: AGENTS.md L41]`
- **Add tests with behavior changes**: especially for schemas, mappers, event ordering, dedupe, and fixture replay. `[VERIFIED: AGENTS.md L42]`
- **Backend/gateway/system notices suppressed**: Hermes gateway/meta/system/update/command/help notices must not leak to ordinary lawyer users. `[VERIFIED: AGENTS.md L8, L35]`

### Carried Human Gates (must NOT be auto-closed by Phase 87)

- Phase 5 live WeCom UAT `[VERIFIED: STATE.md L48-49, ROADMAP.md L31-35]`
- Phase 8 five-workday lawyer trial (artifacts at `.planning/phases/08-lawyer-trial-acceptance/`) `[VERIFIED: STATE.md L54-56]`
- Operator `--live` QQ OpenAPI acceptance (HUMAN GATE by design) `[VERIFIED: STATE.md L50]`

### Phase 87 Specific Scope

Phase 87 is a **verification-only** phase. It produces no new product features. It builds smoke/audit scripts and tests that confirm the console works end-to-end and that gate honesty, privacy, and stdlib-only constraints hold across all new surfaces (Phases 79–86). `[VERIFIED: ROADMAP.md L180-188]`

## 2. Standard Stack

Phase 87 introduces **no new libraries**. All verification work uses the existing stdlib-only stack.

| Component | Technology | Version | Source |
|-----------|-----------|---------|--------|
| Web UI server | `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` | Python ≥3.11 stdlib | `[VERIFIED: services/admin-web-ui/src/admin_web_ui/__main__.py L10, L100]` |
| API server | `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` | Python ≥3.11 stdlib | `[VERIFIED: services/admin-console-api/src/admin_console_api/server.py L12]` |
| SSR rendering | `html.escape()` + f-string templates (no template engine) | stdlib | `[VERIFIED: services/admin-web-ui/src/admin_web_ui/dashboard.py L18-20]` |
| Test framework | `unittest` (not pytest) | stdlib | `[VERIFIED: scripts/run_v2_gates.py L84-150]` |
| Gate runner | `scripts/run_v2_gates.py` (subprocess-isolated `unittest discover`) | project-specific | `[VERIFIED: scripts/run_v2_gates.py L49-150]` |
| Smoke test runner | `scripts/smoke_test.py` (QQBot Protocol-path, `--dry-run` default) | project-specific | `[VERIFIED: scripts/smoke_test.py L1-16]` |
| Startup script | bash (`set -euo pipefail`, env loading, PID tracking) | system bash | `[VERIFIED: scripts/start-console.sh L1-50]` |
| Process orchestration | `subprocess.Popen` + `threading.Lock` | stdlib | `[VERIFIED: services/admin-console-api/src/admin_console_api/process_supervisor.py L13-16, L50]` |
| HTTP client (smoke) | `urllib.request` / `urllib.error` | stdlib | `[VERIFIED: services/admin-web-ui/tests/test_main.py L8-10]` |
| Audit scripts | `scripts/scan_rbac_annotations.py`, `scripts/audit_v2_requirements.py` | project-specific | `[VERIFIED: scripts/scan_rbac_annotations.py L1-40]` |

**No packages to install.** Package Legitimacy Audit is not applicable — this phase adds zero external dependencies. `[VERIFIED: all pyproject.toml have dependencies = [] except wecom-service which lists only first-party packages — services/wecom-service/pyproject.toml]`

## 3. Architecture Patterns

### 3.1 Smoke Test Structure (existing QQBot pattern)

The existing `scripts/smoke_test.py` is the canonical smoke pattern for this codebase. Phase 87's end-to-end console smoke should mirror its structure: `[VERIFIED: scripts/smoke_test.py L1-924]`

- **Default `--dry-run`**: exercises leaf helpers + Protocol path via Fake transports and public DEMO/fixture credentials. Never claims live acceptance. `[VERIFIED: scripts/smoke_test.py L4-7]`
- **`--live` is an explicit HUMAN GATE**: owned by Phase 72; the script always stamps `not_live_acceptance=true` and never auto-claims live acceptance. CI/V2 gates must not invoke `--live`. `[VERIFIED: scripts/smoke_test.py L9-11]`
- **Evidence sanitization**: `sanitize_evidence()` drops forbidden keys (tokens, Authorization, BotSecret, raw content, URLs) and redacts banned substrings via `_strip_forbidden()` + `_redact_string()`. `[VERIFIED: scripts/smoke_test.py L119-186, L245-265]`
- **Step allowlist**: `_STEP_KEY_ALLOW` defines the exact keys allowed per step; unknown keys are dropped. `[VERIFIED: scripts/smoke_test.py L140-175]`
- **`not_live_acceptance=true` stamped on every evidence record** (dry-run and live). `[VERIFIED: scripts/smoke_test.py L250-257, L760, L793]`

### 3.2 Gate Runner Structure

`scripts/run_v2_gates.py` is the gate runner. Each gate is a `Gate(name, command, pythonpath)` tuple run via `subprocess` with `PYTHONPATH` set per-gate. `[VERIFIED: scripts/run_v2_gates.py L15-19, L49-150]`

- Gates run `python -m unittest discover -s <dir>` with the appropriate `PYTHONPATH`. `[VERIFIED: scripts/run_v2_gates.py L82-86]`
- `--json-summary` prints a sanitized JSON summary with `passed` (bool) and `gates` (list of `{name, exit_code}`). `[VERIFIED: scripts/run_v2_gates.py L25, L40-46]`
- The admin-console-api calls this via `subprocess.run` in `admin_console_api/gates.py` with a configurable timeout (300s default, 30s for health endpoint). `[VERIFIED: services/admin-console-api/src/admin_console_api/gates.py L33-57]`
- There is a `rbac-annotation-scan` gate that runs `scripts/scan_rbac_annotations.py` to enforce default-deny at CI time. `[VERIFIED: scripts/run_v2_gates.py L162-166]`

### 3.3 Privacy Audit Structure (existing patterns)

Privacy is enforced through two complementary mechanisms: `[VERIFIED: .planning/research/ARCHITECTURE.md]`

1. **Negative filter (`scrub_contract_payload`)**: rejects any key in `ALL_FORBIDDEN_KEYS` (tokens, secrets, raw payloads) by raising `ValueError`. Used by all contract-log-derived read views (audit, reports, logs). `[VERIFIED: services/conversation-read-view/src/conversation_read_view/privacy.py L51-62]`
2. **Positive allowlist (`HEALTH_ALLOWED_FIELDS`)**: only fields in the set are exposed in health responses. Prevents accidental exposure of new secret-like fields. `[VERIFIED: services/admin-console-api/src/admin_console_api/health.py L22-36]`
3. **HTML escaping (`html.escape` / `_esc`)**: every dynamic value in SSR pages passes through `html.escape` or a local `_esc` helper. `[VERIFIED: services/admin-web-ui/src/admin_web_ui/dashboard.py L18-20, boundary.py L48-63]`
4. **Output boundary (`AdminUiBoundary`)**: wraps `DefaultAssistantOutputBoundary.apply()` and HTML-escapes the resulting visible text, blocking model names, API error traces, and function call internals. `[VERIFIED: services/admin-web-ui/src/admin_web_ui/boundary.py L20-63]`
5. **Log reader scrubbing**: `LogReader` passes every JSONL line through `scrub_contract_payload`; plain-text lines have known secret env values replaced with `[REDACTED]`. `[VERIFIED: services/conversation-read-view/src/conversation_read_view/log_reader.py L6-9, L37]`

### 3.4 CSRF Protection Structure

CSRF is enforced via signed HMAC-SHA256 tokens bound to identity + route: `[VERIFIED: services/admin-web-ui/src/admin_web_ui/csrf.py L1-138]`

- `issue_csrf_token(identity, route, signing_key=...)` → `{nonce}.{signature}`. `[VERIFIED: csrf.py L90-110]`
- `validate_csrf_token(token, identity, route, signing_key=...)` → `hmac.compare_digest` verification. Fails closed on malformed/missing/tampered tokens. `[VERIFIED: csrf.py L113-138]`
- `_validate_post_csrf(body, identity, route, rbac_secret=...)` is the server-level helper that parses the form, extracts `csrf_token`, and validates. `[VERIFIED: services/admin-web-ui/src/admin_web_ui/server.py L755-774]`
- Every POST route in `_POST_ROUTES` validates CSRF before proxying to `handle_admin_put`. `[VERIFIED: server.py L134-141, L622-633]`
- Login/logout flows have their own CSRF validation via `handle_login_post` / `handle_logout_post`. `[VERIFIED: services/admin-web-ui/src/admin_web_ui/auth.py L140-143, L209-212]`

### 3.5 Gate Honesty Banner Structure

The gate-honesty banner is a shared UI element rendered on config and health pages: `[VERIFIED: services/admin-web-ui/src/admin_web_ui/dashboard.py L316-323]`

- `_render_gate_honesty_banner()` returns exact UI-SPEC copy: "This console does not close live acceptance gates" + "not_live_acceptance". `[VERIFIED: dashboard.py L318-322]`
- `_render_carried_human_gates_card()` renders the static carried human gates list. `[VERIFIED: dashboard.py L326-333]`
- `_render_carried_human_gates_row()` renders each carried gate with a distinct non-green visual state (`human-gate-carried` CSS class). `[VERIFIED: dashboard.py L336-344]`
- `CARRIED_HUMAN_GATES` is a static, read-only tuple in `health.py` — no API endpoint or UI control can mutate it. `[VERIFIED: services/admin-console-api/src/admin_console_api/health.py L55-59]`

## 4. Don't Hand-Roll

### 4.1 Existing Scripts to Reuse

| Script | Purpose | Reuse in Phase 87 |
|--------|---------|-------------------|
| `scripts/run_v2_gates.py` | Run all V2 gates via subprocess | Gate-honesty audit should run this and parse `--json-summary`; do NOT reimplement gate discovery `[VERIFIED: scripts/run_v2_gates.py]` |
| `scripts/smoke_test.py` | QQBot Protocol-path smoke (dry-run/live) | Reference pattern for the new console end-to-end smoke; reuse `sanitize_evidence`, `not_live_acceptance` stamping, banned-substring logic `[VERIFIED: scripts/smoke_test.py]` |
| `scripts/scan_rbac_annotations.py` | CI scan for unannotated RBAC endpoints | Reference pattern for source-scan audit scripts (grep/AST-based fail-closed) `[VERIFIED: scripts/scan_rbac_annotations.py]` |
| `scripts/audit_v2_requirements.py` | Deterministic requirement traceability | Reference for audit script structure (AST + grep, deterministic, no test re-run) `[VERIFIED: scripts/audit_v2_requirements.py]` |
| `scripts/start-console.sh` | One-click startup (env loading, PID tracking, trap cleanup) | The end-to-end smoke must boot via this script (or its `--dry-run` path for CI) `[VERIFIED: scripts/start-console.sh]` |

### 4.2 Existing Test Patterns to Reuse

| Pattern | Location | Reuse |
|---------|----------|-------|
| Socket-level integration test (boot on ephemeral port, `urllib.request`) | `services/admin-web-ui/tests/test_main.py L19-60` | The end-to-end smoke test should boot `create_server()` on port 0 and exercise routes via `urllib.request` `[VERIFIED]` |
| `handle_admin_web_ui_request` direct-call integration test | `services/admin-web-ui/tests/test_dashboard_logs.py L23-60`, `test_dashboard_audit.py`, `test_auth_session.py` | For unit-level smoke steps that don't need a real socket `[VERIFIED]` |
| Startup script structure test (grep-based) | `services/admin-web-ui/tests/test_startup_script.py L15-46` | Pattern for asserting script structure without executing it `[VERIFIED]` |
| CSRF token issue/validate test | `services/admin-web-ui/tests/test_csrf.py L41-60` | Pattern for CSRF audit tests `[VERIFIED]` |
| Boundary XSS test | `services/admin-web-ui/tests/test_boundary.py L15-58` | Pattern for XSS escape verification `[VERIFIED]` |

### 4.3 Existing Privacy/Scrubbing Primitives to Reuse

| Primitive | Location | Reuse |
|-----------|----------|-------|
| `scrub_contract_payload` | `services/conversation-read-view/src/conversation_read_view/privacy.py L51-62` | Privacy audit should grep for all rendering paths and confirm they call this or `html.escape` `[VERIFIED]` |
| `AdminUiBoundary.apply()` | `services/admin-web-ui/src/admin_web_ui/boundary.py L26-59` | XSS audit should confirm all SSR pages route dynamic text through this or `_esc` `[VERIFIED]` |
| `_esc` / `html.escape` | `services/admin-web-ui/src/admin_web_ui/dashboard.py L18-20` | Same as above `[VERIFIED]` |
| `sanitize_evidence` / `_strip_forbidden` | `scripts/smoke_test.py L207-265` | Reuse in the new console smoke's evidence sanitization `[VERIFIED]` |

## 5. Common Pitfalls

### 5.1 False-Positive Gate Claims

- **Pitfall**: A new page or report auto-claims Phase 5/8/QQ live acceptance by omitting the `not_live_acceptance` stamp or the gate-honesty banner. `[CITED: .planning/research/PITFALLS.md L227-228]`
- **Mitigation**: The gate-honesty audit must grep all new SSR pages for the banner copy and confirm `not_live_acceptance` appears in every smoke/probe evidence record. `[VERIFIED: scripts/smoke_test.py L250-257]`
- **Existing guard**: `CARRIED_HUMAN_GATES` is static and read-only; a source-scan test in Phase 84 already asserts no `mark_human_gate`/`pass_human_gate`/`close_human_gate` string exists. `[VERIFIED: .planning/phases/84-health-gate-dashboard-enhancement/84-PLAN.md L31]`

### 5.2 Missing CSRF on a State-Changing Route

- **Pitfall**: A new POST route is added to `_POST_ROUTES` but the handler skips `_validate_post_csrf` or validates against the wrong route string.
- **Mitigation**: The privacy/CSRF audit must enumerate every route in `_POST_ROUTES` and confirm each handler calls `_validate_post_csrf(body, identity, <exact_route>, rbac_secret=...)`. Also confirm login/logout validate CSRF. `[VERIFIED: server.py L134-141, L622-633, auth.py L140-143]`
- **Existing guard**: `test_csrf.py` validates cross-route/cross-role/cross-tenant token rejection. `[VERIFIED: test_csrf.py L41-60]`

### 5.3 Unescaped Output (XSS)

- **Pitfall**: A new rendering path interpolates dynamic content into HTML without `html.escape` or `_esc`, allowing script injection.
- **Mitigation**: The XSS audit must grep every `.py` file under `admin_web_ui/src` for f-string HTML interpolation and confirm each interpolated value passes through `_esc`/`html.escape`/`AdminUiBoundary.apply`. `[VERIFIED: dashboard.py L18-20, boundary.py L48-63]`
- **Watch**: `processes.py`, `logs.py`, and `audit.py` each define their own local `_esc` helper (not imported from dashboard) — the audit must confirm these are used consistently. `[VERIFIED: processes.py L37-44, logs.py L30-37, audit.py L16]`

### 5.4 Secret/Token/Bearer Literal in Log Files Under Tests

- **Pitfall**: A test writes a real token/secret/bearer literal to a log file that the log reader surfaces, or a smoke script prints a secret to stdout/evidence.
- **Mitigation**: The privacy audit must grep all test fixtures and test-generated log files for token/secret/bearer literals and confirm they are redacted. The smoke evidence must pass through `sanitize_evidence`. `[VERIFIED: scripts/smoke_test.py L119-186, L245-265]`
- **Existing guard**: `LogReader` scrubs every line via `scrub_contract_payload` and redacts known secret env values. `[VERIFIED: log_reader.py L6-9]`

### 5.5 New Third-Party Dependency Sneaking In

- **Pitfall**: A new `import` of a non-stdlib, non-first-party package is added to admin-web-ui or admin-console-api source.
- **Mitigation**: The stdlib-only audit must grep all `import` statements in new source files and confirm every import is either stdlib or a first-party package (`admin_web_ui`, `admin_console_api`, `rbac`, `conversation_read_view`, `platform_runtime`, `inkstatute_operator_config`, `feedback_service`). `[VERIFIED: all pyproject.toml have dependencies = []]`

### 5.6 Feature Flag Not Defaulting OFF

- **Pitfall**: A new flag is added to `RuntimeFeatureFlags` with `= True` default.
- **Mitigation**: The stdlib-only audit must inspect `feature_flags.py` and confirm every field defaults to `False`. `[VERIFIED: feature_flags.py L16-46 — all 23 flags default False]`

### 5.7 Smoke Test Invoking `--live` in CI

- **Pitfall**: The end-to-end smoke accidentally invokes `--live` or claims live acceptance.
- **Mitigation**: The console smoke must default to dry-run and stamp `not_live_acceptance=true`. CI/gates must never invoke `--live`. `[VERIFIED: scripts/smoke_test.py L9-11]`

## 6. Code Examples

### 6.1 Gate-Honesty Banner Language

`[VERIFIED: services/admin-web-ui/src/admin_web_ui/dashboard.py L316-323]`

```python
def _render_gate_honesty_banner() -> str:
    """Render the shared gate-honesty banner (exact UI-SPEC copy)."""
    return (
        '    <div class="notice-honesty" role="note" aria-label="Gate honesty notice">\n'
        '      <p class="notice-honesty-heading">This console does not close live acceptance gates</p>\n'
        '      <p class="notice-honesty-body">Saving config or running a probe does not claim Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ live acceptance. Smoke and probe evidence remains <code>not_live_acceptance</code>.</p>\n'
        '    </div>'
    )
```

Static carried human gates (read-only, never mutated): `[VERIFIED: services/admin-console-api/src/admin_console_api/health.py L55-59]`

```python
CARRIED_HUMAN_GATES: tuple[dict[str, Any], ...] = (
    {"name": "Phase 5 WeCom UAT", "status": "carried", "auto_closed": False},
    {"name": "Phase 8 lawyer trial", "status": "carried", "auto_closed": False},
    {"name": "QQ live acceptance", "status": "carried", "auto_closed": False},
)
```

### 6.2 CSRF Decorator / Validation Pattern

`[VERIFIED: services/admin-web-ui/src/admin_web_ui/server.py L755-774]`

```python
def _validate_post_csrf(
    body: bytes | str | None,
    identity: Identity,
    route: str,
    *,
    rbac_secret: str | None,
) -> tuple[bool, dict[str, Any] | None]:
    """Parse form body, extract csrf_token, and validate against the exact route."""
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body or "")
    form_map = parse_qs(text, keep_blank_values=True)
    token = _extract_csrf_token(form_map)
    if token is None:
        return False, None
    if not validate_csrf_token(token, identity, route, signing_key=rbac_secret):
        return False, None
    return True, form_map
```

Usage in a POST handler (channels): `[VERIFIED: server.py L622-633]`

```python
valid, form_map = _validate_post_csrf(
    form_body, identity, _CHANNELS_PATH, rbac_secret=rbac_secret
)
if not valid:
    html_body = render_channels_page(
        {"error": {"code": "forbidden", "message": ERROR_CSRF}},
        identity=identity,
        boundary=boundary,
        csrf_token=save_token,
        error_message=ERROR_CSRF,
    )
    return 403, html_body, response_headers
```

Login CSRF (anonymous identity, route-bound): `[VERIFIED: services/admin-web-ui/src/admin_web_ui/auth.py L140-143]`

```python
if csrf_token is None or not validate_csrf_token(
    csrf_token, ANONYMOUS_IDENTITY, LOGIN_PATH, signing_key=rbac_secret
):
    return 403, render_login_page(csrf_token=fresh_token, error_message="CSRF token invalid"), extra_headers
```

### 6.3 html.escape Usage

`[VERIFIED: services/admin-web-ui/src/admin_web_ui/dashboard.py L18-20]`

```python
import html

def _esc(value: Any) -> str:
    """HTML-escape a value for safe rendering."""
    return html.escape(str(value))
```

Boundary-applied escaping (wraps output boundary + escapes): `[VERIFIED: services/admin-web-ui/src/admin_web_ui/boundary.py L39-58]`

```python
decision = self._inner.apply("web", text=text, event_type=event_type, event_metadata=event_metadata)
if decision.action == BoundaryAction.ALLOW and decision.visible_text is not None:
    return BoundaryDecision(
        action=decision.action,
        visible_text=html.escape(decision.visible_text),
        audit_metadata=decision.audit_metadata,
        reason=decision.reason,
    )
```

### 6.4 scrub_contract_payload

`[VERIFIED: services/conversation-read-view/src/conversation_read_view/privacy.py L51-62]`

```python
def scrub_contract_payload(value: Any) -> Any:
    """Return a JSON-like copy after rejecting all forbidden payload fields."""
    forbidden_path = find_forbidden_key_path(value)
    if forbidden_path is not None:
        raise ValueError(f"contract read views must not expose forbidden key at {forbidden_path}")
    if isinstance(value, Mapping):
        return {str(key): scrub_contract_payload(child) for key, child in value.items()}
    if isinstance(value, list):
        return [scrub_contract_payload(child) for child in value]
    return value
```

Usage in audit handler: `[VERIFIED: services/conversation-read-view/src/conversation_read_view/audit.py L78-79]`

```python
scrubbed = scrub_contract_payload(reconstruction)
return 200, scrubbed
```

Usage in reports handler: `[VERIFIED: services/admin-console-api/src/admin_console_api/reports.py L14, L152-153]`

```python
from conversation_read_view.privacy import scrub_contract_payload
# ...
return 200, scrub_contract_payload(response)
```

Usage in log reader: `[VERIFIED: services/conversation-read-view/src/conversation_read_view/log_reader.py L6-9, L20]`

```python
# Every JSONL line is passed through scrub_contract_payload; plain-text lines
# have known secret env values replaced with [REDACTED].
from .privacy import scrub_contract_payload
```

### 6.5 Feature Flag Default OFF

`[VERIFIED: packages/platform-runtime/src/platform_runtime/feature_flags.py L14-46]`

```python
@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    run_runtime_enabled: bool = False
    streaming_lane_enabled: bool = False
    channel_delivery_enabled: bool = False
    # ... all 23 flags default False ...
    # v1.10 operator config — default OFF; mutate paths require explicit opt-in
    operator_config_enabled: bool = False
```

Flag gate at boot: `[VERIFIED: services/admin-web-ui/src/admin_web_ui/__main__.py L71-72]`

```python
feature_flags = RuntimeFeatureFlags.from_env(source)
feature_flags.require_enabled("admin_web_ui_enabled")
```

### 6.6 not_live_acceptance Stamping (smoke evidence)

`[VERIFIED: scripts/smoke_test.py L250-257]`

```python
def sanitize_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Return allowlisted, ban-list-clean evidence for stdout/file (SMOKE-04).
    Dry-run and live script paths always stamp not_live_acceptance=true
    (HUMAN GATE — never auto-claim acceptance).
    """
    stripped = _strip_forbidden(evidence)
    # ...
    # Always stamp not_live_acceptance=true (HUMAN GATE).
```

## 7. Verification Strategy

### Criterion 1: End-to-End Smoke

**What must be TRUE**: An end-to-end smoke boots the console via `start-console.sh`, logs in via session auth, starts a channel host subprocess, views its logs, browses the reports dashboard, and audits a contract event trace — all without errors and within stdlib-only constraints.

**Verification approach**:
1. **Build a new console smoke script** (e.g. `scripts/smoke_console.py` or a unittest module) that:
   - Boots `admin_web_ui.create_server()` on ephemeral port 0 (mirroring `test_main.py` pattern) `[VERIFIED: services/admin-web-ui/tests/test_main.py L42-46]`
   - Sets env: `INKSTATUTE_ADMIN_WEB_UI_ENABLED=true`, `INKSTATUTE_ADMIN_API_ENABLED=true`, `INKSTATUTE_RBAC_ENABLED=true`, `RBAC_TOKEN_SECRET=test-secret`, `ADMIN_USERNAME=admin`, `ADMIN_PASSWORD=test-pass`, `INKSTATUTE_CONTRACT_LOG_PATH=<fixture>`, `INKSTATUTE_FEEDBACK_QUEUE_PATH=<fixture>`
   - Step 1: GET `/login` → extract CSRF token from form `[VERIFIED: test_auth_session.py L71-78 pattern]`
   - Step 2: POST `/login` with CSRF + credentials → assert 302 + `Set-Cookie: inkstatute_session=...` `[VERIFIED: auth.py L168-176]`
   - Step 3: GET `/processes` with session cookie → assert 200 + process list `[VERIFIED: server.py L488-495]`
   - Step 4: POST `/processes` with CSRF + `name=wecom&action=start` → assert 200/302 (start channel host subprocess) `[VERIFIED: processes.py L15-23]`
   - Step 5: GET `/logs?source=wecom_stdout` with cookie → assert 200 + scrubbed log lines `[VERIFIED: logs.py L40-60]`
   - Step 6: GET `/reports?window=7d` with cookie → assert 200 + aggregate stats `[VERIFIED: reports.py L10-60]`
   - Step 7: GET `/audit` with cookie → assert 200 + AgentTurn/FeedbackEvent items `[VERIFIED: audit.py L27-60]`
   - Step 8: GET `/audit/<trace_id>` with cookie → assert 200 + trace reconstruction `[VERIFIED: audit.py L61-79]`
   - Stamp `not_live_acceptance=true` on the evidence record `[VERIFIED: smoke_test.py L250-257 pattern]`
2. **Alternative**: boot via `scripts/start-console.sh --dry-run` for CI (no port binding) and assert the dry-run output structure `[VERIFIED: scripts/start-console.sh L9-21]`
3. **Run**: `python -m unittest discover -s services/admin-web-ui/tests` (the smoke test lives here or in a new test file) + `python scripts/smoke_console.py --dry-run`

**Grep patterns to confirm coverage**:
- `grep -rn "create_server" services/admin-web-ui/tests/` — confirms socket-level boot test exists
- `grep -rn "Set-Cookie.*inkstatute_session" services/admin-web-ui/tests/` — confirms session cookie assertion
- `grep -rn "/processes.*action=start" services/admin-web-ui/tests/` — confirms process start step
- `grep -rn "/audit/" services/admin-web-ui/tests/test_dashboard_audit.py` — confirms audit trace step

### Criterion 2: Gate-Honesty Audit

**What must be TRUE**: No new page, report, or dashboard auto-claims Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ `--live` acceptance (`not_live_acceptance` preserved across all new surfaces).

**Verification approach**:
1. **Build a gate-honesty audit script/test** that:
   - Greps all SSR page render functions in `admin_web_ui/src` for the gate-honesty banner copy ("This console does not close live acceptance gates") on config/health/gates pages `[VERIFIED: dashboard.py L316-323]`
   - Greps for `not_live_acceptance` in all smoke/probe evidence code paths `[VERIFIED: smoke_test.py L250-257]`
   - Asserts `CARRIED_HUMAN_GATES` is static and `auto_closed: False` for all three entries `[VERIFIED: health.py L55-59]`
   - Asserts no `mark_human_gate`/`pass_human_gate`/`close_human_gate`/`auto_close` mutation string exists in `dashboard.py` or `health.py` `[VERIFIED: 84-PLAN.md L31 pattern]`
   - Asserts no new page renders a "passed"/"accepted"/"UAT complete" claim for Phase 5/8/QQ

**Commands**:
```bash
grep -rn "not_live_acceptance" services/admin-web-ui/src/ services/admin-console-api/src/ scripts/smoke_test.py
grep -rn "This console does not close live acceptance" services/admin-web-ui/src/
grep -rn "mark_human_gate\|pass_human_gate\|close_human_gate\|auto_close.*True" services/admin-web-ui/src/ services/admin-console-api/src/
grep -rn "CARRIED_HUMAN_GATES" services/admin-console-api/src/admin_console_api/health.py
```

### Criterion 3: Privacy/XSS Audit

**What must be TRUE**: Every new rendering path passes through `html.escape`/`scrub_contract_payload`, no token/secret/bearer literal appears in log files under tests, and every new state-changing route carries CSRF protection.

**Verification approach**:
1. **XSS audit (source-scan test)**:
   - Enumerate all `.py` files under `services/admin-web-ui/src/admin_web_ui/`
   - For each f-string containing HTML tags (`<td>`, `<div>`, `<span>`, `<p>`, `<h`, `<a `, `<table`), confirm interpolated values pass through `_esc`/`html.escape`/`boundary.apply`/`_esc_dict`
   - Confirm `processes.py`, `logs.py`, `audit.py` local `_esc` helpers are used (not bypassed) `[VERIFIED: processes.py L37-44, logs.py L30-37, audit.py L16]`
   - Grep: `grep -rn "f'.*<\|f\".*<" services/admin-web-ui/src/admin_web_ui/` then manually/AST verify each interpolation is escaped

2. **Scrub audit (source-scan test)**:
   - Confirm `handle_audit`, `handle_reports`, `handle_logs` all call `scrub_contract_payload` on responses `[VERIFIED: audit.py L78, reports.py L152, log_reader.py L20]`
   - Grep: `grep -rn "scrub_contract_payload" services/admin-console-api/src/ services/conversation-read-view/src/`

3. **Secret-in-logs audit**:
   - Grep all test fixtures and test-generated temp files for bearer/token/secret literals: `grep -rni "bearer \|authorization.*token\|bot_secret\|client_secret" services/admin-web-ui/tests/ services/admin-console-api/tests/ --include="*.json" --include="*.jsonl"`
   - Confirm `LogReader` redacts `_SECRET_KEY_HINTS` (`secret`, `token`, `key`, `password`, `authorization`, `cookie`) `[VERIFIED: log_reader.py L37]`

4. **CSRF audit (source-scan test)**:
   - Enumerate `_POST_ROUTES` (`/config/channels`, `/config/providers`, `/config/providers/probe`, `/config/catalog`, `/config/vision`, `/processes`) `[VERIFIED: server.py L134-141]`
   - For each, confirm the handler calls `_validate_post_csrf(body, identity, <exact_route>, rbac_secret=...)` `[VERIFIED: server.py L622-633]`
   - Confirm `/login` and `/logout` validate CSRF `[VERIFIED: auth.py L140-143, L209-212]`
   - Grep: `grep -rn "_validate_post_csrf\|validate_csrf_token" services/admin-web-ui/src/admin_web_ui/server.py services/admin-web-ui/src/admin_web_ui/auth.py`

### Criterion 4: Stdlib-Only Constraint Audit

**What must be TRUE**: No new third-party dependency, no new DB/queue/SPA, and every new feature flag defaults OFF.

**Verification approach**:
1. **Dependency audit**:
   - Grep all `pyproject.toml` for `dependencies` and confirm all are `[]` (except `wecom-service` which lists only first-party packages) `[VERIFIED: all pyproject.toml scanned]`
   - Grep all `import` statements in `services/admin-web-ui/src` and `services/admin-console-api/src` for non-stdlib, non-first-party packages: `grep -rn "^import \|^from " services/admin-web-ui/src/ services/admin-console-api/src/ | grep -v "from \.\|from __future__\|from typing\|from collections\|from dataclasses\|from pathlib\|from urllib\|from datetime\|from http\|from json\|from os\|from sys\|import os\|import sys\|import json\|import html\|import time\|import hmac\|import signal\|import threading\|import argparse\|import traceback\|import base64\|import hashlib\|import secrets\|import re\|import subprocess\|from rbac\|from admin_\|from conversation_\|from platform_\|from inkstatute_\|from feedback_"`
   - Confirm no `import flask`, `import fastapi`, `import django`, `import requests`, `import psutil`, `import celery`, `import redis`, `import aiohttp`, `import websocket` `[VERIFIED: grep returned no matches]`

2. **No new DB/queue/SPA audit**:
   - Confirm no new `sqlite3`, `shelve`, `dbm`, `redis`, `celery` imports in new source
   - Confirm no new `.db`, `.sqlite`, `.redis` files created
   - Confirm no new `package.json`, `node_modules`, `vite.config`, `webpack.config` files (no SPA)

3. **Feature flag default OFF audit**:
   - Inspect `packages/platform-runtime/src/platform_runtime/feature_flags.py` and confirm every field on `RuntimeFeatureFlags` defaults to `False` `[VERIFIED: feature_flags.py L16-46 — all 23 flags default False]`
   - Grep: `grep -n "= True" packages/platform-runtime/src/platform_runtime/feature_flags.py` should return zero matches (excluding comments)

**Commands**:
```bash
grep -rn "^dependencies" --include="pyproject.toml" . | grep -v "\[\]"
grep -rn "import flask\|import fastapi\|import django\|import requests\|import psutil\|import celery\|import redis\|import aiohttp\|import websocket" services/ packages/
grep -n "= True" packages/platform-runtime/src/platform_runtime/feature_flags.py
grep -rn "sqlite3\|import shelve\|import dbm" services/admin-web-ui/src/ services/admin-console-api/src/
```

## 8. Phase 87 Scope

### What Already EXISTS (do NOT rebuild)

| Artifact | Location | Status |
|----------|----------|--------|
| One-click startup script | `scripts/start-console.sh` | Phase 86 — complete with `--dry-run`, env loading, PID tracking, trap cleanup `[VERIFIED]` |
| Gate runner | `scripts/run_v2_gates.py` | Complete, 24+ gates, `--json-summary` `[VERIFIED]` |
| QQBot smoke test | `scripts/smoke_test.py` | Complete, dry-run/live, `not_live_acceptance` stamping, evidence sanitization `[VERIFIED]` |
| RBAC annotation scan | `scripts/scan_rbac_annotations.py` | Complete, CI gate `[VERIFIED]` |
| Requirement audit | `scripts/audit_v2_requirements.py` | Complete, traceability matrix `[VERIFIED]` |
| Session auth (login/logout) | `services/admin-web-ui/src/admin_web_ui/auth.py` | Phase 85 — complete with CSRF, HMAC cookies `[VERIFIED]` |
| Process orchestration | `services/admin-console-api/src/admin_console_api/process_supervisor.py` | Phase 80 — complete with start/stop/restart, health probe `[VERIFIED]` |
| Reports dashboard | `services/admin-console-api/src/admin_console_api/reports.py` | Phase 81 — complete with bounded aggregation, `scrub_contract_payload` `[VERIFIED]` |
| Log viewing | `services/admin-console-api/src/admin_console_api/logs.py` + `conversation_read_view/log_reader.py` | Phase 82 — complete with byte-offset tail-follow, scrubbing `[VERIFIED]` |
| Contract event audit | `services/admin-console-api/src/admin_console_api/audit.py` + `conversation_read_view/audit.py` | Phase 83 — complete with pagination, trace reconstruction, field allowlist `[VERIFIED]` |
| Health/gate dashboard | `services/admin-console-api/src/admin_console_api/health.py` | Phase 84 — complete with unified view, `CARRIED_HUMAN_GATES` `[VERIFIED]` |
| Gate-honesty banner | `services/admin-web-ui/src/admin_web_ui/dashboard.py` L316-323 | Complete, exact UI-SPEC copy `[VERIFIED]` |
| CSRF module | `services/admin-web-ui/src/admin_web_ui/csrf.py` | Phase 76/85 — complete HMAC-SHA256 tokens `[VERIFIED]` |
| Output boundary | `services/admin-web-ui/src/admin_web_ui/boundary.py` | Complete, HTML-escapes visible text `[VERIFIED]` |
| Privacy scrubbing | `services/conversation-read-view/src/conversation_read_view/privacy.py` | Complete, `scrub_contract_payload` `[VERIFIED]` |
| Feature flags (all default OFF) | `packages/platform-runtime/src/platform_runtime/feature_flags.py` | Complete, 23 flags all `False` `[VERIFIED]` |
| Socket-level integration test pattern | `services/admin-web-ui/tests/test_main.py` | Phase 79 — boot on ephemeral port `[VERIFIED]` |
| Startup script structure test | `services/admin-web-ui/tests/test_startup_script.py` | Phase 86 — grep-based structure assertions `[VERIFIED]` |
| `.env.example` | `.env.example` | Phase 86 — documents all env vars `[VERIFIED]` |

### What Needs to be BUILT in Phase 87

| Artifact | Purpose | Success Criterion |
|----------|---------|-------------------|
| **Console end-to-end smoke script/test** (`scripts/smoke_console.py` or `services/admin-web-ui/tests/test_smoke_e2e.py`) | Boots console via `create_server()`, logs in via session auth, starts a channel host, views logs, browses reports, audits a trace — all without errors | SC1 |
| **Gate-honesty audit test** (`services/admin-web-ui/tests/test_gate_honesty_audit.py` or `scripts/audit_gate_honesty.py`) | Source-scan confirms banner copy on all config/health/gates pages, `not_live_acceptance` in all smoke/probe evidence, `CARRIED_HUMAN_GATES` static + `auto_closed: False`, no mutation strings | SC2 |
| **Privacy/XSS audit test** (`services/admin-web-ui/tests/test_privacy_xss_audit.py` or `scripts/audit_privacy_xss.py`) | Source-scan confirms every rendering path uses `html.escape`/`_esc`/`boundary.apply`, every API response uses `scrub_contract_payload`, no secret literals in test fixtures/logs, every POST route validates CSRF | SC3 |
| **Stdlib-only constraint audit test** (`services/admin-web-ui/tests/test_stdlib_only_audit.py` or `scripts/audit_stdlib_only.py`) | Confirms all `pyproject.toml` have `dependencies = []` (or first-party only), no third-party imports, no new DB/queue/SPA files, all feature flags default `False` | SC4 |
| **Phase 87 verification artifact** (`.planning/phases/87-integration-smoke-gate-honesty/87-VERIFICATION.md`) | Documents that all 4 success criteria are met with concrete evidence | — |

### Design Decisions for the Plan Phase

1. **Smoke script vs unittest**: The smoke can be either a standalone `scripts/smoke_console.py` (mirroring `smoke_test.py`) or a unittest module. Given the codebase convention of socket-level integration tests in `test_main.py`, a **unittest module** that boots `create_server()` on port 0 is the most consistent approach. A standalone script with `--dry-run`/`--json-summary` (mirroring `smoke_test.py`) is also acceptable for CI ergonomics. `[ASSUMED]`
2. **Audit scripts vs unittest**: The three audits (gate-honesty, privacy/XSS, stdlib-only) can be either standalone scripts (mirroring `scan_rbac_annotations.py`) or unittest modules. Unittest modules are preferable because they integrate into `run_v2_gates.py` automatically. `[ASSUMED]`
3. **No new gate needed**: If the audits are unittest modules under existing test directories, they are automatically discovered by the existing `admin-web-ui` and `admin-console-api` gates. No new gate entry in `run_v2_gates.py` is required. `[ASSUMED]`
4. **`not_live_acceptance` in console smoke**: The console smoke must stamp `not_live_acceptance=true` on its evidence record, mirroring `smoke_test.py`. `[VERIFIED: smoke_test.py L250-257 pattern]`
5. **Start channel host in smoke**: Starting a real WeCom/QQBot subprocess in the smoke may require fixture env and could be flaky. The smoke should either (a) mock `ProcessSupervisor` and assert the POST returns 200/302, or (b) start a real subprocess with fixture env on port 0 and assert health probe. Option (a) is safer for CI; option (b) is more end-to-end. `[ASSUMED]`
