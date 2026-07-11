"""Frozen refs-only operator config document schemas (CFG-01).

Credential fields are ``*_ref`` only. No Hermes filesystem authority fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JsonObject = dict[str, Any]

__all__ = [
    "QQBotChannelDoc",
    "WeComChannelDoc",
    "ChannelsDoc",
    "ProviderDoc",
    "CatalogSelectionDoc",
    "VisionPolicyDoc",
    "OperatorConfigDocument",
]


@dataclass(frozen=True, slots=True)
class QQBotChannelDoc:
    """QQBot channel settings in the operator config store.

    Aligns with ``QQBotChannelConfig`` field naming: ``*_ref`` credentials only,
    ``enabled`` default False.
    """

    channel_id: str = "qqbot"
    enabled: bool = False
    app_id_ref: str | None = None
    app_secret_ref: str | None = None
    token_secret_ref: str | None = None
    bot_secret_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WeComChannelDoc:
    """WeCom channel settings in the operator config store.

    Aligns with ``WeComChannelConfig`` field naming: ``*_ref`` credentials only,
    ``enabled`` default False.
    """

    channel_id: str = "wecom"
    enabled: bool = False
    token_secret_ref: str | None = None
    encoding_aes_key_secret_ref: str | None = None
    corp_id_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChannelsDoc:
    """Nested channel documents (qqbot + wecom)."""

    qqbot: QQBotChannelDoc = field(default_factory=QQBotChannelDoc)
    wecom: WeComChannelDoc = field(default_factory=WeComChannelDoc)


@dataclass(frozen=True, slots=True)
class ProviderDoc:
    """Provider registry entry: refs-only credentials, disabled by default.

    ``kind`` is ``openai``/``anthropic`` (built-in vendors) or ``custom``
    (OpenAI-compatible endpoint). Built-ins carry an empty ``model_allowlist``
    and the canonical vendor ``api_base_url``; custom providers require a
    non-empty explicit ``model_allowlist`` (PROV-02).
    """

    provider_id: str = ""
    kind: str = ""
    enabled: bool = False
    api_base_url: str | None = None
    api_key_ref: str | None = None
    model_allowlist: tuple[str, ...] = ()
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CatalogSelectionDoc:
    """Catalog selection stub (no vendor catalog content — Phase 76)."""

    provider_id: str | None = None
    model_id: str | None = None


@dataclass(frozen=True, slots=True)
class VisionPolicyDoc:
    """Vision routing policy (VIS-01).

    ``routing_mode`` selects the vision routing strategy:

    - ``auto`` — multimodal main model when it supports vision, otherwise a
      vision→main mix. Requires a complete vision pair.
    - ``always_preprocess`` — always route through the vision model before the
      main model. Requires a complete vision pair.
    - ``main_only`` — never invoke the vision model; the runtime ignores vision
      fields, so an absent/partial/complete pair is a valid persisted draft.
    - ``None`` (unset) preserves the Phase 76 draft-tolerant behavior: no
      completeness enforcement, and a complete pair is still resolved if present.

    A complete ``vision_provider_id`` + ``vision_model_id`` pair is resolved
    against the operator provider registry by the same built-in-vendor or
    custom-allowlist rules as the main catalog selection. ``main_model_id``
    remains an optional echo of ``catalog.model_id``; the validator does not
    require it to match the catalog section (the API plan owns that cross-section
    echo, not the validator).
    """

    routing_mode: str | None = None
    main_model_id: str | None = None
    vision_model_id: str | None = None
    vision_provider_id: str | None = None


@dataclass(frozen=True, slots=True)
class OperatorConfigDocument:
    """Root operator config document persisted by the InkStatute store."""

    schema_version: int = 1
    channels: ChannelsDoc = field(default_factory=ChannelsDoc)
    providers: tuple[ProviderDoc, ...] = ()
    catalog: CatalogSelectionDoc = field(default_factory=CatalogSelectionDoc)
    vision: VisionPolicyDoc = field(default_factory=VisionPolicyDoc)
