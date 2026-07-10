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

__all__ = [
    "CatalogSelectionDoc",
    "ChannelsDoc",
    "OperatorConfigDocument",
    "OperatorConfigError",
    "OperatorConfigValidationError",
    "ProviderDoc",
    "QQBotChannelDoc",
    "VisionPolicyDoc",
    "WeComChannelDoc",
]
