"""Host-level QQBot configuration — secret references only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from qqbot_service.secrets import normalize_config_secret_ref

__all__ = ["QQBotHostConfig", "load_qqbot_host_config"]


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
            app_id_ref=normalize_config_secret_ref(
                mapping.get("INKSTATUTE_QQBOT_APP_ID_REF"),
                field="INKSTATUTE_QQBOT_APP_ID_REF",
            ),
            app_secret_ref=normalize_config_secret_ref(
                mapping.get("INKSTATUTE_QQBOT_APP_SECRET_REF"),
                field="INKSTATUTE_QQBOT_APP_SECRET_REF",
            ),
            token_secret_ref=normalize_config_secret_ref(
                mapping.get("INKSTATUTE_QQBOT_TOKEN_SECRET_REF"),
                field="INKSTATUTE_QQBOT_TOKEN_SECRET_REF",
            ),
            bot_secret_ref=normalize_config_secret_ref(
                mapping.get("INKSTATUTE_QQBOT_BOT_SECRET_REF"),
                field="INKSTATUTE_QQBOT_BOT_SECRET_REF",
            ),
        )

    @classmethod
    def from_operator_doc(cls, doc: Mapping[str, Any] | object) -> "QQBotHostConfig":
        """Materialize host config from operator-store qqbot channel fields.

        Accepts a ``QQBotChannelDoc``-shaped object or Mapping. ``enabled`` is
        the *host/doc* knob only — dual-knob AND with
        ``RuntimeFeatureFlags.qqbot_channel_enabled`` lives in host wiring.
        Copies refs only; never resolves secrets.
        """
        if isinstance(doc, Mapping):
            enabled = bool(doc.get("enabled", False))
            app_id_raw = doc.get("app_id_ref")
            app_secret_raw = doc.get("app_secret_ref")
            token_raw = doc.get("token_secret_ref")
            bot_raw = doc.get("bot_secret_ref")
        else:
            enabled = bool(getattr(doc, "enabled", False))
            app_id_raw = getattr(doc, "app_id_ref", None)
            app_secret_raw = getattr(doc, "app_secret_ref", None)
            token_raw = getattr(doc, "token_secret_ref", None)
            bot_raw = getattr(doc, "bot_secret_ref", None)

        return cls(
            enabled=enabled,
            app_id_ref=normalize_config_secret_ref(
                app_id_raw if isinstance(app_id_raw, str) or app_id_raw is None else None,
                field="app_id_ref",
            ),
            app_secret_ref=normalize_config_secret_ref(
                app_secret_raw
                if isinstance(app_secret_raw, str) or app_secret_raw is None
                else None,
                field="app_secret_ref",
            ),
            token_secret_ref=normalize_config_secret_ref(
                token_raw if isinstance(token_raw, str) or token_raw is None else None,
                field="token_secret_ref",
            ),
            bot_secret_ref=normalize_config_secret_ref(
                bot_raw if isinstance(bot_raw, str) or bot_raw is None else None,
                field="bot_secret_ref",
            ),
        )


def load_qqbot_host_config(
    *,
    store: Any | None = None,
    env: Mapping[str, str] | None = None,
) -> QQBotHostConfig:
    """Load QQ host config: store wins when ``store.path`` exists, else env.

    OQ-1: when ``store`` is provided and ``store.path.exists()``, materialize
    from ``store.load().channels.qqbot`` via ``from_operator_doc``. Otherwise
    fall back to ``from_env``. Never resolves secrets (refs only).
    """
    if store is not None and getattr(store, "path", None) is not None:
        path = store.path
        exists = getattr(path, "exists", None)
        if callable(exists) and exists():
            document = store.load()
            qqbot = document.channels.qqbot
            return QQBotHostConfig.from_operator_doc(qqbot)
    return QQBotHostConfig.from_env(env if env is not None else {})
