# Phase 82: Log Viewing — Validation Criteria

**Phase:** 82 — Log Viewing
**Requirements:** OBS-04, OBS-05, OBS-06
**Date:** 2026-07-14

---

## OBS-04: Runtime log viewing with level filtering and keyword search

### Criterion 1: Per-host source selector

- [ ] `GET /logs` returns a JSON payload with a `sources` array listing all 5 log sources: `contract_events`, `runtime_audit`, `feedback`, `wecom_stdout`, `qqbot_stdout`.
- [ ] Each source entry includes `available` (bool) indicating whether the file exists and is configured.
- [ ] The `/logs` web page renders a `<select>` dropdown with all 5 sources.
- [ ] Selecting a source and submitting the form navigates to `/logs/<source>` and displays lines from that source.

### Criterion 2: Level filtering (DEBUG/INFO/WARN/ERROR)

- [ ] `GET /logs/<source>?level=ERROR` returns only lines with level ERROR (or CRITICAL mapped to ERROR).
- [ ] `GET /logs/<source>?level=WARN` returns WARN and ERROR lines.
- [ ] `GET /logs/<source>?level=INFO` returns INFO, WARN, and ERROR lines.
- [ ] `GET /logs/<source>?level=DEBUG` returns all lines.
- [ ] `GET /logs/<source>` (no level param) returns all lines (no filtering).
- [ ] JSONL lines use a `level` field for level detection; plain-text lines use prefix regex (`ERROR:`, `INFO:`, `WARNING:`/`WARN:`, `CRITICAL:`).
- [ ] Lines without a recognizable level default to INFO.
- [ ] Invalid level value (e.g., `level=TRACE`) returns HTTP 400 with `error.code = "invalid_level"`.
- [ ] The web page renders a level `<select>` dropdown with options: All levels, DEBUG, INFO, WARN, ERROR.

### Criterion 3: Keyword search

- [ ] `GET /logs/<source>?q=keyword` returns only lines containing "keyword" (case-insensitive substring match).
- [ ] Empty `q` parameter returns all lines (no keyword filtering).
- [ ] The web page renders a text input for keyword search.
- [ ] The search input preserves the entered query on page refresh (value attribute set from query param).

### Criterion 4: Log source types

- [ ] `contract_events` source reads from `INKSTATUTE_CONTRACT_LOG_PATH` (JSONL format, one contract event per line).
- [ ] `runtime_audit` source reads from `INKSTATUTE_RUNTIME_AUDIT_PATH` (JSONL format, one audit record per line).
- [ ] `feedback` source reads from `INKSTATUTE_FEEDBACK_QUEUE_PATH` (JSONL format, one feedback event per line).
- [ ] `wecom_stdout` source reads from the WeCom host process log file (plain text, path from `ProcessSupervisor.status("wecom").log_path` or `INKSTATUTE_PROCESS_LOG_DIR / "wecom-host.log"`).
- [ ] `qqbot_stdout` source reads from the QQBot host process log file (plain text, path from `ProcessSupervisor.status("qqbot").log_path` or `INKSTATUTE_PROCESS_LOG_DIR / "qqbot-host.log"`).

---

## OBS-05: Byte-offset tail-follow polling

### Criterion 5: Byte-offset seek + read-to-end + next_offset

- [ ] `LogReader.read(source, offset=N)` opens the file, seeks to byte offset N, reads forward to EOF, and returns lines from offset N onward.
- [ ] The response includes `next_offset` — the byte position after the last read byte.
- [ ] The response includes `eof` — `True` when `next_offset >= file_size` (no more data at this moment).
- [ ] The client polls again with `?offset={next_offset}` to get the next batch of lines.
- [ ] The reader never loads the full file into memory — it uses `seek()` + `readline()` in a bounded loop capped at `max_lines`.
- [ ] `max_lines` defaults to 500 (configurable via `LOG_VIEWER_MAX_LINES` env var); the response is capped at this number of lines.

### Criterion 6: HTTP polling only (CSP constraint)

- [ ] No EventSource, WebSocket, or Server-Sent Events are used.
- [ ] The web page uses `<meta http-equiv="refresh" content="5">` for auto-polling every 5 seconds (CSP-safe, no inline JavaScript).
- [ ] The CSP header on `/logs` responses is `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'` — same as all other pages.
- [ ] No inline `<script>` tags are present in the `/logs` HTML output.
- [ ] A manual "Refresh" button is available as a `<noscript>`-compatible fallback.

### Criterion 7: Rotation-aware cursor

