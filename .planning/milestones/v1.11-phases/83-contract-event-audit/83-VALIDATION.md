# Phase 83: Contract Event Audit — Validation Criteria

**Phase:** 83 — Contract Event Audit
**Requirements:** OBS-07, OBS-08
**Date:** 2026-07-14

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib) |
| **Config file** | none — stdlib unittest |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest conversation_read_view.tests.test_audit services.admin_console_api.tests.test_audit services.admin_web_ui.tests.test_dashboard_audit -v` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest discover -s services/conversation-read-view/tests services/admin-console-api/tests services/admin-web-ui/tests -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command (3 new test modules)
- **After every plan wave:** Run full suite command + RBAC CI scan
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## OBS-07: Paginated audit trail of AgentTurn and FeedbackEvent events

### Criterion 1: Audit trail columns

- [ ] `GET /audit` returns a JSON payload with an `items` array where each item has `timestamp`, `event_type`, `session_id`, `trace_id`, `turn_id`, and `event` keys.
- [ ] `timestamp` is the `occurred_at` value from the contract log record.
- [ ] `event_type` is the `event_key` (`"agent_turn"` or `"feedback_event"`).
- [ ] `session_id` is the `conversation_id` from the event (empty string when absent, e.g. feedback_event without conversation_id).
- [ ] `trace_id` is resolved from the turn's execution_trace or agent_result metadata (empty string when no trace_id is found).
- [ ] The `/audit` web page renders a `<table>` with column headers: Timestamp, Event Type, Session ID, Trace ID.

### Criterion 2: Reverse-chronological ordering

- [ ] `list_audit_events()` returns items sorted by `occurred_at` descending, then `seq` descending (newest first).
- [ ] A test with records at timestamps T1 < T2 < T3 asserts the order T3, T2, T1 in the response.
- [ ] The web page table renders rows in reverse-chronological order.

### Criterion 3: Cursor pagination

- [ ] `GET /audit` response includes `next_cursor` (base64url-encoded opaque string) and `has_more` (bool).
- [ ] `GET /audit?limit=10` with 60 records returns 10 items and `has_more=True`.
- [ ] `GET /audit?cursor={next_cursor}&limit=10` returns the next 10 items (no overlap with the first page).
- [ ] `limit` is clamped to `[1, max_result_limit]` via `clamp_limit`; `max_result_limit` is resolved from `CONVERSATION_READ_VIEW_MAX_LIMIT` env var (default 100).
- [ ] An invalid cursor is treated as "no cursor" (start from beginning), not an error — matches `decode_cursor` behavior.
- [ ] The web page renders a "Next page" link with the `cursor` query param when `has_more=True`.

### Criterion 4: Event-type filter

- [ ] `GET /audit?event_type=agent_turn` returns only `agent_turn` items.
- [ ] `GET /audit?event_type=feedback_event` returns only `feedback_event` items.
- [ ] `GET /audit` (no event_type) returns both agent_turn and feedback_event items.
- [ ] `GET /audit?event_type=bogus` returns HTTP 400 with `error.code = "invalid_event_type"`.
- [ ] The web page renders an event-type `<select>` dropdown with options: All events, AgentTurn, FeedbackEvent.
- [ ] The dropdown preserves the current selection on page render (selected attribute set from query param).

### Criterion 5: Audit event types

- [ ] Only `agent_turn` and `feedback_event` records appear in the audit trail — `route_decision`, `execution_trace`, `agent_result` records are not listed as top-level audit items.
- [ ] A test with 2 agent_turn + 1 feedback_event + 1 route_decision records asserts `count == 3` (route_decision excluded).

---

## OBS-08: Trace reconstruction by trace_id

### Criterion 6: Click trace_id to see full trace

- [ ] `GET /audit/<trace_id>` returns the full trace reconstruction (all events sharing that trace_id) in occurrence order.
- [ ] The response uses the existing `ContractLogReadModel.get_trace_reconstruction` primitive — no reimplementation of trace logic.
- [ ] The response includes `trace_id`, `turn_id`, `task_id`, `conversation_id`, `events` (ordered list), and `metadata` with `event_count` and `reconstruction_complete`.
- [ ] `GET /audit/nonexistent` (trace_id not found) returns HTTP 404 with `error.code = "not_found"`.
- [ ] The web page trace_id cell renders as `<a href="/audit/{trace_id}">{trace_id}</a>` when trace_id is non-empty; `—` when empty.
- [ ] The `/audit/<trace_id>` web page renders an ordered list of events with event_key, occurred_at, seq, and allowlisted fields.

### Criterion 7: Field allowlist displays refs (not resolved secrets)

- [ ] The trace reconstruction response applies `TRACE_FIELD_ALLOWLIST` — only whitelisted fields are retained in each event dict.
- [ ] Allowlisted fields include: `event_key`, `occurred_at`, `seq`, `turn_id`, `conversation_id`, `trace_id`, `channel`, `user_id`, `received_at`, `route_decision_id`, `primary_skill`, `mode`, `status`, `started_at`, `ended_at`, `duration_ms`, `feedback_action`, `action`, `feedback_target`, `raw_payload_ref`, `skill_candidate`, `related_skill`, `related_route_decision`, `created_at`.
- [ ] Unknown fields (e.g. `unknown_field`) are dropped from the trace event output.
- [ ] Refs (e.g. `raw_payload_ref: "ref://..."`) are retained and displayed as text.
- [ ] Resolved secrets (e.g. `raw_payload`) are never present — `scrub_contract_payload` rejects them with `ValueError` before the allowlist is applied.
- [ ] A test verifies that a trace event with `raw_payload_ref` retains it in the output.
- [ ] A test verifies that a trace event with `unknown_field` drops it from the output.

### Criterion 8: scrub_contract_payload on every value

- [ ] `scrub_contract_payload` is called on every audit event item before inclusion in the list.
- [ ] `scrub_contract_payload` is called on the full trace reconstruction before the field allowlist is applied.
- [ ] If `scrub_contract_payload` raises `ValueError` (forbidden key found) on an audit event, that event is excluded from the list (fail-closed — not included, not crashed).
- [ ] Forbidden keys include all keys in `ALL_FORBIDDEN_KEYS`: `raw_payload`, `case_facts`, `customer_document_text`, `document_text`, `full_text`, `payload_text`, `raw_text`, `prompt_content`, `completion_text`, `function_call_result`, `tool_output`.
- [ ] A test verifies that an audit event containing `raw_payload` is excluded from the list.
- [ ] A test verifies that a trace reconstruction containing a forbidden key is rejected (scrub fails closed).

---

## RBAC and Feature Flag Validation

### Criterion 9: RBAC matrix entry

- [ ] `PERMISSIONS_MATRIX` in `packages/rbac/src/rbac/matrix.py` includes `"/audit": frozenset({Role.ADMIN, Role.OPERATOR})`.
- [ ] `ROUTE_PREFIXES` in `services/admin-console-api/src/admin_console_api/routes.py` includes `"/audit"`.
- [ ] The RBAC CI scan (`scripts/scan_rbac_annotations.py`) passes with exit code 0.
- [ ] ADMIN role token → 200 on `GET /audit` and `GET /audit/<trace_id>`.
- [ ] OPERATOR role token → 200 on `GET /audit` and `GET /audit/<trace_id>`.
- [ ] LAWYER role token → 403 on `GET /audit`.
- [ ] VIEWER role token → 403 on `GET /audit`.
- [ ] No token → 401 on `GET /audit` (when RBAC is enabled).
- [ ] `admin_api_enabled=False` → 503 on `GET /audit`.

### Criterion 10: RBAC guard pipeline

- [ ] `/audit` goes through the full `_authenticate_admin` pipeline in `api.py`: feature flag → auth header → RBAC `resolve_identity` → `RbacGuard.check` → tenant guard.
- [ ] The admin-web-ui `/audit` route goes through the web UI's own RBAC pipeline: feature flag → `resolve_identity` → `RbacGuard.check(identity.role, _guard_path("/audit"))`.
- [ ] `_guard_path("/audit")` returns `"/audit"` (not `/config` or `/sessions`).
- [ ] `_guard_path("/audit/trace-001")` returns `"/audit"`.

---

## Web UI Validation

### Criterion 11: SSR with html.escape

- [ ] All dynamic content in the `/audit` and `/audit/<trace_id>` HTML pages is HTML-escaped via `html.escape()` or the local `_esc()` helper.
- [ ] A test with `<script>alert(1)</script>` in `conversation_id` asserts the HTML contains `&lt;script&gt;` not `<script>`.
- [ ] A test with `<script>` in a trace event field value asserts the HTML contains `&lt;script&gt;`.
- [ ] The CSP header on `/audit` responses is `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`.
- [ ] No inline `<script>` tags are present in the `/audit` or `/audit/<trace_id>` HTML output.

### Criterion 12: Navigation

- [ ] The `/audit` page includes a nav link `<a href="/audit">Audit Trail</a>` in the navigation header.
- [ ] The `/audit` page is linked from the dashboard index page sections list.
- [ ] The `/audit/<trace_id>` page includes a "Back to Audit Trail" link to `/audit`.
- [ ] The nav link appears in all page templates that share the nav (dashboard, logs, audit).

### Criterion 13: GET-only

- [ ] `POST /audit` returns 405 (method not allowed).
- [ ] `PUT /audit` returns 405.
- [ ] The web UI `_handle_audit` returns 405 for non-GET methods.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 83-01-01 | 01 | 1 | OBS-07 | T-83-01 | scrub_contract_payload fail-closed on forbidden keys in audit list | unit | `python -m unittest conversation_read_view.tests.test_audit -v` | ❌ W0 | ⬜ pending |
| 83-02-01 | 01 | 1 | OBS-07 | T-83-02 | RBAC /audit ADMIN/OPERATOR only; invalid event_type → 400 | unit | `python -m unittest services.admin_console_api.tests.test_audit -v` | ❌ W0 | ⬜ pending |
| 83-03-01 | 01 | 1 | OBS-08 | T-83-03 | Field allowlist drops unknown fields; html.escape on all values | unit | `python -m unittest services.admin_web_ui.tests.test_dashboard_audit -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/conversation-read-view/tests/test_audit.py` — stubs for OBS-07, OBS-08
- [ ] `services/admin-console-api/tests/test_audit.py` — stubs for OBS-07 RBAC
- [ ] `services/admin-web-ui/tests/test_dashboard_audit.py` — stubs for OBS-08 web UI

*Existing unittest infrastructure covers all phase requirements — no new framework needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Trace_id click navigation in browser | OBS-08 | Requires browser interaction | Open `/audit` in browser, click a trace_id link, confirm `/audit/<trace_id>` renders the trace reconstruction page |
| CSP header inspection in browser | OBS-08 | Requires browser DevTools | Open DevTools Network tab, load `/audit`, confirm CSP header is present and no inline script violations |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
