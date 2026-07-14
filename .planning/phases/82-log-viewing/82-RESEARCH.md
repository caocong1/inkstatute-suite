# Phase 82: Log Viewing — Research

**Researched:** 2026-07-14
**Phase:** 82 — Log Viewing
**Requirements:** OBS-04, OBS-05, OBS-06
**Depends on:** Phase 79 (flags/matrix + threading), Phase 80 (host logging config)

---

## 1. Log File Structures and Paths

### 1.1 Contract Events JSONL (`events.jsonl`)

- **Writer:** `services/hermes-contract-layer/src/hermes_contract_layer/writer.py` — `ContractEventWriter.append()` writes one JSON object per line, newline-terminated.
- **Line shape:** `{"event_key": "agent_turn", "occurred_at": "2026-07-14T...", "ingested_at": "...", "seq": 0, "event": {...}}` (sorted keys, compact separators).
- **Env var:** `INKSTATUTE_CONTRACT_LOG_PATH` — resolved in `admin-console-api/server.py:182` and `admin-web-ui/__main__.py:82`. Default: unset (empty read model).
- **Privacy:** Contract logs should prefer `raw_payload_ref` over `raw_payload`. The `scrub_contract_payload` function rejects any line containing keys in `ALL_FORBIDDEN_KEYS`.

### 1.2 Runtime Audit JSONL (`runtime-audit.jsonl`)

- **Writer:** `services/wecom-service/src/wecom_service/runtime_audit.py` — `append_runtime_audit(path, kind=, direction=, payload=, include_payload=, metadata=)`.
- **Line shape:** `{"occurred_at": "...", "kind": "receive", "direction": "inbound", "payload_summary": {"sha256_16": "...", "length": N}, "metadata": {...}}`. When `include_payload=True`, a `payload` field is included (redacted via `_redact_secrets`).
- **Env var:** No dedicated env var exists yet. The live bridge script (`scripts/inkstatute_wecom_live_bridge.py:655`) defaults to `runtime_dir / "runtime-audit.jsonl"`. Phase 82 should introduce `INKSTATUTE_RUNTIME_AUDIT_PATH` for the log viewer to resolve this source.
- **Privacy:** `_redact_secrets` already strips secret-keyed fields at write time, but `scrub_contract_payload` must still be applied at read time as defense-in-depth (the audit file may contain `payload` with `raw_payload` sub-keys if `include_payload=True`).

### 1.3 Feedback Queue JSONL (`feedback.jsonl`)

- **Env var:** `INKSTATUTE_FEEDBACK_QUEUE_PATH` — resolved in `admin-console-api/server.py:186` and `admin-web-ui/__main__.py:86`.
- **Structure:** FeedbackEvent records as JSONL, one per line. Loaded by `feedback_service.queue.load_jsonl_records` and built via `build_pending_feedback_queue`.
- **Privacy:** Feedback events may contain user message references; `scrub_contract_payload` applies.

### 1.4 Child-Process stdout/stderr Logs

- **Writer:** `services/admin-console-api/src/admin_console_api/process_supervisor.py:228-239` — `ProcessSupervisor.start()` opens `log_path = self._log_dir / f"{name}-host.log"` in append-binary mode and passes it as `stdout` with `stderr=subprocess.STDOUT`.
- **Log dir env var:** `INKSTATUTE_PROCESS_LOG_DIR` — resolved in `process_supervisor.py:58-62`. Default: `Path.home() / ".inkstatute" / "process-logs"`.
- **Log paths:** `{log_dir}/wecom-host.log` and `{log_dir}/qqbot-host.log`.
- **Record field:** `ProcessRecord.log_path` (str) stores the absolute path; visible in `GET /processes` response and the processes UI page.
- **Format:** Plain text stdout/stderr — not JSONL. Lines may contain Python logging output, tracebacks, or print statements. Level filtering must handle non-JSON lines by falling back to text-level grep (e.g., `ERROR:`, `WARN`, `INFO:` patterns).

