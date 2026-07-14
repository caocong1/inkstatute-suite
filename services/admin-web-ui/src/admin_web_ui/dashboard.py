"""Server-side HTML dashboard rendering with html.escape on all dynamic content.

All dynamic content is passed through ``html.escape()`` and inserted as HTML
text content — never ``innerHTML``, never string interpolation into raw HTML.
A strict CSP header is set on every response by the server.
"""

from __future__ import annotations

import html
from typing import Any, Mapping

from rbac import Identity

from .boundary import AdminUiBoundary


def _esc(value: Any) -> str:
    """HTML-escape a value for safe rendering."""
    return html.escape(str(value))


def _esc_dict(data: Mapping[str, Any], boundary: AdminUiBoundary | None = None) -> list[tuple[str, str]]:
    """Render a dict as escaped key-value pairs."""
    result: list[tuple[str, str]] = []
    for key, value in data.items():
        if isinstance(value, str):
            if boundary is not None:
                decision = boundary.apply(value)
                display = decision.visible_text or ""
            else:
                display = _esc(value)
            result.append((_esc(key), display))
        elif isinstance(value, (int, float, bool)):
            result.append((_esc(key), _esc(value)))
        elif isinstance(value, Mapping):
            result.append((_esc(key), _esc(dict(value))))
        elif isinstance(value, list):
            result.append((_esc(key), _esc(f"[{len(value)} items]")))
        elif value is None:
            result.append((_esc(key), ""))
        else:
            result.append((_esc(key), _esc(value)))
    return result


def _render_kv_table(pairs: list[tuple[str, str]]) -> str:
    """Render key-value pairs as an HTML table."""
    if not pairs:
        return "<p class=\"empty\">No data available.</p>"
    rows = []
    for key, value in pairs:
        rows.append(f"      <tr><td class=\"key\">{key}</td><td class=\"val\">{value}</td></tr>")
    return "    <table class=\"data-table\">\n" + "\n".join(rows) + "\n    </table>"


def _render_items(items: list[dict[str, Any]], boundary: AdminUiBoundary) -> str:
    """Render a list of items as HTML cards."""
    if not items:
        return "    <p class=\"empty\">No items found.</p>"
    cards = []
    for item in items:
        pairs = _esc_dict(item, boundary)
        cards.append(f"    <div class=\"card\">\n{_render_kv_table(pairs)}\n    </div>")
    return "\n".join(cards)


