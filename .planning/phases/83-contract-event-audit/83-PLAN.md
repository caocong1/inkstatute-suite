---
phase: 83-contract-event-audit
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/conversation-read-view/src/conversation_read_view/audit.py
  - services/conversation-read-view/src/conversation_read_view/read_model.py
  - services/conversation-read-view/src/conversation_read_view/__init__.py
  - services/admin-console-api/src/admin_console_api/audit.py
  - services/admin-console-api/src/admin_console_api/api.py
  - services/admin-console-api/src/admin_console_api/server.py
  - services/admin-console-api/src/admin_console_api/routes.py
  - services/admin-web-ui/src/admin_web_ui/audit.py
  - services/admin-web-ui/src/admin_web_ui/server.py
  - services/admin-web-ui/src/admin_web_ui/api_client.py
  - services/admin-web-ui/src/admin_web_ui/__main__.py
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - services/admin-web-ui/src/admin_web_ui/logs.py
  - packages/rbac/src/rbac/matrix.py
  - services/conversation-read-view/tests/test_audit.py
  - services/admin-console-api/tests/test_audit.py
  - services/admin-web-ui/tests/test_dashboard_audit.py
autonomous: true
requirements:
  - OBS-07
  - OBS-08
user_setup: []

must_haves:
  truths:
    - "ContractLogReadModel.list_audit_events(event_type=None, tenant_filter=None) returns (sort_key, occurred_at, item) tuples for agent_turn and feedback_event records in reverse-chronological order (occurred_at descending, then seq descending); event_type filter accepts 'agent_turn', 'feedback_event', or None (both)"
    - "Each audit event item is a dict with columns: timestamp (occurred_at), event_type (event_key), session_id (conversation_id from the event), trace_id (resolved from execution_trace/agent_result metadata or empty string), turn_id, and a scrubbed event payload"
    - "Every audit event item passes through scrub_contract_payload before inclusion; forbidden keys raise ValueError and the event is excluded (fail-closed) rather than leaking"
    - "handle_audit_get in conversation_read_view/audit.py dispatches GET /audit (paginated list) and GET /audit/<trace_id> (trace reconstruction) using the existing ContractLogReadModel.get_trace_reconstruction primitive"
    - "GET /audit uses cursor pagination via slice_page/encode_cursor/decode_cursor/clamp_limit from conversation_read_view.pagination; response includes items, count, next_cursor, has_more, and metadata with limit, max_result_limit, event_type filter, and admin_api/read_only flags"
    - "GET /audit/<trace_id> returns the trace reconstruction dict from get_trace_reconstruction with a field allowlist applied — only whitelisted top-level and per-event fields are retained; refs (e.g. raw_payload_ref) are kept, resolved secrets (e.g. raw_payload) are never present because scrub_contract_payload already rejects them"
    - "The field allowlist for trace events includes: event_key, occurred_at, seq, turn_id, conversation_id, trace_id, channel, user_id, received_at, route_decision_id, primary_skill, mode, status, started_at, ended_at, duration_ms, feedback_action, feedback_target, raw_payload_ref, skill_candidate, related_skill, related_route_decision, and metadata.trace_id; unknown fields are dropped"
    - "handle_audit in admin_console_api/audit.py gates on admin_api_enabled, validates event_type query param (agent_turn/feedback_event or absent), validates cursor/limit, and delegates to handle_audit_get with tenant_filter"
    - "RBAC matrix entry /audit allows ADMIN and OPERATOR roles; lawyer/viewer denied 403; ROUTE_PREFIXES includes /audit so the RBAC CI scan passes"
    - "The /audit web page renders a table with columns Timestamp, Event Type, Session ID, Trace ID; each trace_id is a clickable link to /audit/<trace_id>; an event-type filter dropdown and cursor pagination (Next/Prev links) are present"
    - "The /audit/<trace_id> web page renders the full trace reconstruction as an ordered list of events with the field allowlist applied; every value is HTML-escaped via html.escape; refs are shown as text (never resolved)"
    - "All dynamic content in the /audit and /audit/<trace_id> web pages is HTML-escaped; CSP header is set on every response; no inline JavaScript"
    - "_guard_path maps /audit and /audit/<trace_id> to the /audit RBAC prefix; _SECTION_MAP includes /audit mapping to the audit section"
  artifacts:
    - "conversation_read_view.read_model.ContractLogReadModel.list_audit_events method"
    - "conversation_read_view.audit.handle_audit_get function"
    - "conversation_read_view.audit.AUDIT_EVENT_TYPES constant"
    - "conversation_read_view.audit.TRACE_FIELD_ALLOWLIST constant"
    - "conversation_read_view.audit._apply_trace_field_allowlist function"
    - "admin_console_api.audit.handle_audit function"
    - "admin_console_api.api.handle_admin_get /audit route"
    - "admin_console_api.routes.ROUTE_PREFIXES /audit entry"
    - "rbac.matrix.PERMISSIONS_MATRIX /audit entry"
    - "admin_web_ui.audit.render_audit_page function"
    - "admin_web_ui.audit.render_trace_page function"
    - "admin_web_ui.server.handle_admin_web_ui_request /audit route and _SECTION_MAP entry"
    - "admin_web_ui.server._handle_audit function"
    - "admin_web_ui.server._guard_path /audit mapping"
    - "admin_web_ui.api_client.AdminApiClient.proxy read_model pass-through (already present)"
    - "admin_web_ui.dashboard nav_items /audit entry and title_map audit entry"
    - "admin_web_ui.logs nav_items /audit entry (shared nav)"
    - "test_audit.py, test_audit.py (admin-console-api), test_dashboard_audit.py"
  key_links:
    - "list_audit_events is called by conversation_read_view.audit.handle_audit_get for GET /audit"
    - "get_trace_reconstruction is called by handle_audit_get for GET /audit/<trace_id> — existing primitive reused, not reimplemented"
    - "handle_admin_get routes /audit and /audit/<trace_id> to admin_console_api.audit.handle_audit and passes read_model from server instance"
    - "admin-web-ui proxy passes read_model to handle_admin_get via AdminApiClient.proxy (read_model already wired)"
    - "admin_web_ui.audit.render_audit_page renders the handle_audit JSON response as an escaped HTML table with pagination links and event-type filter"
    - "admin_web_ui.audit.render_trace_page renders the trace reconstruction JSON as an escaped HTML event list with allowlisted fields"
    - "scrub_contract_payload is called on every audit event and trace event before inclusion"
