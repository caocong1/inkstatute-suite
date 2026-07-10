"""inkstatute-operator-config: refs-only operator config authority."""

from .errors import OperatorConfigError, OperatorConfigValidationError
from .schemas import (
    CatalogSelectionDoc,
    ChannelsDoc,
    OperatorConfigDocument,
    ProviderDoc,
    QQBotChannelDoc,
    VisionPolicyDoc,
    WeComChannelDoc,
)
from .secrets import InvalidSecretRefError, normalize_config_secret_ref

__all__ = [
    "CatalogSelectionDoc",
    "ChannelsDoc",
    "InvalidSecretRefError",
    "OperatorConfigDocument",
    "OperatorConfigError",
    "OperatorConfigValidationError",
    "ProviderDoc",
    "QQBotChannelDoc",
    "VisionPolicyDoc",
    "WeComChannelDoc",
    "normalize_config_secret_ref",
]
