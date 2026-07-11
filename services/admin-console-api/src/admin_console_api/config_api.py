"""Section-scoped /config/* GET and PUT handlers over OperatorConfigStore.

Pure ``(status, body)`` adapters — auth/RBAC live in ``api.handle_admin_*``.
Persist only through ``OperatorConfigStore.save``; never resolve secrets or
echo store filesystem paths.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from inkstatute_operator_config import (
    OperatorConfigDisabledError,
    OperatorConfigStore,
    OperatorConfigStoreError,
    OperatorConfigValidationError,
)
from inkstatute_operator_config.catalog import (
    BUILTIN_MODEL_CATALOG,
    BUILTIN_VENDOR_PROFILES,
    builtin_vendor_profile,
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
    metadata = _config_metadata(feature_flags, section=section)
    if section == "vision":
        metadata.update(_vision_status_metadata(document))
    body: dict[str, Any] = {
        "data": _json_safe(payload[section]),
        "metadata": metadata,
    }
    if section == "channels":
        body["effective"] = _channels_effective(payload["channels"], feature_flags)
    if section == "providers":
        body["probe_targets"] = _probe_targets(document)
    if section == "catalog":
        body["catalog_entries"] = _catalog_entries()
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

    # Fill canonical VendorProfile URLs for built-in providers with None api_base_url.
    if section == "providers" and isinstance(section_value, list):
        section_value = _fill_builtin_provider_urls(section_value)

    # VIS-01: normalize empty-string vision fields to None so the SSR form's
    # blank selects persist as None (draft-tolerant) rather than "".
    if section == "vision" and isinstance(section_value, Mapping):
        section_value = _normalize_vision_empty_strings(section_value)

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
    metadata = _config_metadata(feature_flags, section=section)
    if section == "vision":
        metadata.update(_vision_status_metadata(updated))
    body: dict[str, Any] = {
        "data": _json_safe(saved[section]),
        "metadata": metadata,
    }
    if section == "channels":
        body["effective"] = _channels_effective(saved["channels"], feature_flags)
    if section == "providers":
        body["probe_targets"] = _probe_targets(updated)
    if section == "catalog":
        body["catalog_entries"] = _catalog_entries()
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
        section_value = dict(body[section])
        allowed = _SECTION_ALLOWED_KEYS.get(section)
        if allowed is not None:
            extra = set(section_value.keys()) - allowed
            if extra:
                return None, _error(
                    "invalid_config",
                    f"{section} body contains unexpected keys: {sorted(extra)}",
                )
        return section_value, None

    allowed = _SECTION_ALLOWED_KEYS.get(section)
    if allowed is not None:
        extra = set(body.keys()) - allowed
        if extra:
            return None, _error(
                "invalid_config",
                f"{section} body contains unexpected keys: {sorted(extra)}",
            )

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
    if section in ("channels", "providers", "catalog", "vision"):
        # Restart-to-apply MVP — never claim live/hot-reload apply.
        metadata["apply_semantics"] = "restart_required"
    if section == "vision":
        metadata["routing_modes"] = ["auto", "always_preprocess", "main_only"]
    if section == "providers":
        metadata["builtin_vendor_profiles"] = [
            {
                "vendor_id": p.vendor_id,
                "api_base_url": p.api_base_url,
                "default_key_ref_env": p.default_key_ref_env,
            }
            for p in BUILTIN_VENDOR_PROFILES
        ]
    if section == "catalog":
        metadata["builtin_catalog"] = [
            {
                "vendor_id": e.vendor_id,
                "model_id": e.model_id,
                "supports_vision": e.supports_vision,
                "description": e.description,
            }
            for e in BUILTIN_MODEL_CATALOG
        ]
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


def _json_safe(obj: Any) -> Any:
    """Convert tuples to lists for JSON-compatible response payloads."""
    return json.loads(json.dumps(obj, default=str))


# Allowed keys per section (rejects unexpected fields like planted secrets).
_SECTION_ALLOWED_KEYS: dict[str, frozenset[str]] = {
    "catalog": frozenset({"provider_id", "model_id"}),
    "vision": frozenset({
        "routing_mode",
        "main_model_id",
        "vision_model_id",
        "vision_provider_id",
    }),
}


def _fill_builtin_provider_urls(providers: list[Any]) -> list[Any]:
    """Fill canonical VendorProfile URLs for built-in providers with None api_base_url.

    Operators send ``api_base_url: None`` for built-in vendors; the API fills in
    the exact canonical URL before persistence so server-side validation passes
    and the stored document always carries the canonical endpoint (PROV-01).
    """
    filled: list[Any] = []
    for item in providers:
        if isinstance(item, Mapping):
            kind = item.get("kind")
            base_url = item.get("api_base_url")
            if kind in ("openai", "anthropic") and not base_url:
                profile = builtin_vendor_profile(kind)
                if profile is not None:
                    item = dict(item)
                    item["api_base_url"] = profile.api_base_url
        filled.append(item)
    return filled


_VISION_STRING_FIELDS = (
    "routing_mode",
    "main_model_id",
    "vision_model_id",
    "vision_provider_id",
)


def _normalize_vision_empty_strings(vision: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize empty-string vision fields to None (VIS-01).

    The SSR form submits blank selects as ``""``; the operator config schema
    treats ``None`` as the draft-tolerant unset value. This keeps persisted
    documents canonical so completeness checks see a truly absent field.
    """
    normalized = dict(vision)
    for field in _VISION_STRING_FIELDS:
        if normalized.get(field, None) == "":
            normalized[field] = None
    return normalized


