"""Model Catalog SSR form — metadata-driven built-in model selection (PROV-03).

Renders API metadata-driven ``vendor_id`` / ``model_id`` / ``supports_vision``
rows, provider-instance selection, and exact UI-SPEC copy. Catalog rows display
source-grounded model IDs and supports_vision badges (words plus color, never
color alone). The catalog save form POSTs an object body matching Phase 74
``PUT /config/catalog`` (``{"provider_id": "...", "model_id": "..."}``).

No live provider, WeCom, QQ, or lawyer-trial acceptance is claimed.
"""

from __future__ import annotations

import html
from typing import Any, Mapping
from urllib.parse import parse_qs

from rbac import Identity

from .boundary import AdminUiBoundary
from .dashboard import _page_template

# UI-SPEC copy (exact strings)
PAGE_TITLE = "Model Catalog"
PRIMARY_CTA = "Save catalog selection"
NAV_LABEL = "Model Catalog"
CATALOG_PANEL_HEADING = "Main model selection"
SELECTION_STATUS_SET = "Main model: {provider_id} / {model_id}"
SELECTION_STATUS_UNSET = "No main model selected"
VISION_BADGE_YES = "Vision: supported"
VISION_BADGE_NO = "Vision: not supported"
EMPTY_HEADING = "No main model selected"
EMPTY_BODY = (
    "Pick a main model from the built-in catalog below. Vision capability is "
    "shown per model for Phase 77 routing."
)
NO_PROVIDERS_NOTE = "Add a provider in Provider Config before selecting a main model."
RESTART_NOTICE = (
    "Changes persist in the operator config store. Runtime reads config at "
    "startup; restart to apply."
)
SUCCESS_FLASH = (
    "Catalog selection saved. Restart runtime to apply (MVP — no hot-reload)."
)
ERROR_VALIDATION = (
    "Invalid secret reference or provider shape. Use `env:NAME`, a bare env key, "
    "or `secret://…` for refs. Raw secrets are rejected."
)
ERROR_FLAG_OFF = (
    "Operator config writes are disabled (`operator_config_enabled` is OFF). "
    "Enable the flag, then retry."
)
ERROR_FORBIDDEN = "You do not have permission to change provider or catalog config."
ERROR_GENERIC = "Could not save catalog selection. Check the message above and try again."

_ROUTE_CATALOG = "/config/catalog"


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _flash_html(flash: str | None, *, kind: str) -> str:
    if not flash:
        return ""
    css = "status-ok" if kind == "success" else "error"
    return f'    <p class="{css}" role="status">{_esc(flash)}</p>\n'


