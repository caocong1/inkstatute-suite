"""Host-level QQBot configuration — secret references only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

__all__ = ["QQBotHostConfig"]


@dataclass(frozen=True, slots=True)
class QQBotHostConfig:
    """QQBot host settings.

    Stores only references to external runtime secrets. Raw secret values must
    never appear on this object; resolve them at process edge via
    ``resolve_secret_ref``.
    """

    enabled: bool = False
    app_id_ref: str | None = None
    app_secret_ref: str | None = None
    token_secret_ref: str | None = None
    bot_secret_ref: str | None = None

    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "QQBotHostConfig":
        value = mapping.get("INKSTATUTE_QQBOT_CHANNEL_ENABLED", "")
        return cls(
            enabled=value.lower() in {"1", "true", "yes"},
            app_id_ref=mapping.get("INKSTATUTE_QQBOT_APP_ID_REF") or None,
            app_secret_ref=mapping.get("INKSTATUTE_QQBOT_APP_SECRET_REF") or None,
            token_secret_ref=mapping.get("INKSTATUTE_QQBOT_TOKEN_SECRET_REF") or None,
            bot_secret_ref=mapping.get("INKSTATUTE_QQBOT_BOT_SECRET_REF") or None,
        )
