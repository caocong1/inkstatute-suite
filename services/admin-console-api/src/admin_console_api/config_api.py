"""Section-scoped /config/* GET and PUT handlers over OperatorConfigStore.

Pure ``(status, body)`` adapters — auth/RBAC live in ``api.handle_admin_*``.
Persist only through ``OperatorConfigStore.save``; never resolve secrets or
echo store filesystem paths.
"""

from __future__ import annotations

from typing import Any, Mapping

from inkstatute_operator_config import (
    OperatorConfigDisabledError,
    OperatorConfigStore,
    OperatorConfigStoreError,
    OperatorConfigValidationError,
)
from inkstatute_operator_config.store import document_from_payload, document_to_payload
from platform_runtime.feature_flags import RuntimeFeatureFlags

__all__ = [
    "CONFIG_SECTIONS",
    "handle_config_get",
    "handle_config_put",
]

CONFIG_SECTIONS = frozenset({"channels", "providers", "catalog", "vision"})


def handle_config_get(
    path: str,
    store: OperatorConfigStore,
    feature_flags: RuntimeFeatureFlags,
) -> tuple[int, dict[str, Any]]:
    """Return one config section as refs-only JSON (no full-document GET)."""
    section = _parse_section(path)
    if section is None:
        return 404, _not_found("route", path)

    try:
        document = store.load()
    except OperatorConfigValidationError as exc:
        return 400, _error("invalid_config", str(exc))
    except OperatorConfigStoreError as exc:
        return 500, _error("config_store_error", _safe_store_message(exc))

    payload = document_to_payload(document)
    body: dict[str, Any] = {
        "data": payload[section],
        "metadata": _config_metadata(feature_flags, section=section),
    }
    if section == "channels":
        body["effective"] = _channels_effective(payload["channels"], feature_flags)
    return 200, body


def handle_config_put(
    path: str,
    body: Any,
    store: OperatorConfigStore,
    feature_flags: RuntimeFeatureFlags,
) -> tuple[int, dict[str, Any]]:
    """Replace one config section and persist via OperatorConfigStore.save."""
    section = _parse_section(path)
    if section is None:
        return 404, _not_found("route", path)

    section_value, value_error = _normalize_section_body(section, body)
    if value_error is not None:
        return 400, value_error

    try:
        current = store.load()
    except OperatorConfigValidationError as exc:
        return 400, _error("invalid_config", str(exc))
    except OperatorConfigStoreError as exc:
        return 500, _error("config_store_error", _safe_store_message(exc))

    try:
        payload = document_to_payload(current)
        payload[section] = section_value
        updated = document_from_payload(payload)
    except OperatorConfigStoreError as exc:
        # Shape/parse faults from the request body are client errors (WR-01).
        return 400, _error("invalid_config", str(exc))

    try:
        store.save(updated, feature_flags=feature_flags)
    except OperatorConfigDisabledError:
        return 403, _error(
            "operator_config_disabled",
            "operator_config_enabled flag is False",
        )
    except OperatorConfigValidationError as exc:
        return 400, _error("invalid_config", str(exc))
    except OperatorConfigStoreError as exc:
        return 500, _error("config_store_error", _safe_store_message(exc))

    saved = document_to_payload(updated)
    body: dict[str, Any] = {
        "data": saved[section],
        "metadata": _config_metadata(feature_flags, section=section),
    }
    if section == "channels":
        body["effective"] = _channels_effective(saved["channels"], feature_flags)
    return 200, body


def _parse_section(path: str) -> str | None:
    """Accept only ``/config/{section}`` for section ∈ CONFIG_SECTIONS."""
    if not path.startswith("/config/"):
        return None
    remainder = path[len("/config/") :]
    if not remainder or "/" in remainder:
        return None
    if remainder not in CONFIG_SECTIONS:
        return None
    return remainder


