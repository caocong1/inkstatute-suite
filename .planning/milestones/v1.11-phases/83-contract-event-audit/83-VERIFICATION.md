# Phase 83 Verification — Contract Event Audit

**Status:** passed

## Summary

Phase 83 adds a `/audit` endpoint and web page to the admin console for browsing
AgentTurn and FeedbackEvent contract events in a paginated, reverse-chronological
audit trail with trace reconstruction. All 3 tasks completed and verified.

## Post-Conditions

1. **RBAC CI scan passes:** `PYTHONPATH=... python3 scripts/scan_rbac_annotations.py` exits 0.
   - Output: `OK: all 9 admin API endpoints have RBAC annotations`

2. **All new tests pass:**
   - `test_audit.py` (conversation-read-view): 18 tests — OK
   - `test_audit.py` (admin-console-api): 16 tests — OK
   - `test_dashboard_audit.py` (admin-web-ui): 16 tests — OK

3. **Existing tests still pass (no regressions):**
   - `test_trace_reconstruction.py`: 13 tests — OK
   - `test_read_model.py`: 11 tests — OK
   - `test_api.py` (conversation-read-view): 7 tests — OK
   - `test_logs.py` (admin-console-api): 16 tests — OK
   - `test_reports.py` (admin-console-api): 12 tests — OK
   - `test_server.py` (admin-console-api): 4 tests — OK
   - `test_routes.py` (admin-console-api): 3 tests — OK (updated to include /logs and /audit)
   - `test_dashboard_logs.py` (admin-web-ui): 13 tests — OK
   - `test_dashboard_reports.py` (admin-web-ui): 9 tests — OK
   - `test_main.py` (admin-web-ui): 3 tests — OK

4. **No new dependencies:** All `pyproject.toml` files have `dependencies = []`.

5. **Privacy:** `scrub_contract_payload` is called on every audit event and trace
   event; forbidden keys cause fail-closed exclusion. The field allowlist drops
   unknown fields from trace reconstruction. No resolved secrets appear — only refs.

6. **Trace reconstruction reuses existing primitive:** `get_trace_reconstruction`
   is called as-is; no reimplementation of trace logic.

7. **CSP compliance:** The /audit and /audit/<trace_id> pages use only HTML-escaped
   content; no inline `<script>` tags; CSP header set on every response.

## Artifacts Created/Modified

### Task 1: conversation-read-view
- `services/conversation-read-view/src/conversation_read_view/read_model.py` — added `list_audit_events` method, `_all_records` storage
- `services/conversation-read-view/src/conversation_read_view/audit.py` — new: `handle_audit_get`, `AUDIT_EVENT_TYPES`, `TRACE_FIELD_ALLOWLIST`, `_apply_trace_field_allowlist`
- `services/conversation-read-view/src/conversation_read_view/__init__.py` — added audit exports
- `services/conversation-read-view/tests/test_audit.py` — new: 18 tests

### Task 2: admin-console-api + RBAC
- `services/admin-console-api/src/admin_console_api/audit.py` — new: `handle_audit` function
- `services/admin-console-api/src/admin_console_api/api.py` — wired `/audit` route
- `services/admin-console-api/src/admin_console_api/routes.py` — added `/audit` to `ROUTE_PREFIXES`
- `packages/rbac/src/rbac/matrix.py` — added `/audit` to `PERMISSIONS_MATRIX` (ADMIN + OPERATOR)
- `services/admin-console-api/tests/test_audit.py` — new: 16 tests
- `services/admin-console-api/tests/test_routes.py` — updated to include /logs and /audit

### Task 3: admin-web-ui
- `services/admin-web-ui/src/admin_web_ui/audit.py` — new: `render_audit_page`, `render_trace_page`
- `services/admin-web-ui/src/admin_web_ui/server.py` — wired `/audit` route, `_handle_audit`, `_guard_path`, `_SECTION_MAP`
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` — added nav link, title, index section
- `services/admin-web-ui/src/admin_web_ui/logs.py` — added audit nav link
- `services/admin-web-ui/tests/test_dashboard_audit.py` — new: 16 tests

## Commits

1. `feat(83): audit trail listing + trace reconstruction handler in conversation-read-view`
2. `feat(83): admin console API /audit endpoint + RBAC wiring`
3. `feat(83): admin web UI /audit and /audit/<trace_id> pages`
