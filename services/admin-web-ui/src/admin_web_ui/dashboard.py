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
        ("/config/channels", "Channel Config"),
        ("/config/providers", "Provider Config"),
        ("/config/catalog", "Model Catalog"),
        ("/config/vision", "Vision Config"),
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
    .data-table td.key {{ font-weight: 600; color: #555; white-space: nowrap; width: 200px; }}
    .data-table td.val {{ word-break: break-all; }}
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


def _render_index(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
    """Render the dashboard index with navigation and config cards."""
    sections = [
        ("Sessions", "/sessions", "Inspect conversations and session details"),
        ("Tasks", "/tasks", "Inspect async tasks and their statuses"),
        ("Feedback Review", "/feedback", "Review pending feedback items"),
        ("Health", "/health", "Monitor system health status"),
        ("Gates", "/gates", "View V2 gate status"),
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


__all__ = ["render_dashboard", "_render_gate_honesty_banner"]
