"""Configuration for the QQBot channel adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class QQBotChannelConfig:
    """QQBot channel settings.

    The channel is deliberately disabled by default and carries only references
    to external runtime secrets (no raw secrets).
    """

    channel_id: str = "qqbot"
    enabled: bool = False
    app_id_ref: str | None = None
    app_secret_ref: str | None = None
    token_secret_ref: str | None = None
    bot_secret_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)

    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "QQBotChannelConfig":
        value = mapping.get("INKSTATUTE_QQBOT_CHANNEL_ENABLED", "")
        return cls(
            enabled=value.lower() in {"1", "true", "yes"},
            app_id_ref=mapping.get("INKSTATUTE_QQBOT_APP_ID_REF") or None,
            app_secret_ref=mapping.get("INKSTATUTE_QQBOT_APP_SECRET_REF") or None,
            token_secret_ref=mapping.get("INKSTATUTE_QQBOT_TOKEN_SECRET_REF") or None,
            bot_secret_ref=mapping.get("INKSTATUTE_QQBOT_BOT_SECRET_REF") or None,
        )


__all__ = ["QQBotChannelConfig"]
