"""Atomic JSON OperatorConfigStore gated by operator_config_enabled (CFG-01/02).

Secrets are never resolved here — only refs-only documents validated by
``validate_document`` are persisted. Writes use a sibling ``.tmp`` file and
``os.replace`` for same-filesystem atomicity.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from platform_runtime.feature_flags import RuntimeFeatureFlags

from .errors import OperatorConfigStoreError
from .flags import require_operator_config_writable
from .schemas import (
    CatalogSelectionDoc,
    ChannelsDoc,
    OperatorConfigDocument,
    ProviderDoc,
    QQBotChannelDoc,
    VisionPolicyDoc,
    WeComChannelDoc,
)
from .validate import validate_document

__all__ = [
    "OperatorConfigStore",
    "default_operator_config_path",
    "document_from_payload",
    "document_to_payload",
]

_ENV_PATH = "INKSTATUTE_OPERATOR_CONFIG_PATH"
_DEFAULT_RELATIVE = Path(".inkstatute") / "operator-config.json"


def default_operator_config_path() -> Path:
    """Resolve store path from ``INKSTATUTE_OPERATOR_CONFIG_PATH`` or default."""
    configured = os.environ.get(_ENV_PATH)
    if configured:
        return Path(configured)
    return Path.cwd() / _DEFAULT_RELATIVE


def document_to_payload(document: OperatorConfigDocument) -> dict[str, Any]:
    """Serialize a document to a JSON-ready mapping (refs only)."""
    return asdict(document)


def document_from_payload(payload: Mapping[str, Any]) -> OperatorConfigDocument:
    """Parse a JSON mapping into a frozen ``OperatorConfigDocument``."""
    if not isinstance(payload, Mapping):
        raise OperatorConfigStoreError("operator config payload must be a JSON object")

    channels_raw = payload.get("channels") or {}
    if not isinstance(channels_raw, Mapping):
        raise OperatorConfigStoreError("channels must be an object")

    qqbot_raw = channels_raw.get("qqbot") or {}
    wecom_raw = channels_raw.get("wecom") or {}
    if not isinstance(qqbot_raw, Mapping) or not isinstance(wecom_raw, Mapping):
        raise OperatorConfigStoreError("channel documents must be objects")

    providers_raw = payload.get("providers") or ()
    if not isinstance(providers_raw, (list, tuple)):
        raise OperatorConfigStoreError("providers must be a list")

    catalog_raw = payload.get("catalog") or {}
    vision_raw = payload.get("vision") or {}
    if not isinstance(catalog_raw, Mapping) or not isinstance(vision_raw, Mapping):
        raise OperatorConfigStoreError("catalog and vision must be objects")

    providers = tuple(
        ProviderDoc(
            provider_id=str(item.get("provider_id", "")),
            kind=str(item.get("kind", "")),
            enabled=bool(item.get("enabled", False)),
            api_base_url=item.get("api_base_url"),
            api_key_ref=item.get("api_key_ref"),
            metadata=dict(item.get("metadata") or {}),
        )
        for item in providers_raw
        if isinstance(item, Mapping)
    )

    return OperatorConfigDocument(
        schema_version=int(payload.get("schema_version", 1)),
        channels=ChannelsDoc(
            qqbot=QQBotChannelDoc(
                channel_id=str(qqbot_raw.get("channel_id", "qqbot")),
                enabled=bool(qqbot_raw.get("enabled", False)),
                app_id_ref=qqbot_raw.get("app_id_ref"),
                app_secret_ref=qqbot_raw.get("app_secret_ref"),
                token_secret_ref=qqbot_raw.get("token_secret_ref"),
                bot_secret_ref=qqbot_raw.get("bot_secret_ref"),
                metadata=dict(qqbot_raw.get("metadata") or {}),
            ),
            wecom=WeComChannelDoc(
                channel_id=str(wecom_raw.get("channel_id", "wecom")),
                enabled=bool(wecom_raw.get("enabled", False)),
                token_secret_ref=wecom_raw.get("token_secret_ref"),
                encoding_aes_key_secret_ref=wecom_raw.get(
                    "encoding_aes_key_secret_ref"
                ),
                corp_id_ref=wecom_raw.get("corp_id_ref"),
                metadata=dict(wecom_raw.get("metadata") or {}),
            ),
        ),
        providers=providers,
        catalog=CatalogSelectionDoc(
            provider_id=catalog_raw.get("provider_id"),
            model_id=catalog_raw.get("model_id"),
        ),
        vision=VisionPolicyDoc(
            routing_mode=vision_raw.get("routing_mode"),
            main_model_id=vision_raw.get("main_model_id"),
            vision_model_id=vision_raw.get("vision_model_id"),
        ),
    )


class OperatorConfigStore:
    """Load/save refs-only operator config JSON with flag-gated atomic writes."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_operator_config_path()

    def load(self) -> OperatorConfigDocument:
        """Load and validate the document, or return defaults when missing.

        Fail-closed: hand-edited or corrupted store files that violate CFG-01/03
        raise ``OperatorConfigValidationError`` rather than returning as SoT.
        """
        if not self.path.is_file():
            return OperatorConfigDocument()
        try:
            raw = self.path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise OperatorConfigStoreError(
                f"failed to load operator config from {self.path.name}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise OperatorConfigStoreError("operator config root must be a JSON object")
        document = document_from_payload(payload)
        validate_document(document)
        return document

    def save(
        self,
        document: OperatorConfigDocument,
        *,
        feature_flags: RuntimeFeatureFlags,
    ) -> None:
        """Validate and atomically persist ``document`` when the flag is ON.

        Order is mandatory: (1) require writable, (2) validate_document,
        (3) sibling ``.tmp`` + ``os.replace``. Never bypass validation.
        """
        require_operator_config_writable(feature_flags)
        validate_document(document)
        payload = document_to_payload(document)
        self._atomic_write(payload)

    def _atomic_write(self, payload: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise OperatorConfigStoreError(
                f"failed to write operator config to {self.path.name}"
            ) from exc
