---
phase: 81-reports-dashboard
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/conversation-read-view/src/conversation_read_view/reports_aggregator.py
  - services/conversation-read-view/src/conversation_read_view/__init__.py
  - services/admin-console-api/src/admin_console_api/reports.py
  - services/admin-console-api/src/admin_console_api/api.py
  - services/admin-console-api/src/admin_console_api/server.py
  - services/admin-console-api/src/admin_console_api/routes.py
  - packages/rbac/src/rbac/matrix.py
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - services/admin-web-ui/src/admin_web_ui/server.py
  - services/admin-web-ui/src/admin_web_ui/api_client.py
  - services/admin-web-ui/src/admin_web_ui/__main__.py
  - .env.example
  - services/conversation-read-view/tests/test_reports_aggregator.py
  - services/conversation-read-view/tests/test_reports_perf.py
  - services/admin-console-api/tests/test_reports.py
  - services/admin-web-ui/tests/test_dashboard_reports.py
autonomous: true
requirements:
  - OBS-01
  - OBS-02
  - OBS-03
user_setup: []

must_haves:
  truths:
    - "GET /reports returns a JSON payload with sessions.count, tasks.total/completed/completion_rate/long_task_success_rate, feedback.up/down/none, gates.passed/rate, and metadata.window/time_from/time_to/aggregated_at"
    - "The /reports web page renders a time-range selector (today/7d/30d/custom), a Refresh button, metric cards, and escaped values"
    - "Report aggregation reads the contract JSONL tail from EOF with a configurable line limit and early-exit; it does not load the full file per request"
    - "RBAC scan passes and /reports is accessible to admin, operator, lawyer, and viewer roles"
    - "A 50k-event perf test asserts <1s response and bounded memory"
  artifacts:
    - "conversation_read_view.reports_aggregator.ReportsAggregator class"
    - "admin_console_api.reports.handle_reports function"
    - "admin_console_api.api.handle_admin_get /reports route"
    - "admin_console_api.server.create_server reports_aggregator wiring"
    - "admin_console_api.routes.ROUTE_PREFIXES /reports entry"
    - "rbac.matrix.PERMISSIONS_MATRIX /reports entry"
    - "admin_web_ui.dashboard._render_reports_section and _SECTION_MAP /reports"
    - "admin_web_ui.server.handle_admin_web_ui_request /reports pass-through and query preservation"
    - "admin_web_ui.api_client.AdminApiClient.proxy reports_aggregator pass-through"
    - "admin_web_ui.__main__.create_server reports_aggregator wiring"
    - "test_reports_aggregator.py, test_reports_perf.py, test_reports.py, test_dashboard_reports.py"
  key_links:
    - "ReportsAggregator.build() is called by admin_console_api.reports.handle_reports for GET /reports"
    - "handle_admin_get routes /reports to handle_reports and passes reports_aggregator from server instance"
    - "admin-web-ui proxy passes the full query string to admin-console-api so window/from/to reach handle_reports"
    - "dashboard.py reports section renders the handle_reports JSON response and re-submits window on Refresh"
    - "gate summary is merged from admin_console_api.gates.run_gate_summary"
---

<objective>
Add a read-only `/reports` dashboard to the admin console. The dashboard displays session count, task completion rate, long-task success rate, and feedback distribution over a selectable time range, aggregated on-demand from the contract JSONL, pending feedback queue, and gate summary without new persistence or a full-file load.

Purpose: Give operators an at-a-glance operational health view that is bounded, privacy-safe, and fits the existing stdlib SSR stack.

Output: A working `/reports` API endpoint, `/reports` web page, bounded scanner, and automated tests.
</objective>

