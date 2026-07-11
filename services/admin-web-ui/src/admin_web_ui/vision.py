"""Vision Config SSR form — metadata-driven routing-mode and provider/model selection (VIS-01).

Renders the Phase 77 Vision Config page at ``/config/vision``. The form is
stdlib-only escaped HTML with no JavaScript, React, or shadcn. It consumes
Plan 77-02 API metadata (``routing_modes``, ``vision_configured``,
``vision_status``, provider list, catalog entries) and posts to the
admin-console-api ``PUT /config/vision`` endpoint.

No live provider, WeCom, QQ, or lawyer-trial acceptance is claimed.
"""

from __future__ import annotations

import html
from typing import Any, Mapping
from urllib.parse import parse_qs

from rbac import Identity

from .boundary import AdminUiBoundary
from .dashboard import _page_template, _render_gate_honesty_banner

# UI-SPEC copy (exact strings)
PAGE_TITLE = "Vision Config"
PRIMARY_CTA = "Save vision config"
NAV_LABEL = "Vision Config"

ROUTING_MODE_PANEL_HEADING = "Routing mode"
ROUTING_MODE_LABEL = "Routing mode"
ROUTING_MODE_HELP = (
    "Choose how image-bearing turns are routed. Text-only turns never invoke the vision model."
)
ROUTING_MODE_OPTION_AUTO = (
    "Auto — multimodal main if it supports vision, else vision→main mix"
)
ROUTING_MODE_OPTION_ALWAYS = (
    "Always preprocess — always route images through the vision model, then main"
)
ROUTING_MODE_OPTION_MAIN_ONLY = (
    "Main only — never invoke a vision model; fail-closed on images the main model cannot read"
)
ROUTING_MODE_DESCRIPTION_AUTO = (
    "On image-bearing turns, the runtime uses the multimodal main model when it supports vision; "
    "otherwise it routes the image through the dedicated vision model and forwards the result to main."
)
ROUTING_MODE_DESCRIPTION_ALWAYS = (
    "On image-bearing turns, the runtime always routes the image through the dedicated vision model, "
    "then forwards its output to main."
)
ROUTING_MODE_DESCRIPTION_MAIN_ONLY = (
    "On image-bearing turns, the runtime never invokes a vision model. "
    "If the main model does not support vision, the turn fails closed with an InkStatute-owned notice "
    "(never a silent image drop)."
)

VISION_PROVIDER_MODEL_PANEL_HEADING = "Vision provider and model"
VISION_PROVIDER_LABEL = "Vision provider"
VISION_MODEL_LABEL = "Vision model"
VISION_PROVIDER_MODEL_HELP = (
    "Optional dedicated vision provider and model used when the routing mode needs a vision step. "
    "Leave blank to skip a dedicated vision path."
)

VISION_STATUS_CONFIGURED = "Vision: {vision_provider_id} / {vision_model_id}"
VISION_STATUS_NOT_CONFIGURED = "No vision model selected"
VISION_STATUS_NOT_REQUIRED = "Vision model not required (main only)"

PROBE_BUTTON_LABEL = "Probe vision connection"
PROBE_HELP = (
    "Non-destructive connectivity check against the stored vision target. "
    "Fail-closes on missing refs. Never logs response bodies or resolved secrets."
)
PROBE_RESULT_SUCCESS = (
    "Probe succeeded — vision provider reachable (no response body logged)."
)
PROBE_RESULT_FAIL_NOT_CONFIGURED = (
    "Probe skipped — vision provider or model is not configured. "
    "Select a vision provider and model, then retry."
)
PROBE_RESULT_FAIL_GENERIC = (
    "Probe failed — see the message above. No secrets or response bodies were logged."
)

NO_PROVIDERS_NOTE = "Add a provider in Provider Config before selecting a vision model."
CUSTOM_PROVIDER_NOTE = (
    "Custom provider models are not in the built-in catalog. Add the model ID to the provider's "
    "allowlist in Provider Config; vision routing for custom models is not supported in this MVP."
)

