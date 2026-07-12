"""Configuration for the concrete provider_model backend adapter prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProviderModelBackendConfig:
    """Adapter-local provider_model prototype configuration.

    ``api_key_ref`` is a *reference name* (e.g. ``"OPENAI_API_KEY"``), not the
    actual key value.  Runtime secrets, API keys, and message payloads
    intentionally stay outside this config object and outside the repository.

    ``model_name`` is referenced in sanitized metadata only, never in visible
    output.
    """

    backend_id: str = "provider-model-prototype"
    backend_version: str = "unknown"
    adapter_version: str = "0.1.0"
    model_name: str = "unknown"
    api_key_ref: str | None = None
    api_base_url: str | None = None
    timeout: float = 30.0
    supports_vision: bool | None = None
    metadata: JsonObject = field(default_factory=dict)


__all__ = ["ProviderModelBackendConfig"]
