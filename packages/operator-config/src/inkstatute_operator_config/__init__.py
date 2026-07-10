"""inkstatute-operator-config: refs-only operator config authority."""

from .errors import (
    OperatorConfigDisabledError,
    OperatorConfigError,
    OperatorConfigStoreError,
    OperatorConfigValidationError,
)
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
from .secrets import InvalidSecretRefError, normalize_config_secret_ref
from .store import OperatorConfigStore, default_operator_config_path
from .validate import OperatorConfigValidator, ValidationIssue, validate_document

__all__ = [
    "CatalogSelectionDoc",
    "ChannelsDoc",
    "InvalidSecretRefError",
    "OperatorConfigDisabledError",
    "OperatorConfigDocument",
    "OperatorConfigError",
    "OperatorConfigStore",
    "OperatorConfigStoreError",
    "OperatorConfigValidationError",
    "OperatorConfigValidator",
    "ProviderDoc",
    "QQBotChannelDoc",
    "ValidationIssue",
    "VisionPolicyDoc",
    "WeComChannelDoc",
    "default_operator_config_path",
    "normalize_config_secret_ref",
    "require_operator_config_writable",
    "validate_document",
]
