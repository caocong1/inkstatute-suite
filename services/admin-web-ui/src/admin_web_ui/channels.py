"""Channel Config SSR form — dual-knob QQ/WeCom panels per Phase 75 UI-SPEC.

Renders platform (read-only) / host (editable) / effective lines and secret-ref
text fields only. Never resolves secrets. Never offers a single bypass toggle.
"""

from __future__ import annotations

import html
from typing import Any, Mapping
from urllib.parse import parse_qs

from rbac import Identity

from .boundary import AdminUiBoundary
from .dashboard import _page_template, _render_gate_honesty_banner

# UI-SPEC copy (exact strings)
PAGE_TITLE = "Channel Config"
PRIMARY_CTA = "Save channel config"
DUAL_KNOB_LEGEND = "Effective enablement requires both knobs ON"
RESTART_NOTICE = (
    "Changes persist in the operator config store. Channel hosts read config "
    "at startup; restart QQ/WeCom hosts to apply."
)
SUCCESS_FLASH = (
    "Channel config saved. Restart channel hosts to apply (MVP — no hot-reload)."
)
REF_HELP = (
    "Secret reference only (`env:NAME`, bare `ENV_NAME`, or `secret://path/segments`). "
    "Never paste raw tokens."
)
EMPTY_HEADING = "No channel overrides yet"
EMPTY_BODY = (
    "Defaults are OFF. Set host enablement and secret refs below, then "
    "Save channel config. Hosts apply after process restart (MVP)."
)
ERROR_VALIDATION = (
    "Invalid config. Check the fields and try again."
)
ERROR_CSRF = (
    "Request could not be verified. Refresh the page and try again."
)
ERROR_FLAG_OFF = (
    "Operator config writes are disabled (`operator_config_enabled` is OFF). "
    "Enable the flag, then retry."
)
ERROR_FORBIDDEN = "You do not have permission to change channel config."
ERROR_GENERIC = "Could not save channel config. Check the message above and try again."

_QQBOT_REF_FIELDS = (
    ("app_id_ref", "env:INKSTATUTE_QQBOT_APP_ID"),
    ("app_secret_ref", "env:INKSTATUTE_QQBOT_APP_SECRET"),
    ("token_secret_ref", "env:INKSTATUTE_QQBOT_TOKEN"),
    ("bot_secret_ref", "env:INKSTATUTE_QQBOT_BOT_SECRET"),
)
_WECOM_REF_FIELDS = (
    ("token_secret_ref", "env:INKSTATUTE_WECOM_TOKEN"),
    ("encoding_aes_key_secret_ref", "env:INKSTATUTE_WECOM_ENCODING_AES_KEY"),
    ("corp_id_ref", "env:INKSTATUTE_WECOM_CORP_ID"),
)


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _bool_status(on: bool) -> tuple[str, str]:
    if on:
        return "ON", "status-ok"
    return "OFF", "empty"


def _ref_status(configured: bool) -> tuple[str, str]:
    if configured:
        return "Configured (ref stored)", "status-ok"
    return "Not set", "empty"


def _effective_line(enabled: bool) -> tuple[str, str]:
    if enabled:
        return "Effective: enabled (platform AND host)", "status-ok"
    return "Effective: disabled — both knobs must be ON for live IO", "status-err"


def _channel_data(api_data: Mapping[str, Any], key: str) -> dict[str, Any]:
    data = api_data.get("data")
    if isinstance(data, Mapping):
        channel = data.get(key)
        if isinstance(channel, Mapping):
            return dict(channel)
    return {}


def _effective_block(api_data: Mapping[str, Any], key: str) -> dict[str, Any]:
    effective = api_data.get("effective")
    if isinstance(effective, Mapping):
        block = effective.get(key)
        if isinstance(block, Mapping):
            return dict(block)
    return {}


def _flash_html(flash: str | None, *, kind: str) -> str:
    if not flash:
        return ""
    css = "status-ok" if kind == "success" else "error"
    return f'    <p class="{css}" role="status">{_esc(flash)}</p>\n'