- [ ] The response includes `inode` — the inode of the file being read (`os.stat().st_ino`).
- [ ] When the client passes `inode` on the next poll and the file's inode has changed (rotation), the reader resets `offset` to 0 and sets `metadata.rotated = True`.
- [ ] When the file size is less than the provided `offset` (file shrank/truncated), the reader resets `offset` to 0 and sets `metadata.rotated = True`.
- [ ] The web page passes `inode` as a hidden form field so the next poll includes it.
- [ ] The web page displays "Rotated: true" in the metadata block when a rotation is detected.

### Criterion 8: No full-file reads

- [ ] `LogReader.read()` uses `open(path, "rb")`, `fh.seek(offset)`, and `fh.readline()` — it never calls `fh.read()` without a size limit or `readlines()` on the full file.
- [ ] The `ReportsAggregator._reverse_line_reader` pattern (chunk-based reverse read) is NOT reused here — the log reader reads forward from an offset, which is simpler and sufficient for tail-following.
- [ ] A test with a 10,000-line file and `max_lines=10` returns only 10 lines and does not read the entire file (verified by checking `next_offset` is less than file size).

---

## OBS-06: Privacy scrubbing and path-traversal guard

### Criterion 9: Privacy scrubbing on every line

- [ ] Every JSONL line is parsed via `json.loads()`, passed through `scrub_contract_payload()`, and re-serialized for display.
- [ ] If `scrub_contract_payload` raises `ValueError` (forbidden key found), the line is replaced with `[REDACTED: forbidden key at {path}]` — the error does not propagate or crash the request.
- [ ] Forbidden keys include all keys in `ALL_FORBIDDEN_KEYS`: `raw_payload`, `case_facts`, `customer_document_text`, `document_text`, `full_text`, `payload_text`, `raw_text`, `prompt_content`, `completion_text`, `function_call_result`, `tool_output`.
- [ ] Plain-text lines (wecom_stdout, qqbot_stdout) have known secret env values replaced with `[REDACTED]` via a text-level redaction pass.
- [ ] The scrubbed line text is HTML-escaped in the web UI via `html.escape()` before rendering.
- [ ] A test verifies that a JSONL line containing `{"raw_payload": "secret-data"}` produces `[REDACTED]` in the response, not `secret-data`.
- [ ] A test verifies that a plain-text line containing a known secret value produces `[REDACTED]` in the response.

### Criterion 10: Path-traversal guard

- [ ] Source names are validated against a fixed allowlist: `{"contract_events", "runtime_audit", "feedback", "wecom_stdout", "qqbot_stdout"}`.
- [ ] Unknown source names raise `ValueError` and return HTTP 404.
- [ ] No user-supplied file paths are accepted — file paths are resolved only from env vars or `ProcessSupervisor` internal state.
- [ ] The source name `../etc/passwd` is rejected (not in allowlist).
- [ ] The source name `contract_events/../../../etc/passwd` is rejected (not in allowlist — exact match required).
- [ ] For child-process logs, the resolved path is verified to be within the log directory (`INKSTATUTE_PROCESS_LOG_DIR` or default). Symlinks that resolve outside the log dir are rejected.
- [ ] A test verifies that `read("../etc/passwd")` raises `ValueError`.
- [ ] A test verifies that no query parameter can override the file path — only the source name is accepted, and it must be in the allowlist.

---

## RBAC and Feature Flag Validation

### Criterion 11: RBAC matrix entry

- [ ] `PERMISSIONS_MATRIX` in `packages/rbac/src/rbac/matrix.py` includes `"/logs": frozenset({Role.ADMIN, Role.OPERATOR})`.
- [ ] `ROUTE_PREFIXES` in `services/admin-console-api/src/admin_console_api/routes.py` includes `"/logs"`.
- [ ] The RBAC CI scan (`scripts/scan_rbac_annotations.py`) passes with exit code 0.
- [ ] ADMIN role token → 200 on `GET /logs` and `GET /logs/<source>`.
- [ ] OPERATOR role token → 200 on `GET /logs` and `GET /logs/<source>`.
- [ ] LAWYER role token → 403 on `GET /logs`.
- [ ] VIEWER role token → 403 on `GET /logs`.
- [ ] No token → 401 on `GET /logs` (when RBAC is enabled).
- [ ] `admin_api_enabled=False` → 503 on `GET /logs`.

### Criterion 12: RBAC guard pipeline

