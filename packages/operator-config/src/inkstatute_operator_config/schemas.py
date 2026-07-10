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
    """Provider registry entry: refs-only credentials, disabled by default."""

    provider_id: str = ""
    kind: str = ""
    enabled: bool = False
    api_base_url: str | None = None
    api_key_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CatalogSelectionDoc:
    """Catalog selection stub (no vendor catalog content — Phase 76)."""

    provider_id: str | None = None
    model_id: str | None = None


@dataclass(frozen=True, slots=True)
class VisionPolicyDoc:
    """Vision routing policy stub (runtime flag deferred to Phase 77)."""

    routing_mode: str | None = None
    main_model_id: str | None = None
    vision_model_id: str | None = None


@dataclass(frozen=True, slots=True)
class OperatorConfigDocument:
    """Root operator config document persisted by the InkStatute store."""

    schema_version: int = 1
    channels: ChannelsDoc = field(default_factory=ChannelsDoc)
    providers: tuple[ProviderDoc, ...] = ()
    catalog: CatalogSelectionDoc = field(default_factory=CatalogSelectionDoc)
    vision: VisionPolicyDoc = field(default_factory=VisionPolicyDoc)
