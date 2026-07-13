# Phase 81 — Research Notes

**Phase:** 81 — Reports Dashboard
**Researched:** 2026-07-13
**Domain:** Report aggregation, bounded contract-log scanning, admin console dashboard for the v1.11 Product Console.
**Confidence:** HIGH

> Note: `gsd-phase-researcher` subagent spawning was not available in this environment (no MCP subagent server, no Anthropic API key). The orchestrator performed the research directly using the repository, Python stdlib docs, and the existing GSD research artifacts.

## User Constraints

Copied from `81-CONTEXT.md` (auto-generated, no locked decisions):

- **Claude's Discretion:** All implementation choices are at Claude's discretion. Use the ROADMAP phase goal, success criteria, and codebase conventions.
- **Deferred Ideas:** Report export, real-time push, multi-tenant feedback scoping, and persisted aggregate cache.

### Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-01 | Reports dashboard with session count, task completion rate, long-task success rate, and feedback distribution (up/down/none) over a selectable time range. | `admin_console_api` has `/sessions`, `/tasks`, `/feedback`; `admin-web-ui` has `_SECTION_MAP` and dashboard section renderer; metrics are derived from existing events. |
| OBS-02 | Reports aggregate on-demand from `ContractLogReadModel`, feedback queue, and gate summary without new DB or time-series store. | `read_model` exists; `feedback` queue is in-memory; `gate_summary` is in `admin_console_api/gates.py`; no new persistence needed. |
| OBS-03 | Bounded scanning (tail-read with limits, not full-file in-memory load) to avoid OOM on large logs. | `load_records_from_jsonl` reads the whole file; a new tail scanner is required for report aggregation. |

## Summary

Phase 81 adds a read-only `/reports` dashboard to the admin console. The work is a single vertical slice:

1. **Bounded contract-log scanner/aggregator** (`conversation_read_view/reports_aggregator.py`) — tail-reads the JSONL event log from EOF, groups events by `turn_id` for the requested window, and computes counts without building the full conversation/task index. This satisfies OBS-03 and prevents report requests from reloading the entire log.
2. **API route** (`admin_console_api/reports.py`) — `GET /reports?window=today|7d|30d|custom&from=...&to=...` returns `sessions`, `tasks`, `feedback`, `gates`, and `metadata`.
3. **UI section** (`admin_web_ui/dashboard.py`) — renders a `Reports` page with a time-range selector, refresh action, metric cards, and gate summary.
4. **RBAC and route wiring** — add `/reports` to `ROUTE_PREFIXES`, `PERMISSIONS_MATRIX`, and `admin-web-ui` `_SECTION_MAP`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bounded JSONL scanning | `conversation_read_view` | `admin_console_api` | The contract-log domain owns the record format; the admin API owns the `/reports` endpoint. |
| Metric aggregation | `conversation_read_view` (`ReportsAggregator`) | `admin_console_api` (`handle_reports`) | Pure read over contract events; admin API only validates input and merges gate summary. |
| Gate summary | `admin_console_api` (`gates.py`) | — | `run_gate_summary()` already produces a summary dict. |
| Feedback distribution | `conversation_read_view` (`ReportsAggregator`) | `feedback_service` queue | Queue items are passed in and filtered by `created_at`. |
| Time-range window / refresh | `admin_console_api` | `admin_web_ui` | API resolves `window`/`from`/`to`; UI renders the selector and refresh link. |
| Reports UI | `admin_web_ui` | `admin_console_api` | SSR page; all dynamic values escaped; CSP unchanged. |
| RBAC enforcement | `packages/rbac` | `admin_console_api` | Longest-prefix matrix; `/reports` is read-only and accessible to all roles. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `json` | Python stdlib | Parse JSONL event lines. | No external dependency; line-at-a-time parsing. |
| `datetime` / `zoneinfo` | Python stdlib | Parse ISO `occurred_at`/`started_at`/`ended_at` and bucket by display timezone. | Avoid naive timezone bugs (Pitfall 12). |
| `pathlib` / `os` | Python stdlib | Open JSONL file, seek from EOF, read tail chunks. | Bounded file I/O; no new DB. |
| `collections.Counter` | Python stdlib | Feedback distribution and status counts. | No pandas/numpy. |
| `tracemalloc` | Python stdlib | Perf test memory bound. | Assert bounded memory for 50k-event fixture. |
| `html` | Python stdlib | Escape report values in SSR. | Already used by `dashboard.py`. |

### Avoid

- No new DB, Redis, PostgreSQL, MongoDB, InfluxDB, or time-series store.
- No pandas/numpy; aggregation is simple counts.
- No WebSocket, SSE, or EventSource; UI uses HTTP GET polling.
- No full-file `load_records_from_jsonl` per report request.

## Data Sources

### 1. Contract Log JSONL