---

## 2. Phase 80 Host Logging Config

### 2.1 ProcessSupervisor (`process_supervisor.py`)

- `_resolve_log_dir()` reads `INKSTATUTE_PROCESS_LOG_DIR` from env, defaults to `~/.inkstatute/process-logs/`.
- `_ensure_log_dir()` creates the directory with `mkdir(parents=True, exist_ok=True)`.
- `start()` opens the log file in append-binary (`"ab"`), passes it as `stdout` to `subprocess.Popen`, and closes the file handle immediately after `Popen` (the child inherits the fd).
- `ProcessRecord` stores `log_path` as a string field; `status_all()` returns records that include it.
- Thread safety: `self._lock = threading.Lock()` guards `_procs` and `_registry` mutations.

### 2.2 Processes API (`processes_api.py`)

- `handle_process_get(path, process_supervisor, feature_flags)` — GET `/processes` returns all records; GET `/processes/<name>` returns a single record.
- `handle_process_put(path, body, process_supervisor, feature_flags)` — PUT `/processes/<name>/<action>` where action ∈ {start, stop, restart}.
- `_PROCESS_NAMES = {"wecom", "qqbot"}` — fixed allowlist, same pattern Phase 82 should reuse for log source names.
- Feature flag gate: `admin_api_enabled` checked first; 503 if disabled.

### 2.3 Process Record Structure (`process_registry.py`)

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

The `log_path` field is the key link from process orchestration to log viewing — the log viewer can use `ProcessSupervisor` to resolve child-process log paths dynamically.

---

## 3. Admin Console API Server Wiring

### 3.1 `server.py` — `create_server(env)`

- Creates `RuntimeFeatureFlags.from_env(source)`, calls `require_enabled("admin_api_enabled")`.
- Resolves `INKSTATUTE_CONTRACT_LOG_PATH` → builds `read_model` via `_build_read_model()`.
- Resolves `INKSTATUTE_FEEDBACK_QUEUE_PATH` → builds `feedback_queue` via `_build_feedback_queue()`.
- Creates `ReportsAggregator(contract_log_path, env=source)`.
- Creates `ProcessSupervisor(env=source, config_store=config_store)`, calls `reconcile_on_startup()`.
- Sets all deps as attributes on the `ThreadingHTTPServer` instance: `feature_flags`, `env`, `rbac_secret`, `read_model`, `feedback_queue`, `config_store`, `process_supervisor`, `reports_aggregator`.
- Overrides `httpd.shutdown` to call `process_supervisor.shutdown_all()` first.
- **Phase 82 addition:** A `LogReader` instance (or the env dict) must be wired here so `handle_admin_get` can access it for `/logs`.

### 3.2 `api.py` — `handle_admin_get` / `handle_admin_put`

- `_authenticate_admin()` runs the full pipeline: feature flag → auth header → RBAC `resolve_identity` → `RbacGuard.check(role, route_path)` → `TenantScopeResolver` → `TenantGuard.enforce`.
- `handle_admin_get` routes by prefix:
  - `/sessions`, `/tasks` → views handlers
  - `/feedback` → feedback handler
  - `/health` → health handler
  - `/gates` → gates handler
  - `/processes` → `handle_process_get`
  - `/reports` → `handle_reports`
  - `/config` → `handle_config_get`
  - else → 404
- **Phase 82 addition:** Add `/logs` route → `handle_logs` handler, passing `log_reader` (or env) from server instance.

### 3.3 `routes.py` — `ROUTE_PREFIXES`

```python
ROUTE_PREFIXES: tuple[str, ...] = (
    "/sessions", "/tasks", "/feedback", "/health", "/gates", "/config", "/reports",
)
```
- **Phase 82 addition:** Add `"/logs"` to this tuple so the RBAC CI scan (`scripts/scan_rbac_annotations.py`) enforces the matrix entry.

---

## 4. Admin Web UI Server Wiring

### 4.1 `server.py` — `handle_admin_web_ui_request`