def _vision_status_metadata(document: Any) -> dict[str, Any]:
    """Compute ``vision_configured`` and ``vision_status`` from the stored document.

    ``vision_configured`` is True when both ``vision_provider_id`` and
    ``vision_model_id`` are non-empty; ``vision_status`` is ``"configured"``
    when both present, ``"not_configured"`` otherwise. Consumed by the SSR
    vision form (VIS-01).
    """
    vision = document.vision
    has_provider = bool(vision.vision_provider_id)
    has_model = bool(vision.vision_model_id)
    configured = has_provider and has_model
    return {
        "vision_configured": configured,
        "vision_status": "configured" if configured else "not_configured",
    }


def _probe_targets(document: Any) -> dict[str, dict[str, Any]]:
    """Build refs-safe probe target metadata from the validated stored document.

    Each entry exposes only ``status``, ``provider_id``, and ``model_id`` —
    never ``api_key_ref``, resolved secrets, base URLs, headers, or endpoint
    details. A complete valid pair exposes ``status='configured'`` with IDs;
    absent/partial exposes ``status='not_configured'`` with None IDs.
    """
    main_pid = document.catalog.provider_id
    main_mid = document.catalog.model_id
    vision_pid = document.vision.vision_provider_id
    vision_mid = document.vision.vision_model_id
    return {
        "main": _target_entry(main_pid, main_mid),
        "vision": _target_entry(vision_pid, vision_mid),
    }


def _target_entry(provider_id: str | None, model_id: str | None) -> dict[str, Any]:
    """Return a refs-safe probe target status entry."""
    if provider_id and model_id:
        return {
            "status": "configured",
            "provider_id": provider_id,
            "model_id": model_id,
        }
    return {
        "status": "not_configured",
        "provider_id": None,
        "model_id": None,
    }


def _catalog_entries() -> list[dict[str, Any]]:
    """Serialize the built-in model catalog for the SSR consumer (PROV-03)."""
    return [
        {
            "vendor_id": e.vendor_id,
            "model_id": e.model_id,
            "supports_vision": e.supports_vision,
            "description": e.description,
        }
        for e in BUILTIN_MODEL_CATALOG
    ]


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