def _knob_row(label: str, on: bool, *, editable: bool, checkbox_name: str | None) -> str:
    word, css = _bool_status(on)
    if editable and checkbox_name:
        checked = " checked" if on else ""
        control = (
            f'<label class="field-check" for="{_esc(checkbox_name)}">'
            f'<input type="checkbox" id="{_esc(checkbox_name)}" '
            f'name="{_esc(checkbox_name)}" value="1"{checked}>'
            f"</label>"
        )
        return (
            f'      <p class="field dual-knob-row">'
            f'<span class="key">{_esc(label)}</span> '
            f"{control} "
            f'<span class="{css}">{word}</span></p>'
        )
    return (
        f'      <p class="field dual-knob-row">'
        f'<span class="key">{_esc(label)}</span> '
        f'<span class="{css}">{word}</span></p>'
    )


def _ref_field(
    name: str,
    label: str,
    value: str | None,
    *,
    placeholder: str,
    configured: bool,
    disabled: bool,
) -> str:
    status_text, status_css = _ref_status(configured)
    display = value or ""
    disabled_attr = " disabled" if disabled else ""
    return (
        f'      <p class="field">\n'
        f'        <label for="{_esc(name)}">{_esc(label)}</label>\n'
        f'        <input class="ref-input" type="text" id="{_esc(name)}" '
        f'name="{_esc(name)}" value="{_esc(display)}" '
        f'placeholder="{_esc(placeholder)}" autocomplete="off"{disabled_attr}>\n'
        f'        <span class="{status_css}">{_esc(status_text)}</span>\n'
        f"      </p>"
    )


def _render_qqbot_panel(
    channel: Mapping[str, Any],
    effective: Mapping[str, Any],
    *,
    disabled: bool,
) -> str:
    platform = bool(effective.get("platform_flag", False))
    host = bool(effective.get("host_enabled", channel.get("enabled", False)))
    eff = bool(effective.get("effective_enabled", platform and host))
    refs_cfg = effective.get("refs_configured")
    if not isinstance(refs_cfg, Mapping):
        refs_cfg = {}
    eff_text, eff_css = _effective_line(eff)
    parts = [
        '    <div class="card channel-panel">',
        "      <h3>QQBot channel</h3>",
        _knob_row(
            "Platform flag (`qqbot_channel_enabled`)",
            platform,
            editable=False,
            checkbox_name=None,
        ),
        _knob_row(
            "Host enabled (`channels.qqbot.enabled`)",
            host,
            editable=not disabled,
            checkbox_name="qqbot.enabled",
        ),
        f'      <p class="field"><span class="{eff_css}">{_esc(eff_text)}</span></p>',
        f'      <p class="empty">{_esc(DUAL_KNOB_LEGEND)}</p>',
    ]
    for field, placeholder in _QQBOT_REF_FIELDS:
        raw = channel.get(field)
        value = raw if isinstance(raw, str) else None
        configured = bool(refs_cfg.get(field)) or bool(value and value.strip())
        parts.append(
            _ref_field(
                f"qqbot.{field}",
                field,
                value,
                placeholder=placeholder,
                configured=configured,
                disabled=disabled,
            )
        )
    parts.append('      <input type="hidden" name="qqbot.channel_id" value="qqbot">')
    parts.append("    </div>")
    return "\n".join(parts)