Location: `INKSTATUTE_CONTRACT_LOG_PATH` env var (JSONL file, append-ordered).

Relevant events for reports:

| `event_key` | Fields used | Why |
|-------------|-------------|-----|
| `agent_turn` | `turn_id`, `conversation_id`, `user_id`, `channel`, `received_at`, `occurred_at`, `tenant_id` | Anchor for a task/session; provides `conversation_id` for session count. |
| `execution_trace` | `turn_id`, `started_at`, `ended_at`, `occurred_at`, `tenant_id` | Provides duration for long-task detection. |
| `agent_result` | `turn_id`, `status`, `occurred_at`, `tenant_id` | Provides terminal status for completion/success. |
| `route_decision` | `turn_id` | Optional; not needed for reports metrics. |
| `feedback_event` | `turn_id`, `action`, `created_at`, `conversation_id` | May appear in contract log; aggregator can optionally count, but primary feedback source is the queue. |

`occurred_at` is the ISO 8601 timestamp at the top level of the record (not inside `event`). It is the canonical event time for scanning and bucketing.

### 2. Pending Feedback Queue

`admin_console_api` creates a `ThreadSafeFeedbackQueue` from `INKSTATUTE_FEEDBACK_QUEUE_PATH`. Each item is a `FeedbackEvent` dict with:

- `action`: `up` | `down` | `needs_fix` | `route_wrong`
- `created_at`: ISO 8601 timestamp
- `conversation_id`, `turn_id`, `feedback_id`, `source`

The aggregator filters by `created_at` within the time window and groups by `action`, collapsing `down`/`needs_fix`/`route_wrong` into `down` and missing/unrecognized into `none`.

### 3. Gate Summary

`admin_console_api/gates.py` `run_gate_summary()` returns a dict like:

```json
{
  "gates": {"passed": true, "gate_count": 10, "gates_passed": 8, "gates_failed": 2, "rate": 0.8},
  "details": [...]
}
```

`handle_reports` calls `run_gate_summary()` and merges the `gates` block into the report response. It is not re-implemented in the aggregator because the `gate_summary.py` CLI already runs `run_v2_gates.py` and parses `stdout`.

## Aggregation Algorithm

1. Resolve `window` → `(time_from, time_to)` in UTC.
2. `scan_from = time_from - lookback_seconds` (default 86400). This captures long-running turns whose `agent_turn` occurred before the window but whose `execution_trace`/`agent_result` end inside the window.
3. Open `INKSTATUTE_CONTRACT_LOG_PATH`, seek to EOF, and read chunks (e.g. 64 KB) backwards.
4. Parse each JSON line in reverse order. Skip records with `occurred_at < scan_from` and stop after `max_scan_lines` (default 10000) or when `occurred_at < scan_from - 1 hour`.
5. Collect all records in a list, then reverse it to chronological order. Group by `turn_id`.
6. For each `turn_id`:
   - Use `agent_turn` for `conversation_id`, `channel`, `user_id`, `tenant_id`, and turn start time.
   - Use `execution_trace` for duration: `ended_at - started_at`.
   - Use `agent_result` for terminal status.
   - Only include if `agent_turn.occurred_at` (or `agent_result.occurred_at` for completed tasks) is within `[time_from, time_to]`.
7. Count unique `conversation_id` values → `sessions`.
8. Count turns → `tasks.total`. Count `agent_result.status` in `success|partial` → `completed`; other terminal statuses → `failed`; no result → `incomplete`.
9. `completion_rate = completed / total`.
10. `long_task_total = tasks with duration > long_task_threshold`; `long_task_success = long tasks with status in success|partial`; `long_task_success_rate = long_task_success / long_task_total`.
11. Filter `feedback_queue` by `created_at` in window, group by `action` → `up`, `down`, `none`.
12. Return scrubbed aggregate dict.

## Metric Definitions

| Metric | Source | Formula | Notes |
|--------|--------|---------|-------|
| Session count | `agent_turn` events | unique `conversation_id` | One session = one conversation. |
| Task count | `agent_turn` events | count of `turn_id` | Each turn is a task. |
| Completed tasks | `agent_result` | `status in {success, partial}` | `partial` is a completed-but-not-perfect result. |
| Failed tasks | `agent_result` | `status in {failed, blocked, needs_clarification}` | Everything else is a terminal failure. |
| Incomplete tasks | — | `total - completed - failed` | Task still running or no result yet. |
| Task completion rate | derived | `completed / total` | 0.0 if total is 0. |
| Long-task threshold | `REPORTS_LONG_TASK_THRESHOLD_SECONDS` env | default `60.0` seconds | A task whose `execution_trace` duration exceeds this is a long task. |
| Long-task success rate | derived | `long tasks with status in {success, partial} / long tasks` | Measures whether slow tasks still succeed. |
| Feedback up | feedback queue | `action == 'up'` | Positive feedback. |
| Feedback down | feedback queue | `action in {down, needs_fix, route_wrong}` | Negative or corrective feedback. |
| Feedback none | feedback queue | `action` missing or not in above | Queue items without a rating action. |

