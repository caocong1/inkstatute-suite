"""Configuration for the agent-core model layer providers.

``ProviderModelConfig`` is a frozen dataclass holding provider configuration
for the agent-core model layer.  It is adapted from
``ProviderModelBackendConfig`` in ``packages/backends/provider_model`` but
without ``backend_id`` — agent-core is not a ``BackendAdapter`` in Phase 100.

``api_key_ref`` is a *reference name* (e.g. ``"OPENAI_API_KEY"``), not the
actual key value.  Runtime secrets, API keys, and message payloads
intentionally stay outside this config object and outside the repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProviderModelConfig:
    """Agent-core provider model configuration.

    Fields:
        model_name: The model name to use for requests.  Referenced in
            sanitized metadata only, never in visible output.
        api_key_ref: Reference name for the API key environment variable
            (e.g. ``"OPENAI_API_KEY"``).  Not the actual key value.
        api_base_url: Base URL for the provider API endpoint.
        timeout: Request timeout in seconds.  Default 300.0.
        metadata: Additional metadata (e.g. ``system_prompt``).
    """

    model_name: str = "unknown"
    api_key_ref: str | None = None
    api_base_url: str | None = None
    timeout: float = 300.0
    metadata: JsonObject = field(default_factory=dict)


__all__ = ["ProviderModelConfig"]
