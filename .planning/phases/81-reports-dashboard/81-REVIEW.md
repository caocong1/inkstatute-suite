---
phase: 81-reports-dashboard
status: findings
reviewed_at: 2026-07-14T00:00:00Z
---

# Phase 81 — Reports Dashboard Code Review

## Scope

Reviewed all 12 source files changed during Phase 81 plus the 4 test files:

- `services/conversation-read-view/src/conversation_read_view/reports_aggregator.py` (NEW)
- `services/conversation-read-view/src/conversation_read_view/__init__.py` (MODIFIED)
- `services/admin-console-api/src/admin_console_api/reports.py` (NEW)
- `services/admin-console-api/src/admin_console_api/api.py` (MODIFIED)
- `services/admin-console-api/src/admin_console_api/server.py` (MODIFIED)
- `services/admin-console-api/src/admin_console_api/routes.py` (MODIFIED)
- `packages/rbac/src/rbac/matrix.py` (MODIFIED)
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` (MODIFIED)
- `services/admin-web-ui/src/admin_web_ui/server.py` (MODIFIED)
- `services/admin-web-ui/src/admin_web_ui/api_client.py` (MODIFIED)
- `services/admin-web-ui/src/admin_web_ui/__main__.py` (MODIFIED)
- `.env.example` (MODIFIED)

## Summary

The reports dashboard is well-structured: bounded tail-scan aggregation, fail-closed
privacy scrubbing, RBAC matrix wiring, and consistent HTML escaping. Two MEDIUM
severity bugs were found that produce incorrect/missing user-facing behavior, plus
several LOW severity code-quality items.

---

## Findings

### MEDIUM-1 — Gate Pass Rate metric always shows 0.0% (key mismatch)

**Files:**
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` lines 441-443 (read side)
- `services/admin-console-api/src/admin_console_api/reports.py` lines 132-138 (write side)

**Description:**

The dashboard's "Gate Pass Rate" metric card reads `gates.get("gates_passed", 0)`:

```python
_metric_card("Gate Pass Rate", _rate(
    gates.get("gate_count", 0) and gates.get("gates_passed", 0) / gates.get("gate_count", 1) or 0.0
) if gates.get("gate_count") else "N/A"),
```

However, the `/reports` API response builds `gates_payload` with only `passed` (a
boolean) and `gate_count` (an int) — it does **not** include a `gates_passed` count:

```python
gates_payload: dict[str, Any] = {
    "passed": gate_summary.get("passed", False),
    "gate_count": len(gate_summary.get("gates", [])),
}
```

Because `gates_passed` is absent from the response, `gates.get("gates_passed", 0)`
always defaults to `0`. As a result, whenever `gate_count > 0` the Gate Pass Rate
always renders as `0.0%` regardless of how many gates actually passed.

For comparison, `handle_gates` in `gates.py` (lines 79-86) **does** return a
`gates_passed` count via `_count_gates(gates, 0)`. The reports endpoint omits this
field, so the dashboard can never compute a correct rate.

**Fix direction:** Either add `"gates_passed": sum(1 for g in gate_summary.get("gates", []) if g.get("exit_code") == 0)` to `gates_payload` in `reports.py`, or change the dashboard to derive the rate from the available fields. The former matches the existing `handle_gates` pattern.

**Test coverage gap:** No test asserts on the Gate Pass Rate value or on the
presence of `gates_passed` in the `/reports` response. The dashboard test
`test_reports_page_escapes_script_injection` uses `gate_count: 0` (→ "N/A"), and
the API test `test_reports_returns_200_with_expected_keys` only checks that
`body["gates"]` exists.

---

### MEDIUM-2 — Inline `onchange` handler blocked by CSP (auto-submit silently broken)

**File:** `services/admin-web-ui/src/admin_web_ui/dashboard.py` line 405

**Description:**

The reports time-range selector uses an inline event handler to auto-submit the form:

```python
f'<select id="window" name="window" onchange="this.form.submit()">\n'
```

The server sets a strict Content-Security-Policy header
(`services/admin-web-ui/src/admin_web_ui/server.py` line 77):

```python
CSP_HEADER = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
```

`script-src 'self'` does **not** include `'unsafe-inline'`, so browsers will block
inline event-handler attributes like `onchange="..."`. The auto-submit on window
selection will silently fail in any conformant browser. This is the only inline
event handler in the entire `admin_web_ui` package (all other forms use a submit
button).

The "Refresh" submit button on the same form is a working fallback, so the page is
still usable, but the intended auto-submit UX is broken.

**Fix direction:** Remove the `onchange` inline handler and rely on the existing
"Refresh" button, or move the submit logic to an external `'self'`-served script
file. Do **not** weaken the CSP by adding `'unsafe-inline'` to `script-src`.

---

### LOW-1 — Duplicated helper functions (`_load_zone`, `_parse_iso`)

**Files:**
- `services/conversation-read-view/src/conversation_read_view/reports_aggregator.py` lines 23-43, 52-62
- `services/admin-console-api/src/admin_console_api/reports.py` lines 21-31, 65-75

