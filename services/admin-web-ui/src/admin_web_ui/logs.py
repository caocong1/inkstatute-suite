"""Log viewing UI page for the admin web UI (Phase 82).

Renders a source selector, level filter, keyword search input, and a
``<pre>`` block of scrubbed log lines with a ``meta http-equiv="refresh"``
tag for CSP-safe auto-polling.  All dynamic content is HTML-escaped.
"""

from __future__ import annotations

from typing import Any, Mapping

from rbac import Identity

from .boundary import AdminUiBoundary
from .dashboard import _page_template

__all__ = ["render_logs_page"]

_SOURCE_OPTIONS = [
    ("contract_events", "Contract Events"),
    ("runtime_audit", "Runtime Audit"),
    ("feedback", "Feedback Queue"),
    ("wecom_stdout", "WeCom stdout/stderr"),
    ("qqbot_stdout", "QQBot stdout/stderr"),
]

_LEVEL_OPTIONS = ["DEBUG", "INFO", "WARN", "ERROR"]


def _esc(value: Any) -> str:
    text = str(value) if value is not None else ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_logs_page(
    api_data: Mapping[str, Any],
    identity: Identity | None = None,
    boundary: AdminUiBoundary | None = None,
    query_params: Mapping[str, str] | None = None,
) -> str:
    """Render the /logs page from API response data.

    ``api_data`` is the dict returned by ``handle_logs`` (or an error dict).
    ``query_params`` carries the current filter state so the form can
    re-render with the user's previous selection.
    """
    if boundary is None:
        boundary = AdminUiBoundary()

    qp = dict(query_params) if query_params else {}
    current_source = qp.get("source", "")
    current_level = qp.get("level", "")
    current_q = qp.get("q", "")

    # Error short-circuit.
    if isinstance(api_data, Mapping) and "error" in api_data:
        error = api_data["error"]
        error_code = _esc(error.get("code", "unknown")) if isinstance(error, dict) else "unknown"
        error_msg = _esc(error.get("message", "An error occurred.")) if isinstance(error, dict) else _esc(str(error))
        body = f'    <p class="error">Error [{error_code}]: {error_msg}</p>'
        return _page_template("Log Viewer", body, identity, active_path="/logs")

    # Build source availability map from the API ``sources`` list (if present).
    sources_list = api_data.get("sources", []) if isinstance(api_data, Mapping) else []
    available_map: dict[str, bool] = {}
    if isinstance(sources_list, list):
        for entry in sources_list:
            if isinstance(entry, Mapping):
                available_map[str(entry.get("source", ""))] = bool(entry.get("available", False))

    # --- Source selector ---
    source_options_html: list[str] = [
        '        <option value="">— Select source —</option>',
    ]
    for value, label in _SOURCE_OPTIONS:
        selected = " selected" if value == current_source else ""
        suffix = ""
        if value in available_map and not available_map[value]:
            suffix = " (not configured)"
        source_options_html.append(
            f'        <option value="{_esc(value)}"{selected}>{_esc(label)}{_esc(suffix)}</option>'
        )

    # --- Level filter ---
    level_options_html: list[str] = ['        <option value="">All levels</option>']
    for lvl in _LEVEL_OPTIONS:
        selected = " selected" if lvl == current_level else ""
        level_options_html.append(
            f'        <option value="{_esc(lvl)}"{selected}>{_esc(lvl)}</option>'
        )

    # --- Lines / metadata from read response ---
    lines = api_data.get("lines", []) if isinstance(api_data, Mapping) else []
    next_offset = api_data.get("next_offset", 0) if isinstance(api_data, Mapping) else 0
    inode = api_data.get("inode", "") if isinstance(api_data, Mapping) else ""
    eof = api_data.get("eof", False) if isinstance(api_data, Mapping) else False
    metadata = api_data.get("metadata", {}) if isinstance(api_data, Mapping) else {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    lines_returned = metadata.get("lines_returned", len(lines))
    lines_filtered = metadata.get("lines_filtered", 0)
    max_lines = metadata.get("max_lines", 500)
    rotated = metadata.get("rotated", False)

    # --- Log lines display ---
    escaped_lines = [_esc(line.get("text", "")) if isinstance(line, Mapping) else _esc(line) for line in lines]
    log_block = "\n".join(escaped_lines) if escaped_lines else "(no lines)"

    # --- Build form ---
    form_html = (
        '    <form method="GET" action="/logs" class="card">\n'
        '      <div class="field">\n'
        '        <label for="source">Log Source</label>\n'
        '        <select id="source" name="source">\n'
        + "\n".join(source_options_html)
        + "\n        </select>\n"
        "      </div>\n"
        '      <div class="field">\n'
        '        <label for="level">Level</label>\n'
        '        <select id="level" name="level">\n'
        + "\n".join(level_options_html)
        + "\n        </select>\n"
        "      </div>\n"
        '      <div class="field">\n'
        '        <label for="q">Keyword Search</label>\n'
        f'        <input type="text" id="q" name="q" value="{_esc(current_q)}" placeholder="Filter by keyword..." class="ref-input">\n'
        "      </div>\n"
        f'      <input type="hidden" name="offset" value="{_esc(next_offset)}">\n'
        f'      <input type="hidden" name="inode" value="{_esc(inode)}">\n'
        '      <button type="submit" class="btn-primary">Refresh</button>\n'
        "    </form>"
    )

    # --- Auto-refresh note ---
    reset_href = f"/logs?source={_esc(current_source)}&level={_esc(current_level)}&q={_esc(current_q)}"
    auto_refresh_note = (
        '    <p class="auto-refresh-note">Auto-refreshing every 5 seconds. '
        f'<a href="{reset_href}">Reset</a></p>'
    )

    # --- Log output ---
    log_output_html = (
        '    <pre class="log-output">\n'
        f"{log_block}\n"
        "    </pre>"
    )

    # --- Metadata ---
    meta_html = (
        f'    <p class="empty">Lines: {_esc(lines_returned)}/{_esc(max_lines)}'
        f' | Filtered: {_esc(lines_filtered)}'
        f' | EOF: {_esc(eof)}'
        f' | Offset: {_esc(next_offset)}'
        f' | Rotated: {_esc(rotated)}</p>'
    )

    body = "\n".join([form_html, auto_refresh_note, log_output_html, meta_html])

    # Use a custom page template that injects the meta refresh tag.
    return _logs_page_template("Log Viewer", body, identity)


def _logs_page_template(title: str, body: str, identity: Identity | None = None) -> str:
    """Page template with a ``<meta http-equiv="refresh">`` tag for auto-polling.

    Thin wrapper delegating to ``_page_template`` with ``head_extras`` injecting
    the meta-refresh tag and ``active_path="/logs"`` for nav active-state.
    """
    return _page_template(
        title,
        body,
        identity,
        active_path="/logs",
        head_extras='<meta http-equiv="refresh" content="5">',
    )
