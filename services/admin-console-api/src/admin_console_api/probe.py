"""Destination-safe non-destructive connection probe (PROV-04).

Stdlib-only probe primitive and ``handle_config_probe`` handler. The primitive
accepts only a server-resolved ``ProviderDoc`` — target selection and
provider/model resolution remain the handler's responsibility so no client
selector can bypass stored config.

Security invariants:
- Credentials are attached only after destination validation (URL + DNS).
- Custom probes accept public HTTPS destinations only, reject userinfo and
  unsafe resolved addresses, and never follow redirects.
- OpenAI/custom uses ``Authorization: Bearer``; Anthropic uses ``x-api-key``
  plus ``anthropic-version: 2023-06-01`` and no ``Authorization`` header.
- Probe execution never reads or logs response bodies, resolved keys, auth
  headers, endpoint details, or raw HTTP status.
- Results contain only generic ``ok``/``code`` — never secrets, URLs, or bodies.
- No ``openai``, ``httpx``, ``aiohttp``, Hermes, or external package imports.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.request
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from inkstatute_operator_config import (
    OperatorConfigDisabledError,
    OperatorConfigStore,
    OperatorConfigStoreError,
    OperatorConfigValidationError,
    ProviderDoc,
)
from inkstatute_operator_config.catalog import builtin_vendor_profile
from inkstatute_operator_config.flags import require_operator_config_writable
from platform_runtime.feature_flags import RuntimeFeatureFlags

__all__ = ["handle_config_probe", "probe_provider"]

_PROBE_TIMEOUT = 10  # seconds (finite — T-76-18 DoS mitigation)
_ANTHROPIC_VERSION = "2023-06-01"

# Built-in vendor kinds that use canonical VendorProfile URLs.
_BUILTIN_KINDS = frozenset({"openai", "anthropic"})


# ---------------------------------------------------------------------------
# No-redirect opener (T-76-17: 3xx cannot forward credentials)
# ---------------------------------------------------------------------------


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Disable all HTTP redirects so credentials never cross origins."""

    def redirect_request(  # type: ignore[override]
        self, req, fp, code, msg, headers, newurl
    ):
        return None


def _default_opener(
    url: str, *, headers: Mapping[str, str] | None = None, timeout: float = _PROBE_TIMEOUT, **_kwargs: Any
) -> Any:
    """Build a no-redirect urllib opener and issue a single GET.

    This default is used in production; tests inject their own opener.
    """
    req = urllib.request.Request(url, headers=dict(headers) if headers else {})
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(req, timeout=timeout)


# ---------------------------------------------------------------------------
# Secret-ref → env-name resolution (process-edge only)
# ---------------------------------------------------------------------------


def _resolve_env_name(ref: str | None) -> str | None:
    """Convert a secret ref to an env var name.

    Returns ``None`` for blank/None/unsupported refs (``secret://`` paths
    cannot be resolved to env names). Never raises.
    """
    if ref is None:
        return None
    stripped = ref.strip()
    if not stripped:
        return None
    if stripped.startswith("env:"):
        return stripped[4:]
    if stripped.startswith("secret://"):
        return None  # secret:// paths are not env-name resolvable here
    # Bare env-key identifier
    return stripped


# ---------------------------------------------------------------------------
# URL and address validation
# ---------------------------------------------------------------------------


def _validate_custom_url(url: str) -> bool:
    """Structural public-HTTPS check for a custom provider URL.

    Requires https, hostname, no userinfo/query/fragment, a valid port, and
    rejects unsafe literal IP hostnames (loopback/private/link-local/etc.)
    for consistency with ``validate._is_valid_custom_base_url``.
    Never raises — returns False for any malformed shape.
    """
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    if not parsed.hostname:
        return False
    if "@" in parsed.netloc:
        return False
    if parsed.query or parsed.fragment:
        return False
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        return False
    # Reject unsafe literal IP hostnames (defense-in-depth before DNS resolution).
    try:
        literal_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and _is_unsafe_ip(literal_ip):
        return False
    return True