BLANK_OPTION = "— none —"

RESTART_NOTICE = (
    "Changes persist in the operator config store. Runtime reads config at startup; restart to apply."
)
SUCCESS_FLASH = (
    "Vision config saved. Restart runtime to apply (MVP — no hot-reload)."
)

ERROR_VALIDATION = (
    "Invalid vision routing mode or selection. Routing mode must be `auto`, `always_preprocess`, "
    "or `main_only`. Vision provider and model must be a complete pair or both blank."
)
ERROR_FLAG_OFF = (
    "Operator config writes are disabled (`operator_config_enabled` is OFF). "
    "Enable the flag, then retry."
)
ERROR_FORBIDDEN = "You do not have permission to change vision config."
ERROR_GENERIC = "Could not save vision config. Check the message above and try again."

_ROUTE_VISION = "/config/vision"
_ROUTE_PROBE = "/config/providers/probe"
_VALID_ROUTING_MODES = ("auto", "always_preprocess", "main_only")
_BUILTIN_KINDS = frozenset({"openai", "anthropic"})


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _metadata(api_data: Mapping[str, Any]) -> dict[str, Any]:
    raw = api_data.get("metadata")
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _selection(api_data: Mapping[str, Any]) -> dict[str, Any]:
    data = api_data.get("data")
    if isinstance(data, Mapping):
        return dict(data)
    return {}


