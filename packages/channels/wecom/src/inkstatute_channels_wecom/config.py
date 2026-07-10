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

    @classmethod
    def from_operator_doc(cls, doc: Mapping[str, Any] | object) -> "WeComChannelConfig":
        """Materialize host/doc fields only (no platform feature-flag AND).

        Accepts a Mapping or WeComChannelDoc-shaped object. Dual-knob composition
        with ``RuntimeFeatureFlags.wecom_channel_enabled`` lives in wecom-service
        wiring — this package stays flag-free.
        """
        enabled = bool(_doc_field(doc, "enabled", False))
        token_secret_ref = _doc_field(doc, "token_secret_ref", None) or None
        encoding_aes_key_secret_ref = (
            _doc_field(doc, "encoding_aes_key_secret_ref", None) or None
        )
        corp_id_ref = _doc_field(doc, "corp_id_ref", None) or None
        raw_metadata = _doc_field(doc, "metadata", None)
        if raw_metadata is None:
            metadata: JsonObject = {}
        elif isinstance(raw_metadata, Mapping):
            metadata = dict(raw_metadata)
        else:
            metadata = {}
        return cls(
            enabled=enabled,
            token_secret_ref=token_secret_ref,
            encoding_aes_key_secret_ref=encoding_aes_key_secret_ref,
            corp_id_ref=corp_id_ref,
            metadata=metadata,
        )


def _doc_field(doc: Mapping[str, Any] | object, key: str, default: Any) -> Any:
    if isinstance(doc, Mapping):
        return doc.get(key, default)
    return getattr(doc, key, default)


__all__ = ["WeComChannelConfig"]
