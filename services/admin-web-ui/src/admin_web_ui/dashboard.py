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
    .header h1 {{ margin: 0; font-size: 1.25rem; }}
    .nav {{ background: #16213e; padding: 0.5rem 2rem; display: flex; gap: 1rem; flex-wrap: wrap; }}
    .nav-link {{ color: #aaccff; text-decoration: none; font-size: 0.9rem; }}
    .nav-link:hover {{ color: #fff; }}
    .main {{ padding: 2rem; max-width: 1200px; margin: 0 auto; }}
    .section {{ background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .section h2 {{ margin-top: 0; font-size: 1.1rem; border-bottom: 1px solid #eee; padding-bottom: 0.5rem; }}
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    .data-table td {{ padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee; vertical-align: top; }}
    .data-table td.key {{ font-weight: 600; color: #555; white-space: nowrap; width: 200px; }}
    .data-table td.val {{ word-break: break-all; }}
    .card {{ background: #fafafa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }}
    .empty {{ color: #888; font-style: italic; }}
    .identity {{ padding: 0.5rem 2rem; background: #0f3460; color: #aaccff; font-size: 0.8rem; }}
    .error {{ color: #c0392b; font-weight: 600; }}
    .status-ok {{ color: #27ae60; font-weight: 600; }}
    .status-err {{ color: #c0392b; font-weight: 600; }}
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
    else:
        pairs = _esc_dict(data, boundary)
        body = _render_kv_table(pairs)

    return _page_template(title, body, identity)


def _render_index(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    """Render the dashboard index with navigation cards."""
    sections = [
        ("Sessions", "/sessions", "Inspect conversations and session details"),
        ("Tasks", "/tasks", "Inspect async tasks and their statuses"),
        ("Feedback Review", "/feedback", "Review pending feedback items"),
        ("Health", "/health", "Monitor system health status"),
        ("Gates", "/gates", "View V2 gate status"),
    ]
    cards = []
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
    """Render the health monitoring section."""
    parts: list[str] = []
    # Render top-level scalar fields as a table
    scalar_pairs: list[tuple[str, str]] = []
    nested_sections: list[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            nested_sections.append(f'    <h3>{_esc(key)}</h3>')
            nested_sections.append(_render_items(value, boundary))
        elif isinstance(value, Mapping):
            nested_pairs = _esc_dict(value, boundary)
            nested_sections.append(f'    <h3>{_esc(key)}</h3>')
            nested_sections.append(_render_kv_table(nested_pairs))
        else:
            if isinstance(value, str):
                decision = boundary.apply(value)
                display = decision.visible_text or ""
            else:
                display = _esc(value)
            scalar_pairs.append((_esc(key), display))
    if scalar_pairs:
        parts.append(_render_kv_table(scalar_pairs))
    parts.extend(nested_sections)
    return "\n".join(parts)


def _render_gates_section(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    """Render the gate status section."""
    gates = data.get("gates", data.get("items", []))
    if isinstance(gates, list) and gates:
        parts = []
        for gate in gates:
            if isinstance(gate, dict):
                name = _esc(gate.get("name", gate.get("gate", "")))
                status = gate.get("status", gate.get("exit_code", ""))
                status_class = "status-ok" if str(status) in ("0", "passed", "ok", "OK") else "status-err"
                parts.append(f'    <div class="card"><span>{name}</span> <span class="{status_class}">{_esc(status)}</span></div>')
            else:
                parts.append(f'    <div class="card">{_esc(gate)}</div>')
        return "\n".join(parts)
    pairs = _esc_dict(data, boundary)
    return _render_kv_table(pairs)


__all__ = ["render_dashboard"]