def _render_wecom_panel(
    channel: Mapping[str, Any],
    effective: Mapping[str, Any],
    *,
    disabled: bool,
) -> str:
    platform = bool(effective.get("platform_flag", False))
    host = bool(effective.get("host_enabled", channel.get("enabled", False)))
    eff = bool(effective.get("effective_enabled", platform and host))
    refs_cfg = effective.get("refs_configured")
    if not isinstance(refs_cfg, Mapping):
        refs_cfg = {}
    eff_text, eff_css = _effective_line(eff)
    parts = [
        '    <div class="card channel-panel">',
        "      <h3>WeCom channel</h3>",
        _knob_row(
            "Platform flag (`wecom_channel_enabled`)",
            platform,
            editable=False,
            checkbox_name=None,
        ),
        _knob_row(
            "Host enabled (`channels.wecom.enabled`)",
            host,
            editable=not disabled,
            checkbox_name="wecom.enabled",
        ),
        f'      <p class="field"><span class="{eff_css}">{_esc(eff_text)}</span></p>',
        f'      <p class="empty">{_esc(DUAL_KNOB_LEGEND)}</p>',
    ]
    for field, placeholder in _WECOM_REF_FIELDS:
        raw = channel.get(field)
        value = raw if isinstance(raw, str) else None
        configured = bool(refs_cfg.get(field)) or bool(value and value.strip())
        parts.append(
            _ref_field(
                f"wecom.{field}",
                field,
                value,
                placeholder=placeholder,
                configured=configured,
                disabled=disabled,
            )
        )
    parts.append('      <input type="hidden" name="wecom.channel_id" value="wecom">')
    parts.append("    </div>")
    return "\n".join(parts)


def render_channels_form(
    api_data: Mapping[str, Any],
    *,
    csrf_token: str | None = None,
    read_only: bool = False,
    flash: str | None = None,
    flash_kind: str = "success",
    error_message: str | None = None,
) -> str:
    """Render the Channel Config form body (inside page section)."""
    qq = _channel_data(api_data, "qqbot")
    we = _channel_data(api_data, "wecom")
    qq_eff = _effective_block(api_data, "qqbot")
    we_eff = _effective_block(api_data, "wecom")

    metadata = api_data.get("metadata") if isinstance(api_data.get("metadata"), Mapping) else {}
    flag_off = not bool(metadata.get("operator_config_enabled", True)) if metadata else False
    disabled = read_only or flag_off

    parts: list[str] = [_render_gate_honesty_banner()]
    if error_message:
        parts.append(_flash_html(error_message, kind="error"))
    elif flash:
        parts.append(_flash_html(flash, kind=flash_kind))
    if flag_off and not error_message:
        parts.append(_flash_html(ERROR_FLAG_OFF, kind="error"))

    parts.append(f'    <p class="empty restart-notice">{_esc(RESTART_NOTICE)}</p>')

    empty = not qq and not we and not qq_eff and not we_eff
    if empty:
        parts.append(f'    <p class="empty"><strong>{_esc(EMPTY_HEADING)}</strong></p>')
        parts.append(f'    <p class="empty">{_esc(EMPTY_BODY)}</p>')

    parts.append('    <form method="post" action="/config/channels" class="channels-form">')
    token = csrf_token or ""
    parts.append(
        f'      <input type="hidden" name="csrf_token" value="{_esc(token)}">'
    )
    parts.append(_render_qqbot_panel(qq, qq_eff, disabled=disabled))
    parts.append(_render_wecom_panel(we, we_eff, disabled=disabled))
    parts.append(f'      <p class="empty">{_esc(REF_HELP)}</p>')
    disabled_attr = " disabled" if disabled else ""
    parts.append(
        f'      <button type="submit" class="btn-primary"{disabled_attr}>'
        f"{_esc(PRIMARY_CTA)}</button>"
    )
    parts.append("    </form>")
    return "\n".join(parts)