<execution_context>
@$HOME/.codeium/windsurf/gsd-core/workflows/execute-plan.md
@$HOME/.codeium/windsurf/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/81-reports-dashboard/81-CONTEXT.md
@.planning/phases/81-reports-dashboard/81-RESEARCH.md
@services/conversation-read-view/src/conversation_read_view/read_model.py
@services/conversation-read-view/src/conversation_read_view/privacy.py
@services/admin-console-api/src/admin_console_api/api.py
@services/admin-console-api/src/admin_console_api/views.py
@services/admin-console-api/src/admin_console_api/gates.py
@services/admin-console-api/src/admin_console_api/server.py
@services/admin-console-api/src/admin_console_api/routes.py
@services/admin-web-ui/src/admin_web_ui/dashboard.py
@services/admin-web-ui/src/admin_web_ui/server.py
@services/admin-web-ui/src/admin_web_ui/api_client.py
@services/admin-web-ui/src/admin_web_ui/__main__.py
@packages/rbac/src/rbac/matrix.py
@packages/platform-contract/src/platform_contract/events.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: ReportsAggregator with bounded JSONL tail scanner</name>
  <files>
    services/conversation-read-view/src/conversation_read_view/reports_aggregator.py
    services/conversation-read-view/src/conversation_read_view/__init__.py
    services/conversation-read-view/tests/test_reports_aggregator.py
    services/conversation-read-view/tests/test_reports_perf.py
  </files>
  <read_first>
    services/conversation-read-view/src/conversation_read_view/read_model.py
    services/conversation-read-view/src/conversation_read_view/privacy.py
    services/conversation-read-view/src/conversation_read_view/__init__.py
    packages/platform-contract/src/platform_contract/events.py
    services/feedback-service/src/feedback_service/feedback.py
    packages/platform-contract/src/platform_contract/schemas/feedback_event.schema.json
    .planning/phases/81-reports-dashboard/81-RESEARCH.md
  </read_first>
  <action>
    Create `services/conversation-read-view/src/conversation_read_view/reports_aggregator.py` with a `ReportsAggregator` class.

    `__init__(self, contract_log_path, default_max_scan_lines=10000, default_lookback_seconds=86400, long_task_threshold_seconds=60.0, display_tz='UTC', env=None)` stores the path and defaults. Env overrides are read from `env` (or `os.environ` if `env` is None): `REPORTS_MAX_SCAN_LINES`, `REPORTS_SCAN_LOOKBACK_SECONDS`, `REPORTS_LONG_TASK_THRESHOLD_SECONDS`, and `INKSTATUTE_REPORT_DISPLAY_TZ`.

    `build(self, time_from, time_to, feedback_queue, tenant_filter=None, max_scan_lines=None)` returns a dict:
    - `sessions`: `{"count": unique conversation_id}` from `agent_turn` events in the window.
    - `tasks`: `{"total", "completed", "failed", "incomplete", "completion_rate", "long_task_total", "long_task_success", "long_task_success_rate"}`; `completed` = `agent_result.status in {"success", "partial"}`; `failed` = status in `{failed, blocked, needs_clarification}`; `incomplete` = no terminal result; duration from `execution_trace.started_at`/`ended_at`; long task threshold from config.
    - `feedback`: `{"up", "down", "none", "total"}` from `feedback_queue` items filtered by `created_at` in window; `down` = `action in {"down", "needs_fix", "route_wrong"}`; `none` = action missing or not in above.
    - `metadata`: `{"window", "time_from", "time_to", "aggregated_at", "scan_lines", "max_scan_lines", "lookback_seconds", "display_tz"}`.

    The scanner opens `contract_log_path`, seeks to EOF, reads chunks backwards (e.g. 64 KiB), parses JSON lines, and collects records until `occurred_at < (time_from - lookback_seconds)` or `max_scan_lines` is reached, then reverses the list. Records are grouped by `turn_id` to combine `agent_turn`, `execution_trace`, and `agent_result`. `scrub_contract_payload` is called on every collected record before extraction; forbidden keys cause the scan to fail closed. `tenant_filter` is applied by checking `record.tenant_id` (top-level) when the filter is active.

    Update `services/conversation-read-view/src/conversation_read_view/__init__.py` to add `ReportsAggregator` to `__all__`.

    Create `services/conversation-read-view/tests/test_reports_aggregator.py` with unit tests: a small JSONL fixture with two turns (one success, one failed long task), assert counts, rates, and long-task detection; an empty file returns zeros; an invalid `window` is not tested here (handled by API); timezone boundary with `display_tz`.

    Create `services/conversation-read-view/tests/test_reports_perf.py` with a `test_50k_events_bounded` test: generate a 50k-line JSONL fixture, call `ReportsAggregator.build()` for a 7-day window, assert elapsed < 1.0 second and peak memory increase via `tracemalloc` is under 25 MB (or `max_scan_lines * 4 KB` if smaller). Clean up the fixture in `tearDown`.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src python -m unittest services.conversation-read-view.tests.test_reports_aggregator services.conversation-read-view.tests.test_reports_perf -q</automated>
  </verify>
  <done>`ReportsAggregator` is created, exported, passes unit tests, and the 50k-event perf test asserts <1s and bounded memory.</done>
