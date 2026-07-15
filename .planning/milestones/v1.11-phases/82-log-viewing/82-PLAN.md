---
phase: 82-log-viewing
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/conversation-read-view/src/conversation_read_view/log_reader.py
  - services/conversation-read-view/src/conversation_read_view/__init__.py
  - services/admin-console-api/src/admin_console_api/logs.py
  - services/admin-console-api/src/admin_console_api/api.py
  - services/admin-console-api/src/admin_console_api/server.py
  - services/admin-console-api/src/admin_console_api/routes.py
  - services/admin-web-ui/src/admin_web_ui/logs.py
  - services/admin-web-ui/src/admin_web_ui/server.py
  - services/admin-web-ui/src/admin_web_ui/api_client.py
  - services/admin-web-ui/src/admin_web_ui/__main__.py
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - packages/rbac/src/rbac/matrix.py
  - .env.example
  - services/conversation-read-view/tests/test_log_reader.py
  - services/admin-console-api/tests/test_logs.py
  - services/admin-web-ui/tests/test_dashboard_logs.py
autonomous: true
requirements:
  - OBS-04
  - OBS-05
  - OBS-06
user_setup: []

must_haves:
  truths:
    - "LogReader.read(source, offset, level, q, max_lines) returns {lines, next_offset, eof, inode, source} using byte-offset seek + read-to-end; never loads the full file"
    - "LogReader resolves source names from a fixed allowlist {contract_events, runtime_audit, feedback, wecom_stdout, qqbot_stdout} to env-var-derived paths; rejects unknown sources, .., absolute paths, and symlinks outside the expected log dir"
    - "LogReader detects file rotation by comparing os.stat st_size and st_ino against the provided offset/inode; resets to 0 when the file shrinks or inode changes"
    - "Every JSONL line is parsed and passed through scrub_contract_payload before inclusion in the response; forbidden keys produce a [REDACTED] marker instead of raising"
    - "Level filtering supports DEBUG/INFO/WARN/ERROR with severity ordering (DEBUG shows all, ERROR shows only ERROR); JSONL lines use a level field, plain-text lines use prefix regex"
    - "Keyword search filters lines by case-insensitive substring match on the scrubbed line text"
    - "GET /logs returns a JSON payload with lines, next_offset, eof, inode, source, and metadata; GET /logs/<source> returns lines for that source only"
    - "RBAC matrix entry /logs allows ADMIN and OPERATOR roles; lawyer/viewer denied 403"
    - "The /logs web page renders a source selector dropdown, level filter dropdown, keyword search input, log lines in a <pre> block, and a meta-refresh polling mechanism using next_offset"
    - "All dynamic content in the /logs web page is HTML-escaped via html.escape; CSP header is set on every response"
    - "ROUTE_PREFIXES includes /logs and PERMISSIONS_MATRIX includes /logs so the RBAC CI scan passes"
  artifacts:
    - "conversation_read_view.log_reader.LogReader class"
    - "admin_console_api.logs.handle_logs function"
    - "admin_console_api.api.handle_admin_get /logs route"
    - "admin_console_api.server.create_server log_reader wiring"
    - "admin_console_api.routes.ROUTE_PREFIXES /logs entry"
    - "rbac.matrix.PERMISSIONS_MATRIX /logs entry"
    - "admin_web_ui.logs.render_logs_page function"
    - "admin_web_ui.server.handle_admin_web_ui_request /logs route and _SECTION_MAP entry"
    - "admin_web_ui.api_client.AdminApiClient.proxy log_reader pass-through"
    - "admin_web_ui.__main__.create_server log_reader wiring"
    - "admin_web_ui.dashboard nav_items /logs entry and title_map logs entry"
    - "test_log_reader.py, test_logs.py, test_dashboard_logs.py"
  key_links:
    - "LogReader is constructed in admin-console-api/server.py create_server with env dict and process_supervisor for child-process log path resolution"
    - "handle_admin_get routes /logs to handle_logs and passes log_reader from server instance"
    - "admin-web-ui proxy passes log_reader to handle_admin_get via AdminApiClient.proxy"
    - "admin_web_ui.logs.render_logs_page renders the handle_logs JSON response as escaped HTML with polling controls"
    - "scrub_contract_payload is imported from conversation_read_view.privacy and called on every JSONL line inside LogReader.read"
---

<objective>
Add a `/logs` endpoint and web page to the admin console that lets operators view runtime logs (contract events, runtime audit, feedback, child-process stdout/stderr) with level filtering (DEBUG/INFO/WARN/ERROR), keyword search, and a per-host source selector. Log viewing uses byte-offset tail-follow polling (seek + read-to-end + next_offset) so the browser refreshes without re-reading the full file. Every line is privacy-scrubbed via `scrub_contract_payload`. A path-traversal guard validates source names against a fixed allowlist. The cursor is rotation-aware (resets on file shrink/inode change). HTTP polling only — no EventSource/WebSocket (CSP constraint).

Purpose: Give operators real-time visibility into runtime logs without SSH access, while ensuring secrets and raw legal payloads never appear in the console.

Output: A working `LogReader` class, `/logs` API endpoint, `/logs` web page with polling, RBAC matrix entry, and automated tests.
</objective>

