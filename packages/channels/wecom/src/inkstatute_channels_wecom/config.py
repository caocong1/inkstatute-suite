"""Configuration for the WeCom channel wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class WeComChannelConfig:
    """Channel-local WeCom settings.

    Raw WeCom tokens, AES keys, and corp ids stay in the runtime secret store.
    This object carries only references to those values.
    """

    channel_id: str = "wecom"
    enabled: bool = False
    token_secret_ref: str | None = None
    encoding_aes_key_secret_ref: str | None = None
    corp_id_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)

    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "WeComChannelConfig":
        value = mapping.get("INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED", "")
        return cls(
            enabled=value.lower() in {"1", "true", "yes"},
            token_secret_ref=mapping.get("INKSTATUTE_WECOM_TOKEN_SECRET_REF") or None,
            encoding_aes_key_secret_ref=mapping.get("INKSTATUTE_WECOM_AES_KEY_SECRET_REF") or None,
            corp_id_ref=mapping.get("INKSTATUTE_WECOM_CORP_ID_REF") or None,
        )


__all__ = ["WeComChannelConfig"]