---

<objective>
Add a `/audit` endpoint and web page to the admin console that lets operators browse AgentTurn and FeedbackEvent contract events in a paginated, reverse-chronological audit trail with timestamp, event type, session_id, and trace_id columns. Operators can click a trace_id to see the full trace reconstruction (all events sharing that trace_id) using the existing `ContractLogReadModel.get_trace_reconstruction` primitive. A field allowlist displays refs (not resolved secrets) and every value passes through `scrub_contract_payload` / `html.escape`.

Purpose: Give operators a contract-event-level audit trail for debugging and compliance review, with full trace reconstruction and privacy-safe field display.

Output: A working `list_audit_events` method, `handle_audit_get` pure handler, `/audit` API endpoint, `/audit` and `/audit/<trace_id>` web pages, RBAC matrix entry, and automated tests.
</objective>

<execution_context>
@$HOME/.codeium/windsurf/gsd-core/workflows/execute-plan.md
@$HOME/.codeium/windsurf/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/83-contract-event-audit/83-CONTEXT.md
@services/conversation-read-view/src/conversation_read_view/read_model.py
@services/conversation-read-view/src/conversation_read_view/api.py
@services/conversation-read-view/src/conversation_read_view/pagination.py
@services/conversation-read-view/src/conversation_read_view/privacy.py
@services/conversation-read-view/src/conversation_read_view/__init__.py
@services/conversation-read-view/tests/test_trace_reconstruction.py
@services/admin-console-api/src/admin_console_api/api.py
@services/admin-console-api/src/admin_console_api/server.py
@services/admin-console-api/src/admin_console_api/routes.py
@services/admin-console-api/src/admin_console_api/reports.py
@services/admin-console-api/src/admin_console_api/logs.py
@services/admin-console-api/src/admin_console_api/views.py
@services/admin-web-ui/src/admin_web_ui/server.py
@services/admin-web-ui/src/admin_web_ui/dashboard.py
@services/admin-web-ui/src/admin_web_ui/logs.py
@services/admin-web-ui/src/admin_web_ui/api_client.py
@services/admin-web-ui/src/admin_web_ui/__main__.py
@packages/rbac/src/rbac/matrix.py
@packages/rbac/src/rbac/guard.py
@packages/platform-runtime/src/platform_runtime/privacy_keys.py
@packages/platform-contract/src/platform_contract/events.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit trail listing + trace reconstruction handler in conversation-read-view</name>
  <files>
    services/conversation-read-view/src/conversation_read_view/read_model.py
    services/conversation-read-view/src/conversation_read_view/audit.py
    services/conversation-read-view/src/conversation_read_view/__init__.py
    services/conversation-read-view/tests/test_audit.py
  </files>
  <read_first>
    services/conversation-read-view/src/conversation_read_view/read_model.py
    services/conversation-read-view/src/conversation_read_view/api.py
    services/conversation-read-view/src/conversation_read_view/pagination.py
    services/conversation-read-view/src/conversation_read_view/privacy.py
    services/conversation-read-view/src/conversation_read_view/__init__.py
    services/conversation-read-view/tests/test_trace_reconstruction.py
    packages/platform-runtime/src/platform_runtime/privacy_keys.py
    packages/platform-contract/src/platform_contract/events.py
  </read_first>
  <action>
    ### Modify `services/conversation-read-view/src/conversation_read_view/read_model.py`

    Add a `list_audit_events` method to `ContractLogReadModel`:

    ```python
    def list_audit_events(
        self,
        *,
        event_type: str | None = None,
        tenant_filter: Any = None,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Return AgentTurn and FeedbackEvent records as ``(sort_key, occurred_at, item)`` tuples.

        Sorted reverse-chronologically (occurred_at descending, then seq descending).
        ``event_type`` filters to ``"agent_turn"`` or ``"feedback_event"``; ``None``
        returns both. ``tenant_filter`` is applied by checking ``record.event.get("tenant_id")``
        when active. Each item dict contains: ``timestamp``, ``event_type``,
        ``session_id``, ``trace_id``, ``turn_id``, and ``event`` (scrubbed payload).
        """
    ```

    Implementation details:
    - Iterate over `self._trace_events` values (which are lists of `_Record`) — but `_trace_events` only contains records that have a resolved trace_id. Instead, to capture ALL agent_turn and feedback_event records (including those without a trace_id), iterate over the normalized records stored during `from_records`. **Approach:** store the full normalized record list on the model. Add `self._all_records: list[_Record]` in `__init__` (defaulting to `[]`) and populate it in `from_records` from the `normalized` list before returning. This is a minimal addition — the records are already materialized.
    - For each record in `self._all_records`:
      - Skip if `record.event_key` not in `{"agent_turn", "feedback_event"}`.
      - If `event_type` is not None, skip if `record.event_key != event_type`.
      - If `tenant_filter` is active, skip if `record.event.get("tenant_id")` does not match.
      - Extract `conversation_id` from `record.event.get("conversation_id")` (for agent_turn) or from the feedback event's associated turn (feedback_event records have `turn_id`; resolve `conversation_id` via `trace_id_by_turn` or look up the turn's conversation). For feedback_event, `conversation_id` may be absent — use `""` as fallback.
      - Extract `trace_id`: for agent_turn, resolve via `self._turn_to_trace.get(turn_id)` (the turn-to-trace map already built in `from_records`). For feedback_event, resolve the turn_id's trace the same way. If no trace_id is found, use `""`.
      - Build the item dict: `{"timestamp": record.occurred_at, "event_type": record.event_key, "session_id": conversation_id, "trace_id": trace_id, "turn_id": turn_id, "event": scrubbed_event}`.
      - Call `scrub_contract_payload(record.event)` for the `event` field. If it raises `ValueError` (forbidden key), skip this record (fail-closed — do not include it in the audit trail).
    - Sort key for reverse-chronological: use `(record.occurred_at, record.seq)` but in descending order. Since `slice_page` expects a forward-sorted list, build the list in reverse order: sort by `(-occurred_at` is not possible with strings). Instead, sort the list in descending occurred_at+seq order, then use a **reverse-aware slice_page** or simply reverse the list and use a dedicated cursor. **Decision:** Use a simple approach — sort descending, then `slice_page` works on the descending list as-is (it slices forward from the cursor in list order). The cursor encodes `(sort_key, occurred_at)` where `sort_key` is a composite of `occurred_at + seq` to ensure uniqueness. Use `sort_key = f"{record.occurred_at}|{record.seq}"`.
    - Return `list[tuple[str, str, dict]]` — `(sort_key, occurred_at, item)`.

    Update `__init__` to accept `all_records: list | None = None` and store `self._all_records = list(all_records) if all_records else []`.

    Update `from_records` to pass `all_records=normalized` to the constructor.

    ### Create `services/conversation-read-view/src/conversation_read_view/audit.py`

    ```python
    """Pure GET handlers for the contract event audit trail (Phase 83)."""

    from __future__ import annotations

    from typing import Any, Mapping
    from urllib.parse import parse_qs

    from .pagination import clamp_limit, resolve_max_result_limit, slice_page
    from .privacy import scrub_contract_payload

    AUDIT_EVENT_TYPES = ("agent_turn", "feedback_event")

    # Field allowlist for trace reconstruction display.
    # Only these fields are retained in each event dict; all others are dropped.
    # Refs (e.g. raw_payload_ref) are kept; resolved secrets are never present
    # because scrub_contract_payload already rejects forbidden keys.
    TRACE_FIELD_ALLOWLIST = frozenset({
        "event_key",
        "occurred_at",
        "seq",
        "turn_id",
        "conversation_id",
        "trace_id",
        "channel",
        "user_id",
        "received_at",
        "route_decision_id",
        "primary_skill",
        "mode",
        "status",
        "started_at",
        "ended_at",
        "duration_ms",
        "feedback_action",
        "action",
        "feedback_target",
        "raw_payload_ref",
        "skill_candidate",
        "related_skill",
        "related_route_decision",
        "created_at",
    })
    ```

    Define `handle_audit_get(path, query, read_model, tenant_filter=None)`:
    - Split path/query via the same `_split_path_query` pattern used in `api.py` (copy the helper or import it).
    - `GET /audit` (no rest after `/audit`):
      - Parse `event_type` from query (must be in `AUDIT_EVENT_TYPES` or absent). Invalid → 400.
      - Parse `cursor` and `limit` from query.
      - Call `read_model.list_audit_events(event_type=event_type, tenant_filter=tenant_filter)`.
      - Use `resolve_max_result_limit()`, `clamp_limit(query.get("limit"), max_limit)`, `slice_page(items, cursor, limit)`.
      - Return 200 with `{"items": page, "count": len(page), "next_cursor": next_cursor, "has_more": has_more, "metadata": {...}}`.
    - `GET /audit/<trace_id>` (rest is the trace_id):
      - Call `read_model.get_trace_reconstruction(trace_id)`.
      - If None → 404.
      - Apply `_apply_trace_field_allowlist` to each event in `reconstruction["events"]`.
      - Scrub the full reconstruction via `scrub_contract_payload`.
      - Return 200 with the allowlisted, scrubbed reconstruction.

    Define `_apply_trace_field_allowlist(events: list[dict]) -> list[dict]`:
    - For each event entry `{"event_key": ..., "occurred_at": ..., "seq": ..., "event": {...}}`:
      - Keep `event_key`, `occurred_at`, `seq` at the entry level.
      - Filter the `event` dict to only keys in `TRACE_FIELD_ALLOWLIST`.
      - If `event` contains nested `metadata` dict, keep only `trace_id` from metadata.
    - Return the filtered list.

    ### Update `services/conversation-read-view/src/conversation_read_view/__init__.py`

    Add to imports and `__all__`:
    - `from .audit import handle_audit_get, AUDIT_EVENT_TYPES, TRACE_FIELD_ALLOWLIST`
    - Add `"handle_audit_get"`, `"AUDIT_EVENT_TYPES"`, `"TRACE_FIELD_ALLOWLIST"` to `__all__`.

    ### Tests: `services/conversation-read-view/tests/test_audit.py`

    Create tests following the `test_trace_reconstruction.py` pattern (synthetic records + `build_read_model`):

    1. **test_list_audit_events_both_types:** Build a read model with 2 agent_turn + 1 feedback_event records. Call `list_audit_events()`. Assert 3 items, all with `timestamp`, `event_type`, `session_id`, `trace_id`, `turn_id`, `event` keys. Assert reverse-chronological order (newest first).
    2. **test_list_audit_events_filter_agent_turn:** Call `list_audit_events(event_type="agent_turn")`. Assert 2 items, all `event_type == "agent_turn"`.
    3. **test_list_audit_events_filter_feedback:** Call `list_audit_events(event_type="feedback_event")`. Assert 1 item.
    4. **test_list_audit_events_invalid_type:** Call `list_audit_events(event_type="unknown")` — assert it returns empty list (or the handler raises 400; the method itself returns empty for unknown types, the handler validates).
    5. **test_list_audit_events_trace_id_resolved:** Build records with execution_trace containing `trace_id="trace-001"`. Assert the agent_turn item has `trace_id == "trace-001"`.
    6. **test_list_audit_events_no_trace_id:** Build records without execution_trace. Assert `trace_id == ""`.
    7. **test_list_audit_events_scrubbed:** Build a record with a forbidden key (`raw_payload`). Assert the record is excluded from the list (fail-closed).
    8. **test_handle_audit_get_list:** Call `handle_audit_get("/audit", {}, read_model)`. Assert 200, `items`, `count`, `next_cursor`, `has_more`, `metadata`.
    9. **test_handle_audit_get_pagination:** Create 60 records, call with `limit=10`, assert 10 items and `has_more=True`. Call with `cursor` from first response, assert next 10 items.
    10. **test_handle_audit_get_invalid_event_type:** Call `handle_audit_get("/audit", {"event_type": "bogus"}, read_model)`. Assert 400.
    11. **test_handle_audit_get_trace_reconstruction:** Call `handle_audit_get("/audit/trace-001", {}, read_model)`. Assert 200, `trace_id`, `events` list with allowlisted fields only.
    12. **test_handle_audit_get_trace_not_found:** Call `handle_audit_get("/audit/nonexistent", {}, read_model)`. Assert 404.
    13. **test_trace_field_allowlist_drops_unknown:** Build a trace with an event containing `{"unknown_field": "x", "turn_id": "t1"}`. Assert `unknown_field` is not in the allowlisted output, `turn_id` is.
    14. **test_trace_field_allowlist_keeps_refs:** Build a trace with `raw_payload_ref: "ref://..."`. Assert `raw_payload_ref` is retained in the output.
    15. **test_handle_audit_get_tenant_filter:** Build records with `tenant_id="t1"` and `tenant_id="t2"`. Call with `tenant_filter="t1"`. Assert only t1 records returned.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src python -m unittest conversation_read_view.tests.test_audit -v</automated>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src python -m unittest conversation_read_view.tests.test_trace_reconstruction -v</automated>
    <manual>Confirm that list_audit_events returns reverse-chronological order and that scrub_contract_payload excludes records with forbidden keys (fail-closed).</manual>
  </verify>