<execution_context>
@$HOME/.codeium/windsurf/gsd-core/workflows/execute-plan.md
@$HOME/.codeium/windsurf/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/82-log-viewing/82-CONTEXT.md
@.planning/phases/82-log-viewing/82-RESEARCH.md
@services/conversation-read-view/src/conversation_read_view/privacy.py
@services/conversation-read-view/src/conversation_read_view/__init__.py
@services/conversation-read-view/src/conversation_read_view/reports_aggregator.py
@services/admin-console-api/src/admin_console_api/api.py
@services/admin-console-api/src/admin_console_api/server.py
@services/admin-console-api/src/admin_console_api/routes.py
@services/admin-console-api/src/admin_console_api/reports.py
@services/admin-console-api/src/admin_console_api/processes_api.py
@services/admin-console-api/src/admin_console_api/process_supervisor.py
@services/admin-console-api/src/admin_console_api/process_registry.py
@services/admin-web-ui/src/admin_web_ui/server.py
@services/admin-web-ui/src/admin_web_ui/dashboard.py
@services/admin-web-ui/src/admin_web_ui/api_client.py
@services/admin-web-ui/src/admin_web_ui/__main__.py
@services/admin-web-ui/src/admin_web_ui/processes.py
@services/admin-web-ui/src/admin_web_ui/boundary.py
@packages/rbac/src/rbac/matrix.py
@packages/rbac/src/rbac/guard.py
@packages/platform-runtime/src/platform_runtime/privacy_keys.py
@services/wecom-service/src/wecom_service/runtime_audit.py
@services/hermes-contract-layer/src/hermes_contract_layer/writer.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: LogReader with byte-offset polling, privacy scrubbing, path-traversal guard</name>
  <files>
    services/conversation-read-view/src/conversation_read_view/log_reader.py
    services/conversation-read-view/src/conversation_read_view/__init__.py
    services/conversation-read-view/tests/test_log_reader.py
  </files>
  <read_first>
    services/conversation-read-view/src/conversation_read_view/privacy.py
    services/conversation-read-view/src/conversation_read_view/__init__.py
    services/conversation-read-view/src/conversation_read_view/reports_aggregator.py
    packages/platform-runtime/src/platform_runtime/privacy_keys.py
    services/admin-console-api/src/admin_console_api/process_supervisor.py
    services/admin-console-api/src/admin_console_api/process_registry.py
    services/wecom-service/src/wecom_service/runtime_audit.py
    services/hermes-contract-layer/src/hermes_contract_layer/writer.py
    .planning/phases/82-log-viewing/82-RESEARCH.md
  </read_first>
  <action>
    Create `services/conversation-read-view/src/conversation_read_view/log_reader.py` with a `LogReader` class.

    ### Class: `LogReader`

    `__init__(self, env=None, process_supervisor=None)`:
    - Store `self._env = dict(env) if env is not None else dict(os.environ)`.
    - Store `self._process_supervisor = process_supervisor` (used to resolve child-process log paths from `ProcessRecord.log_path`).
    - Define `self._max_lines = int(source.get("LOG_VIEWER_MAX_LINES", "500"))`.
    - Define the fixed source allowlist:
      ```python
      _ALLOWED_SOURCES = frozenset({
          "contract_events",
          "runtime_audit",
          "feedback",
          "wecom_stdout",
          "qqbot_stdout",
      })
      ```
    - Define level severity ordering:
      ```python
      _LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}
      _LEVEL_ALIASES = {"WARNING": "WARN", "CRITICAL": "ERROR"}
      ```

    ### Method: `resolve_path(self, source) -> str | None`

    Maps a source name to a file path. Returns `None` if the source is unknown or the path is not configured.

    - Validate `source` is in `_ALLOWED_SOURCES`; raise `ValueError(f"unknown log source: {source!r}")` if not.
    - For `contract_events`: return `self._env.get("INKSTATUTE_CONTRACT_LOG_PATH")` or `None`.
    - For `runtime_audit`: return `self._env.get("INKSTATUTE_RUNTIME_AUDIT_PATH")` or `None`.
    - For `feedback`: return `self._env.get("INKSTATUTE_FEEDBACK_QUEUE_PATH")` or `None`.
    - For `wecom_stdout` and `qqbot_stdout`:
      - If `self._process_supervisor` is not None, call `self._process_supervisor.status(name)` where `name` is `"wecom"` or `"qqbot"` (derived from the source name by stripping `_stdout` suffix). Return `record.log_path` if it is non-empty.
      - Fall back to resolving from `INKSTATUTE_PROCESS_LOG_DIR` env var (or `~/.inkstatute/process-logs/` default): `log_dir / f"{name}-host.log"`.
    - **Path-traversal guard:** This method never accepts user-supplied paths. The source name is validated against the fixed allowlist. All paths come from env vars or the process supervisor's internal state. After resolving the path, check that it does not contain `..` components (defense-in-depth, even though the path comes from env). For child-process logs, verify the resolved path is within the log dir by checking `Path(path).resolve().parent == Path(log_dir).resolve()` or that `Path(path).resolve()` starts with `Path(log_dir).resolve()`. If the path is a symlink that resolves outside the log dir, reject it.

    ### Method: `list_sources(self) -> list[dict[str, Any]]`

    Return a list of `{"source": name, "available": bool, "path": str_or_empty}` for each source in `_ALLOWED_SOURCES` (sorted). `available` is `True` when `resolve_path(source)` returns a non-None path and `Path(path).is_file()`.

    ### Method: `read(self, source, offset=0, inode=None, level=None, q=None, max_lines=None) -> dict[str, Any]`

    The core tail-read method. Returns:
    ```python
    {
        "source": source,
        "lines": [{"line_number": int, "text": str, "level": str, "offset": int}],
        "next_offset": int,
        "eof": bool,
        "inode": int,
        "file_size": int,
        "metadata": {
            "lines_returned": int,
            "lines_filtered": int,
            "max_lines": int,
            "level_filter": level_or_None,
            "keyword": q_or_None,
            "rotated": bool,
        },
    }
    ```

    Algorithm:
    1. Validate `source` against `_ALLOWED_SOURCES`.
    2. Resolve the path via `resolve_path(source)`. If `None`, return `{"error": {"code": "source_not_configured", "message": f"Log source {source} has no path configured"}}`.
    3. If the path does not exist (`not Path(path).is_file()`), return `{"error": {"code": "source_not_found", "message": f"Log file not found: {source}"}}`.
    4. Stat the file: `stat = os.stat(path)`. Get `file_size = stat.st_size`, `current_inode = stat.st_ino`.
    5. **Rotation detection:**
       - If `inode is not None` and `current_inode != inode`: the file was rotated. Set `offset = 0`, `rotated = True`.
       - If `offset > 0` and `file_size < offset`: the file shrank (truncated/rotated). Set `offset = 0`, `rotated = True`.
       - Otherwise `rotated = False`.
    6. If `offset > file_size`: set `offset = 0` (defensive).
    7. Open the file in binary mode: `with open(path, "rb") as fh:`.
    8. `fh.seek(offset)`.
    9. Read forward in a loop, collecting decoded lines:
       - Read chunks or use `fh.readline()` in a loop (readline is simpler and naturally handles partial lines).
       - For each raw line (bytes), decode as UTF-8 with `errors="replace"`.
       - Strip trailing `\n` / `\r\n`.
       - Track the byte offset of the start of each line: `line_start_offset = offset + bytes_consumed_so_far`.
    10. For each line, determine the level:
        - Try `json.loads(line)`. If it succeeds and the result is a dict with a `"level"` key, use that level (uppercased, aliased via `_LEVEL_ALIASES`).
        - If JSON parse fails or no `level` key, try regex match: `^(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\b` (case-insensitive). Map via `_LEVEL_ALIASES`.
        - If no level detected, default to `"INFO"`.
    11. Apply level filter: if `level` param is not None, skip lines whose level severity is below the requested level. Use `_LEVEL_ORDER`: keep lines where `_LEVEL_ORDER.get(line_level, 1) >= _LEVEL_ORDER.get(level, 0)`.
    12. Apply keyword filter: if `q` param is not None and non-empty, skip lines where `q.lower()` is not a substring of `line.lower()`.
    13. **Privacy scrub:**
        - If the line parsed as JSON (step 10), call `scrub_contract_payload(parsed)`. If `ValueError` is raised (forbidden key found), replace the line text with `f"[REDACTED: forbidden key at {forbidden_path}]"` (extract the path from the error message). Re-serialize the scrubbed dict as `json.dumps(scrubbed, ensure_ascii=False)` for display.
        - If the line did not parse as JSON, pass the raw text through as-is (it's a plain-text stdout/stderr line; `scrub_contract_payload` on a string returns the string unchanged, but we don't call it for non-JSON lines since it would be a no-op). Apply a simple secret redaction: replace any env value that looks like a secret (reuse the `_redact_known_env_values` pattern from `runtime_audit.py` — iterate env vars with secret-like names and replace their values with `[REDACTED]`). Import this as a helper function.
    14. Collect matching lines (up to `max_lines` cap) with their metadata: `{"line_number": sequential_int, "text": scrubbed_text, "level": level, "offset": line_start_offset}`.
    15. Track `next_offset = fh.tell()` (the byte position after the last byte read).
    16. `eof = next_offset >= file_size` (no more data to read at this moment).
    17. Count `lines_filtered` = total lines scanned minus lines returned (for metadata).
    18. Return the response dict.

    **Important:** The read loop must stop after collecting `max_lines` matching lines, but must continue tracking `next_offset` to the end of the current file content (so the next poll starts from where we left off). Actually, for tail-follow efficiency, `next_offset` should be the offset after the last *read* byte (whether or not the line was returned), so the next poll doesn't re-scan filtered-out lines. Set `next_offset = fh.tell()` after the read loop completes (either by hitting max_lines or EOF).

    **Edge case:** If `max_lines` is reached mid-file, `eof = False` and the client should poll again with the new `next_offset` to get the next batch.

    ### Method: `_redact_text_secrets(self, text) -> str`

    Helper that replaces known secret env values in plain text. Iterate `self._env` items where the key name contains any of `("secret", "token", "key", "password", "authorization", "cookie")` (case-insensitive) and the value is at least 8 characters. Replace occurrences of the value in `text` with `[REDACTED]`.

    ### Update `__init__.py`

    Add `LogReader` to imports and `__all__` in `services/conversation-read-view/src/conversation_read_view/__init__.py`.

    ### Tests: `services/conversation-read-view/tests/test_log_reader.py`

    Create comprehensive unit tests:

    1. **test_read_basic:** Write a temp JSONL file with 3 lines, call `read("contract_events", offset=0)`, assert 3 lines returned, `next_offset` equals file size, `eof=True`.
    2. **test_read_with_offset:** Write 3 lines, read with `offset=0` and `max_lines=1`, assert 1 line returned, `eof=False`. Read again with `next_offset`, assert remaining 2 lines.
    3. **test_level_filter_json:** Write JSONL lines with `"level": "ERROR"`, `"level": "INFO"`, `"level": "DEBUG"`. Filter with `level="WARN"`, assert only the ERROR line is returned.
    4. **test_level_filter_plain_text:** Write plain-text lines with `ERROR: ...`, `INFO: ...`, `WARNING: ...`. Filter with `level="WARN"`, assert ERROR and WARNING lines returned.
    5. **test_level_filter_default_info:** Lines without a recognizable level default to INFO. Filter with `level="ERROR"`, assert they are excluded.
    6. **test_keyword_search:** Write lines containing "error" and "success". Filter with `q="error"`, assert only matching lines returned. Case-insensitive: `q="ERROR"` matches lowercase "error".
    7. **test_privacy_scrub_jsonl:** Write a JSONL line containing a forbidden key (`"raw_payload": "secret"`). Assert the line is replaced with a `[REDACTED: ...]` marker, not the raw payload.
    8. **test_privacy_scrub_clean_jsonl:** Write a JSONL line without forbidden keys. Assert the scrubbed line is returned with the same content (keys may be reordered).
    9. **test_privacy_scrub_text_secrets:** Write a plain-text line containing a known env secret value. Assert the secret is replaced with `[REDACTED]`.
    10. **test_rotation_file_shrink:** Write 5 lines, read all (get `next_offset`). Truncate file to 2 lines. Read again with the old `next_offset`. Assert `rotated=True`, offset reset to 0, and only 2 lines returned.
    11. **test_rotation_inode_change:** Write 3 lines, read all (get `inode`). Delete and recreate the file with 1 line. Read again with old `inode`. Assert `rotated=True`, offset reset to 0.
    12. **test_unknown_source_rejected:** Call `read("malicious_source")`, assert `ValueError` raised.
    13. **test_source_not_configured:** Call `read("contract_events")` with no `INKSTATUTE_CONTRACT_LOG_PATH` in env. Assert error response with `code: "source_not_configured"`.
    14. **test_source_not_found:** Configure a path that doesn't exist. Assert error response with `code: "source_not_found"`.
    15. **test_max_lines_cap:** Write 10 lines, read with `max_lines=3`, assert 3 lines returned, `eof=False`.
    16. **test_list_sources:** Configure all paths, call `list_sources()`, assert 5 sources listed with `available=True` when files exist.
    17. **test_path_traversal_rejected:** The source name `../etc/passwd` is not in `_ALLOWED_SOURCES`, so `ValueError` is raised. No path concatenation from user input.
    18. **test_empty_file:** Write an empty file, read with offset=0, assert 0 lines, `eof=True`, `next_offset=0`.
    19. **test_partial_line:** Write a line without trailing newline, read, assert the line is returned and `next_offset` points past it.
    20. **test_wecom_stdout_via_process_supervisor:** Mock a `ProcessSupervisor` with a `status("wecom")` returning a `ProcessRecord(log_path="/tmp/test.log")`. Assert `resolve_path("wecom_stdout")` returns that path.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src python -m unittest services.conversation_read_view.tests.test_log_reader -v</automated>
    <manual>Confirm that LogReader never loads a full file into memory — it uses seek + readline in a bounded loop. Confirm that source names are validated against the fixed allowlist and no user-supplied file paths are accepted.</manual>
  </verify>