def _catalog_entries(api_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = api_data.get("catalog_entries")
    if isinstance(raw, list):
        return [dict(e) for e in raw if isinstance(e, Mapping)]
    return []


def _providers_list(api_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = api_data.get("providers")
    if isinstance(raw, list):
        return [dict(p) for p in raw if isinstance(p, Mapping)]
    return []


def _selection(api_data: Mapping[str, Any]) -> dict[str, Any]:
    data = api_data.get("data")
    if isinstance(data, Mapping):
        return dict(data)
    return {}


def _metadata(api_data: Mapping[str, Any]) -> dict[str, Any]:
    raw = api_data.get("metadata")
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _vision_badge(supports_vision: bool) -> str:
    if supports_vision:
        return (
            f'<span class="badge-vision-yes">{_esc(VISION_BADGE_YES)}</span>'
        )
    return (
        f'<span class="badge-vision-no">{_esc(VISION_BADGE_NO)}</span>'
    )


def _render_catalog_row(
    entry: Mapping[str, Any],
    selected_model: str | None,
) -> str:
    model_id = str(entry.get("model_id", "") or "")
    supports_vision = bool(entry.get("supports_vision", False))
    description = entry.get("description")
    checked = " checked" if selected_model and model_id == selected_model else ""
    badge = _vision_badge(supports_vision)
    desc_html = f' <span class="empty">{_esc(str(description))}</span>' if description else ""
    return (
        f'      <p class="catalog-row">'
        f'<label class="field-check">'
        f'<input type="radio" name="model_id" value="{_esc(model_id)}"{checked}> '
        f'<span>{_esc(model_id)}</span> '
        f"{badge}{desc_html}"
        f"</label></p>"
    )


def _render_provider_selector(
    providers: list[dict[str, Any]],
    selected_provider: str | None,
    *,
    disabled: bool,
) -> str:
    if not providers:
        return f'    <p class="empty">{_esc(NO_PROVIDERS_NOTE)}</p>'
    if len(providers) == 1:
        pid = str(providers[0].get("provider_id", "") or "")
        return (
            f'      <input type="hidden" name="provider_id" value="{_esc(pid)}">'
        )
    options: list[str] = []
    for provider in providers:
        pid = str(provider.get("provider_id", "") or "")
        selected = " selected" if selected_provider and pid == selected_provider else ""
        options.append(
            f'<option value="{_esc(pid)}"{selected}>{_esc(pid)}</option>'
        )
    disabled_attr = " disabled" if disabled else ""
    return (
        f'      <p class="field">\n'
        f'        <label for="provider_id">Provider</label>\n'
        f'        <select id="provider_id" name="provider_id"{disabled_attr}>\n'
        + "\n".join(f"          {opt}" for opt in options)
        + "\n        </select>\n"
        f"      </p>"
    )


def render_catalog_form(
    api_data: Mapping[str, Any],
    *,
    csrf_token: str | None = None,
    read_only: bool = False,
    flash: str | None = None,
    flash_kind: str = "success",
    error_message: str | None = None,
) -> str:
    """Render the Model Catalog form body (inside page section)."""
    metadata = _metadata(api_data)
    entries = _catalog_entries(api_data)
    providers = _providers_list(api_data)
    selection = _selection(api_data)
    selected_provider = selection.get("provider_id")
    if selected_provider is not None:
        selected_provider = str(selected_provider)
    selected_model = selection.get("model_id")
    if selected_model is not None:
        selected_model = str(selected_model)
    flag_off = not bool(metadata.get("operator_config_enabled", True))
    disabled = read_only or flag_off

    parts: list[str] = []
    if error_message:
        parts.append(_flash_html(error_message, kind="error"))
    elif flash:
        parts.append(_flash_html(flash, kind=flash_kind))
    if flag_off and not error_message:
        parts.append(_flash_html(ERROR_FLAG_OFF, kind="error"))

    parts.append(f'    <p class="empty restart-notice">{_esc(RESTART_NOTICE)}</p>')

    # Selection status line
    if selected_provider and selected_model:
        status_text = SELECTION_STATUS_SET.format(
            provider_id=selected_provider, model_id=selected_model
        )
        parts.append(f'    <p class="status-ok">{_esc(status_text)}</p>')
    else:
        parts.append(f'    <p class="empty">{_esc(SELECTION_STATUS_UNSET)}</p>')

    parts.append(f'    <form method="post" action="{_esc(_ROUTE_CATALOG)}" class="catalog-form">')
    token = csrf_token or ""
    parts.append(
        f'      <input type="hidden" name="csrf_token" value="{_esc(token)}">'
    )

    # Provider selector
    parts.append(_render_provider_selector(providers, selected_provider, disabled=disabled))

    # Catalog panel
    parts.append('    <div class="card">')
    parts.append(f"      <h3>{_esc(CATALOG_PANEL_HEADING)}</h3>")
    if not entries:
        parts.append(f'      <p class="empty">{_esc(EMPTY_HEADING)}</p>')
        parts.append(f'      <p class="empty">{_esc(EMPTY_BODY)}</p>')
    else:
        for entry in entries:
            parts.append(_render_catalog_row(entry, selected_model))
    parts.append("    </div>")

    disabled_attr = " disabled" if disabled else ""
    parts.append(
        f'      <button type="submit" class="btn-primary"{disabled_attr}>'
        f"{_esc(PRIMARY_CTA)}</button>"
    )
    parts.append("    </form>")
    return "\n".join(parts)


def render_catalog_page(
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
    """Render the full Model Catalog HTML page."""
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
        if isinstance(api_data.get("data"), Mapping):
            body = render_catalog_form(
                api_data,
                csrf_token=csrf_token,
                read_only=True,
                error_message=error_message,
            )
        return _page_template(PAGE_TITLE, body, identity)

    body = render_catalog_form(
        api_data,
        csrf_token=csrf_token,
        read_only=read_only,
        flash=flash,
        flash_kind=flash_kind,
        error_message=error_message,
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


def parse_catalog_form(
    form: Mapping[str, Any] | str | bytes,
) -> dict[str, Any]:
    """Parse urlencoded form fields into a Phase 74 ``PUT /config/catalog`` body.

    Returns ``{"provider_id": ..., "model_id": ...}``. Empty values become
    ``None``. Never resolves secrets.
    """
    if isinstance(form, (str, bytes)):
        text = form.decode("utf-8") if isinstance(form, bytes) else form
        parsed: dict[str, list[str]] = parse_qs(text, keep_blank_values=True)
        form_map: Mapping[str, Any] = parsed
    else:
        form_map = form

    provider_id = _form_get(form_map, "provider_id")
    model_id = _form_get(form_map, "model_id")
    return {
        "provider_id": provider_id,
        "model_id": model_id,
    }


# Alias expected by Wave 0 scaffold discovery
render = render_catalog_page

__all__ = [
    "parse_catalog_form",
    "render",
    "render_catalog_form",
    "render_catalog_page",
    "PRIMARY_CTA",
    "PAGE_TITLE",
    "SUCCESS_FLASH",
    "RESTART_NOTICE",
    "ERROR_FLAG_OFF",
    "ERROR_FORBIDDEN",
    "ERROR_VALIDATION",
    "ERROR_GENERIC",
]