</task>

<task type="auto">
  <name>Task 2: /reports API route and RBAC wiring</name>
  <files>
    services/admin-console-api/src/admin_console_api/reports.py
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/server.py
    services/admin-console-api/src/admin_console_api/routes.py
    packages/rbac/src/rbac/matrix.py
    services/admin-console-api/tests/test_reports.py
  </files>
  <read_first>
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/views.py
    services/admin-console-api/src/admin_console_api/gates.py
    services/admin-console-api/src/admin_console_api/server.py
    services/admin-console-api/src/admin_console_api/routes.py
    packages/rbac/src/rbac/matrix.py
    packages/rbac/src/rbac/roles.py
    packages/platform-runtime/src/platform_runtime/feature_flags.py
    .planning/phases/81-reports-dashboard/81-RESEARCH.md
  </read_first>
  <action>
    Create `services/admin-console-api/src/admin_console_api/reports.py` with `handle_reports(query, reports_aggregator, feedback_queue, feature_flags, tenant_filter=None, env=None)`.

    It validates `window` in `{today, 7d, 30d, custom}` (default `7d`). For `custom`, it parses `from` and `to` ISO strings. It resolves `time_from`/`time_to` in UTC using `INKSTATUTE_REPORT_DISPLAY_TZ` from `env` (default `UTC`) for `today` local start. It calls `reports_aggregator.build()` and merges the gate summary from `admin_console_api.gates.run_gate_summary()` or `handle_gates()`. It returns `200` with `scrub_contract_payload` applied. Unknown window returns `400`; aggregator errors return `500` with generic message. The `admin_api_enabled` feature-flag gate is handled by `handle_admin_get` before dispatch.

    Update `services/admin-console-api/src/admin_console_api/api.py`:
    - Add `reports_aggregator=None` to the `handle_admin_get` signature.
    - Add `from .reports import handle_reports`.
    - After the `/processes` block, add `if route_path == "/reports" or route_path.startswith("/reports/"): return handle_reports(route_query, reports_aggregator, feedback_queue, feature_flags, tenant_filter=tenant_filter, env=env)`.

    Update `services/admin-console-api/src/admin_console_api/server.py`:
    - Import `ReportsAggregator` from `conversation_read_view`.
    - In `create_server`, build `reports_aggregator = ReportsAggregator(contract_log_path, env=source)` and attach to `httpd.reports_aggregator`.
    - Update `AdminConsoleApiServer._dispatch` to pass `reports_aggregator=self.server.reports_aggregator` to `handle_admin_get`.

    Update `services/admin-console-api/src/admin_console_api/routes.py` to add `"/reports"` to `ROUTE_PREFIXES`.

    Update `packages/rbac/src/rbac/matrix.py` to add `"/reports": frozenset({Role.ADMIN, Role.OPERATOR, Role.LAWYER, Role.VIEWER})`.

    Create `services/admin-console-api/tests/test_reports.py` with tests: `GET /reports` returns 200 with the expected keys; `GET /reports?window=today` returns a `today` window; `GET /reports?window=invalid` returns 400; RBAC `viewer` token can access `/reports`; `admin_api_enabled` OFF returns 503 before route handling.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src python -m unittest services.admin-console-api.tests.test_reports -q</automated>
    <automated>PYTHONPATH=packages/rbac/src:services/admin-console-api/src python scripts/scan_rbac_annotations.py</automated>
  </verify>
  <done>`GET /reports` returns the expected aggregate JSON; `window` validation and RBAC work; `scan_rbac_annotations.py` exits 0.</done>