Request flow:
1. Feature flag gate (`admin_web_ui_enabled`)
2. Route resolution via `_SECTION_MAP` (dict mapping path → section name)
3. Method check (POST only on `_POST_ROUTES`; all others GET-only)
4. RBAC auth: `resolve_identity` → `RbacGuard.check(identity.role, _guard_path(route_path))`
5. Route-specific handlers: `_handle_channels`, `_handle_providers`, `_handle_processes`, etc.
6. Default: proxy to `admin-console-api` via `AdminApiClient.proxy()`, then `render_dashboard(section, api_data, identity, boundary)`.

### 4.2 `_SECTION_MAP`

```python
_SECTION_MAP = {
    "/": "index",
    "/sessions": "sessions",
    "/tasks": "tasks",
    "/feedback": "feedback",
    "/health": "health",
    "/gates": "gates",
    "/reports": "reports",
    "/processes": "processes",
    "/config/channels": "channels",
    "/config/providers": "providers",
    "/config/providers/probe": "providers_probe",
    "/config/catalog": "catalog",
    "/config/vision": "vision",
}
```
- **Phase 82 addition:** Add `"/logs": "logs"` entry.

### 4.3 `_guard_path(route_path)`

Maps UI routes to RBAC matrix prefixes:
- `/` → `/sessions`
- `/config/*` → `/config`
- `/processes` or `/processes/*` → `/config`
- else → `route_path` as-is

- **Phase 82 addition:** `/logs` should map to `/logs` (its own RBAC prefix), not to `/config`.

### 4.4 `AdminApiClient.proxy()`

Passes `process_supervisor`, `reports_aggregator`, `config_store` as kwargs to `handle_admin_get` only when they are not None. **Phase 82 addition:** Add `log_reader` pass-through in the same pattern.

### 4.5 `__main__.py` — `create_server(env)`

Mirrors `admin-console-api/server.py:create_server`: builds `feature_flags`, `read_model`, `feedback_queue`, `reports_aggregator`, `process_supervisor`, and sets them as server attributes. **Phase 82 addition:** Build `LogReader` and wire it as `httpd.log_reader`.

---

## 5. Privacy Scrubbing

### 5.1 `scrub_contract_payload` (`conversation-read-view/src/conversation_read_view/privacy.py`)

```python
def scrub_contract_payload(value: Any) -> Any:
    forbidden_path = find_forbidden_key_path(value)
    if forbidden_path is not None:
        raise ValueError(f"contract read views must not expose forbidden key at {forbidden_path}")
    if isinstance(value, Mapping):
        return {str(key): scrub_contract_payload(child) for key, child in value.items()}
    if isinstance(value, list):
        return [scrub_contract_payload(child) for child in value]
    return value
```

