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
    return 200, {
        "data": payload[section],
        "metadata": _config_metadata(feature_flags),
    }


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
        payload = document_to_payload(current)
        payload[section] = section_value
        updated = document_from_payload(payload)
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
    return 200, {
        "data": saved[section],
        "metadata": _config_metadata(feature_flags),
    }


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


def _config_metadata(feature_flags: RuntimeFeatureFlags) -> dict[str, Any]:
    return {
        "admin_api": True,
        "config_surface": True,
        "operator_config_enabled": bool(feature_flags.operator_config_enabled),
        "read_only": False,
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
