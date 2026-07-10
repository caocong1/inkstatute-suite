"""Code-defined built-in vendor profiles and model catalog (PROV-01/03).

The catalog is a frozen, source-grounded tuple — never fetched from a remote
``/models`` endpoint (PROV-F01 deferred). It is the shared authority for the
admin API, the SSR forms, and the Phase 77 vision runtime. No secret
resolution, no environment reads, and no Hermes filesystem authority live here.

Official references checked 2026-07-11:
- OpenAI: ``GET https://api.openai.com/v1/models`` (Bearer auth); ``gpt-5``
  demonstrates image input.
- Anthropic OpenAI-compatible base URL ``https://api.anthropic.com/v1/``;
  native Models API uses ``x-api-key`` + ``anthropic-version``; current docs
  identify ``claude-opus-4-8``.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "BuiltInCatalogEntry",
    "VendorProfile",
    "BUILTIN_VENDOR_PROFILES",
    "BUILTIN_MODEL_CATALOG",
    "builtin_vendor_profile",
    "builtin_catalog_entry",
]

# Built-in provider kinds (distinct from operator-chosen provider_id instances).
BUILTIN_VENDOR_IDS: tuple[str, ...] = ("openai", "anthropic")


@dataclass(frozen=True, slots=True)
class VendorProfile:
    """Canonical built-in vendor profile (read-only preset).

    ``vendor_id`` is the built-in kind (``openai``/``anthropic``); it is never
    named ``provider_id`` (that is the operator registry instance id).
    ``default_key_ref_env`` is a convention only — the operator still sets the
    explicit ``api_key_ref`` on the ``ProviderDoc``.
    """

    vendor_id: str
    api_base_url: str
    default_key_ref_env: str


@dataclass(frozen=True, slots=True)
class BuiltInCatalogEntry:
    """Source-grounded built-in model catalog row (PROV-03).

    ``vendor_id`` binds the model to a built-in vendor kind; ``supports_vision``
    is a required boolean so Phase 77 never misreads a missing value as false.
    """

    vendor_id: str
    model_id: str
    supports_vision: bool
    description: str | None = None


BUILTIN_VENDOR_PROFILES: tuple[VendorProfile, ...] = (
    VendorProfile(
        vendor_id="openai",
        api_base_url="https://api.openai.com/v1",
        default_key_ref_env="OPENAI_API_KEY",
    ),
    VendorProfile(
        vendor_id="anthropic",
        api_base_url="https://api.anthropic.com/v1",
        default_key_ref_env="ANTHROPIC_API_KEY",
    ),
)

BUILTIN_MODEL_CATALOG: tuple[BuiltInCatalogEntry, ...] = (
    BuiltInCatalogEntry(
        vendor_id="openai",
        model_id="gpt-5",
        supports_vision=True,
        description="OpenAI multimodal main model",
    ),
    BuiltInCatalogEntry(
        vendor_id="anthropic",
        model_id="claude-opus-4-8",
        supports_vision=True,
        description="Anthropic multimodal main model",
    ),
)


def builtin_vendor_profile(vendor_id: str) -> VendorProfile | None:
    """Return the canonical ``VendorProfile`` for ``vendor_id`` or ``None``."""
    for profile in BUILTIN_VENDOR_PROFILES:
        if profile.vendor_id == vendor_id:
            return profile
    return None


def builtin_catalog_entry(
    vendor_id: str, model_id: str
) -> BuiltInCatalogEntry | None:
    """Return the catalog entry matching ``vendor_id``/``model_id`` or ``None``."""
    for entry in BUILTIN_MODEL_CATALOG:
        if entry.vendor_id == vendor_id and entry.model_id == model_id:
            return entry
    return None
