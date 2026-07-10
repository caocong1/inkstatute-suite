"""WeCom host dual-knob apply helpers (CHAN-02 / CHAN-03).

Maps ``RuntimeFeatureFlags.wecom_channel_enabled`` AND host/doc ``enabled``
onto ``WeComChannelConfig.enabled``. The channel adapter package stays
flag-free — composition lives only in this host module.

Store wins when ``OperatorConfigStore.path`` exists (OQ-1); env ``from_env``
is bootstrap fallback only. Thin config apply — does not rebuild ingress.
"""

from __future__ import annotations

from typing import Any, Mapping

from inkstatute_channels_wecom.config import WeComChannelConfig
from platform_runtime.feature_flags import RuntimeFeatureFlags

__all__ = [
    "build_wecom_channel_config",
    "load_wecom_channel_config",
]


def build_wecom_channel_config(
    *,
    flags: RuntimeFeatureFlags,
    doc: Mapping[str, Any] | object,
) -> WeComChannelConfig:
    """Map dual default-OFF knobs → channel config.enabled; copy secret refs.

    Channel enablement is fail-closed AND of
    ``flags.wecom_channel_enabled`` and doc/host ``enabled``. Either knob
    alone must not enable the channel. Do not use ``channel_delivery_enabled``
    as the WeCom platform knob.
    """
    base = WeComChannelConfig.from_operator_doc(doc)
    return WeComChannelConfig(
        enabled=bool(flags.wecom_channel_enabled and base.enabled),
        token_secret_ref=base.token_secret_ref,
        encoding_aes_key_secret_ref=base.encoding_aes_key_secret_ref,
        corp_id_ref=base.corp_id_ref,
        metadata=dict(base.metadata),
    )


def load_wecom_channel_config(
    *,
    flags: RuntimeFeatureFlags,
    store: object | None = None,
    env: Mapping[str, str] | None = None,
) -> WeComChannelConfig:
    """Load WeCom channel config: store-wins-if-exists, else env, then dual-knob AND.

    When ``store`` is provided and ``store.path.exists()``, materialize from
    ``store.load().channels.wecom``. Otherwise fall back to
    ``WeComChannelConfig.from_env`` and AND with the platform flag.
    """
    if store is not None:
        path = getattr(store, "path", None)
        exists = getattr(path, "exists", None)
        if callable(exists) and exists():
            document = store.load()  # type: ignore[attr-defined]
            channels = getattr(document, "channels", None)
            wecom = getattr(channels, "wecom", None) if channels is not None else None
            if wecom is None and isinstance(channels, Mapping):
                wecom = channels.get("wecom")
            if wecom is not None:
                return build_wecom_channel_config(flags=flags, doc=wecom)

    base = WeComChannelConfig.from_env(env if env is not None else {})
    return WeComChannelConfig(
        enabled=bool(flags.wecom_channel_enabled and base.enabled),
        token_secret_ref=base.token_secret_ref,
        encoding_aes_key_secret_ref=base.encoding_aes_key_secret_ref,
        corp_id_ref=base.corp_id_ref,
        metadata=dict(base.metadata),
    )