</task>

<task type="auto">
  <name>Task 2: /logs API endpoint with level filtering, keyword search, source selector + RBAC</name>
  <files>
    services/admin-console-api/src/admin_console_api/logs.py
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/server.py
    services/admin-console-api/src/admin_console_api/routes.py
    packages/rbac/src/rbac/matrix.py
    .env.example
    services/admin-console-api/tests/test_logs.py
  </files>
  <read_first>
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/server.py
    services/admin-console-api/src/admin_console_api/routes.py
    services/admin-console-api/src/admin_console_api/reports.py
    services/admin-console-api/src/admin_console_api/processes_api.py
    services/admin-console-api/tests/test_reports.py
    packages/rbac/src/rbac/matrix.py
    packages/rbac/src/rbac/guard.py
    services/conversation-read-view/src/conversation_read_view/log_reader.py
    .planning/phases/82-log-viewing/82-RESEARCH.md
  </read_first>
  <action>
    ### Create `services/admin-console-api/src/admin_console_api/logs.py`

    ```python
    """Admin API handler for log viewing (Phase 82)."""

    from __future__ import annotations
    from typing import Any, Mapping
    from conversation_read_view.privacy import scrub_contract_payload

    _VALID_LEVELS = {"DEBUG", "INFO", "WARN", "ERROR"}

    def handle_logs(
        path: str,
        query: Mapping[str, str],
        log_reader: Any,
        feature_flags: Any,
    ) -> tuple[int, dict[str, Any]]:
        """Handle GET /logs and GET /logs/<source>."""
    ```

    Logic:
    1. Check `feature_flags.admin_api_enabled`; return 503 `admin_api_disabled` if False.
    2. If `log_reader is None`, return 503 `{"error": {"code": "log_reader_unavailable", "message": "Log reader is not configured"}}`.
    3. Parse the path: `rest = path.removeprefix("/logs").strip("/")`.
    4. If `rest` is empty (i.e., `GET /logs`):
       - Return 200 with `{"sources": log_reader.list_sources(), "metadata": {"admin_api": True, "read_only": True}}`.
    5. If `rest` is non-empty, it is the source name:
       - Extract query params: `source = rest`, `offset = int(query.get("offset", "0"))`, `inode = int(query["inode"]) if "inode" in query else None`, `level = query.get("level")`, `q = query.get("q")`, `max_lines = int(query.get("max_lines", "500"))`.
       - Validate `level`: if provided and `level.upper() not in _VALID_LEVELS`, return 400 `{"error": {"code": "invalid_level", "message": f"level must be one of {sorted(_VALID_LEVELS)}"}}`.
       - Validate `offset >= 0`: if negative, return 400 `{"error": {"code": "invalid_offset", "message": "offset must be non-negative"}}`.
       - Validate `max_lines` is in `[1, 5000]`: if out of range, clamp to 500 (default) or return 400. Clamping is safer for MVP.
       - Call `log_reader.read(source, offset=offset, inode=inode, level=level.upper() if level else None, q=q, max_lines=max_lines)`.
       - If the result contains an `"error"` key, return 404 (for `source_not_found` / `source_not_configured`) or 400 (for `ValueError` from unknown source).
       - Wrap the result: add `"metadata": {**result.get("metadata", {}), "admin_api": True, "read_only": True}`.
       - Return 200 with the result.
    6. Catch `ValueError` from `log_reader.read` (unknown source) → return 404 `{"error": {"code": "not_found", "message": str(exc)}}`.
    7. Catch `Exception` → return 500 `{"error": {"code": "internal_error", "message": "log read failed"}}`.

    ### Modify `services/admin-console-api/src/admin_console_api/api.py`

    In `handle_admin_get`:
    - Add import: `from .logs import handle_logs`.
    - Add route dispatch after the `/reports` block and before the `/config` block:
      ```python
      if route_path == "/logs" or route_path.startswith("/logs/"):
          return handle_logs(
              route_path,
              route_query,
              log_reader=getattr(self, "log_reader", None) if hasattr(self, "log_reader") else None,
              feature_flags=feature_flags,
          )
      ```
    - **Important:** `handle_admin_get` is a function, not a method — it doesn't have `self`. The `log_reader` must be passed as a parameter. Add `log_reader: Any = None` to the `handle_admin_get` signature (after `reports_aggregator: Any = None`).
    - In the `_dispatch` method of `AdminConsoleApiServer` in `server.py`, add `log_reader=getattr(self.server, "log_reader", None)` to the `handle_admin_get` call kwargs.

    ### Modify `services/admin-console-api/src/admin_console_api/server.py`

    In `create_server(env)`:
    - Add import: `from conversation_read_view.log_reader import LogReader`.
    - After creating `process_supervisor` and calling `reconcile_on_startup()`:
      ```python
      log_reader = LogReader(env=source, process_supervisor=process_supervisor)
      ```
    - Add `httpd.log_reader = log_reader` after the other server attribute assignments.
    - In `_dispatch` method of `AdminConsoleApiServer`, add `log_reader=getattr(self.server, "log_reader", None)` to the `handle_admin_get` call.

    ### Modify `services/admin-console-api/src/admin_console_api/routes.py`

    Add `"/logs"` to `ROUTE_PREFIXES`:
    ```python
    ROUTE_PREFIXES: tuple[str, ...] = (
        "/sessions",
        "/tasks",
        "/feedback",
        "/health",
        "/gates",
        "/config",
        "/reports",
        "/logs",
    )
    ```

    ### Modify `packages/rbac/src/rbac/matrix.py`

    Add `"/logs"` entry to `PERMISSIONS_MATRIX`:
    ```python
    "/logs": frozenset({Role.ADMIN, Role.OPERATOR}),
    ```
    Place it after the `"/processes"` entry.

    ### Modify `.env.example`

    After the process orchestration section, add:
    ```
    # --- Log viewing (Phase 82) ---
    # INKSTATUTE_RUNTIME_AUDIT_PATH=/path/to/runtime/runtime-audit.jsonl
    # LOG_VIEWER_MAX_LINES=500
    ```

    ### Tests: `services/admin-console-api/tests/test_logs.py`

    Create tests following the `test_reports.py` pattern:

    1. **test_logs_list_sources:** Call `handle_admin_get("/logs", ...)`, assert 200, `sources` key present, list of 5 sources.
    2. **test_logs_read_contract_events:** Create temp JSONL, configure `INKSTATUTE_CONTRACT_LOG_PATH`, call `handle_admin_get("/logs/contract_events", ...)`, assert 200, `lines` present, `next_offset` > 0.
    3. **test_logs_read_with_offset:** Read first batch with `max_lines=1`, get `next_offset`. Read second batch with that offset, assert different lines.
    4. **test_logs_level_filter:** Write lines with different levels, filter with `level=ERROR`, assert only ERROR lines.
    5. **test_logs_keyword_search:** Write lines with different content, filter with `q=keyword`, assert only matching lines.
    6. **test_logs_privacy_scrub:** Write a JSONL line with `raw_payload` key, assert response contains `[REDACTED]` marker.
    7. **test_logs_rotation:** Read file, truncate, read again with old offset, assert `rotated=True` in metadata.
    8. **test_logs_unknown_source:** Call `/logs/unknown`, assert 404.
    9. **test_logs_source_not_configured:** Call `/logs/contract_events` with no path configured, assert 404 with `source_not_configured`.
    10. **test_logs_source_not_found:** Configure a non-existent path, assert 404 with `source_not_found`.
    11. **test_logs_invalid_level:** Call with `level=TRACE`, assert 400.
    12. **test_logs_negative_offset:** Call with `offset=-1`, assert 400.
    13. **test_logs_admin_api_disabled:** `RuntimeFeatureFlags()` (all OFF), assert 503.
    14. **test_logs_log_reader_none:** Pass `log_reader=None`, assert 503.
    15. **test_logs_rbac_admin_allowed:** Issue ADMIN token, assert 200.
    16. **test_logs_rbac_operator_allowed:** Issue OPERATOR token, assert 200.
    17. **test_logs_rbac_lawyer_denied:** Issue LAWYER token, assert 403.
    18. **test_logs_rbac_viewer_denied:** Issue VIEWER token, assert 403.
    19. **test_logs_wecom_stdout:** Mock `ProcessSupervisor.status("wecom")` returning a record with `log_path`, write to that file, call `/logs/wecom_stdout`, assert 200 with lines.
    20. **test_rbac_scan_passes:** Import `ROUTE_PREFIXES` and `PERMISSIONS_MATRIX`, assert `"/logs"` is in both.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src python -m unittest services.admin_console_api.tests.test_logs -v</automated>
    <automated>PYTHONPATH=packages/rbac/src:services/admin-console-api/src python3 scripts/scan_rbac_annotations.py</automated>
    <manual>Confirm that /logs is routed through the full _authenticate_admin pipeline (feature flag + auth + RBAC + tenant guard). Confirm that the log_reader is wired in create_server and passed through _dispatch.</manual>
  </verify>