def _page_template(title: str, body: str, identity: Identity | None = None) -> str:
    """Render the full HTML page with CSP-compliant inline structure."""
    escaped_title = _esc(title)
    nav_items = [
        ("/", "Dashboard"),
        ("/sessions", "Sessions"),
        ("/tasks", "Tasks"),
        ("/feedback", "Feedback Review"),
        ("/health", "Health"),
        ("/gates", "Gates"),
        ("/reports", "Reports"),
        ("/logs", "Logs"),
        ("/audit", "Audit Trail"),
        ("/config/channels", "Channel Config"),
        ("/config/providers", "Provider Config"),
        ("/config/catalog", "Model Catalog"),
        ("/config/vision", "Vision Config"),
        ("/login", "Login"),
        ("/logout", "Logout"),
    ]
    nav_links = "\n".join(
        f'      <a href="{_esc(href)}" class="nav-link">{_esc(label)}</a>'
        for href, label in nav_items
    )
    identity_html = ""
    if identity is not None:
        identity_html = (
            f'    <div class="identity">Role: <strong>{_esc(identity.role.value)}</strong>'
            f' &middot; Tenant: <strong>{_esc(identity.tenant_id)}</strong></div>'
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title} - InkStatute Admin</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; padding: 0; background: #f5f5f5; color: #222; }}
    .header {{ background: #1a1a2e; color: #fff; padding: 1rem 2rem; }}
    .header h1 {{ margin: 0; font-size: 1.25rem; font-weight: 600; line-height: 1.2; }}
    .nav {{ background: #16213e; padding: 0.5rem 2rem; display: flex; gap: 1rem; flex-wrap: wrap; }}
    .nav-link {{ color: #aaccff; text-decoration: none; font-size: 0.875rem; font-weight: 600; }}
    .nav-link:hover {{ color: #fff; }}
    .main {{ padding: 2rem; max-width: 1200px; margin: 0 auto; }}
    .section {{ background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .section h2 {{ margin-top: 0; font-size: 1.125rem; font-weight: 600; line-height: 1.2; border-bottom: 1px solid #eee; padding-bottom: 0.5rem; }}
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
    .data-table td {{ padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee; vertical-align: top; }}
    .data-table td.key {{ font-weight: 600; color: #555; white-space: nowrap; max-width: 200px; min-width: 120px; }}
    .data-table td.val {{ word-break: break-all; overflow-wrap: break-word; }}
    .card {{ background: #fafafa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }}
    .empty {{ color: #888; font-style: italic; }}
    .identity {{ padding: 0.5rem 2rem; background: #0f3460; color: #aaccff; font-size: 0.875rem; font-weight: 600; }}
    .notice-honesty {{ background: #f5f8ff; border: 1px solid #aaccff; border-radius: 6px; padding: 16px; margin-bottom: 16px; }}
    .notice-honesty-heading {{ font-size: 0.875rem; font-weight: 600; color: #222; margin: 0 0 0.5rem 0; }}
    .notice-honesty-body {{ font-size: 1rem; font-weight: 400; color: #222; margin: 0; }}
    .notice-honesty-body code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .error {{ color: #c0392b; font-weight: 600; }}
    .status-ok {{ color: #27ae60; font-weight: 600; }}
    .status-err {{ color: #c0392b; font-weight: 600; }}
    .field {{ margin: 0.5rem 0; font-size: 1rem; }}
    .field .key {{ font-weight: 600; font-size: 0.875rem; color: #555; }}
    .field label {{ display: block; font-weight: 600; font-size: 0.875rem; color: #555; margin-bottom: 0.25rem; }}
    .field-check {{ display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 0.25rem; }}
    .dual-knob-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin: 0.5rem 0; }}
    .channel-panel {{ margin-bottom: 3rem; }}
    .ref-input {{
      display: block; width: 100%; box-sizing: border-box; padding: 8px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      border: 1px solid #e0e0e0; border-radius: 6px; background: #fff;
    }}
    .ref-input:focus-visible, .field-check input:focus-visible, .btn-primary:focus-visible {{
      outline: 2px solid #aaccff; outline-offset: 2px;
    }}
    .btn-primary {{
      background: #1a1a2e; color: #fff; border: none; border-radius: 6px;
      padding: 8px 16px; min-height: 44px; font-size: 1rem; cursor: pointer;
    }}
    .btn-primary:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    .restart-notice {{ margin-bottom: 1.5rem; }}
    .section h2, .card h3 {{ font-size: 1.125rem; font-weight: 600; line-height: 1.2; }}
    .provider-panel {{ margin-bottom: 3rem; }}
    .badge-vision-yes {{ color: #27ae60; font-weight: 600; font-size: 0.875rem; padding: 4px 8px; }}
    .badge-vision-no {{ color: #888; font-weight: 600; font-size: 0.875rem; padding: 4px 8px; }}
    .catalog-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-height: 44px; padding: 1rem 0; border-bottom: 1px solid #eee; }}
    .catalog-row:last-child {{ border-bottom: none; }}
    .probe-result {{ margin-bottom: 1.5rem; }}
    select {{ min-height: 44px; padding: 8px; border: 1px solid #e0e0e0; border-radius: 6px; font-size: 1rem; }}
    select:focus-visible {{ outline: 2px solid #aaccff; outline-offset: 2px; }}
    .human-gate-carried {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 0.5rem; color: #856404; font-weight: 600; }}
    .human-gate-label {{ font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #856404; }}
    .health-services-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; margin-bottom: 1rem; }}
    .health-services-table th {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 2px solid #eee; font-weight: 600; font-size: 0.8125rem; color: #555; }}
    .health-services-table td {{ padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee; }}
    .flags-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
    .flags-table th {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 2px solid #eee; font-weight: 600; font-size: 0.8125rem; color: #555; }}
    .flags-table td {{ padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee; }}
    .flag-on {{ color: #27ae60; font-weight: 600; }}
    .flag-off {{ color: #888; }}
    .gate-pass-rate {{ font-size: 1.5rem; font-weight: 700; margin: 0.5rem 0; }}
    .gate-pass-rate-ok {{ color: #27ae60; }}
    .gate-pass-rate-fail {{ color: #c0392b; }}
    .gate-pass-rate-na {{ color: #888; font-size: 1rem; font-weight: 400; }}
    .run-gates-link {{ display: inline-block; margin: 0.5rem 0; padding: 6px 12px; background: #1a1a2e; color: #fff; border-radius: 6px; text-decoration: none; font-size: 0.875rem; font-weight: 600; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>InkStatute Admin Dashboard</h1>
  </div>
  <div class="nav">
{nav_links}
  </div>
{identity_html}
  <div class="main">
    <div class="section">
      <h2>{escaped_title}</h2>
{body}
    </div>
  </div>
</body>
</html>"""


def render_error_page(
    status_code: int,
    title: str,
    message: str,
    identity: Identity | None = None,
) -> str:
    """Render a dedicated error page with nav and back-to-dashboard link.

    All dynamic content (title, message) is passed through ``_esc()`` to
    prevent XSS. The page uses ``_page_template`` so it inherits the full
    nav bar, CSP header, and responsive CSS.

    Args:
        status_code: HTTP status code (e.g. 404, 500, 413).
        title: Short error title (e.g. "Not Found").
        message: Human-readable error detail (e.g. "Unknown route: /foo").
        identity: The resolved caller identity (for display).

    Returns:
        A complete HTML document string with all dynamic content escaped.
    """
    body = (
        f'    <p class="error">Error {status_code}: {_esc(title)}</p>\n'
        f'    <p>{_esc(message)}</p>\n'
        f'    <p><a href="/" class="btn-primary">Back to Dashboard</a></p>'
    )
    return _page_template(title, body, identity)


def render_dashboard(
    section: str,
    data: dict[str, Any],
    identity: Identity | None = None,
    boundary: AdminUiBoundary | None = None,
) -> str:
    """Render a dashboard section as escaped HTML.

    Args:
        section: The section name ("index", "sessions", "tasks", "feedback",
                 "health", "gates").
        data: The response dict from admin-console-api.
        identity: The resolved caller identity (for display).
        boundary: The output boundary for text filtering.

    Returns:
        A complete HTML document string with all dynamic content escaped.
    """
    if boundary is None:
        boundary = AdminUiBoundary()

    title_map = {
        "index": "Dashboard Overview",
        "sessions": "Session Inspection",
        "tasks": "Task Inspection",
        "feedback": "Feedback Review Queue",
        "health": "Health Monitoring",
        "gates": "Gate Status",
        "reports": "Reports Dashboard",
        "logs": "Log Viewer",
        "audit": "Contract Event Audit",
        "login": "Login",
        "logout": "Logout",
    }
    title = title_map.get(section, "Admin Dashboard")

    if "error" in data:
        error = data["error"]
        error_code = _esc(error.get("code", "unknown")) if isinstance(error, dict) else "unknown"
        error_msg = _esc(error.get("message", "An error occurred.")) if isinstance(error, dict) else _esc(str(error))
        body = f'    <p class="error">Error [{error_code}]: {error_msg}</p>'
        return _page_template(title, body, identity)

    if section == "index":
        body = _render_index(data, boundary)
    elif section in ("sessions", "tasks"):
        body = _render_list_section(data, boundary)
    elif section == "feedback":
        body = _render_feedback_section(data, boundary)
    elif section == "health":
        body = _render_health_section(data, boundary)
    elif section == "gates":
        body = _render_gates_section(data, boundary)
    elif section == "reports":
        body = _render_reports_section(data, boundary)
    else:
        pairs = _esc_dict(data, boundary)
        body = _render_kv_table(pairs)

    return _page_template(title, body, identity)


def _render_gate_honesty_banner() -> str:
    """Render the shared gate-honesty banner (exact UI-SPEC copy)."""
    return (
        '    <div class="notice-honesty" role="note" aria-label="Gate honesty notice">\n'
        '      <p class="notice-honesty-heading">This console does not close live acceptance gates</p>\n'
        '      <p class="notice-honesty-body">Saving config or running a probe does not claim Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ live acceptance. Smoke and probe evidence remains <code>not_live_acceptance</code>.</p>\n'
        '    </div>'
    )


def _render_carried_human_gates_card() -> str:
    """Render the carried human gates card on the Gate Status page."""
    return (
        '    <div class="card">\n'
        '      <h3>Carried human gates</h3>\n'
        '      <p class="notice-honesty-body">Phase 5 WeCom UAT, Phase 8 lawyer trial, and QQ live acceptance remain open. Automated gate results do not replace live acceptance.</p>\n'
        '    </div>'
    )


def _render_carried_human_gates_row(gate: dict[str, Any]) -> str:
    """Render a single carried human gate with a distinct non-green visual state."""
    name = _esc(gate.get("name", ""))
    return (
        f'    <div class="human-gate-carried" role="status" aria-label="Carried human gate">\n'
        f'      <span class="human-gate-label">HUMAN GATE — carried, not auto-closed</span><br>\n'
        f'      <span>{name}</span>\n'
        f'    </div>'
    )


def _render_index(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    """Render the dashboard index with navigation and config cards."""
    sections = [
        ("Sessions", "/sessions", "Inspect conversations and session details"),
        ("Tasks", "/tasks", "Inspect async tasks and their statuses"),
        ("Feedback Review", "/feedback", "Review pending feedback items"),
        ("Health", "/health", "Monitor system health status"),
        ("Gates", "/gates", "View V2 gate status"),
        ("Reports", "/reports", "View aggregate report statistics over a time range"),
        ("Log Viewer", "/logs", "View runtime logs with level filtering and keyword search"),
        ("Contract Event Audit", "/audit", "Browse AgentTurn and FeedbackEvent contract events with trace reconstruction"),
        (
            "Process Orchestration",
            "/processes",
            "Start, stop, and restart WeCom and QQBot host processes",
        ),
        (
            "Channel Config",
            "/config/channels",
            "Configure QQ and WeCom enablement and credential refs",
        ),
        (
            "Provider Config",
            "/config/providers",
            "Configure built-in and custom OpenAI-compatible providers",
        ),
        (
            "Model Catalog",
            "/config/catalog",
            "Select the main model from the built-in catalog",
        ),
        (
            "Vision Config",
            "/config/vision",
            "Configure image-turn routing and dedicated vision model",
        ),
    ]
    cards = [_render_gate_honesty_banner()]
    for label, href, desc in sections:
        cards.append(
            f'    <div class="card">\n'
            f'      <h3><a href="{_esc(href)}">{_esc(label)}</a></h3>\n'
            f'      <p>{_esc(desc)}</p>\n'
            f'    </div>'
        )
    return "\n".join(cards)


def _render_list_section(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    """Render a list section (sessions or tasks)."""
    items = data.get("items", [])
    count = data.get("count", len(items))
    has_more = data.get("has_more", False)
    next_cursor = data.get("next_cursor")

    parts = [f'    <p>Showing <strong>{_esc(count)}</strong> items.</p>']
    parts.append(_render_items(items, boundary))
    if has_more and next_cursor:
        parts.append(f'    <p>More items available. Next cursor: <code>{_esc(next_cursor)}</code></p>')
    return "\n".join(parts)


def _render_feedback_section(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    """Render the feedback review queue."""
    items = data.get("items", [])
    count = data.get("count", len(items))
    parts = [f'    <p>Pending feedback items: <strong>{_esc(count)}</strong></p>']
    parts.append(_render_items(items, boundary))
    return "\n".join(parts)


def _render_health_section(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    """Render the unified health monitoring section.

    Sub-sections:
    1. Gate honesty banner (always rendered first)
    2. Service Health table (admin API, WeCom host, QQBot host)
    3. Gate Pass Rate (percentage or 'Not run' with Run Gates link)
    4. Feature Flags table
    5. Carried Human Gates (distinct non-green visual state)
    """
    parts: list[str] = []
    parts.append(_render_gate_honesty_banner())

    # Service Health table
    services = data.get("services", [])
    if isinstance(services, list) and services:
        parts.append('    <h3>Service Health</h3>')
        parts.append('    <table class="health-services-table">')
        parts.append('      <thead><tr><th>Service</th><th>Status</th><th>OK</th><th>Host</th><th>Port</th></tr></thead>')
        parts.append('      <tbody>')
        for svc in services:
            if isinstance(svc, dict):
                name = _esc(svc.get("name", ""))
                status = _esc(svc.get("status", ""))
                ok = svc.get("ok", False)
                ok_class = "status-ok" if ok else "status-err"
                ok_text = "yes" if ok else "no"
                host = _esc(svc.get("host") or "—")
                port = _esc(svc.get("port") or "—")
                parts.append(f'        <tr><td>{name}</td><td>{status}</td><td class="{ok_class}">{ok_text}</td><td>{host}</td><td>{port}</td></tr>')
        parts.append('      </tbody>')
        parts.append('    </table>')
    else:
        parts.append('    <h3>Service Health</h3>')
        parts.append('    <p class="empty">No service health data available.</p>')

    # Gate Pass Rate
    parts.append('    <h3>Gate Pass Rate</h3>')
    gate_pass_rate = data.get("gate_pass_rate")
    if gate_pass_rate is not None:
        pct = f"{gate_pass_rate * 100:.0f}%"
        rate_class = "gate-pass-rate-ok" if gate_pass_rate >= 1.0 else "gate-pass-rate-fail"
        parts.append(f'    <div class="gate-pass-rate {rate_class}">{_esc(pct)}</div>')
        gate_count = data.get("gate_count")
        gates_passed = data.get("gates_passed")
        gates_failed = data.get("gates_failed")
        if gate_count is not None:
            parts.append(f'    <p>{_esc(gates_passed)} passed / {_esc(gate_count)} total ({_esc(gates_failed)} failed)</p>')
    else:
        parts.append('    <div class="gate-pass-rate gate-pass-rate-na">Not run</div>')
        parts.append('    <a href="/health?gates=true" class="run-gates-link">Run Gates</a>')

    # Feature Flags
    feature_flags = data.get("feature_flags", [])
    if isinstance(feature_flags, list) and feature_flags:
        parts.append('    <h3>Feature Flags</h3>')
        parts.append('    <table class="flags-table">')
        parts.append('      <thead><tr><th>Flag</th><th>Enabled</th></tr></thead>')
        parts.append('      <tbody>')
        for flag in feature_flags:
            if isinstance(flag, dict):
                fname = _esc(flag.get("name", ""))
                enabled = flag.get("enabled", False)
                flag_class = "flag-on" if enabled else "flag-off"
                flag_text = "on" if enabled else "off"
                parts.append(f'        <tr><td>{fname}</td><td class="{flag_class}">{flag_text}</td></tr>')
        parts.append('      </tbody>')
        parts.append('    </table>')
    else:
        parts.append('    <h3>Feature Flags</h3>')
        parts.append('    <p class="empty">No feature flag data available.</p>')

    # Carried Human Gates
    carried = data.get("carried_human_gates", [])
    if isinstance(carried, list) and carried:
        parts.append('    <h3>Carried Human Gates</h3>')
        for gate in carried:
            if isinstance(gate, dict):
                parts.append(_render_carried_human_gates_row(gate))
    else:
        parts.append('    <h3>Carried Human Gates</h3>')
        parts.append('    <p class="empty">No carried human gates data available.</p>')

    return "\n".join(parts)


def _render_gates_section(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    """Render the gate status section with automated gate cards and carried human gates."""
    gates = data.get("gates", data.get("items", []))
    parts: list[str] = []
    if isinstance(gates, list) and gates:
        for gate in gates:
            if isinstance(gate, dict):
                name = _esc(gate.get("name", gate.get("gate", "")))
                status = gate.get("status", gate.get("exit_code", ""))
                status_class = "status-ok" if str(status) in ("0", "passed", "ok", "OK") else "status-err"
                parts.append(f'    <div class="card"><span>{name}</span> <span class="{status_class}">{_esc(status)}</span></div>')
            else:
                parts.append(f'    <div class="card">{_esc(gate)}</div>')
    else:
        pairs = _esc_dict(data, boundary)
        parts.append(_render_kv_table(pairs))
    parts.append(_render_carried_human_gates_card())
    return "\n".join(parts)


def _render_reports_section(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    """Render the reports dashboard with a time-range selector and metric cards.

    All dynamic text is escaped via ``html.escape`` or ``boundary.escape_value``.
    The ``window`` selection uses ``metadata.window`` from the API response.
    """
    if "error" in data:
        error = data["error"]
        error_code = _esc(error.get("code", "unknown")) if isinstance(error, dict) else "unknown"
        error_msg = _esc(error.get("message", "An error occurred.")) if isinstance(error, dict) else _esc(str(error))
        return f'    <p class="error">Error [{error_code}]: {error_msg}</p>'

    metadata = data.get("metadata", {}) if isinstance(data.get("metadata"), Mapping) else {}
    current_window = str(metadata.get("window", "7d"))
    valid_windows = ("today", "7d", "30d", "custom")

    options_html: list[str] = []
    for w in valid_windows:
        selected = " selected" if w == current_window else ""
        options_html.append(f'      <option value="{_esc(w)}"{selected}>{_esc(w)}</option>')

    from_inputs = ""
    to_inputs = ""
    if current_window == "custom":
        from_val = _esc(metadata.get("time_from", ""))
        to_val = _esc(metadata.get("time_to", ""))
        from_inputs = (
            f'      <div class="field"><label for="from">From (UTC)</label>'
            f'<input type="datetime-local" id="from" name="from" value="{from_val}"></div>'
        )
        to_inputs = (
            f'      <div class="field"><label for="to">To (UTC)</label>'
            f'<input type="datetime-local" id="to" name="to" value="{to_val}"></div>'
        )

    form_html = (
        '    <form method="GET" action="/reports" class="card">\n'
        '      <div class="field"><label for="window">Time Range</label>'
        f'<select id="window" name="window">\n'
        + "\n".join(options_html)
        + "      </select></div>\n"
        f'{from_inputs}{to_inputs}'
        '      <button type="submit" class="btn-primary">Refresh</button>\n'
        '    </form>'
    )

    sessions = data.get("sessions", {}) if isinstance(data.get("sessions"), Mapping) else {}
    tasks = data.get("tasks", {}) if isinstance(data.get("tasks"), Mapping) else {}
    feedback = data.get("feedback", {}) if isinstance(data.get("feedback"), Mapping) else {}
    gates = data.get("gates", {}) if isinstance(data.get("gates"), Mapping) else {}

    def _metric_card(label: str, value: Any) -> str:
        return (
            f'    <div class="card">\n'
            f'      <h3>{_esc(label)}</h3>\n'
            f'      <p class="notice-honesty-body">{_esc(value)}</p>\n'
            f'    </div>'
        )

    def _rate(value: Any) -> str:
        try:
            return f"{float(value) * 100:.1f}%"
        except (TypeError, ValueError):
            return _esc(value)

    cards = [
        _metric_card("Sessions", sessions.get("count", 0)),
        _metric_card("Tasks Total", tasks.get("total", 0)),
        _metric_card("Tasks Completed", tasks.get("completed", 0)),
        _metric_card("Completion Rate", _rate(tasks.get("completion_rate", 0.0))),
        _metric_card("Long Task Total", tasks.get("long_task_total", 0)),
        _metric_card("Long Task Success Rate", _rate(tasks.get("long_task_success_rate", 0.0))),
        _metric_card("Feedback Up", feedback.get("up", 0)),
        _metric_card("Feedback Down", feedback.get("down", 0)),
        _metric_card("Gate Pass Rate", _rate(
            gates.get("gate_count", 0) and gates.get("gates_passed", 0) / gates.get("gate_count", 1) or 0.0
        ) if gates.get("gate_count") else "N/A"),
    ]

    aggregated_at = _esc(metadata.get("aggregated_at", ""))
    note = (
        '    <p class="empty">Values are in UTC. '
        f'Aggregated at: <code>{aggregated_at}</code></p>'
    )

    return "\n".join([form_html] + cards + [note])


__all__ = ["render_dashboard", "_render_gate_honesty_banner", "_render_carried_human_gates_row"]