def _is_unsafe_ip(ip: ipaddress._BaseAddress) -> bool:
    """True when the address is loopback, private, link-local, multicast,
    reserved, or unspecified."""
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _check_resolved_addresses(addrinfos: list[tuple]) -> bool:
    """Return True if every resolved address is public-safe.

    Extracts the IP from the sockaddr (last element of each addrinfo tuple)
    and rejects any unsafe class. Never raises — malformed entries reject.
    """
    for info in addrinfos:
        try:
            sockaddr = info[-1]
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
        except (IndexError, ValueError, TypeError):
            return False
        if _is_unsafe_ip(ip):
            return False
    return True


# ---------------------------------------------------------------------------
# Auth headers by provider kind
# ---------------------------------------------------------------------------


def _build_auth_headers(kind: str, key_value: str) -> dict[str, str]:
    """Build credential headers for the provider kind.

    OpenAI/custom: ``Authorization: Bearer <key>``.
    Anthropic: ``x-api-key: <key>`` + ``anthropic-version`` (no Bearer).
    """
    if kind == "anthropic":
        return {
            "x-api-key": key_value,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
    # openai and custom both use Bearer
    return {"Authorization": f"Bearer {key_value}"}


# ---------------------------------------------------------------------------
# Probe primitive — accepts only a server-resolved ProviderDoc
# ---------------------------------------------------------------------------


def probe_provider(
    provider: ProviderDoc,
    *,
    env: Mapping[str, str],
    resolver: Callable[..., list] | None = None,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Probe a single server-selected provider endpoint.

    Returns ``{"ok": bool, "code": str}`` with generic codes only:
    ``ok``, ``missing_ref``, ``unsafe_destination``, ``auth_error``, ``network``.
    Never reads response bodies, never logs secrets/headers/URLs/exceptions,
    and never calls ``store.save``.
    """
    _resolver = resolver if resolver is not None else socket.getaddrinfo
    _opener = opener if opener is not None else _default_opener

    # 1. Resolve the API key ref → env value (before any network work).
    env_name = _resolve_env_name(provider.api_key_ref)
    if env_name is None:
        return {"ok": False, "code": "missing_ref"}
    source: Mapping[str, str] = env if env is not None else {}
    key_value = source.get(env_name, "")
    if not key_value or not key_value.strip():
        return {"ok": False, "code": "missing_ref"}
    key_value = key_value.strip()

    # 2. Determine and validate the base URL (before credential construction).
    if provider.kind in _BUILTIN_KINDS:
        profile = builtin_vendor_profile(provider.kind)
        if profile is None or provider.api_base_url != profile.api_base_url:
            return {"ok": False, "code": "unsafe_destination"}
        base_url = profile.api_base_url
    elif provider.kind == "custom":
        if not isinstance(provider.api_base_url, str) or not _validate_custom_url(provider.api_base_url):
            return {"ok": False, "code": "unsafe_destination"}
        base_url = provider.api_base_url
    else:
        return {"ok": False, "code": "unsafe_destination"}

    # 3. DNS resolution + unsafe-address check (before credential Request).
    parsed = urlsplit(base_url)
    hostname = parsed.hostname
    port = parsed.port or 443
    try:
        addrinfos = _resolver(hostname, port, 0, socket.SOCK_STREAM)
    except Exception:
        return {"ok": False, "code": "network"}
    if not addrinfos or not _check_resolved_addresses(addrinfos):
        return {"ok": False, "code": "unsafe_destination"}

    # 4. Build credential headers (after all validation passes).
    headers = _build_auth_headers(provider.kind, key_value)
    models_url = base_url.rstrip("/") + "/models"

    # 5. Single GET with finite timeout — status code only, never read().
    try:
        response = _opener(models_url, headers=headers, timeout=_PROBE_TIMEOUT)
        status = getattr(response, "status", None)
        if status is None:
            status = response.getcode()  # type: ignore[union-attr]
        if 200 <= int(status) < 300:
            return {"ok": True, "code": "ok"}
        if int(status) in (401, 403):
            return {"ok": False, "code": "auth_error"}
        return {"ok": False, "code": "network"}
    except Exception:
        return {"ok": False, "code": "network"}


# ---------------------------------------------------------------------------
# Handler — target resolution, flag/RBAC gate, non-mutating dispatch
# ---------------------------------------------------------------------------


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
        },
        "metadata": {
            "admin_api": True,
            "config_surface": True,
            "read_only": True,
        },
    }


def _probe_data(
    status: str,
    target: str,
    provider_id: str | None,
    model_id: str | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "target": target,
        "provider_id": provider_id,
        "model_id": model_id,
    }


def handle_config_probe(
    path: str,
    body: Any,
    headers: Mapping[str, str] | None,
    flags: RuntimeFeatureFlags,
    env: Mapping[str, str] | None,
    *,
    config_store: OperatorConfigStore | None = None,
    rbac_secret: str | None = None,
    resolver: Callable[..., list] | None = None,
    opener: Callable[..., Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Handle ``POST /config/providers/probe`` — stored-target connection probe.

    Accepts only ``target=main|vision``; resolves provider/model from the
    validated stored document; never accepts client-supplied overrides; never
    calls ``store.save``. Returns generic status only.
    """
    # 1. Shared auth/RBAC pipeline (lazy import to avoid circular dependency).
    from .api import _authenticate_admin

    auth = _authenticate_admin(path, None, headers, flags, env, rbac_secret)
    if auth[0] is not None:
        return auth  # type: ignore[return-value]
    route_path, _route_query, _identity, _tenant_filter = auth[1]

    # 2. operator_config_enabled gate (before store load or network).
    try:
        require_operator_config_writable(flags)
    except OperatorConfigDisabledError:
        return 403, _error(
            "operator_config_disabled",
            "operator_config_enabled flag is False",
        )

    # 3. Body validation: exactly {"target": "main"|"vision"}, no overrides.
    if not isinstance(body, Mapping):
        return 400, _error("invalid_config", "probe body must be a JSON object")
    if set(body.keys()) != {"target"}:
        return 400, _error(
            "invalid_config",
            "probe body must contain only the 'target' field",
        )
    target = body["target"]
    if target not in ("main", "vision"):
        return 400, _error(
            "invalid_config",
            "target must be 'main' or 'vision'",
        )

    # 4. Load the validated stored document (never save).
    store = config_store if config_store is not None else OperatorConfigStore()
    try:
        document = store.load()
    except OperatorConfigValidationError as exc:
        return 400, _error("invalid_config", str(exc))
    except OperatorConfigStoreError as exc:
        text = str(exc)
        if "/" in text or "\\" in text:
            text = "config store operation failed"
        return 500, _error("config_store_error", text or "config store operation failed")

    # 5. Resolve the stored target selection.
    if target == "main":
        sel_provider_id = document.catalog.provider_id
        sel_model_id = document.catalog.model_id
    else:
        sel_provider_id = document.vision.vision_provider_id
        sel_model_id = document.vision.vision_model_id

    # Absent or partial selection → generic not_configured (no side effects).
    if not sel_provider_id or not sel_model_id:
        return 200, {
            "data": _probe_data("not_configured", target, None, None),
            "metadata": {
                "admin_api": True,
                "config_surface": True,
                "read_only": True,
            },
        }

    # 6. Resolve exactly one provider from the registry.
    matches = [
        p for p in document.providers if p.provider_id == sel_provider_id
    ]
    if len(matches) != 1:
        return 200, {
            "data": _probe_data("fail", target, None, None),
            "metadata": {
                "admin_api": True,
                "config_surface": True,
                "read_only": True,
            },
        }

    provider = matches[0]

    # 7. Call the shared probe primitive.
    result = probe_provider(
        provider,
        env=env if env is not None else {},
        resolver=resolver,
        opener=opener,
    )
    status = "ok" if result.get("ok") else "fail"

    return 200, {
        "data": _probe_data(status, target, sel_provider_id, sel_model_id),
        "metadata": {
            "admin_api": True,
            "config_surface": True,
            "read_only": True,
        },
    }