def render_channels_page(
    api_data: Mapping[str, Any],
    identity: Identity | None = None,
    boundary: AdminUiBoundary | None = None,
    *,
    csrf_token: str | None = None,
    read_only: bool = False,
    flash: str | None = None,
    flash_kind: str = "success",
    error_message: str | None = None,
) -> str:
    """Render the full Channel Config HTML page."""
    del boundary  # reserved for free-text API messages; form uses escaped copy
    if "error" in api_data and not flash and error_message is None:
        error = api_data["error"]
        if isinstance(error, dict):
            code = str(error.get("code", "unknown"))
            msg = str(error.get("message", "An error occurred."))
            if code == "forbidden":
                error_message = ERROR_FORBIDDEN
            elif code == "operator_config_disabled":
                error_message = ERROR_FLAG_OFF
            elif code == "invalid_config":
                error_message = ERROR_VALIDATION
            else:
                error_message = f"Error [{code}]: {msg}"
        else:
            error_message = ERROR_GENERIC
        body = (
            f'    <p class="error">{_esc(error_message)}</p>\n'
            if error_message
            else f'    <p class="error">{_esc(ERROR_GENERIC)}</p>\n'
        )
        # Still show form shell when possible for dual-knob visibility on soft errors
        if isinstance(api_data.get("data"), Mapping) or isinstance(
            api_data.get("effective"), Mapping
        ):
            body = render_channels_form(
                api_data,
                csrf_token=csrf_token,
                read_only=True,
                error_message=error_message,
            )
        return _page_template(PAGE_TITLE, body, identity)

    body = render_channels_form(
        api_data,
        csrf_token=csrf_token,
        read_only=read_only,
        flash=flash,
        flash_kind=flash_kind,
        error_message=error_message,
    )
    return _page_template(PAGE_TITLE, body, identity)


def _form_get(form: Mapping[str, list[str] | str], key: str) -> str | None:
    raw = form.get(key)
    if raw is None:
        return None
    if isinstance(raw, list):
        if not raw:
            return None
        value = raw[-1]
    else:
        value = raw
    text = str(value).strip()
    return text if text else None


def _form_checkbox(form: Mapping[str, list[str] | str], key: str) -> bool:
    raw = form.get(key)
    if raw is None:
        return False
    if isinstance(raw, list):
        return any(str(v).strip() not in ("", "0", "false", "off") for v in raw)
    return str(raw).strip() not in ("", "0", "false", "off")


def parse_channels_form(
    form: Mapping[str, Any] | str | bytes,
) -> dict[str, Any]:
    """Parse urlencoded form fields into a Phase 74 PUT ``/config/channels`` body.

    Returns unwrapped section value: ``{"qqbot": {...}, "wecom": {...}}``.
    Empty ref strings become ``None``. Does not resolve secrets.
    """
    if isinstance(form, (str, bytes)):
        text = form.decode("utf-8") if isinstance(form, bytes) else form
        parsed: dict[str, list[str]] = parse_qs(text, keep_blank_values=True)
        form_map: Mapping[str, list[str] | str] = parsed
    else:
        form_map = form  # type: ignore[assignment]

    def ref(prefix: str, field: str) -> str | None:
        return _form_get(form_map, f"{prefix}.{field}")

    qqbot = {
        "channel_id": _form_get(form_map, "qqbot.channel_id") or "qqbot",
        "enabled": _form_checkbox(form_map, "qqbot.enabled"),
        "app_id_ref": ref("qqbot", "app_id_ref"),
        "app_secret_ref": ref("qqbot", "app_secret_ref"),
        "token_secret_ref": ref("qqbot", "token_secret_ref"),
        "bot_secret_ref": ref("qqbot", "bot_secret_ref"),
        "metadata": {},
    }
    wecom = {
        "channel_id": _form_get(form_map, "wecom.channel_id") or "wecom",
        "enabled": _form_checkbox(form_map, "wecom.enabled"),
        "token_secret_ref": ref("wecom", "token_secret_ref"),
        "encoding_aes_key_secret_ref": ref("wecom", "encoding_aes_key_secret_ref"),
        "corp_id_ref": ref("wecom", "corp_id_ref"),
        "metadata": {},
    }
    return {"qqbot": qqbot, "wecom": wecom}


# Alias expected by Wave 0 scaffold discovery
render = render_channels_page

__all__ = [
    "parse_channels_form",
    "render",
    "render_channels_form",
    "render_channels_page",
    "PRIMARY_CTA",
    "PAGE_TITLE",
    "SUCCESS_FLASH",
    "RESTART_NOTICE",
    "ERROR_FLAG_OFF",
    "ERROR_FORBIDDEN",
    "ERROR_CSRF",
    "ERROR_VALIDATION",
    "ERROR_GENERIC",
]