- [ ] `/logs` goes through the full `_authenticate_admin` pipeline in `api.py`: feature flag → auth header → RBAC `resolve_identity` → `RbacGuard.check` → tenant guard.
- [ ] The admin-web-ui `/logs` route goes through the web UI's own RBAC pipeline: feature flag → `resolve_identity` → `RbacGuard.check(identity.role, _guard_path("/logs"))`.
- [ ] `_guard_path("/logs")` returns `"/logs"` (not `/config` or `/sessions`).

---

## Web UI Validation

### Criterion 13: SSR with html.escape

- [ ] All dynamic content in the `/logs` HTML page is HTML-escaped via `html.escape()` or the local `_esc()` helper.
- [ ] A JSONL line containing `<script>alert(1)</script>` renders as `&lt;script&gt;alert(1)&lt;/script&gt;` in the HTML.
- [ ] No `innerHTML` or `dangerouslySetInnerHTML` is used (not applicable — this is SSR with no React).
- [ ] The CSP header is set on every `/logs` response.

### Criterion 14: Navigation and page template

- [ ] The nav bar in `_page_template` includes a "Logs" link to `/logs`.
- [ ] The dashboard index page (`/`) includes a "Log Viewer" card linking to `/logs`.
- [ ] The `/logs` page uses `_page_template` for consistent layout (header, nav, identity banner).

### Criterion 15: Form controls and polling

- [ ] The source selector `<select>` preserves the selected source on refresh (via `selected` attribute on the matching `<option>`).
- [ ] The level filter `<select>` preserves the selected level on refresh.
- [ ] The keyword search `<input>` preserves the entered query on refresh.
- [ ] Hidden `offset` and `inode` fields carry the `next_offset` and `inode` from the last response.
- [ ] The `<meta http-equiv="refresh" content="5">` tag is present in the `<head>` for auto-polling.
- [ ] A "Reset" link is available to clear the offset and start from the beginning.

---

## Integration and Wiring Validation

### Criterion 16: Server wiring

- [ ] `admin-console-api/server.py:create_server` builds a `LogReader` instance with `env` and `process_supervisor`, and sets it as `httpd.log_reader`.
- [ ] `admin-web-ui/__main__.py:create_server` builds a `LogReader` instance with `env` and `process_supervisor`, and sets it as `httpd.log_reader`.
- [ ] `AdminConsoleApiServer._dispatch` passes `log_reader=getattr(self.server, "log_reader", None)` to `handle_admin_get`.
- [ ] `AdminWebUiServer` passes `log_reader` from `self.server.log_reader` to `handle_admin_web_ui_request`.
- [ ] `AdminApiClient.proxy()` passes `log_reader` to `handle_admin_get` when it is not None.

### Criterion 17: API signature compatibility

- [ ] `handle_admin_get` accepts a new `log_reader: Any = None` keyword argument — existing callers that don't pass it still work (default None).
- [ ] `handle_admin_web_ui_request` accepts a new `log_reader: Any = None` keyword argument — existing callers that don't pass it still work.
- [ ] `AdminApiClient.proxy()` accepts a new `log_reader: Any = None` keyword argument — existing callers that don't pass it still work.
- [ ] All existing tests (`test_server.py`, `test_main.py`, `test_reports.py`, `test_dashboard_reports.py`, `test_process_supervisor.py`) pass without modification.

---

## Environment Variable Validation

### Criterion 18: New env vars documented

- [ ] `.env.example` includes `INKSTATUTE_RUNTIME_AUDIT_PATH` with a comment explaining its purpose.
- [ ] `.env.example` includes `LOG_VIEWER_MAX_LINES` with a comment explaining its default (500).
- [ ] No new feature flag is introduced — `/logs` is gated by existing `admin_api_enabled` and `admin_web_ui_enabled` flags.

---

## Test Coverage Validation

### Criterion 19: LogReader unit tests

- [ ] `services/conversation-read-view/tests/test_log_reader.py` covers: basic read, offset polling, level filter (JSON + plain text), keyword search, privacy scrub (JSON + text), rotation (shrink + inode change), unknown source rejection, source not configured, source not found, max_lines cap, list_sources, path traversal rejection, empty file, partial line, wecom_stdout via process_supervisor.
- [ ] All tests pass: `PYTHONPATH=... python -m unittest services.conversation_read_view.tests.test_log_reader -v`.

### Criterion 20: /logs API handler tests