def _providers_list(api_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = api_data.get("providers")
    if isinstance(raw, list):
        return [dict(p) for p in raw if isinstance(p, Mapping)]
    return []


def _catalog_entries(api_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = api_data.get("catalog_entries")
    if isinstance(raw, list):
        return [dict(e) for e in raw if isinstance(e, Mapping)]
    return []


def _routing_mode_description(mode: str) -> str:
    if mode == "always_preprocess":
        return ROUTING_MODE_DESCRIPTION_ALWAYS
    if mode == "main_only":
        return ROUTING_MODE_DESCRIPTION_MAIN_ONLY
    return ROUTING_MODE_DESCRIPTION_AUTO


def _flash_html(flash: str | None, *, kind: str) -> str:
    if not flash:
        return ""
    css = "status-ok" if kind == "success" else "error"
    return f'    <p class="{css}" role="status">{_esc(flash)}</p>\n'


def _probe_result_html(result: Mapping[str, Any] | None) -> str:
    if not result:
        return ""
    status = str(result.get("status", "")).lower()
    if status == "ok":
        copy = PROBE_RESULT_SUCCESS
        css = "status-ok"
    elif status == "not_configured":
        copy = PROBE_RESULT_FAIL_NOT_CONFIGURED
        css = "empty"
    elif status == "fail":
        copy = PROBE_RESULT_FAIL_GENERIC
        css = "status-err"
    else:
        copy = PROBE_RESULT_FAIL_GENERIC
        css = "status-err"
    return (
        f'    <div class="probe-result">\n'
        f'      <p class="{css}" role="status">{_esc(copy)}</p>\n'
        f"    </div>\n"
    )


def _selected_routing_mode(api_data: Mapping[str, Any]) -> str:
    selection = _selection(api_data)
    mode = selection.get("routing_mode")
    if mode in _VALID_ROUTING_MODES:
        return str(mode)
    return "auto"


def _vision_status_line(
    mode: str, provider_id: str | None, model_id: str | None
) -> tuple[str, str]:
    if mode == "main_only":
        return VISION_STATUS_NOT_REQUIRED, "empty"
    if provider_id and model_id:
        return (
            VISION_STATUS_CONFIGURED.format(
                vision_provider_id=provider_id, vision_model_id=model_id
            ),
            "status-ok",
        )
    return VISION_STATUS_NOT_CONFIGURED, "empty"


def _render_routing_mode_card(
    mode: str,
    *,
    disabled: bool,
) -> str:
    disabled_attr = " disabled" if disabled else ""
    options = [
        ("auto", ROUTING_MODE_OPTION_AUTO),
        ("always_preprocess", ROUTING_MODE_OPTION_ALWAYS),
        ("main_only", ROUTING_MODE_OPTION_MAIN_ONLY),
    ]
    option_tags = "\n".join(
        f'          <option value="{_esc(value)}"{" selected" if value == mode else ""}>'
        f"{_esc(label)}</option>"
        for value, label in options
    )
    description = _routing_mode_description(mode)
    return (
        f'    <div class="card">\n'
        f"      <h3>{_esc(ROUTING_MODE_PANEL_HEADING)}</h3>\n"
        f'      <p class="field">\n'
        f'        <label for="routing_mode">{_esc(ROUTING_MODE_LABEL)}</label>\n'
        f'        <select id="routing_mode" name="routing_mode" aria-describedby="routing-mode-description"'
        f' autocomplete="off"{disabled_attr}>\n'
        f"{option_tags}\n"
        f"        </select>\n"
        f'        <p id="routing-mode-description" class="empty">{_esc(description)}</p>\n'
        f"      </p>\n"
        f"    </div>"
    )


def _render_vision_status_line(
    mode: str, provider_id: str | None, model_id: str | None
) -> str:
    text, css = _vision_status_line(mode, provider_id, model_id)
    return f'    <p class="{css}" role="status">{_esc(text)}</p>\n'


def _render_provider_select(
    providers: list[dict[str, Any]],
    selected_provider_id: str | None,
    *,
    disabled: bool,
) -> str:
    disabled_attr = " disabled" if disabled else ""
    options: list[str] = [
        f'          <option value=""{" selected" if not selected_provider_id else ""}>'
        f"{_esc(BLANK_OPTION)}</option>"
    ]
    if not providers:
        note = NO_PROVIDERS_NOTE
    else:
        for provider in providers:
            pid = str(provider.get("provider_id", "") or "")
            if not pid:
                continue
            selected = " selected" if selected_provider_id and pid == selected_provider_id else ""
            options.append(
                f'          <option value="{_esc(pid)}"{selected}>{_esc(pid)}</option>'
            )
        note = ""

    select_html = (
        f'      <p class="field">\n'
        f'        <label for="vision_provider_id">{_esc(VISION_PROVIDER_LABEL)}</label>\n'
        f'        <select id="vision_provider_id" name="vision_provider_id"'
        f' autocomplete="off"{disabled_attr}>\n'
        + "\n".join(options)
        + "\n        </select>\n"
    )
    if note:
        select_html += f'        <span class="empty">{_esc(note)}</span>\n'
    select_html += "      </p>"
    return select_html


def _render_model_select(
    providers: list[dict[str, Any]],
    catalog_entries: list[dict[str, Any]],
    selected_provider_id: str | None,
    selected_model_id: str | None,
    *,
    disabled: bool,
) -> str:
    disabled_attr = " disabled" if disabled else ""

    selected_kind = None
    for provider in providers:
        pid = str(provider.get("provider_id", "") or "")
        if pid and selected_provider_id and pid == selected_provider_id:
            selected_kind = str(provider.get("kind", "") or "")
            break

    options: list[str] = [
        f'          <option value=""{" selected" if not selected_model_id else ""}>'
        f"{_esc(BLANK_OPTION)}</option>"
    ]

    if selected_kind in _BUILTIN_KINDS:
        for entry in catalog_entries:
            vendor_id = str(entry.get("vendor_id", "") or "")
            if vendor_id != selected_kind:
                continue
            model_id = str(entry.get("model_id", "") or "")
            selected = " selected" if selected_model_id and model_id == selected_model_id else ""
            options.append(
                f'          <option value="{_esc(model_id)}"{selected}>{_esc(model_id)}</option>'
            )
        note = ""
    elif selected_kind == "custom":
        note = CUSTOM_PROVIDER_NOTE
    else:
        note = ""

    select_html = (
        f'      <p class="field">\n'
        f'        <label for="vision_model_id">{_esc(VISION_MODEL_LABEL)}</label>\n'
        f'        <select id="vision_model_id" name="vision_model_id"'
        f' autocomplete="off"{disabled_attr}>\n'
        + "\n".join(options)
        + "\n        </select>\n"
    )
    if note:
        # Text content does not need quote escaping; preserve apostrophes in UI-SPEC copy.
        select_html += f'        <span class="empty">{html.escape(note, quote=False)}</span>\n'
    select_html += "      </p>"
    return select_html


def _render_probe_form(
    *,
    disabled: bool,
    probe_csrf_token: str | None,
) -> str:
    disabled_attr = " disabled" if disabled else ""
    token = probe_csrf_token or ""
    return (
        f'    <form method="post" action="{_esc(_ROUTE_PROBE)}" class="probe-form">\n'
        f'      <input type="hidden" name="csrf_token" value="{_esc(token)}">\n'
        f'      <input type="hidden" name="target" value="vision">\n'
        f'      <input type="hidden" name="return_to" value="vision">\n'
        f'      <button type="submit" class="btn-primary"{disabled_attr}>'
        f"{_esc(PROBE_BUTTON_LABEL)}</button>\n"
        f"    </form>"
    )


def render_vision_form(
    api_data: Mapping[str, Any],
    *,
    csrf_token: str | None = None,
    probe_csrf_token: str | None = None,
    read_only: bool = False,
    flash: str | None = None,
    flash_kind: str = "success",
    error_message: str | None = None,
    probe_result: Mapping[str, Any] | None = None,
) -> str:
    """Render the Vision Config form body (inside page section)."""
    metadata = _metadata(api_data)
    selection = _selection(api_data)
    providers = _providers_list(api_data)
    catalog_entries = _catalog_entries(api_data)

    mode = _selected_routing_mode(api_data)
    selected_provider_id = selection.get("vision_provider_id")
    selected_provider_id = str(selected_provider_id) if selected_provider_id else None
    selected_model_id = selection.get("vision_model_id")
    selected_model_id = str(selected_model_id) if selected_model_id else None
    main_model_id = selection.get("main_model_id")
    main_model_id = str(main_model_id) if main_model_id else None

    flag_off = not bool(metadata.get("operator_config_enabled", True))
    mode_disabled = read_only or flag_off
    vision_disabled = read_only or flag_off or mode == "main_only"

    parts: list[str] = [_render_gate_honesty_banner()]
    if error_message:
        parts.append(_flash_html(error_message, kind="error"))
    if flash:
        parts.append(_flash_html(flash, kind=flash_kind))
    if flag_off and not error_message:
        parts.append(_flash_html(ERROR_FLAG_OFF, kind="error"))

    if probe_result:
        parts.append(_probe_result_html(probe_result))

    parts.append(f'    <p class="empty restart-notice">{_esc(RESTART_NOTICE)}</p>')

    parts.append(_render_vision_status_line(mode, selected_provider_id, selected_model_id))

    parts.append(f'    <form method="post" action="{_esc(_ROUTE_VISION)}" class="vision-form">')
    token = csrf_token or ""
    parts.append(
        f'      <input type="hidden" name="csrf_token" value="{_esc(token)}">'
    )
    parts.append(
        f'      <input type="hidden" name="main_model_id" value="{_esc(main_model_id if main_model_id else "")}">'
    )

    parts.append(_render_routing_mode_card(mode, disabled=mode_disabled))

    parts.append(f'    <div class="card">')
    parts.append(f"      <h3>{_esc(VISION_PROVIDER_MODEL_PANEL_HEADING)}</h3>")
    parts.append(f'      <p class="empty">{_esc(VISION_PROVIDER_MODEL_HELP)}</p>')
    parts.append(
        _render_provider_select(
            providers,
            selected_provider_id,
            disabled=vision_disabled,
        )
    )
    parts.append(
        _render_model_select(
            providers,
            catalog_entries,
            selected_provider_id,
            selected_model_id,
            disabled=vision_disabled,
        )
    )
    parts.append(f"    </div>")

    save_disabled = " disabled" if (read_only or flag_off) else ""
    parts.append(
        f'      <button type="submit" class="btn-primary"{save_disabled}>'
        f"{_esc(PRIMARY_CTA)}</button>"
    )
    parts.append("    </form>")

    parts.append(_render_probe_form(disabled=vision_disabled, probe_csrf_token=probe_csrf_token))

    return "\n".join(parts)


def render_vision_page(
    api_data: Mapping[str, Any],
    identity: Identity | None = None,
    boundary: AdminUiBoundary | None = None,
    *,
    csrf_token: str | None = None,
    probe_csrf_token: str | None = None,
    read_only: bool = False,
    flash: str | None = None,
    flash_kind: str = "success",
    error_message: str | None = None,
    probe_result: Mapping[str, Any] | None = None,
) -> str:
    """Render the full Vision Config HTML page."""
    del boundary  # reserved for free-text API messages; form uses escaped copy
    if "error" in api_data and not flash and error_message is None:
        err = api_data["error"]
        if isinstance(err, dict):
            code = str(err.get("code", "unknown"))
            if code in ("forbidden", "operator_config_disabled"):
                error_message = ERROR_FORBIDDEN if code == "forbidden" else ERROR_FLAG_OFF
                read_only = True
            elif code == "invalid_config":
                error_message = ERROR_VALIDATION
            else:
                error_message = ERROR_GENERIC
        else:
            error_message = ERROR_GENERIC

    body = render_vision_form(
        api_data,
        csrf_token=csrf_token,
        probe_csrf_token=probe_csrf_token,
        read_only=read_only,
        flash=flash,
        flash_kind=flash_kind,
        error_message=error_message,
        probe_result=probe_result,
    )
    return _page_template(PAGE_TITLE, body, identity)


def _form_get(form: Mapping[str, Any], key: str) -> str | None:
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


def parse_vision_form(
    form: Mapping[str, Any] | str | bytes,
) -> dict[str, Any]:
    """Parse urlencoded form fields into a Phase 77 ``PUT /config/vision`` body.

    Returns ``{"routing_mode": ..., "main_model_id": ..., "vision_model_id": ...,
    "vision_provider_id": ...}``. Empty values become ``None``. Never resolves
    secrets.
    """
    if isinstance(form, (str, bytes)):
        text = form.decode("utf-8") if isinstance(form, bytes) else form
        parsed: dict[str, list[str]] = parse_qs(text, keep_blank_values=True)
        form_map: Mapping[str, Any] = parsed
    else:
        form_map = form

    return {
        "routing_mode": _form_get(form_map, "routing_mode"),
        "main_model_id": _form_get(form_map, "main_model_id"),
        "vision_model_id": _form_get(form_map, "vision_model_id"),
        "vision_provider_id": _form_get(form_map, "vision_provider_id"),
    }


# Alias expected by Wave 0 scaffold discovery
render = render_vision_page

__all__ = [
    "parse_vision_form",
    "render",
    "render_vision_form",
    "render_vision_page",
    "PRIMARY_CTA",
    "PAGE_TITLE",
    "SUCCESS_FLASH",
    "RESTART_NOTICE",
    "ERROR_FLAG_OFF",
    "ERROR_FORBIDDEN",
    "ERROR_VALIDATION",
    "ERROR_GENERIC",
    "NAV_LABEL",
    "BLANK_OPTION",
    "CUSTOM_PROVIDER_NOTE",
    "NO_PROVIDERS_NOTE",
    "VISION_STATUS_CONFIGURED",
    "VISION_STATUS_NOT_CONFIGURED",
    "VISION_STATUS_NOT_REQUIRED",
    "PROBE_BUTTON_LABEL",
    "ROUTING_MODE_OPTION_AUTO",
    "ROUTING_MODE_OPTION_ALWAYS",
    "ROUTING_MODE_OPTION_MAIN_ONLY",
]