**Description:**

`_parse_iso` and `_load_zone` are defined identically in both modules. This violates
DRY and risks divergence. Consider extracting to a shared helper (e.g. in
`conversation_read_view` or a `datetime_utils` module) and importing from both
call sites.

---

### LOW-2 — Scrub re-assignment discards scrubbed copies (code smell)

**File:** `services/admin-console-api/src/admin_console_api/reports.py` lines 143-146

**Description:**

```python
scrubbed = scrub_contract_payload(aggregate)
scrubbed["metadata"] = aggregate["metadata"]
scrubbed["gates"] = gates_payload
```

After scrubbing the full aggregate (which already validated and deep-copied
`metadata` and `gates`), the scrubbed copies of those keys are overwritten with
references to the original unscrubbed objects. This is safe in practice because
`scrub_contract_payload` fails closed (raises `ValueError` on any forbidden key)
and the internally-constructed `metadata`/`gates_payload` contain no forbidden
keys, but the pattern is confusing and partially defeats the scrub step. Prefer
mutating `aggregate` before scrubbing so a single `scrub_contract_payload` call
produces the final output, or document why the re-assignment is intentional.

---

### LOW-3 — `scrub_contract_payload` ValueError surfaces as generic 500

**File:** `services/admin-console-api/src/admin_console_api/reports.py` line 144

**Description:**

The `scrub_contract_payload(aggregate)` call is outside the `try/except ValueError`
block that wraps `reports_aggregator.build(...)`. If scrubbing rejects a forbidden
key, the `ValueError` propagates to the server's generic `except Exception` handler
(`server.py` lines 124-132) and is returned as a `500` with `code: "internal_error"`.
Fail-closed behavior is correct, but a specific error code (e.g.
`reports_scrub_failed`) would aid operator diagnosis. Consider wrapping the scrub
call in its own `try/except ValueError` returning a `500` with a descriptive code.

---

### INFO-1 — `display_tz` stored in metadata but never applied to timestamp formatting

**File:** `services/conversation-read-view/src/conversation_read_view/reports_aggregator.py` lines 124, 282-290

**Description:**

`display_tz` is read from `INKSTATUTE_REPORT_DISPLAY_TZ` and included in the
`metadata` output, but all timestamps (`time_from`, `time_to`, `aggregated_at`) are
always formatted in UTC via `_format_iso`. The dashboard correctly notes "Values are
in UTC." The `display_tz` field is metadata-only and currently has no behavioral
effect. This is acceptable if `display_tz` is reserved for future use, but the
naming may mislead callers into expecting local-time output.

---

### INFO-2 — Reverse scanner assumes chronological order for early break

**File:** `services/conversation-read-view/src/conversation_read_view/reports_aggregator.py` line 166

**Description:**

The scanner breaks early when `occurred_at < scan_from`, assuming the JSONL contract
log is append-ordered chronologically (newest at EOF). If the log ever contains
out-of-order records, in-window entries before an older record could be missed. This
assumption is consistent with the existing `read_model` loader and is reasonable for
an append-only contract log, but it is not documented in the docstring.

---

## Items Verified Clean

- **Privacy / scrub_contract_payload usage:** `reports_aggregator.py` scrubs every
  record via `scrub_contract_payload` before appending (line 170). `reports.py`
  scrubs the final aggregate (line 144). The `test_forbidden_payload_fails_closed`
  test confirms a `raw_payload` key raises `ValueError`. No raw payload leaks.
- **RBAC wiring:** `/reports` added to both `routes.py` and `PERMISSIONS_MATRIX`
  with `{ADMIN, OPERATOR, LAWYER, VIEWER}` — consistent with other read-only views
  (`/sessions`, `/tasks`). RBAC guard and tenant scope flow through
  `_authenticate_admin` unchanged.
- **HTML escaping:** All dynamic content in `_render_reports_section` is passed
  through `_esc()` or `boundary.apply()`. The `test_reports_page_escapes_script_injection`
  test confirms `<script>` is escaped to `&lt;script&gt;`.
- **Query string preservation:** `server.py` passes `api_path = path` (with query
  string intact) to `client.proxy`, and `api.py`'s `_split_path_query` correctly
  parses inline `?window=today` when `query=None`. Verified by
  `test_reports_page_window_today_selected`.
- **Bounded scan:** `max_scan_lines` cap and `lookback_seconds` early break prevent
  unbounded file reads. `test_50k_events_bounded` confirms <1s and bounded memory.
- **Thread-safety:** `ThreadSafeFeedbackQueue.__iter__` returns a snapshot under
  lock; `feedback_queue or []` correctly handles empty queues.
- **`__init__.py` export:** `ReportsAggregator` added to `__all__` and imported.
- **`.env.example`:** `REPORTS_*` vars documented with sensible defaults.
- **Server wiring:** Both `admin-console-api/server.py` and `admin-web-ui/__main__.py`
  construct `ReportsAggregator(contract_log_path, env=source)` and attach to the
  HTTP server; `api_client.proxy` forwards `reports_aggregator` kwarg.