</task>

<task type="auto">
  <name>Task 3: Admin-web-ui reports page and wiring</name>
  <files>
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/api_client.py
    services/admin-web-ui/src/admin_web_ui/__main__.py
    .env.example
    services/admin-web-ui/tests/test_dashboard_reports.py
  </files>
  <read_first>
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/api_client.py
    services/admin-web-ui/src/admin_web_ui/__main__.py
    services/admin-web-ui/src/admin_web_ui/boundary.py
    services/admin-console-api/src/admin_console_api/api.py
    .planning/phases/81-reports-dashboard/81-RESEARCH.md
  </read_first>
  <action>
    Update `services/admin-web-ui/src/admin_web_ui/dashboard.py`:
    - Add `("/reports", "Reports")` to `_page_template` `nav_items` and `_render_index` card list.
    - In `render_dashboard`, add a `section == "reports"` branch that calls a new `_render_reports_section(api_data, identity, boundary)`.
    - `_render_reports_section` renders: a `<form method="GET" action="/reports">` with a `<select name="window">` for `today`, `7d`, `30d`, `custom`, and a `Refresh` submit button; when `custom` is selected (or the query param is `custom`), optional `<input type="datetime-local" name="from">` and `<input name="to">` fields are shown and submitted. Metric cards show sessions, task completion rate, long-task success rate, feedback counts, and a gate summary. The `metadata.aggregated_at` timestamp and a note that values are UTC are displayed. All dynamic text is passed through `boundary.escape_value` or `html.escape`. `window` selection uses `metadata.window` from `api_data`.

    Update `services/admin-web-ui/src/admin_web_ui/server.py`:
    - Add `("/reports", "reports")` to `_SECTION_MAP`.
    - Add `_REPORTS_PATH = "/reports"`.
    - Update `handle_admin_web_ui_request` signature to accept `reports_aggregator=None`.
    - In `handle_admin_web_ui_request`, pass `reports_aggregator` to `client.proxy` for operational routes and to `_handle_*` helpers as needed.
    - At the operational GET proxy point, change `api_path = "/sessions" if route_path == "/" else route_path` to `api_path = "/sessions" if route_path == "/" else path` so the query string (`?window=...`) is preserved and reaches `handle_admin_get`.
    - Update `_guard_path` if needed; `/reports` already maps to `/reports` by default.

    Update `services/admin-web-ui/src/admin_web_ui/api_client.py`:
    - Add `reports_aggregator=None` to `AdminApiClient.proxy` signature and include it in `kwargs` when not None.

    Update `services/admin-web-ui/src/admin_web_ui/__main__.py`:
    - Import `ReportsAggregator`.
    - Build `reports_aggregator = ReportsAggregator(contract_log_path, env=source)` and attach to `httpd.reports_aggregator`.

    Update `.env.example` to add `INKSTATUTE_REPORT_MAX_SCAN_LINES`, `INKSTATUTE_REPORT_SCAN_LOOKBACK_SECONDS`, `INKSTATUTE_REPORT_LONG_TASK_THRESHOLD_SECONDS`, and `INKSTATUTE_REPORT_DISPLAY_TZ` with inline comments and default values (commented out).

    Create `services/admin-web-ui/tests/test_dashboard_reports.py` with integration tests: GET `/reports` returns 200 with the reports title; the metric card strings are present; selecting `window=today` in the query string returns the page with `selected` on the `today` option; raw `<script>` injected via a mocked API response is escaped in the output.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin-web-ui.tests.test_dashboard_reports -q</automated>
  </verify>
  <done>`/reports` renders a reports page with a time selector, Refresh button, metric cards, and escaped values; the `window` query parameter reaches the API and updates the page.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Client → Admin Web UI → Admin API | Browser is untrusted; all output must be escaped and all inputs validated before aggregation. |
