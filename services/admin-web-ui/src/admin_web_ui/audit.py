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

_EVENT_TYPE_OPTIONS = [
    ("", "All events"),
    ("agent_turn", "AgentTurn"),
    ("feedback_event", "FeedbackEvent"),
]


def render_audit_page(
    api_data: Mapping[str, Any],
    identity: Identity | None = None,
    boundary: AdminUiBoundary | None = None,
    query_params: Mapping[str, str] | None = None,
) -> str:
    """Render the /audit page from API response data.

    ``api_data`` is the dict returned by ``handle_audit`` (or an error dict).
    ``query_params`` carries the current filter state so the form can
    re-render with the user's previous selection.
    """
    if boundary is None:
        boundary = AdminUiBoundary()

    qp = dict(query_params) if query_params else {}
    current_event_type = qp.get("event_type", "")
    current_limit = qp.get("limit", "")

    # Error short-circuit.
    if isinstance(api_data, Mapping) and "error" in api_data:
        error = api_data["error"]
        error_code = _esc(error.get("code", "unknown")) if isinstance(error, dict) else "unknown"
        error_msg = _esc(error.get("message", "An error occurred.")) if isinstance(error, dict) else _esc(str(error))
        body = f'    <p class="error">Error [{error_code}]: {error_msg}</p>'
        return _page_template("Contract Event Audit", body, identity, active_path="/audit")

    items = api_data.get("items", []) if isinstance(api_data, Mapping) else []
    count = api_data.get("count", len(items)) if isinstance(api_data, Mapping) else len(items)
    has_more = api_data.get("has_more", False) if isinstance(api_data, Mapping) else False
    next_cursor = api_data.get("next_cursor") if isinstance(api_data, Mapping) else None
    metadata = api_data.get("metadata", {}) if isinstance(api_data, Mapping) else {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    limit = metadata.get("limit", "")

    # --- Event-type filter dropdown ---
    options_html: list[str] = []
    for value, label in _EVENT_TYPE_OPTIONS:
        selected = " selected" if value == current_event_type else ""
        options_html.append(f'        <option value="{_esc(value)}"{selected}>{_esc(label)}</option>')

    form_html = (
        '    <form method="GET" action="/audit" class="card">\n'
        '      <div class="field">\n'
        '        <label for="event_type">Event Type</label>\n'
        '        <select id="event_type" name="event_type">\n'
        + "\n".join(options_html)
        + "\n        </select>\n"
        "      </div>\n"
        f'      <input type="hidden" name="limit" value="{_esc(current_limit or limit)}">\n'
        '      <button type="submit" class="btn-primary">Filter</button>\n'
        "    </form>"
    )

    # --- Table ---
    rows: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        timestamp = _esc(item.get("timestamp", ""))
        event_type = _esc(item.get("event_type", ""))
        session_id = _esc(item.get("session_id", ""))
        trace_id = str(item.get("trace_id", ""))
        if trace_id:
            trace_cell = f'<a href="/audit/{_esc(trace_id)}">{_esc(trace_id)}</a>'
        else:
            trace_cell = "&mdash;"
        rows.append(
            f"      <tr>"
            f"<td>{timestamp}</td>"
            f"<td>{event_type}</td>"
            f"<td>{session_id}</td>"
            f"<td>{trace_cell}</td>"
            f"</tr>"
        )

    if rows:
        table_html = (
            '    <table class="data-table">\n'
            "      <thead><tr>"
            "<th>Timestamp</th>"
            "<th>Event Type</th>"
            "<th>Session ID</th>"
            "<th>Trace ID</th>"
            "</tr></thead>\n"
            "      <tbody>\n"
            + "\n".join(rows)
            + "\n      </tbody>\n"
            "    </table>"
        )
    else:
        table_html = '    <p class="empty">No audit events found.</p>'

    # --- Pagination ---
    pagination_html = ""
    if has_more and next_cursor:
        next_href = f"/audit?cursor={_esc(next_cursor)}&event_type={_esc(current_event_type)}&limit={_esc(current_limit or limit)}"
        pagination_html = f'    <p><a href="{next_href}">Next page</a></p>'

    # --- Back link (always present for cursor pagination) ---
    back_html = '    <p><a href="/audit">Back to audit trail</a></p>'

    count_html = f'    <p>Showing <strong>{_esc(count)}</strong> audit events.</p>'

    body = "\n".join([form_html, count_html, table_html, pagination_html, back_html])
    return _page_template("Contract Event Audit", body, identity, active_path="/audit")


def render_trace_page(
    api_data: Mapping[str, Any],
    identity: Identity | None = None,
    boundary: AdminUiBoundary | None = None,
    trace_id: str | None = None,
) -> str:
    """Render the /audit/<trace_id> trace reconstruction page.

    ``api_data`` is the dict returned by ``handle_audit_get`` for a trace
    reconstruction (or an error dict).
    """
    if boundary is None:
        boundary = AdminUiBoundary()

    # Error short-circuit.
    if isinstance(api_data, Mapping) and "error" in api_data:
        error = api_data["error"]
        error_code = _esc(error.get("code", "unknown")) if isinstance(error, dict) else "unknown"
        error_msg = _esc(error.get("message", "An error occurred.")) if isinstance(error, dict) else _esc(str(error))
        body = f'    <p class="error">Error [{error_code}]: {error_msg}</p>'
        body += '\n    <p><a href="/audit">Back to Audit Trail</a></p>'
        return _page_template("Trace Reconstruction", body, identity, active_path="/audit")

    metadata = api_data.get("metadata", {}) if isinstance(api_data, Mapping) else {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    event_count = metadata.get("event_count", 0)
    reconstruction_complete = metadata.get("reconstruction_complete", False)

    header = f'    <h3>Trace Reconstruction: {_esc(trace_id or "")}</h3>'
    meta_html = (
        f'    <p class="empty">Events: <strong>{_esc(event_count)}</strong>'
        f' | Reconstruction complete: <strong>{_esc(reconstruction_complete)}</strong></p>'
    )

    events = api_data.get("events", []) if isinstance(api_data, Mapping) else []
    event_items: list[str] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_key = _esc(event.get("event_key", ""))
        occurred_at = _esc(event.get("occurred_at", ""))
        seq = _esc(event.get("seq", ""))
        event_data = event.get("event", {})
        if not isinstance(event_data, Mapping):
            event_data = {}

        # Render allowlisted fields as a definition list.
        dl_rows: list[str] = []
        for key, value in event_data.items():
            esc_key = _esc(key)
            if isinstance(value, Mapping):
                esc_value = _esc(dict(value))
            elif isinstance(value, list):
                esc_value = _esc(f"[{len(value)} items]")
            elif value is None:
                esc_value = ""
            else:
                esc_value = _esc(value)
            dl_rows.append(f"        <dt>{esc_key}</dt><dd>{esc_value}</dd>")

        dl_html = ""
        if dl_rows:
            dl_html = '        <dl class="data-table">\n' + "\n".join(dl_rows) + "\n        </dl>"

        event_items.append(
            f"      <li><strong>{event_key}</strong>"
            f" &middot; {occurred_at} &middot; seq={seq}\n{dl_html}\n      </li>"
        )

    if event_items:
        events_html = '    <ol class="trace-events">\n' + "\n".join(event_items) + "\n    </ol>"
    else:
        events_html = '    <p class="empty">No events found in trace.</p>'

    back_html = '    <p><a href="/audit">Back to Audit Trail</a></p>'

    body = "\n".join([header, meta_html, events_html, back_html])
    return _page_template("Trace Reconstruction", body, identity, active_path="/audit")