- **Behavior:** Recursively walks the value. If any key in `ALL_FORBIDDEN_KEYS` is found, raises `ValueError` (fail-closed). Otherwise returns a deep copy with all keys stringified.
- **`ALL_FORBIDDEN_KEYS`** (`platform-runtime/src/platform_runtime/privacy_keys.py`): `{"raw_payload", "case_facts", "customer_document_text", "document_text", "full_text", "payload_text", "raw_text", "prompt_content", "completion_text", "function_call_result", "tool_output"}`.
- **Usage pattern in reports:** `reports.py:144` calls `scrub_contract_payload(aggregate)` on the final payload. `reports_aggregator.py:170` calls it on every record during scanning.
- **Phase 82 usage:** For JSONL lines (contract events, runtime audit, feedback), parse JSON → `scrub_contract_payload` → re-serialize for display. For plain-text stdout/stderr lines, the line is not JSON — apply `scrub_contract_payload` to the raw string (it passes through as-is since it's not a Mapping/list), but also apply a text-level secret redaction pass. If a JSON line contains a forbidden key, the line must be replaced with a redaction marker (e.g., `"[REDACTED: forbidden key at path X]"`) rather than raising, so one bad line doesn't break the entire log view.

### 5.2 Import Path

```python
from conversation_read_view.privacy import scrub_contract_payload
```

Already used by `admin_console_api/reports.py:14` and `conversation_read_view/reports_aggregator.py:14`. The `conversation-read-view` package is on `PYTHONPATH` in both `admin-console-api` and `admin-web-ui` entry points.

---

## 6. Dashboard Rendering Patterns

### 6.1 `dashboard.py` — `render_dashboard(section, data, identity, boundary)`

- Dispatches by section name to section-specific renderers: `_render_index`, `_render_list_section`, `_render_feedback_section`, `_render_health_section`, `_render_gates_section`, `_render_reports_section`.
- All dynamic content is HTML-escaped via `_esc()` (wraps `html.escape`).
- `_page_template(title, body, identity)` renders the full HTML document with nav links, CSS, and identity banner.
- Nav items are hardcoded in `_page_template` — **Phase 82 addition:** Add `("/logs", "Logs")` to nav_items.

### 6.2 Section-Specific Page Modules

Phase 80 created `services/admin-web-ui/src/admin_web_ui/processes.py` with:
- `render_processes_page(api_data, identity, boundary, csrf_token, error_message, flash, flash_kind)` — renders the full page using `_page_template` from `dashboard.py`.
- `parse_processes_form(form_map)` — validates form input against an allowlist.
- `_esc()` local helper (same pattern as dashboard.py).
- `_ALLOWED_NAMES = {"wecom", "qqbot"}` — fixed allowlist.

**Phase 82 pattern:** Create `services/admin-web-ui/src/admin_web_ui/logs.py` with `render_logs_page(api_data, identity, boundary, query_params)` following the same pattern — escaped HTML, `_page_template`, source selector dropdown, level filter, keyword search input, log lines in a `<pre>` block, and a JavaScript polling snippet that uses `fetch()` with the last `next_offset` as a query parameter.

### 6.3 Server Route Handler Pattern

Phase 80's `_handle_processes` in `server.py`:
- Issues CSRF token for POST.
- GET: proxies to `handle_admin_get` via `AdminApiClient.proxy()`, then calls `render_processes_page()`.
- POST: validates CSRF, parses form, proxies PUT via `AdminApiClient.proxy_put()`.

**Phase 82 pattern:** `/logs` is GET-only (no POST, no mutation). The handler should:
1. Proxy to `handle_admin_get` with the full query string (source, level, q, offset).
2. Call `render_logs_page()` with the API response.
3. Return HTML with CSP headers.

---

## 7. RBAC Matrix and CI Scan

### 7.1 `PERMISSIONS_MATRIX` (`packages/rbac/src/rbac/matrix.py`)

```python
PERMISSIONS_MATRIX = {
    "/sessions": {ADMIN, OPERATOR, LAWYER, VIEWER},
    "/tasks": {ADMIN, OPERATOR, LAWYER, VIEWER},
    "/feedback": {ADMIN, OPERATOR},
    "/health": {ADMIN, OPERATOR},
    "/gates": {ADMIN},
    "/skills-write": {ADMIN},
    "/config": {ADMIN, OPERATOR},
    "/processes": {ADMIN, OPERATOR},
    "/reports": {ADMIN, OPERATOR, LAWYER, VIEWER},
}
```

- **Phase 82 addition:** `"/logs": frozenset({Role.ADMIN, Role.OPERATOR})` — logs contain operational detail; lawyer/viewer should not see runtime logs.
- `RbacGuard.check(role, endpoint)` uses longest-prefix match. `/logs` and `/logs/<source>` both resolve to the `/logs` prefix.

### 7.2 RBAC CI Scan (`scripts/scan_rbac_annotations.py`)

- Reads `ROUTE_PREFIXES` from `admin_console_api.routes` and `PERMISSIONS_MATRIX` from `rbac.matrix`.
- Fails (exit 1) if any route prefix lacks a matrix entry.
- **Phase 82:** Must add `/logs` to both `ROUTE_PREFIXES` and `PERMISSIONS_MATRIX` simultaneously or the CI scan will fail.

---

## 8. Architecture Research Notes

From `.planning/research/ARCHITECTURE.md` (Phase 82 section, lines 61-73):

- **Location:** `services/admin-console-api/src/admin_console_api/logs.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/logs.py` (NEW SSR page).
- **Data flow:** `GET /logs/{source}?level=ERROR&seek=12345&q=keyword` → `LogReader.read(source, offset, level_filter, search)` → `open(log_path, "r"), seek(offset), read lines forward, parse JSONL, filter by level/search` → `return {lines: [...], next_offset: <byte_pos>, eof: bool}`.
- **Tail-follow:** Client polls with last `next_offset`; server reads from byte offset onward.
- **Design:** `LogReader` is a pure stdlib class (`open`/`seek`/`readline`). Sources mapped by name → file path via a `LOG_SOURCES` registry. Privacy: every line through `scrub_contract_payload`. Level filter parses `level` field in JSONL or falls back to text grep for non-JSON stdout logs.

---

## 9. Log Source Registry Design

The log viewer needs a fixed allowlist of source names mapped to file paths. The path-traversal guard validates the source name against this allowlist — no user-supplied file paths are ever accepted.

### 9.1 Source Names and Path Resolution

| Source Name | Env Var | Default Path | Format |
|---|---|---|---|
| `contract_events` | `INKSTATUTE_CONTRACT_LOG_PATH` | (unset = empty) | JSONL |
| `runtime_audit` | `INKSTATUTE_RUNTIME_AUDIT_PATH` (NEW) | (unset = empty) | JSONL |
| `feedback` | `INKSTATUTE_FEEDBACK_QUEUE_PATH` | (unset = empty) | JSONL |
| `wecom_stdout` | `INKSTATUTE_PROCESS_LOG_DIR` + `/wecom-host.log` | `~/.inkstatute/process-logs/wecom-host.log` | Plain text |
| `qqbot_stdout` | `INKSTATUTE_PROCESS_LOG_DIR` + `/qqbot-host.log` | `~/.inkstatute/process-logs/qqbot-host.log` | Plain text |

### 9.2 Path-Traversal Guard

- `_ALLOWED_SOURCES = frozenset({"contract_events", "runtime_audit", "feedback", "wecom_stdout", "qqbot_stdout"})`.
- The source name is validated against this set. No path concatenation from user input.
- File paths are resolved only from env vars or defaults — never from query parameters.
- Reject `..`, absolute paths, and symlinks: after resolving the path, check `Path.resolve()` is within the expected directory for child-process logs (the log dir). For env-var-sourced paths (contract events, audit, feedback), the path is trusted because it comes from operator-configured env, but the source name must still be in the allowlist.

### 9.3 Rotation-Aware Cursor

- On each read, check `os.stat(path).st_size` and `os.stat(path).st_ino`.
- If `st_size < saved_offset` or `st_ino != saved_inode`, reset offset to 0 (file was rotated/truncated).
- Return `next_offset` and `inode` in the response so the client can pass them back on the next poll.

---

## 10. Level Filtering Design

### 10.1 JSONL Lines (contract_events, runtime_audit, feedback)

- Parse JSON; extract `level` field (if present). Contract events don't have a `level` field by default, but runtime audit records have `kind` and `direction`. For level filtering on JSONL sources, check for a `level` key in the parsed JSON object. If absent, treat as `INFO` (default level).
- Valid levels: `DEBUG`, `INFO`, `WARN`, `ERROR`. Case-insensitive matching.

### 10.2 Plain-Text Lines (wecom_stdout, qqbot_stdout)

- Parse using a regex or simple prefix match for standard Python logging format: `^(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\b`.
- Map `WARNING` → `WARN`, `CRITICAL` → `ERROR` for filter compatibility.
- Lines without a recognizable level prefix are treated as `INFO`.

### 10.3 Filter Semantics

- `level=ERROR` shows only ERROR (and CRITICAL) lines.
- `level=WARN` shows WARN and ERROR.
- `level=INFO` shows INFO, WARN, and ERROR.
- `level=DEBUG` shows all levels.
- No `level` param → show all levels (no filtering).

---

## 11. Key Patterns to Follow

1. **Stdlib-only:** `open()`, `seek()`, `readline()`, `os.stat()`, `json.loads()`. No external libraries.
2. **ThreadingHTTPServer:** Already set up in Phase 79. Log reads are I/O-bound (file reads) so threading prevents blocking.
3. **SSR with html.escape:** All dynamic content in the web UI must pass through `html.escape()`. No `innerHTML`, no template engines.
4. **RBAC guard pipeline:** Feature flag → auth → RBAC check → tenant guard → handler. The `/logs` route goes through the same `_authenticate_admin` pipeline in `api.py`.
5. **Privacy scrubbing on every line:** `scrub_contract_payload` is called on each JSONL line. For plain-text lines, apply a text-level secret redaction (reuse `_redact_known_env_values` pattern from `runtime_audit.py` or simply pass the string through `scrub_contract_payload` which returns strings as-is).
6. **Bounded reads:** Cap the number of lines returned per request (e.g., `max_lines=500`) to prevent unbounded response sizes. The client polls with `next_offset` for more.
7. **Fixed allowlist for source names:** Same pattern as `_PROCESS_NAMES = {"wecom", "qqbot"}` in `processes_api.py`.
8. **HTTP polling only:** No EventSource, no WebSocket. The client uses `fetch()` or `XMLHttpRequest` with the last `next_offset` as a query parameter. CSP allows `script-src 'self'` so inline polling JS must be in an external file or use `<script>` with `src`. However, the current CSP allows `'unsafe-inline'` for styles only, not scripts. The polling script must be served as a separate `.js` file from the same origin, or use a `<meta http-equiv="refresh">` approach. Given the CSP constraint (`script-src 'self'`), the simplest approach is a small inline `<script>` tag — but CSP `script-src 'self'` blocks inline scripts. **Solution:** Serve a `/logs.js` static file from the admin-web-ui, or use a `<noscript>` fallback with a manual Refresh button and a `<meta http-equiv="refresh" content="5">` tag. The meta-refresh approach is CSP-safe and simpler for MVP.

---

## 12. Environment Variables Summary

| Variable | Existing? | Purpose |
|---|---|---|
| `INKSTATUTE_CONTRACT_LOG_PATH` | Yes | Path to contract events JSONL |
| `INKSTATUTE_FEEDBACK_QUEUE_PATH` | Yes | Path to feedback queue JSONL |
| `INKSTATUTE_PROCESS_LOG_DIR` | Yes (Phase 80) | Directory for child-process stdout/stderr logs |
| `INKSTATUTE_RUNTIME_AUDIT_PATH` | **NEW** | Path to runtime audit JSONL |
| `LOG_VIEWING_ENABLED` | **NEW** (optional flag) | Feature flag for log viewing; default OFF. Alternatively, reuse `admin_api_enabled` / `admin_web_ui_enabled`. |
| `LOG_VIEWER_MAX_LINES` | **NEW** | Max lines per response (default 500) |

**Decision:** Rather than introducing a new `LOG_VIEWING_ENABLED` flag, the `/logs` endpoint will be gated by the existing `admin_api_enabled` flag (for the API) and `admin_web_ui_enabled` flag (for the UI), consistent with how `/processes` and `/reports` work. This avoids a new flag that must be frozen in the allowlist. The `LOG_VIEWER_MAX_LINES` env var will be optional with a sensible default.

---

## 13. Test Patterns

### 13.1 Admin Console API Tests (`services/admin-console-api/tests/`)

- `test_reports.py` pattern: Create temp JSONL fixtures, build `ReportsAggregator`, call `handle_admin_get("/reports", ...)`, assert status codes and response keys.
- RBAC tests: Issue tokens with `rbac.issue_token(secret, role=Role.X)`, pass as `Authorization: Bearer <token>`, assert 200/403.
- Feature flag tests: `RuntimeFeatureFlags()` (all OFF) → 403; `RuntimeFeatureFlags(admin_api_enabled=True)` → 200.

### 13.2 Admin Web UI Tests (`services/admin-web-ui/tests/`)

- `test_dashboard_reports.py` pattern: Create temp JSONL, build `ReportsAggregator`, call `handle_admin_web_ui_request("/reports", ...)`, assert HTML contains expected escaped content.
- Tests call `handle_admin_web_ui_request` directly (testable core, no HTTP server needed).

### 13.3 Conversation Read View Tests (`services/conversation-read-view/tests/`)

- `test_reports_aggregator.py` pattern: Unit tests for the aggregator with small fixtures.
- `test_reports_perf.py` pattern: 50k-line fixture, assert bounded time/memory.

**Phase 82 test plan:**
- `services/admin-console-api/tests/test_logs.py` — API handler tests (source resolution, level filter, keyword search, offset polling, rotation reset, privacy scrub, path traversal rejection, RBAC).
- `services/admin-web-ui/tests/test_dashboard_logs.py` — Web UI rendering tests (escaped output, source selector, level filter UI, polling attributes).
- `services/conversation-read-view/tests/test_log_reader.py` — LogReader unit tests (byte-offset read, rotation-aware cursor, privacy scrub, path-traversal guard, level filtering, max_lines cap).

---

## 14. Files to Create or Modify

### New Files
| File | Purpose |
|---|---|
| `services/conversation-read-view/src/conversation_read_view/log_reader.py` | `LogReader` class — byte-offset tail reader with privacy scrub, path-traversal guard, level filter, rotation-aware cursor |
| `services/admin-console-api/src/admin_console_api/logs.py` | `handle_logs` — API handler for `GET /logs` and `GET /logs/<source>` |
| `services/admin-web-ui/src/admin_web_ui/logs.py` | `render_logs_page` — SSR page with source selector, level filter, keyword search, log display, polling |
| `services/conversation-read-view/tests/test_log_reader.py` | LogReader unit tests |
| `services/admin-console-api/tests/test_logs.py` | /logs API handler tests |
| `services/admin-web-ui/tests/test_dashboard_logs.py` | /logs web UI rendering tests |

### Modified Files
| File | Change |
|---|---|
| `services/conversation-read-view/src/conversation_read_view/__init__.py` | Export `LogReader` |
| `services/admin-console-api/src/admin_console_api/api.py` | Add `/logs` route dispatch in `handle_admin_get`, pass `log_reader` kwarg |
| `services/admin-console-api/src/admin_console_api/server.py` | Build `LogReader` in `create_server`, wire as `httpd.log_reader` |
| `services/admin-console-api/src/admin_console_api/routes.py` | Add `"/logs"` to `ROUTE_PREFIXES` |
| `services/admin-web-ui/src/admin_web_ui/server.py` | Add `/logs` to `_SECTION_MAP`, `_guard_path`, proxy pass-through, route handler |
| `services/admin-web-ui/src/admin_web_ui/api_client.py` | Add `log_reader` pass-through in `proxy()` |
| `services/admin-web-ui/src/admin_web_ui/__main__.py` | Build `LogReader` in `create_server`, wire as `httpd.log_reader` |
| `services/admin-web-ui/src/admin_web_ui/dashboard.py` | Add `("/logs", "Logs")` to nav_items, add `"logs"` to title_map, add `_render_logs_section` or delegate to `logs.py` |
| `packages/rbac/src/rbac/matrix.py` | Add `"/logs": frozenset({Role.ADMIN, Role.OPERATOR})` |
| `.env.example` | Add `INKSTATUTE_RUNTIME_AUDIT_PATH` and `LOG_VIEWER_MAX_LINES` |
