"""Model Provider Gateway — composite BackendAdapter for the InkStatute platform."""

from .config import ModelProviderGatewayConfig
from .gateway import ModelProviderGateway

__all__ = [
    "ModelProviderGateway",
    "ModelProviderGatewayConfig",
]