</task>

<task type="auto">
  <name>Task 3: /logs web UI page with polling, filtering UI, and wiring</name>
  <files>
    services/admin-web-ui/src/admin_web_ui/logs.py
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/api_client.py
    services/admin-web-ui/src/admin_web_ui/__main__.py
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/tests/test_dashboard_logs.py
  </files>
  <read_first>
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/api_client.py
    services/admin-web-ui/src/admin_web_ui/__main__.py
    services/admin-web-ui/src/admin_web_ui/processes.py
    services/admin-web-ui/src/admin_web_ui/boundary.py
    services/admin-web-ui/tests/test_dashboard_reports.py
    services/admin-console-api/src/admin_console_api/logs.py
    services/admin-console-api/src/admin_console_api/api.py
    .planning/phases/82-log-viewing/82-RESEARCH.md
  </read_first>
  <action>
    ### Create `services/admin-web-ui/src/admin_web_ui/logs.py`

    ```python
    """Log viewing UI page for the admin web UI (Phase 82)."""

    from __future__ import annotations
    from typing import Any, Mapping
    from .boundary import AdminUiBoundary

    __all__ = ["render_logs_page"]
    ```

    `render_logs_page(api_data, identity=None, boundary=None, query_params=None)`:
    - If `boundary is None`, create `AdminUiBoundary()`.
    - Extract query params from `query_params` (a dict): `source`, `level`, `q`, `offset`, `inode`.
    - If `api_data` contains an `"error"` key, render an error message block.
    - Render the page with these sections:

    **1. Source selector:**
    ```html
    <div class="field">
      <label for="source">Log Source</label>
      <select id="source" name="source" onchange="this.form.submit()">
        <option value="">— Select source —</option>
        <option value="contract_events" selected>Contract Events</option>
        <option value="runtime_audit">Runtime Audit</option>
        <option value="feedback">Feedback Queue</option>
        <option value="wecom_stdout">WeCom stdout/stderr</option>
        <option value="qqbot_stdout">QQBot stdout/stderr</option>
      </select>
    </div>
    ```
    The `selected` attribute is set on the option matching `query_params["source"]`. Each option's `available` status from the API `sources` list can be indicated with a suffix `(not configured)` when `available=False`.

    **2. Level filter:**
    ```html
    <div class="field">
      <label for="level">Level</label>
      <select id="level" name="level">
        <option value="">All levels</option>
        <option value="DEBUG">DEBUG</option>
        <option value="INFO">INFO</option>
        <option value="WARN">WARN</option>
        <option value="ERROR">ERROR</option>
      </select>
    </div>
    ```
    The `selected` attribute is set on the option matching `query_params["level"]`.

    **3. Keyword search:**
    ```html
    <div class="field">
      <label for="q">Keyword Search</label>
      <input type="text" id="q" name="q" value="{escaped_query}" placeholder="Filter by keyword..." class="ref-input">
    </div>
    ```

    **4. Hidden offset/inode fields and Refresh button:**
    ```html
    <input type="hidden" name="offset" value="{next_offset}">
    <input type="hidden" name="inode" value="{inode}">
    <button type="submit" class="btn-primary">Refresh</button>
    ```

    **5. Auto-refresh (CSP-safe):**
    Use `<meta http-equiv="refresh" content="5">` inside the page `<head>` for auto-polling every 5 seconds. This is CSP-safe (no inline script required). The meta refresh re-submits the current URL with the same query params, and the hidden `offset` field carries the `next_offset` from the last response. Add a note: `<p class="auto-refresh-note">Auto-refreshing every 5 seconds. <a href="/logs?source={source}&level={level}&q={q}">Reset</a></p>`.

    **6. Log lines display:**
    ```html
    <pre class="log-output">
    {escaped_line_1}
    {escaped_line_2}
    ...
    </pre>
    ```
    Each line is HTML-escaped via `_esc()`. Lines are rendered as plain text in a `<pre>` block with `class="log-output"`. A CSS style for `.log-output` is added: `max-height: 600px; overflow-y: scroll; background: #1a1a2e; color: #e0e0e0; padding: 1rem; border-radius: 6px; font-size: 0.8125rem;`.

    **7. Metadata:**
    Render a small metadata block: `Lines: {lines_returned}/{max_lines} | Filtered: {lines_filtered} | EOF: {eof} | Offset: {next_offset} | Rotated: {rotated}`.

    **8. Wrap in `_page_template`:**
    ```python
    from .dashboard import _page_template
    return _page_template("Log Viewer", body, identity)
    ```

    Use a local `_esc()` helper (same pattern as `processes.py`):
    ```python
    def _esc(value: Any) -> str:
        text = str(value) if value is not None else ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
    ```

    ### Modify `services/admin-web-ui/src/admin_web_ui/server.py`

    1. Add import at top:
       ```python
       from .logs import render_logs_page
       ```

    2. Add to `_SECTION_MAP`:
       ```python
       "/logs": "logs",
       ```

    3. Add `_LOGS_PATH = "/logs"` constant.

    4. In `_guard_path`, add:
       ```python
       if route_path == _LOGS_PATH or route_path.startswith("/logs/"):
           return "/logs"
       ```
       (This maps `/logs` and `/logs/<source>` to the `/logs` RBAC prefix.)

    5. In `handle_admin_web_ui_request`, after the `_handle_processes` block and before the default proxy block, add:
       ```python
       if route_path == _LOGS_PATH or route_path.startswith("/logs/"):
           return _handle_logs(
               http_method=http_method,
               identity=identity,
               auth_header=auth_header,
               feature_flags=feature_flags,
               handle_admin_get=handle_admin_get,
               read_model=read_model,
               feedback_queue=feedback_queue,
               env=env,
               rbac_secret=secret,
               log_reader=getattr(httpd_or_context, "log_reader", None),
               client=client,
               boundary=boundary,
               response_headers=response_headers,
               path=path,
           )
       ```
       Actually, since `handle_admin_web_ui_request` is a function (not a method), the `log_reader` should be passed as a parameter. Add `log_reader: Any = None` to the `handle_admin_web_ui_request` signature (after `reports_aggregator: Any = None`).

    6. Add `_handle_logs` function:
       ```python
       def _handle_logs(
           *,
           http_method: str,
           identity: Identity,
           auth_header: str | None,
           feature_flags: RuntimeFeatureFlags,
           handle_admin_get: HandleAdminGet,
           read_model: Any,
           feedback_queue: list[dict[str, Any]] | None,
           env: Mapping[str, str] | None,
           rbac_secret: str | None,
           log_reader: Any,
           client: AdminApiClient,
           boundary: AdminUiBoundary,
           response_headers: dict[str, str],
           path: str,
       ) -> tuple[int, str, dict[str, str]]:
       ```
       - `/logs` is GET-only. If `http_method != "GET"`, return 405.
       - Parse query params from `path` (split on `?`, use `parse_qs`).
       - Build the API path: if `source` param is present, `api_path = f"/logs/{source}"`; else `api_path = "/logs"`.
       - Append query params: `offset`, `inode`, `level`, `q`, `max_lines` as URL query string.
       - Proxy to `handle_admin_get` via `client.proxy()` with `log_reader=log_reader`.
       - Call `render_logs_page(api_data, identity=identity, boundary=boundary, query_params=parsed_query)`.
       - Return `(status, html_body, response_headers)`.

    7. In the `AdminWebUiServer` class (the `BaseHTTPRequestHandler` subclass at the bottom of `server.py`), ensure `log_reader` is passed from `self.server.log_reader` to `handle_admin_web_ui_request` in the `do_GET` / `do_POST` dispatch.

    ### Modify `services/admin-web-ui/src/admin_web_ui/api_client.py`

    In `AdminApiClient.proxy()`, add `log_reader` pass-through:
    ```python
    if log_reader is not None:
        kwargs["log_reader"] = log_reader
    ```
    Add `log_reader: Any = None` to the `proxy()` method signature.

    ### Modify `services/admin-web-ui/src/admin_web_ui/__main__.py`

    In `create_server(env)`:
    - Add import: `from conversation_read_view.log_reader import LogReader`.
    - After creating `process_supervisor` and `reconcile_on_startup()`:
      ```python
      log_reader = LogReader(env=source, process_supervisor=process_supervisor)
      ```
    - Add `httpd.log_reader = log_reader`.

    ### Modify `services/admin-web-ui/src/admin_web_ui/dashboard.py`

    1. In `_page_template`, add to `nav_items`:
       ```python
       ("/logs", "Logs"),
       ```
       Place it after `("/reports", "Reports")` and before `("/config/channels", "Channel Config")`.

    2. In `render_dashboard`, add to `title_map`:
       ```python
       "logs": "Log Viewer",
       ```

    3. In `_render_index`, add to `sections`:
       ```python
       ("Log Viewer", "/logs", "View runtime logs with level filtering and keyword search"),
       ```
       Place it after the Reports entry.

    4. Add a `"logs"` section handler in `render_dashboard`:
       ```python
       elif section == "logs":
           body = _render_logs_section(data, boundary)
       ```
       However, the `/logs` page is rendered by `logs.py:render_logs_page` directly (not through `render_dashboard`), because it has custom form controls. So this branch is only needed if `/logs` is ever rendered through the default dashboard path (it won't be, since `_handle_logs` calls `render_logs_page` directly). **Skip this** — the `/logs` route bypasses `render_dashboard` entirely, same as `/processes` bypasses it via `render_processes_page`.

    ### Tests: `services/admin-web-ui/tests/test_dashboard_logs.py`

    Create tests following the `test_dashboard_reports.py` pattern:

    1. **test_logs_page_renders_sources:** Call `handle_admin_web_ui_request("/logs", ...)`, assert 200, HTML contains "Log Source", "Contract Events", "Runtime Audit", "Feedback Queue", "WeCom", "QQBot".
    2. **test_logs_page_renders_lines:** Configure a temp JSONL, call `handle_admin_web_ui_request("/logs/contract_events?offset=0", ...)`, assert 200, HTML contains the escaped log line text.
    3. **test_logs_page_level_filter:** Call with `?level=ERROR`, assert the level dropdown has `ERROR` selected.
    4. **test_logs_page_keyword_search:** Call with `?q=keyword`, assert the search input contains the escaped keyword.
    5. **test_logs_page_html_escaped:** Write a JSONL line containing `<script>alert(1)</script>`, assert the HTML contains `&lt;script&gt;` not `<script>`.
    6. **test_logs_page_privacy_scrubbed:** Write a JSONL line with `raw_payload`, assert HTML contains `[REDACTED]` not the raw payload.
    7. **test_logs_page_meta_refresh:** Assert the HTML contains `<meta http-equiv="refresh"` for auto-polling.
    8. **test_logs_page_next_offset_hidden:** Assert the HTML contains a hidden input with `name="offset"` and `value="{next_offset}"`.
    9. **test_logs_page_post_returns_405:** Call with `method="POST"`, assert 405.
    10. **test_logs_page_rbac_admin:** Issue ADMIN token, assert 200.
    11. **test_logs_page_rbac_lawyer_denied:** Issue LAWYER token, assert 403.
    12. **test_logs_page_nav_link:** Assert the HTML contains `<a href="/logs">Logs</a>` in the nav.
    13. **test_logs_page_error_renders:** Call with no log_reader configured, assert HTML contains error message.
    14. **test_logs_page_rotation_indicator:** Read a file, truncate, read again, assert HTML contains "Rotated: true" or similar metadata.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_web_ui.tests.test_dashboard_logs -v</automated>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_web_ui.tests.test_main -v</automated>
    <manual>Confirm that the /logs page renders with CSP headers (default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'). Confirm that no inline JavaScript is used — only meta http-equiv refresh for polling. Confirm that all dynamic content is HTML-escaped.</manual>
  </verify>
</task>

</tasks>

<post_conditions>
After all three tasks are complete:

1. **RBAC CI scan passes:** `PYTHONPATH=packages/rbac/src:services/admin-console-api/src python3 scripts/scan_rbac_annotations.py` exits 0.
2. **All new tests pass:** `test_log_reader.py`, `test_logs.py`, `test_dashboard_logs.py`.
3. **Existing tests still pass:** `test_reports.py`, `test_dashboard_reports.py`, `test_server.py`, `test_main.py`, `test_process_supervisor.py` — no regressions from the `api.py` / `server.py` / `api_client.py` signature changes.
4. **No new dependencies:** `pip show` confirms no new packages; `dependencies = []` in all `pyproject.toml` files.
5. **CSP compliance:** The /logs page uses only `meta http-equiv="refresh"` for polling — no inline `<script>` tags, no EventSource, no WebSocket.
6. **Privacy:** No test fixture or committed file contains real secrets, tokens, or legal payloads. All test JSONL files use synthetic data.
</post_conditions>