| Admin API → Contract JSONL | The contract log is read-only; the scanner must not expose raw payloads or forbidden keys. |
| Admin API → Gate Subprocess | Gate summary runs an isolated subprocess; stdout/stderr is not exposed. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-81-01 | Information Disclosure | `ReportsAggregator` | mitigate | `scrub_contract_payload` on every event; response contains only counts and rates; no `raw_payload_ref` or message content. |
| T-81-02 | Information Disclosure | `/reports` UI | mitigate | All interpolated values pass through `html.escape` / `AdminUiBoundary.escape_value`; no `innerHTML` or unescaped JSON. |
| T-81-03 | Denial of Service | `ReportsAggregator` | mitigate | Bounded tail scan with `REPORTS_MAX_SCAN_LINES` and `REPORTS_SCAN_LOOKBACK_SECONDS`; OOM on large logs prevented by 50k perf test. |
| T-81-04 | Elevation | `/reports` route | mitigate | Added to `PERMISSIONS_MATRIX` for read-only roles; `handle_admin_get` runs auth and `RbacGuard` before dispatch. |
| T-81-05 | Tampering | `window`/`from`/`to` query params | mitigate | `handle_reports` validates `window` and parses ISO timestamps; malformed input returns 400. |
| T-81-06 | Information Disclosure | Admin API response | mitigate | `scrub_contract_payload` is applied to the final JSON before serialization; forbidden keys fail closed. |
| T-81-07 | Denial of Service | Gate summary subprocess | mitigate | `run_gate_summary` has a 300s timeout and returns a generic error; it is not called with user-controlled parameters. |
</threat_model>

<verification>
- `python scripts/scan_rbac_annotations.py` exits 0.
- `python -m unittest services.conversation-read-view.tests.test_reports_aggregator services.conversation-read-view.tests.test_reports_perf services.admin-console-api.tests.test_reports services.admin-web-ui.tests.test_dashboard_reports -q` exits 0.
- Manual `GET /reports` in the browser shows the page with a selector and metrics.
- Manual `GET /reports?window=today` returns the expected `today` window and updates the UI.
</verification>

<success_criteria>
- `GET /reports` returns `200` JSON with `sessions`, `tasks`, `feedback`, `gates`, and `metadata`.
- `/reports` page renders a time selector, Refresh button, metric cards, and escaped values.
- `ReportsAggregator` does not call `load_records_from_jsonl`; it tail-reads the JSONL with `max_scan_lines` limit.
- The 50k-event perf test passes (<1s, bounded memory).
- `scripts/scan_rbac_annotations.py` passes and `/reports` is in the permissions matrix.
- All new tests are green.
</success_criteria>

<output>
Create `.planning/phases/81-reports-dashboard/81-PLAN-SUMMARY.md` when done.
</output>

## Artifacts this phase produces

- `conversation_read_view.reports_aggregator.ReportsAggregator` class (new file)
- `conversation_read_view.__init__.py` `__all__` addition
- `admin_console_api.reports.handle_reports` function (new file)
- `admin_console_api.api.handle_admin_get` signature and `/reports` route additions
- `admin_console_api.server.create_server` `reports_aggregator` instance and `_dispatch` pass-through
- `admin_console_api.routes.ROUTE_PREFIXES` `/reports` entry
- `rbac.matrix.PERMISSIONS_MATRIX` `/reports` entry
- `admin_web_ui.dashboard._render_reports_section` and `_SECTION_MAP` nav wiring
- `admin_web_ui.server.handle_admin_web_ui_request` query-string preservation and `reports_aggregator` pass-through
- `admin_web_ui.api_client.AdminApiClient.proxy` `reports_aggregator` kwarg
- `admin_web_ui.__main__.create_server` `reports_aggregator` wiring
- `.env.example` additions for report scanner env vars
- `services/conversation-read-view/tests/test_reports_aggregator.py`
- `services/conversation-read-view/tests/test_reports_perf.py`
- `services/admin-console-api/tests/test_reports.py`
- `services/admin-web-ui/tests/test_dashboard_reports.py`