def _normalize_section_body(
    section: str,
    body: Any,
) -> tuple[Any, dict[str, Any] | None]:
    """Prefer body == section JSON value; unwrap ``{section: value}`` once.

    Reject multi-section / full-document shaped bodies so a wrapped PUT cannot
    silently replace the section with schema defaults (CR-01).
    """
    if section == "providers":
        if isinstance(body, list):
            return body, None
        if isinstance(body, Mapping) and "providers" in body and isinstance(
            body["providers"], list
        ):
            foreign = (CONFIG_SECTIONS - {"providers"}) & set(body.keys())
            if foreign:
                return None, _error(
                    "invalid_config",
                    "providers body must be the section value only "
                    f"(unexpected keys: {sorted(foreign)})",
                )
            return body["providers"], None
        return None, _error(
            "invalid_config",
            "providers section body must be a list (or {\"providers\": [...]})",
        )

    if not isinstance(body, Mapping):
        return None, _error(
            "invalid_config",
            f"{section} section body must be a JSON object",
        )

    foreign = (CONFIG_SECTIONS - {section}) & set(body.keys())
    if foreign:
        return None, _error(
            "invalid_config",
            f"{section} body must be the section value only "
            f"(unexpected keys: {sorted(foreign)})",
        )

    if set(body.keys()) == {section} and isinstance(body[section], Mapping):
        return dict(body[section]), None

    return dict(body), None


def _config_metadata(
    feature_flags: RuntimeFeatureFlags,
    *,
    section: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": bool(feature_flags.operator_config_enabled),
        "read_only": False,
    }
    if section == "channels":
        # Restart-to-apply MVP (CHAN-03) — never claim live/hot-reload apply.
        metadata["apply_semantics"] = "restart_required"
    return metadata


_QQBOT_REF_FIELDS = (
    "app_id_ref",
    "app_secret_ref",
    "token_secret_ref",
    "bot_secret_ref",
)
_WECOM_REF_FIELDS = (
    "token_secret_ref",
    "encoding_aes_key_secret_ref",
    "corp_id_ref",
)


def _refs_configured(channel: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, bool]:
    """Presence-only map: True when the stored ref string is non-empty."""
    configured: dict[str, bool] = {}
    for field in fields:
        value = channel.get(field)
        configured[field] = isinstance(value, str) and bool(value.strip())
    return configured


def _channels_effective(
    data: Mapping[str, Any],
    flags: RuntimeFeatureFlags,
) -> dict[str, Any]:
    """Dual-knob read model — does not mutate or collapse ``data.*.enabled``."""
    qq = data.get("qqbot") if isinstance(data.get("qqbot"), Mapping) else {}
    we = data.get("wecom") if isinstance(data.get("wecom"), Mapping) else {}
    qq_host = bool(qq.get("enabled", False))
    we_host = bool(we.get("enabled", False))
    qq_platform = bool(flags.qqbot_channel_enabled)
    we_platform = bool(flags.wecom_channel_enabled)
    return {
        "qqbot": {
            "platform_flag": qq_platform,
            "host_enabled": qq_host,
            "effective_enabled": bool(qq_platform and qq_host),
            "refs_configured": _refs_configured(qq, _QQBOT_REF_FIELDS),
        },
        "wecom": {
            "platform_flag": we_platform,
            "host_enabled": we_host,
            "effective_enabled": bool(we_platform and we_host),
            "refs_configured": _refs_configured(we, _WECOM_REF_FIELDS),
        },
    }


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
        },
        "metadata": {
            "admin_api": True,
            "config_surface": True,
            "read_only": False,
        },
    }


def _not_found(resource: str, identifier: str) -> dict[str, Any]:
    return {
        "error": {
            "code": "not_found",
            "resource": resource,
            "identifier": identifier,
        },
        "metadata": {
            "admin_api": True,
            "config_surface": True,
            "read_only": False,
        },
    }


def _safe_store_message(exc: OperatorConfigStoreError) -> str:
    """Return a store error message without filesystem secret paths."""
    text = str(exc)
    # Store already uses path.name; still strip absolute-looking segments.
    if "/" in text or "\\" in text:
        return "config store operation failed"
    return text or "config store operation failed"