## Pitfalls and Mitigations

### Pitfall 10: Rebuilding the full in-memory read model per request

`ContractLogReadModel.from_records()` loads, sorts, and indexes every JSONL record. If `/reports` calls this per request, large logs will cause OOM and multi-second latency.

**Mitigation:** `ReportsAggregator` tail-reads the JSONL from EOF and stops once outside the window. It does not call `from_records()` or build the conversation/task index. The existing `read_model` is left untouched for `/sessions` and `/tasks`.

### Pitfall 11: Stale report data

If the aggregate is cached at startup and never refreshed, operators see old data after new events are written.

**Mitigation:** Every `GET /reports` rebuilds the aggregate on demand. The UI shows `aggregated_at` (UTC). The `Refresh` button re-GETs the same URL with the chosen window. No persistent cache is introduced in this phase; bounded scanning keeps per-request cost acceptable.

### Pitfall 12: Timezone inconsistency

`occurred_at` is UTC; the UI may be viewed in a local timezone. Naive string slicing will bucket events into the wrong day.

**Mitigation:** Parse all timestamps to aware UTC `datetime` using `datetime.fromisoformat`. Convert to the display timezone (`INKSTATUTE_REPORT_DISPLAY_TZ`, default `UTC`) only when computing day buckets. For this phase, the response returns UTC ISO strings; the UI can display them as-is. The aggregator's window boundaries are computed in UTC from the selected local window.

### Pitfall 13: Unbounded JSONL scan

A "30 days" report with no line limit could read months of events.

**Mitigation:** `REPORTS_MAX_SCAN_LINES` caps the number of lines read per request. The default window is `7d` and opt-in `30d`/`custom` increases the cap. The scanner early-exits when `occurred_at < scan_from` and the chunk boundary is outside the window.

## Security & Privacy

- `ReportsAggregator` calls `scrub_contract_payload` on every record before extracting fields. If a forbidden key appears, the scanner fails closed (raises `ValueError`) so raw payloads cannot leak through a report.
- The UI escapes every metric value with `html.escape` / `AdminUiBoundary.escape_value`.
- The API returns no raw messages, attachments, or `raw_payload_ref` fields; only counts and derived rates.
- The `ReportsAggregator` does not log the contract log path or event contents.

## Validation Architecture

> Section required for Nyquist validation.

- **Framework:** `unittest` (existing repo convention) with `python -m unittest`.
- **Quick run:** `PYTHONPATH=... python -m unittest services.conversation-read-view.tests.test_reports_aggregator services.admin-console-api.tests.test_reports services.admin-web-ui.tests.test_dashboard_reports -q`
- **Full run:** `python -m unittest discover -s services -p "test_*.py" -q` (or per-service test invocation).
- **Per-task verification:** Every plan task contains an `<automated>` verify block.
- **Wave 0:** No new test framework needed; `conversation-read-view` and `admin-console-api` already have tests.
- **Manual-only:** None.

## Open Questions / Risks

1. **Contract log file size:** The 50k-event perf test validates the bounded scanner, but the `read_model` in `admin-console-api` and `admin-web-ui` still loads the entire log at startup. OBS-03 only applies to report aggregation, but the console startup still loads full. This is accepted because startup happens once per process.
2. **Feedback queue multi-tenancy:** The `ThreadSafeFeedbackQueue` is not tenant-scoped. Reports will aggregate all feedback regardless of `tenant_filter`. This is acceptable for the MVP and noted in deferred ideas.
3. **Gate summary cost:** `run_gate_summary()` runs `python run_v2_gates.py` each time. This may be expensive for `/reports`. If it is too slow, the gate summary can be made optional with a query flag (`?include_gates=1`) in a follow-up.

## References

- `.planning/research/ARCHITECTURE.md` — reports aggregation flow and metric definitions
- `.planning/research/PITFALLS.md` — Pitfalls 10–13 (reports-specific)
- `.planning/research/STACK.md` — stdlib-only stack constraints
- `.planning/research/SUMMARY.md` — must-address items for Phase 81
- `.planning/REQUIREMENTS.md` — OBS-01, OBS-02, OBS-03
- `.planning/ROADMAP.md` — Phase 81 goal
- `services/conversation-read-view/src/conversation_read_view/read_model.py`
- `services/conversation-read-view/src/conversation_read_view/privacy.py`
- `services/admin-console-api/src/admin_console_api/api.py`
- `services/admin-console-api/src/admin_console_api/views.py`
- `services/admin-console-api/src/admin_console_api/gates.py`
- `services/admin-web-ui/src/admin_web_ui/dashboard.py`
- `packages/rbac/src/rbac/matrix.py`
