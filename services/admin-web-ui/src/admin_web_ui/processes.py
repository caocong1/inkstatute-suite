"""Process orchestration UI page and form parser for the admin web UI."""

from __future__ import annotations

from typing import Any, Mapping

from .boundary import AdminUiBoundary

__all__ = ["parse_processes_form", "render_processes_page"]

_ALLOWED_NAMES = {"wecom", "qqbot"}
_ALLOWED_ACTIONS = {"start", "stop", "restart"}


def parse_processes_form(form_map: Mapping[str, Any]) -> tuple[str, str]:
    """Extract and validate name/action from the process control form."""
    raw_name = _single_value(form_map, "name")
    raw_action = _single_value(form_map, "action")
    if raw_name not in _ALLOWED_NAMES:
        raise ValueError(f"unknown process name: {raw_name!r}")
    if raw_action not in _ALLOWED_ACTIONS:
        raise ValueError(f"unknown process action: {raw_action!r}")
    return raw_name, raw_action


def _single_value(form_map: Mapping[str, Any], key: str) -> str:
    raw = form_map.get(key)
    if isinstance(raw, list):
        values = [str(v).strip() for v in raw if str(v).strip()]
        if len(values) != 1:
            return ""
        return values[0]
    text = str(raw or "").strip()
    return text


def _esc(value: Any) -> str:
    text = str(value) if value is not None else ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _status_class(status: str) -> str:
    if status == "running":
        return "status-ok"
    if status in ("degraded", "orphaned"):
        return "status-warn"
    if status in ("starting", "stopping"):
        return "status-pending"
    return "status-err"


def render_processes_page(
    api_data: Mapping[str, Any],
    identity: Any | None = None,
    boundary: AdminUiBoundary | None = None,
    csrf_token: str | None = None,
    error_message: str | None = None,
    flash: str | None = None,
    flash_kind: str = "success",
) -> str:
    """Render the Process Orchestration page with status and control buttons."""
    if boundary is None:
        from .boundary import AdminUiBoundary

        boundary = AdminUiBoundary()

    title = "Process Orchestration"
    process_list = api_data.get("processes", []) if isinstance(api_data, Mapping) else []
    if not isinstance(process_list, list):
        process_list = []

    parts: list[str] = []
    parts.append(f"<h2>{_esc(title)}</h2>")

    if flash:
        parts.append(
            f'    <p class="flash flash-{_esc(flash_kind)}">{_esc(flash)}</p>'
        )
    if error_message:
        parts.append(
            f'    <p class="error">{_esc(error_message)}</p>'
        )

    parts.append(
        "    <p>Start, stop, or restart the WeCom and QQBot host processes. "
        "Changes take effect after restart.</p>"
    )

    parts.append('    <table class="data-table">')
    parts.append(
        "      <tr>"
        "        <th>Name</th>"
        "        <th>Status</th>"
        "        <th>PID</th>"
        "        <th>Host</th>"
        "        <th>Port</th>"
        "        <th>Log</th>"
        "        <th>Actions</th>"
        "      </tr>"
    )

    for process in process_list:
        if not isinstance(process, Mapping):
            continue
        name = _esc(process.get("name", ""))
        status = _esc(process.get("status", "unknown"))
        status_class = _status_class(process.get("status", ""))
        pid = _esc(process.get("pid") if process.get("pid") is not None else "—")
        host = _esc(process.get("host", "127.0.0.1"))
        port = _esc(process.get("port", "0"))
        log_path = _esc(process.get("log_path", ""))
        log_link = (
            f'<a href="file://{_esc(log_path)}">{_esc(log_path)}</a>'
            if log_path
            else "—"
        )

        actions = ""
        for action in ("start", "stop", "restart"):
            actions += (
                f'      <form method="post" action="/processes" class="inline-form">\n'
                f'        <input type="hidden" name="csrf_token" value="{_esc(csrf_token)}" />\n'
                f'        <input type="hidden" name="name" value="{name}" />\n'
                f'        <input type="hidden" name="action" value="{action}" />\n'
                f'        <button type="submit" class="btn">{action.capitalize()}</button>\n'
                f'      </form>\n'
            )

        parts.append(
            f'      <tr>\n'
            f'        <td>{name}</td>\n'
            f'        <td><span class="{status_class}">{status}</span></td>\n'
            f'        <td>{pid}</td>\n'
            f'        <td>{host}</td>\n'
            f'        <td>{port}</td>\n'
            f'        <td>{log_link}</td>\n'
            f'        <td>{actions}</td>\n'
            f'      </tr>'
        )

    parts.append("    </table>")

    body = "\n".join(parts)
    from .dashboard import _page_template

    return _page_template(title, body, identity)
