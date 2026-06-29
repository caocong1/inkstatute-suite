"""Configuration for the fixture-grade Web/SSE channel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class WebSseChannelConfig:
    """Web/SSE fixture channel settings.

    The channel is deliberately disabled by default and carries only references
    to external runtime material.
    """

    channel_id: str = "web"
    enabled: bool = False
    session_secret_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)

    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "WebSseChannelConfig":
        value = mapping.get("INKSTATUTE_WEB_SSE_CHANNEL_ENABLED", "")
        return cls(
            enabled=value.lower() in {"1", "true", "yes"},
            session_secret_ref=mapping.get("INKSTATUTE_WEB_SSE_SESSION_SECRET_REF") or None,
        )


__all__ = ["WebSseChannelConfig"]
