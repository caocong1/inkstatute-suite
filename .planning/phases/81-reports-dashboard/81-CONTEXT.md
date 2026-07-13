# Phase 81: Reports Dashboard - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Add a reports dashboard to the existing admin console so operators can view aggregate operational statistics over a selectable time range. Reports are read-only, derive from existing sources, and must not introduce new persistence or full-file event-log loads.

### Requirements

This phase covers:

- **OBS-01**: Operator can view a reports dashboard with aggregate statistics: session count, task completion rate, long-task success rate, and feedback distribution (up/down/none) over a selectable time range.
- **OBS-02**: Reports aggregate on-demand from existing data sources (`ContractLogReadModel`, feedback queue, gate summary) without introducing a new database or time-series store.
- **OBS-03**: Report aggregation uses bounded scanning (tail-read with limits, not full-file in-memory load) to avoid OOM on large event logs.

### Success Criteria (what must be TRUE)

1. The console renders a `/reports` page with a time-range selector (`today` / `7d` / `30d` / custom) and a refresh action.
2. The page displays: unique session count, task completion rate, long-task success rate, feedback distribution (`up` / `down` / `none`), and gate summary.
3. Aggregation reads from the contract JSONL file, pending feedback queue, and gate summary only; no new DB or time-series store is introduced.
4. Aggregation is bounded: it reverse-reads the JSONL tail with configurable line limits and early-exits once outside the requested window; a perf test with a 50k-event fixture asserts <1s response and bounded memory.
5. No secret token or raw legal payload is rendered; all UI values pass through `html.escape`/`AdminUiBoundary.escape_value` and the API response passes through `scrub_contract_payload`.
6. RBAC is enforced: `/reports` is added to `ROUTE_PREFIXES` and `PERMISSIONS_MATRIX` for `admin`, `operator`, `lawyer`, and `viewer` read access.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key discretion points:

- Place the bounded scanner/aggregator in `conversation_read_view` so it can reuse contract-log JSONL and privacy scrubbing while keeping the admin API thin.
- Implement a `ReportsAggregator` class that scans from EOF backwards in chunks, groups events by `turn_id` for the requested window, and computes counts without materializing the full read model.
- Use `agent_result.status` and `execution_trace.started_at`/`ended_at` for completion and duration; treat `success` and `partial` as completed, `failed`/`blocked`/`needs_clarification` as failed.
- Long-task threshold is `REPORTS_LONG_TASK_THRESHOLD_SECONDS` env var, default `60.0`.
- Bounded scan defaults: `REPORTS_MAX_SCAN_LINES` default `10000`, `REPORTS_SCAN_LOOKBACK_SECONDS` default `86400` (1 day lookback to capture long-running turns that start before the window start).
- Time-range bucketing uses a configured display timezone (`INKSTATUTE_REPORT_DISPLAY_TZ`, default `UTC`); `occurred_at`/`started_at`/`ended_at` are normalized to aware `datetime` in UTC before bucketing.
- `last_built_at` / `aggregated_at` timestamp is returned on every request; the UI refresh button re-GETs the page with the chosen window.
- Reports are gated by `admin_api_enabled` / `admin_web_ui_enabled` service flags; no new feature flag is added because the dashboard is a read-only view inside the existing admin console.

</decisions>

<code_context>
## Existing Code Insights

- `admin_console_api` is a stdlib `http.server` service with `api.py` dispatching `/sessions`, `/tasks`, `/feedback`, `/health`, `/gates`, `/processes`, `/config`. `server.py` creates `read_model`, `feedback_queue`, `feature_flags`, `env`, `rbac_secret`, and `process_supervisor` on the server instance.
- `admin_console_api/views.py` uses `TenantScopedContractLogReadModel` and `scrub_contract_payload` for list views and CSV/JSON export.
- `admin_console_api/routes.py` lists `ROUTE_PREFIXES`; `packages/rbac/matrix.py` defines `PERMISSIONS_MATRIX`.
- `admin_console_api/gates.py` already runs `run_gate_summary()` and returns a gate summary dict.
- `admin-web-ui` is a pure SSR server (`server.py` + `dashboard.py`). `dashboard.py` has `_page_template`, `_SECTION_MAP`, nav list, and `render_dashboard` dispatching sections by `section` name.
- `conversation_read_view` provides `ContractLogReadModel`, `load_records_from_jsonl`, `build_read_model`, `privacy.scrub_contract_payload`, and `TenantScopedContractLogReadModel`.
- `feedback_service.feedback` provides `ThreadSafeFeedbackQueue` and normalization; feedback items have an `action` field (`up`, `down`, `needs_fix`, `route_wrong`) and `created_at`.
- `platform_contract` `events.py` defines `AgentTurn`, `AgentResult` (status enum `success`, `partial`, `failed`, `blocked`, `needs_clarification`), and `ExecutionTrace` (`started_at`, `ended_at`).
- `RuntimeFeatureFlags` reads `INKSTATUTE_<FIELD_NAME_UPPER>` env vars and defaults all flags to OFF.
- CSP stays exactly as-is; no inline JS, no EventSource, no WebSocket. UI refresh is an HTTP GET (form or link).
</code_context>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before implementing:

- `services/admin-console-api/src/admin_console_api/api.py` — route dispatch
- `services/admin-console-api/src/admin_console_api/views.py` — existing list view patterns
- `services/admin-console-api/src/admin_console_api/routes.py` — `ROUTE_PREFIXES`
- `services/admin-console-api/src/admin_console_api/server.py` — server bootstrap and `handle_admin_get` invocation
- `services/admin-console-api/src/admin_console_api/gates.py` — `run_gate_summary`
- `services/admin-web-ui/src/admin_web_ui/server.py` — `_SECTION_MAP`, `_POST_ROUTES`, `AdminApiClient`, `handle_admin_web_ui_request`
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` — `_page_template`, `_SECTION_MAP`, `render_dashboard`, nav rendering
- `services/conversation-read-view/src/conversation_read_view/read_model.py` — contract log record model and task grouping
- `services/conversation-read-view/src/conversation_read_view/privacy.py` — `scrub_contract_payload`
- `packages/rbac/src/rbac/matrix.py` — `PERMISSIONS_MATRIX`
- `packages/rbac/src/rbac/roles.py` — `Role` enum
- `.planning/research/ARCHITECTURE.md` — reports aggregation flow, recommended env vars
- `.planning/research/PITFALLS.md` — Pitfalls 10–13 (bounded scan, stale data, timezone, unbounded scan)
- `.planning/research/STACK.md` — report aggregation stack recommendations
- `.planning/research/SUMMARY.md` — must-address items for Phase 81
- `.planning/REQUIREMENTS.md` — OBS-01, OBS-02, OBS-03
- `.planning/ROADMAP.md` — Phase 81 goal and dependencies
</canonical_refs>

<specifics>
## Specific Ideas

- Add `/reports` to `admin_console_api` returning `200` JSON with `sessions`, `tasks`, `feedback`, `gates`, and `metadata`.
- Add `conversation_read_view/reports_aggregator.py` containing `ReportsAggregator` with `__init__(contract_log_path, default_max_scan_lines, default_lookback_seconds, long_task_threshold_seconds)` and `build(time_from, time_to, feedback_queue, tenant_filter=None)`.
- Add `admin_console_api/reports.py` containing `handle_reports(query, reports_aggregator, feedback_queue, feature_flags, tenant_filter)`.
- Update `admin-web-ui` dashboard with a `Reports` section, time-range `<select>` and a refresh `<button>` (GET form), metric cards, and a gate summary table.
- Add `services/conversation-read-view/tests/test_reports_aggregator.py` and `services/admin-console-api/tests/test_reports.py` and `services/admin-web-ui/tests/test_dashboard.py` test cases for reports rendering.
- Add `services/conversation-read-view/tests/test_reports_perf.py` with a 50k-event JSONL fixture asserting `ReportsAggregator.build()` runs in <1s and uses bounded memory via `tracemalloc`.
</specifics>

<deferred>
## Deferred Ideas

- Report export (CSV/JSON download) is deferred to CON-F07.
- Real-time SSE/WebSocket updates are deferred (CSP/AGENTS.md forbids new push channels).
- Multi-tenant scoped reports for feedback queue are not added; the feedback queue is filtered by `created_at` only in this phase.
- Persisted aggregate cache with mtime invalidation is a future optimization; the initial implementation rebuilds per request but bounded.
</deferred>