</task>

<task type="auto">
  <name>Task 2: Admin Console API /audit endpoint + RBAC wiring</name>
  <files>
    services/admin-console-api/src/admin_console_api/audit.py
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/server.py
    services/admin-console-api/src/admin_console_api/routes.py
    packages/rbac/src/rbac/matrix.py
    services/admin-console-api/tests/test_audit.py
  </files>
  <read_first>
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/server.py
    services/admin-console-api/src/admin_console_api/routes.py
    services/admin-console-api/src/admin_console_api/reports.py
    services/admin-console-api/src/admin_console_api/logs.py
    services/admin-console-api/src/admin_console_api/views.py
    packages/rbac/src/rbac/matrix.py
    services/conversation-read-view/src/conversation_read_view/audit.py
  </read_first>
  <action>
    ### Create `services/admin-console-api/src/admin_console_api/audit.py`

    ```python
    """Admin API handler for contract event audit trail (Phase 83)."""

    from __future__ import annotations

    from typing import Any, Mapping

    from conversation_read_view.audit import AUDIT_EVENT_TYPES, handle_audit_get


    def handle_audit(
        path: str,
        query: Mapping[str, str],
        read_model: Any,
        feature_flags: Any,
        tenant_filter: Any = None,
    ) -> tuple[int, dict[str, Any]]:
        """Handle ``GET /audit`` (paginated audit trail) and ``GET /audit/<trace_id>``.

        ``GET /audit`` returns AgentTurn and FeedbackEvent records in
        reverse-chronological order with cursor pagination and event-type filter.
        ``GET /audit/<trace_id>`` returns the full trace reconstruction with a
        field allowlist applied.
        """
    ```

    Implementation:
    - Gate on `feature_flags.admin_api_enabled` → 503 if disabled.
    - If `read_model is None` → 503 `audit_unavailable`.
    - Validate `event_type` query param if present: must be in `AUDIT_EVENT_TYPES`. Invalid → 400 `invalid_event_type`.
    - Delegate to `handle_audit_get(path, query, read_model, tenant_filter=tenant_filter)`.
    - Merge `admin_api: True, read_only: True` into the response metadata.
    - Return the `(status, body)` tuple from `handle_audit_get`.

    ### Modify `services/admin-console-api/src/admin_console_api/api.py`

    1. Add import: `from .audit import handle_audit`.

    2. In `handle_admin_get`, after the `/logs` block and before the `/config` block, add:
       ```python
       if route_path == "/audit" or route_path.startswith("/audit/"):
           return handle_audit(
               route_path,
               route_query,
               read_model=read_model,
               feature_flags=feature_flags,
               tenant_filter=tenant_filter,
           )
       ```
       `read_model` is already a parameter of `handle_admin_get` — no signature change needed.

    ### Modify `services/admin-console-api/src/admin_console_api/routes.py`

    Add `"/audit"` to `ROUTE_PREFIXES`:
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
        "/audit",
    )
    ```

    ### Modify `packages/rbac/src/rbac/matrix.py`

    Add to `PERMISSIONS_MATRIX`:
    ```python
    "/audit": frozenset({Role.ADMIN, Role.OPERATOR}),
    ```
    Place it after the `"/logs"` entry.

    ### Modify `services/admin-console-api/src/admin_console_api/server.py`

    No changes needed — `read_model` is already wired on the server instance and passed to `handle_admin_get`. The `/audit` route uses `read_model` which is already constructed in `create_server`.

    ### Tests: `services/admin-console-api/tests/test_audit.py`

    Create tests following the `test_logs.py` / `test_reports.py` pattern:

    1. **test_audit_list_admin:** Call `handle_admin_get("/audit", {}, headers=ADMIN_TOKEN, read_model=rm, ...)`. Assert 200, `items`, `count`, `next_cursor`, `has_more`, `metadata.admin_api=True`.
    2. **test_audit_list_event_type_filter:** Call with `query={"event_type": "agent_turn"}`. Assert all items have `event_type == "agent_turn"`.
    3. **test_audit_list_invalid_event_type:** Call with `query={"event_type": "bogus"}`. Assert 400, `error.code == "invalid_event_type"`.
    4. **test_audit_list_pagination:** Create 60 records, call with `query={"limit": "10"}`. Assert 10 items, `has_more=True`. Follow `next_cursor`, assert next 10.
    5. **test_audit_trace_reconstruction:** Call `handle_admin_get("/audit/trace-001", {}, ...)`. Assert 200, `trace_id`, `events` with allowlisted fields.
    6. **test_audit_trace_not_found:** Call `handle_admin_get("/audit/nonexistent", {}, ...)`. Assert 404.
    7. **test_audit_disabled:** Set `admin_api_enabled=False`. Assert 503.
    8. **test_audit_rbac_admin_ok:** ADMIN token → 200.
    9. **test_audit_rbac_operator_ok:** OPERATOR token → 200.
    10. **test_audit_rbac_lawyer_denied:** LAWYER token → 403.
    11. **test_audit_rbac_viewer_denied:** VIEWER token → 403.
    12. **test_audit_no_token:** No auth header (RBAC enabled) → 401.
    13. **test_audit_privacy_scrubbed:** Build a record with `raw_payload` forbidden key. Assert it is excluded from the audit list (not present in items).
    14. **test_audit_trace_allowlist:** Build a trace with `unknown_field`. Assert it is dropped from the trace reconstruction response.
    15. **test_audit_read_model_none:** Pass `read_model=None`. Assert 503 `audit_unavailable`.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src python -m unittest services.admin_console_api.tests.test_audit -v</automated>
    <automated>PYTHONPATH=packages/rbac/src:services/admin-console-api/src python3 scripts/scan_rbac_annotations.py</automated>
    <manual>Confirm that the RBAC CI scan passes with exit code 0 after adding /audit to ROUTE_PREFIXES and PERMISSIONS_MATRIX.</manual>
  </verify>
</task>

<task type="auto">
  <name>Task 3: Admin Web UI /audit and /audit/<trace_id> pages</name>
  <files>
    services/admin-web-ui/src/admin_web_ui/audit.py
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/api_client.py
    services/admin-web-ui/src/admin_web_ui/__main__.py
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/logs.py
    services/admin-web-ui/tests/test_dashboard_audit.py
  </files>
  <read_first>
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/logs.py
    services/admin-web-ui/src/admin_web_ui/api_client.py
    services/admin-web-ui/src/admin_web_ui/__main__.py
    services/admin-web-ui/src/admin_web_ui/boundary.py
    services/admin-console-api/src/admin_console_api/audit.py
    services/conversation-read-view/src/conversation_read_view/audit.py
  </read_first>
  <action>
    ### Create `services/admin-web-ui/src/admin_web_ui/audit.py`

    ```python
    """Contract event audit UI pages for the admin web UI (Phase 83).

    Renders a paginated audit trail table (AgentTurn + FeedbackEvent) with
    timestamp, event type, session_id, and trace_id columns. Trace IDs are
    clickable links to /audit/<trace_id> for full trace reconstruction.
    All dynamic content is HTML-escaped.
    """

    from __future__ import annotations

    from typing import Any, Mapping

    from rbac import Identity

    from .boundary import AdminUiBoundary
    from .dashboard import _page_template, _esc

    __all__ = ["render_audit_page", "render_trace_page"]

    _EVENT_TYPE_OPTIONS = [("", "All events"), ("agent_turn", "AgentTurn"), ("feedback_event", "FeedbackEvent")]
    ```

    Define `render_audit_page(api_data, identity=None, boundary=None, query_params=None) -> str`:
    - If `api_data` contains `error`, render an error block (same pattern as `logs.py`).
    - Render an event-type filter `<select>` dropdown with `_EVENT_TYPE_OPTIONS`, preserving the current selection from `query_params`.
    - Render a `<table>` with columns: Timestamp, Event Type, Session ID, Trace ID.
    - For each item in `api_data["items"]`:
      - Render a `<tr>` with escaped values.
      - The Trace ID cell: if `trace_id` is non-empty, render as `<a href="/audit/{esc(trace_id)}">{esc(trace_id)}</a>`; else render `—`.
    - Render pagination links: if `has_more`, a "Next" link with `?cursor={next_cursor}&event_type={current}&limit={limit}`. If `cursor` is present in query_params, a "Previous" link (cursor-based; Previous is best-effort — since cursor pagination is forward-only, Previous can link to `/audit` without cursor or use a stored previous cursor; **Decision:** provide a "Back to audit trail" link to `/audit` without cursor, and a "Next page" link with the cursor).
    - Use `_page_template("Contract Event Audit", body, identity)` for the full page.

    Define `render_trace_page(api_data, identity=None, boundary=None, trace_id=None) -> str`:
    - If `api_data` contains `error`, render an error block.
    - Render a header: "Trace Reconstruction: {esc(trace_id)}".
    - Render metadata: `event_count`, `reconstruction_complete`.
    - Render an ordered list `<ol>` of events, each as a `<li>` with:
      - Event key, occurred_at, seq.
      - A `<dl>` (definition list) of allowlisted fields from the `event` dict (key-value pairs, all escaped).
    - A "Back to Audit Trail" link to `/audit`.
    - Use `_page_template` for the full page.

    ### Modify `services/admin-web-ui/src/admin_web_ui/server.py`

    1. Add import: `from .audit import render_audit_page, render_trace_page`.

    2. Add to `_SECTION_MAP`:
       ```python
       "/audit": "audit",
       ```

    3. Add a constant: `_AUDIT_PATH = "/audit"`.

    4. In `_guard_path`, add:
       ```python
       if route_path == _AUDIT_PATH or route_path.startswith("/audit/"):
           return "/audit"
       ```

    5. In the route resolution section (after the `/logs` subpath check), add:
       ```python
       if section is None and (route_path == _AUDIT_PATH or route_path.startswith("/audit/")):
           section = "audit"
       ```

    6. In `handle_admin_web_ui_request`, after the `_handle_logs` block and before the default proxy block, add:
       ```python
       if route_path == _AUDIT_PATH or route_path.startswith("/audit/"):
           return _handle_audit(
               http_method=http_method,
               identity=identity,
               auth_header=auth_header,
               feature_flags=feature_flags,
               handle_admin_get=handle_admin_get,
               read_model=read_model,
               feedback_queue=feedback_queue,
               env=env,
               rbac_secret=secret,
               client=client,
               boundary=boundary,
               response_headers=response_headers,
               path=path,
           )
       ```

    7. Add `_handle_audit` function:
       ```python
       def _handle_audit(
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
           client: AdminApiClient,
           boundary: AdminUiBoundary,
           response_headers: dict[str, str],
           path: str,
       ) -> tuple[int, str, dict[str, str]]:
       ```
       - `/audit` is GET-only. If `http_method != "GET"`, return 405.
       - Parse query params from `path` (split on `?`, use `parse_qs`).
       - Build the API path: use the full `path` (preserves `/audit/<trace_id>` and query string).
       - Proxy to `handle_admin_get` via `client.proxy()` with `read_model=read_model` (already passed by default).
       - If the route is `/audit/<trace_id>` (rest after `/audit/` is non-empty), call `render_trace_page(api_data, identity=identity, boundary=boundary, trace_id=trace_id)`.
       - Else call `render_audit_page(api_data, identity=identity, boundary=boundary, query_params=parsed_query)`.
       - Return `(status, html_body, response_headers)`.

    ### Modify `services/admin-web-ui/src/admin_web_ui/api_client.py`

    No changes needed — `read_model` is already passed through `AdminApiClient.proxy()`. The `/audit` route uses `read_model` which is already a standard parameter.

    ### Modify `services/admin-web-ui/src/admin_web_ui/__main__.py`

    No changes needed — `read_model` is already wired on the server instance. The `/audit` route uses the existing `read_model` attribute.

    ### Modify `services/admin-web-ui/src/admin_web_ui/dashboard.py`

    1. In `_page_template`, add to `nav_items` (after `("/logs", "Logs")`):
       ```python
       ("/audit", "Audit Trail"),
       ```

    2. In `render_dashboard`, add to `title_map`:
       ```python
       "audit": "Contract Event Audit",
       ```

    3. In `_render_index`, add to `sections` (after the Log Viewer entry):
       ```python
       ("Contract Event Audit", "/audit", "Browse AgentTurn and FeedbackEvent contract events with trace reconstruction"),
       ```

    ### Modify `services/admin-web-ui/src/admin_web_ui/logs.py`

    In `_logs_page_template`, add to `nav_items` (after `("/logs", "Logs")`):
    ```python
    ("/audit", "Audit Trail"),
    ```

    ### Tests: `services/admin-web-ui/tests/test_dashboard_audit.py`

    Create tests following the `test_dashboard_logs.py` pattern:

    1. **test_audit_page_renders_table:** Call `handle_admin_web_ui_request("/audit", ...)`. Assert 200, HTML contains "Contract Event Audit", `<table>`, "Timestamp", "Event Type", "Session ID", "Trace ID".
    2. **test_audit_page_renders_items:** Configure a read_model with agent_turn records. Assert HTML contains the escaped session_id and trace_id values.
    3. **test_audit_page_event_type_filter:** Call with `?event_type=agent_turn`. Assert the dropdown has `agent_turn` selected.
    4. **test_audit_page_trace_id_link:** Build a record with trace_id="trace-001". Assert HTML contains `<a href="/audit/trace-001">trace-001</a>`.
    5. **test_audit_page_pagination:** Create 60 records, call with `?limit=10`. Assert "Next" link is present with cursor. Call with cursor, assert next page.
    6. **test_audit_page_html_escaped:** Build a record with `<script>` in conversation_id. Assert HTML contains `&lt;script&gt;` not `<script>`.
    7. **test_audit_page_post_returns_405:** Call with `method="POST"`. Assert 405.
    8. **test_audit_page_rbac_admin:** ADMIN token → 200.
    9. **test_audit_page_rbac_lawyer_denied:** LAWYER token → 403.
    10. **test_audit_page_nav_link:** Assert HTML contains `<a href="/audit">Audit Trail</a>` in nav.
    11. **test_trace_page_renders:** Call `handle_admin_web_ui_request("/audit/trace-001", ...)`. Assert 200, HTML contains "Trace Reconstruction", "trace-001", event list.
    12. **test_trace_page_allowlist_fields:** Build a trace with `turn_id` and `unknown_field`. Assert `turn_id` appears, `unknown_field` does not.
    13. **test_trace_page_html_escaped:** Build a trace with `<script>` in a field value. Assert escaped.
    14. **test_trace_page_back_link:** Assert HTML contains `<a href="/audit">` back link.
    15. **test_trace_page_not_found:** Call `/audit/nonexistent`. Assert 404 or error rendering.
    16. **test_trace_page_reconstruction_complete:** Build a trace with execution_trace. Assert `reconstruction_complete` indicator is shown.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_web_ui.tests.test_dashboard_audit -v</automated>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_web_ui.tests.test_main -v</automated>
    <manual>Confirm that the /audit page renders with CSP headers and all dynamic content is HTML-escaped. Confirm that trace_id links navigate to /audit/<trace_id> and the trace reconstruction page shows only allowlisted fields.</manual>
  </verify>
</task>

</tasks>

<post_conditions>
After all three tasks are complete:

1. **RBAC CI scan passes:** `PYTHONPATH=packages/rbac/src:services/admin-console-api/src python3 scripts/scan_rbac_annotations.py` exits 0.
2. **All new tests pass:** `test_audit.py` (conversation-read-view), `test_audit.py` (admin-console-api), `test_dashboard_audit.py` (admin-web-ui).
3. **Existing tests still pass:** `test_trace_reconstruction.py`, `test_read_model.py`, `test_api.py`, `test_logs.py`, `test_reports.py`, `test_server.py`, `test_routes.py`, `test_dashboard_logs.py`, `test_dashboard_reports.py` — no regressions from the `read_model.py` / `api.py` / `server.py` changes.
4. **No new dependencies:** `dependencies = []` in all `pyproject.toml` files; no new third-party imports.
5. **Privacy:** `scrub_contract_payload` is called on every audit event and trace event; forbidden keys cause fail-closed exclusion. The field allowlist drops unknown fields from trace reconstruction. No resolved secrets appear — only refs.
6. **Trace reconstruction reuses existing primitive:** `get_trace_reconstruction` is called as-is; no reimplementation of trace logic.
7. **CSP compliance:** The /audit and /audit/<trace_id> pages use only HTML-escaped content; no inline `<script>` tags; CSP header set on every response.
</post_conditions>