- [ ] `services/admin-console-api/tests/test_logs.py` covers: list sources, read with offset, level filter, keyword search, privacy scrub, rotation, unknown source, source not configured, source not found, invalid level, negative offset, admin_api disabled, log_reader None, RBAC (admin/operator/lawyer/viewer), wecom_stdout via process_supervisor, RBAC scan passes.
- [ ] All tests pass: `PYTHONPATH=... python -m unittest services.admin_console_api.tests.test_logs -v`.

### Criterion 21: /logs web UI tests

- [ ] `services/admin-web-ui/tests/test_dashboard_logs.py` covers: source selector rendering, line rendering, level filter UI, keyword search UI, HTML escaping, privacy scrub display, meta refresh, next_offset hidden field, POST 405, RBAC (admin/lawyer), nav link, error rendering, rotation indicator.
- [ ] All tests pass: `PYTHONPATH=... python -m unittest services.admin_web_ui.tests.test_dashboard_logs -v`.

### Criterion 22: No regressions

- [ ] `PYTHONPATH=... python -m unittest services.admin_console_api.tests.test_server -v` passes.
- [ ] `PYTHONPATH=... python -m unittest services.admin_web_ui.tests.test_main -v` passes.
- [ ] `PYTHONPATH=... python -m unittest services.admin_console_api.tests.test_reports -v` passes.
- [ ] `PYTHONPATH=... python -m unittest services.admin_web_ui.tests.test_dashboard_reports -v` passes.
- [ ] `PYTHONPATH=... python -m unittest services.admin_console_api.tests.test_process_supervisor -v` passes.
- [ ] `PYTHONPATH=packages/rbac/src:services/admin-console-api/src python3 scripts/scan_rbac_annotations.py` exits 0.

---

## Constraint Validation

### Criterion 23: Stdlib-only

- [ ] No new packages added to any `pyproject.toml` — `dependencies = []` maintained.
- [ ] Only stdlib imports used: `os`, `json`, `re`, `html`, `pathlib`, `typing`, `datetime`, `collections`, `http.server`, `urllib.parse`.
- [ ] No Flask, FastAPI, Django, React, Vue, or any external web framework.

### Criterion 24: No new DB/queue/SPA

- [ ] No new database, message queue, or SPA framework introduced.
- [ ] Log reading is stateless (no persistence) — the cursor is maintained client-side via query parameters.

### Criterion 25: No WebSocket/SSE

- [ ] No `websockets`, `aiohttp`, `sse-starlette`, or any push-protocol library imported.
- [ ] Polling is via standard HTTP GET with query parameters.
- [ ] The web page uses `<meta http-equiv="refresh">` only — no `<script>` for polling.

---

## Summary Checklist

| # | Criterion | Requirement | Task |
|---|---|---|---|
| 1 | Per-host source selector | OBS-04 | T2, T3 |
| 2 | Level filtering DEBUG/INFO/WARN/ERROR | OBS-04 | T1, T2 |
| 3 | Keyword search | OBS-04 | T1, T2 |
| 4 | Log source types (5 sources) | OBS-04 | T1, T2 |
| 5 | Byte-offset seek + read-to-end + next_offset | OBS-05 | T1 |
| 6 | HTTP polling only (CSP constraint) | OBS-05 | T3 |
| 7 | Rotation-aware cursor | OBS-05 | T1 |
| 8 | No full-file reads | OBS-05 | T1 |
| 9 | Privacy scrubbing on every line | OBS-06 | T1 |
| 10 | Path-traversal guard | OBS-06 | T1 |
| 11 | RBAC matrix entry | OBS-04/05/06 | T2 |
| 12 | RBAC guard pipeline | OBS-04/05/06 | T2 |
| 13 | SSR with html.escape | OBS-06 | T3 |
| 14 | Navigation and page template | OBS-04 | T3 |
| 15 | Form controls and polling | OBS-05 | T3 |
| 16 | Server wiring | OBS-04/05/06 | T2, T3 |
| 17 | API signature compatibility | OBS-04/05/06 | T2, T3 |
| 18 | New env vars documented | OBS-04 | T2 |
| 19 | LogReader unit tests | OBS-04/05/06 | T1 |
| 20 | /logs API handler tests | OBS-04/05/06 | T2 |
| 21 | /logs web UI tests | OBS-04/05/06 | T3 |
| 22 | No regressions | OBS-04/05/06 | T2, T3 |
| 23 | Stdlib-only | OBS-04/05/06 | T1, T2, T3 |
| 24 | No new DB/queue/SPA | OBS-04/05/06 | T1, T2, T3 |
| 25 | No WebSocket/SSE | OBS-05 | T3 |
