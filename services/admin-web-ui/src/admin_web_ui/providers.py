"""Provider Config SSR form — metadata-driven built-in/custom provider registry.

Renders API metadata-driven built-in vendor profiles (read-only canonical URL)
and custom OpenAI-compatible providers (editable URL + allowlist). Provider save
controls belong to one ``/config/providers`` form; each Probe connection action
is a submit button with ``formaction`` posting to ``/config/providers/probe``
with ``target=main`` (or ``target=vision`` when configured). No nested forms.

Refs-only: ``api_key_ref`` is a text reference field — never a resolved secret.
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
PAGE_TITLE = "Provider Config"
PRIMARY_CTA = "Save provider config"
NAV_LABEL = "Provider Config"
BUILTIN_VENDOR_LABEL = "Built-in vendor"
CUSTOM_PROVIDER_LABEL = "Custom OpenAI-compatible"
PROVIDER_KIND_HELP = (
    "Choose a built-in vendor profile or define a custom OpenAI-compatible endpoint."
)
API_BASE_URL_LABEL = "API base URL"
API_KEY_REF_LABEL = "API key ref"
REF_HELP = (
    "Secret reference only (`env:NAME`, bare `ENV_NAME`, or `secret://path/segments`). "
    "Never paste raw tokens."
)
REF_STATUS_CONFIGURED = "Configured (ref stored)"
REF_STATUS_MISSING = "Not set"
MODEL_ALLOWLIST_LABEL = "Model allowlist"
MODEL_ALLOWLIST_HELP = (
    "Comma-separated model IDs this provider may serve. Built-in vendors ship a "
    "preset catalog; custom providers require an explicit allowlist."
)
BUILTIN_ALLOWLIST_NOTE = "Built-in catalog provided — see Model Catalog."
PROBE_BUTTON_LABEL = "Probe connection"
PROBE_HELP = (
    "Non-destructive connectivity check. Fail-closes on missing refs. "
    "Never logs response bodies or resolved secrets."
)
PROBE_RESULT_SUCCESS = (
    "Probe succeeded — provider reachable (no response body logged)."
)
PROBE_RESULT_FAIL_MISSING_REF = (
    "Probe failed — API key ref is not set. Configure the ref, then retry."
)
PROBE_RESULT_FAIL_NETWORK = (
    "Probe failed — could not reach provider endpoint. Check `api_base_url` and network, then retry."
)
PROBE_RESULT_FAIL_GENERIC = (
    "Probe failed — see the message above. No secrets or response bodies were logged."
)
EMPTY_HEADING = "No providers configured yet"
EMPTY_BODY = (
    "Defaults are OFF. Add a built-in vendor or custom OpenAI-compatible provider "
    "below, then Save provider config."
)
RESTART_NOTICE = (
    "Changes persist in the operator config store. Runtime reads config at "
    "startup; restart to apply."
)
SUCCESS_FLASH = (
    "Provider config saved. Restart runtime to apply (MVP — no hot-reload)."
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
ERROR_GENERIC = "Could not save provider config. Check the message above and try again."

_ROUTE_PROVIDERS = "/config/providers"
_ROUTE_PROBE = "/config/providers/probe"
_BUILTIN_KINDS = frozenset({"openai", "anthropic"})


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _ref_status(configured: bool) -> tuple[str, str]:
    if configured:
        return REF_STATUS_CONFIGURED, "status-ok"
    return REF_STATUS_MISSING, "empty"


def _flash_html(flash: str | None, *, kind: str) -> str:
    if not flash:
        return ""
    css = "status-ok" if kind == "success" else "error"
    return f'    <p class="{css}" role="status">{_esc(flash)}</p>\n'


def _probe_result_html(result: Mapping[str, Any] | None) -> str:
    if not result:
        return ""
    status = str(result.get("status", "")).lower()
    target = str(result.get("target", "")).lower()
    if status == "ok":
        copy = PROBE_RESULT_SUCCESS
        css = "status-ok"
    elif status == "not_configured":
        copy = f"Probe target '{target}' is not configured. Select a main model in Model Catalog first."
        css = "empty"
    elif status == "fail":
        copy = PROBE_RESULT_FAIL_GENERIC
        css = "status-err"
    else:
        copy = PROBE_RESULT_FAIL_GENERIC
        css = "status-err"
    return (
        f'    <div class="probe-result">\n'
        f'      <p class="{css}">{_esc(copy)}</p>\n'
        f"    </div>\n"
    )


def _vendor_profile_map(
    metadata: Mapping[str, Any] | None,
) -> dict[str, dict[str, str]]:
    """Build a vendor_id → profile dict from API ``builtin_vendor_profiles`` metadata."""
    profiles: dict[str, dict[str, str]] = {}
    if metadata is None:
        return profiles
    raw = metadata.get("builtin_vendor_profiles")
    if not isinstance(raw, list):
        return profiles
    for entry in raw:
        if isinstance(entry, Mapping):
            vid = entry.get("vendor_id")
            if isinstance(vid, str):
                profiles[vid] = {
                    "vendor_id": vid,
                    "api_base_url": str(entry.get("api_base_url", "")),
                    "default_key_ref_env": str(entry.get("default_key_ref_env", "")),
                }
    return profiles


def _provider_list(api_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    data = api_data.get("data")
    if isinstance(data, list):
        return [dict(p) for p in data if isinstance(p, Mapping)]
    return []


def _probe_targets(api_data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = api_data.get("probe_targets")
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _metadata(api_data: Mapping[str, Any]) -> dict[str, Any]:
    raw = api_data.get("metadata")
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _render_kind_selector(
    index: int,
    kind: str,
    profiles: dict[str, dict[str, str]],
    *,
    disabled: bool,
) -> str:
    options: list[str] = []
    for vid in sorted(profiles):
        selected = " selected" if kind == vid else ""
        options.append(
            f'<option value="{_esc(vid)}"{selected}>{_esc(vid)}</option>'
        )
    custom_selected = " selected" if kind == "custom" else ""
    options.append(
        f'<option value="custom"{custom_selected}>{_esc(CUSTOM_PROVIDER_LABEL)}</option>'
    )
    disabled_attr = " disabled" if disabled else ""
    name = f"providers[{index}].kind"
    return (
        f'      <p class="field">\n'
        f'        <label for="{_esc(name)}">Provider kind</label>\n'
        f'        <select id="{_esc(name)}" name="{_esc(name)}"{disabled_attr}>\n'
        + "\n".join(f"          {opt}" for opt in options)
        + "\n        </select>\n"
        f'        <span class="empty">{_esc(PROVIDER_KIND_HELP)}</span>\n'
        f"      </p>"
    )


def _render_provider_card(
    index: int,
    provider: Mapping[str, Any],
    profiles: dict[str, dict[str, str]],
    *,
    disabled: bool,
) -> str:
    kind = str(provider.get("kind", "") or "")
    provider_id = str(provider.get("provider_id", "") or "")
    enabled = bool(provider.get("enabled", False))
    api_base_url = provider.get("api_base_url")
    api_key_ref = provider.get("api_key_ref")
    allowlist = provider.get("model_allowlist")
    is_builtin = kind in _BUILTIN_KINDS

    heading = (
        f"Provider: {_esc(provider_id)}" if provider_id else "New provider"
    )

    parts: list[str] = [
        '    <div class="card provider-panel">',
        f"      <h3>{heading}</h3>",
        _render_kind_selector(index, kind, profiles, disabled=disabled),
    ]

    # provider_id
    pid_name = f"providers[{index}].provider_id"
    parts.append(
        f'      <p class="field">\n'
        f'        <label for="{_esc(pid_name)}">Provider ID</label>\n'
        f'        <input class="ref-input" type="text" id="{_esc(pid_name)}" '
        f'name="{_esc(pid_name)}" value="{_esc(provider_id)}" autocomplete="off"{(" disabled" if disabled else "")}>\n'
        f"      </p>"
    )

    # enabled checkbox
    en_name = f"providers[{index}].enabled"
    checked = " checked" if enabled else ""
    parts.append(
        f'      <p class="field">\n'
        f'        <label class="field-check" for="{_esc(en_name)}">\n'
        f'          <input type="checkbox" id="{_esc(en_name)}" '
        f'name="{_esc(en_name)}" value="1"{checked}{(" disabled" if disabled else "")}> Enabled\n'
        f"        </label>\n"
        f"      </p>"
    )

    # api_base_url — read-only for built-in, editable for custom
    if is_builtin:
        profile = profiles.get(kind, {})
        canonical_url = profile.get("api_base_url", str(api_base_url or ""))
        url_id = f"providers[{index}].api_base_url"
        parts.append(
            f'      <p class="field">\n'
            f'        <label for="{_esc(url_id)}">{_esc(API_BASE_URL_LABEL)}</label>\n'
            f'        <span class="empty" id="{_esc(url_id)}">{_esc(canonical_url)}</span>\n'
            f"      </p>"
        )
    else:
        url_name = f"providers[{index}].api_base_url"
        url_value = str(api_base_url or "")
        parts.append(
            f'      <p class="field">\n'
            f'        <label for="{_esc(url_name)}">{_esc(API_BASE_URL_LABEL)}</label>\n'
            f'        <input class="ref-input" type="text" id="{_esc(url_name)}" '
            f'name="{_esc(url_name)}" value="{_esc(url_value)}" '
            f'placeholder="https://api.openai.com/v1" autocomplete="off"{(" disabled" if disabled else "")}>\n'
            f"      </p>"
        )

    # api_key_ref
    ref_name = f"providers[{index}].api_key_ref"
    ref_value = str(api_key_ref or "")
    ref_configured = bool(ref_value.strip())
    ref_text, ref_css = _ref_status(ref_configured)
    parts.append(
        f'      <p class="field">\n'
        f'        <label for="{_esc(ref_name)}">{_esc(API_KEY_REF_LABEL)}</label>\n'
        f'        <input class="ref-input" type="text" id="{_esc(ref_name)}" '
        f'name="{_esc(ref_name)}" value="{_esc(ref_value)}" '
        f'placeholder="env:INKSTATUTE_PROVIDER_OPENAI_KEY" autocomplete="off"{(" disabled" if disabled else "")}>\n'
        f'        <span class="{ref_css}">{_esc(ref_text)}</span>\n'
        f'        <span class="empty">{_esc(REF_HELP)}</span>\n'
        f"      </p>"
    )

    # model allowlist — read-only note for built-in, editable for custom
    if is_builtin:
        al_id = f"providers[{index}].model_allowlist"
        parts.append(
            f'      <p class="field">\n'
            f'        <label for="{_esc(al_id)}">{_esc(MODEL_ALLOWLIST_LABEL)}</label>\n'
            f'        <span class="empty" id="{_esc(al_id)}">{_esc(BUILTIN_ALLOWLIST_NOTE)}</span>\n'
            f"      </p>"
        )
    else:
        al_name = f"providers[{index}].model_allowlist"
        if isinstance(allowlist, (list, tuple)):
            al_value = ", ".join(str(m) for m in allowlist)
        else:
            al_value = str(allowlist or "")
        parts.append(
            f'      <p class="field">\n'
            f'        <label for="{_esc(al_name)}">{_esc(MODEL_ALLOWLIST_LABEL)}</label>\n'
            f'        <input class="ref-input" type="text" id="{_esc(al_name)}" '
            f'name="{_esc(al_name)}" value="{_esc(al_value)}" autocomplete="off"{(" disabled" if disabled else "")}>\n'
            f'        <span class="empty">{_esc(MODEL_ALLOWLIST_HELP)}</span>\n'
            f"      </p>"
        )

    parts.append("    </div>")
    return "\n".join(parts)


def _render_probe_section(
    probe_targets: Mapping[str, Any],
    *,
    disabled: bool,
    probe_csrf_token: str | None = None,
) -> str:
    """Render probe buttons in a separate form with its own route-bound CSRF token."""
    parts: list[str] = []
    parts.append(f'    <p class="empty">{_esc(PROBE_HELP)}</p>')

    has_buttons = False
    main_target = probe_targets.get("main") if isinstance(probe_targets, Mapping) else None
    if isinstance(main_target, Mapping):
        main_status = str(main_target.get("status", ""))
        if main_status == "configured":
            has_buttons = True
        else:
            parts.append(
                f'    <p class="empty">Main probe target: not_configured</p>'
            )

    vision_target = probe_targets.get("vision") if isinstance(probe_targets, Mapping) else None
    if isinstance(vision_target, Mapping):
        vision_status = str(vision_target.get("status", ""))
        if vision_status == "configured":
            has_buttons = True
        else:
            parts.append(
                f'    <p class="empty">Vision probe target: not_configured</p>'
            )

    if has_buttons and not disabled:
        parts.append(f'    <form method="post" action="{_esc(_ROUTE_PROBE)}" class="probe-form">')
        probe_token = probe_csrf_token or ""
        parts.append(
            f'      <input type="hidden" name="csrf_token" value="{_esc(probe_token)}">'
        )
        if isinstance(main_target, Mapping) and str(main_target.get("status", "")) == "configured":
            parts.append(
                f'      <button type="submit" '
                f'name="target" value="main" class="btn-primary">'
                f"{_esc(PROBE_BUTTON_LABEL)}</button>"
            )
        if isinstance(vision_target, Mapping) and str(vision_target.get("status", "")) == "configured":
            parts.append(
                f'      <button type="submit" '
                f'name="target" value="vision" class="btn-primary">'
                f"{_esc(PROBE_BUTTON_LABEL)}</button>"
            )
        parts.append("    </form>")

    return "\n".join(parts)


def render_providers_form(
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
    """Render the Provider Config form body (inside page section)."""
    metadata = _metadata(api_data)
    profiles = _vendor_profile_map(metadata)
    providers = _provider_list(api_data)
    probe_targets = _probe_targets(api_data)
    flag_off = not bool(metadata.get("operator_config_enabled", True))
    disabled = read_only or flag_off

    parts: list[str] = [_render_gate_honesty_banner()]
    if error_message:
        parts.append(_flash_html(error_message, kind="error"))
    elif flash:
        parts.append(_flash_html(flash, kind=flash_kind))
    if flag_off and not error_message:
        parts.append(_flash_html(ERROR_FLAG_OFF, kind="error"))

    if probe_result:
        parts.append(_probe_result_html(probe_result))

    parts.append(f'    <p class="empty restart-notice">{_esc(RESTART_NOTICE)}</p>')

    if not providers:
        parts.append(f'    <p class="empty"><strong>{_esc(EMPTY_HEADING)}</strong></p>')
        parts.append(f'    <p class="empty">{_esc(EMPTY_BODY)}</p>')

    parts.append(f'    <form method="post" action="{_esc(_ROUTE_PROVIDERS)}" class="providers-form">')
    token = csrf_token or ""
    parts.append(
        f'      <input type="hidden" name="csrf_token" value="{_esc(token)}">'
    )

    for index, provider in enumerate(providers):
        parts.append(_render_provider_card(index, provider, profiles, disabled=disabled))

    # Trailing blank card for adding a new provider (no JS).
    blank_index = len(providers)
    blank_provider: dict[str, Any] = {
        "kind": "openai" if profiles else "custom",
        "provider_id": "",
        "enabled": False,
        "api_base_url": None,
        "api_key_ref": None,
        "model_allowlist": [],
    }
    parts.append(_render_provider_card(blank_index, blank_provider, profiles, disabled=disabled))

    parts.append(f'      <p class="empty">{_esc(REF_HELP)}</p>')
    disabled_attr = " disabled" if disabled else ""
    parts.append(
        f'      <button type="submit" class="btn-primary"{disabled_attr}>'
        f"{_esc(PRIMARY_CTA)}</button>"
    )
    parts.append("    </form>")

    # Probe section (separate form with its own route-bound CSRF token, after save form).
    parts.append(_render_probe_section(probe_targets, disabled=disabled, probe_csrf_token=probe_csrf_token))

    return "\n".join(parts)


def render_providers_page(
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
    """Render the full Provider Config HTML page."""
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
        if isinstance(api_data.get("data"), list):
            body = render_providers_form(
                api_data,
                csrf_token=csrf_token,
                read_only=True,
                error_message=error_message,
            )
        return _page_template(PAGE_TITLE, body, identity, active_path="/config/providers")

    body = render_providers_form(
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


def _form_checkbox(form: Mapping[str, Any], key: str) -> bool:
    raw = form.get(key)
    if raw is None:
        return False
    if isinstance(raw, list):
        return any(str(v).strip() not in ("", "0", "false", "off") for v in raw)
    return str(raw).strip() not in ("", "0", "false", "off")


def _parse_provider_index(key: str) -> int | None:
    """Extract the numeric index from ``providers[N].field`` keys."""
    prefix = "providers["
    if not key.startswith(prefix):
        return None
    rest = key[len(prefix):]
    bracket = rest.find("]")
    if bracket == -1:
        return None
    try:
        return int(rest[:bracket])
    except ValueError:
        return None


def parse_providers_form(
    form: Mapping[str, Any] | str | bytes,
    *,
    vendor_profiles: Mapping[str, Mapping[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Parse urlencoded form fields into a Phase 74 ``PUT /config/providers`` list body.

    Built-in kinds (openai/anthropic) get their canonical ``api_base_url`` from
    trusted vendor profile metadata and an empty ``model_allowlist``. Custom
    kinds use the editable URL and comma-separated allowlist. Entries with a
    blank ``provider_id`` are dropped. Metadata is left absent for server-side
    merge. Never resolves secrets.
    """
    if isinstance(form, (str, bytes)):
        text = form.decode("utf-8") if isinstance(form, bytes) else form
        parsed: dict[str, list[str]] = parse_qs(text, keep_blank_values=True)
        form_map: Mapping[str, Any] = parsed
    else:
        form_map = form

    profiles = dict(vendor_profiles) if vendor_profiles else {}

    # Collect indices present in the form.
    indices: set[int] = set()
    for key in form_map:
        idx = _parse_provider_index(key)
        if idx is not None:
            indices.add(idx)

    providers: list[dict[str, Any]] = []
    for idx in sorted(indices):
        pid = _form_get(form_map, f"providers[{idx}].provider_id")
        if not pid:
            continue  # Drop blank provider_id cards.
        kind = _form_get(form_map, f"providers[{idx}].kind") or "custom"
        enabled = _form_checkbox(form_map, f"providers[{idx}].enabled")
        api_key_ref = _form_get(form_map, f"providers[{idx}].api_key_ref")

        if kind in _BUILTIN_KINDS:
            profile = profiles.get(kind, {})
            api_base_url = profile.get("api_base_url") or None
            model_allowlist: list[str] = []
        else:
            api_base_url = _form_get(form_map, f"providers[{idx}].api_base_url")
            raw_allowlist = _form_get(form_map, f"providers[{idx}].model_allowlist")
            if raw_allowlist:
                model_allowlist = [
                    m.strip() for m in raw_allowlist.split(",") if m.strip()
                ]
            else:
                model_allowlist = []

        provider: dict[str, Any] = {
            "provider_id": pid,
            "kind": kind,
            "enabled": enabled,
            "api_base_url": api_base_url,
            "api_key_ref": api_key_ref,
            "model_allowlist": model_allowlist,
        }
        providers.append(provider)

    return providers


# Alias expected by Wave 0 scaffold discovery
render = render_providers_page

__all__ = [
    "parse_providers_form",
    "render",
    "render_providers_form",
    "render_providers_page",
    "PRIMARY_CTA",
    "PAGE_TITLE",
    "SUCCESS_FLASH",
    "RESTART_NOTICE",
    "ERROR_FLAG_OFF",
    "ERROR_FORBIDDEN",
    "ERROR_VALIDATION",
    "ERROR_GENERIC",
]
