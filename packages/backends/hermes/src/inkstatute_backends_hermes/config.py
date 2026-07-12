"""Configuration for the concrete Hermes backend adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class HermesBackendConfig:
    """Adapter-local Hermes configuration.

    Runtime secrets, live profile paths, and message payloads intentionally stay
    outside this config object and outside the repository.
    """

    backend_id: str = "hermes-lawfirm"
    backend_version: str = "unknown"
    profile_name: str = "lawfirm"
    adapter_version: str = "0.1.0"
    oneshot_command: tuple[str, ...] = ()
    api_runs_enabled: bool = False
    api_base_url: str | None = None
    supports_vision: bool | None = None
    metadata: JsonObject = field(default_factory=dict)

    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "HermesBackendConfig":
        """Create config from environment-like mappings without enabling runs by accident."""

        value = mapping.get("INKSTATUTE_HERMES_API_RUNS_ENABLED", "")
        return cls(
            api_runs_enabled=value.lower() in {"1", "true", "yes"},
            api_base_url=mapping.get("INKSTATUTE_HERMES_API_BASE_URL") or None,
        )


__all__ = ["HermesBackendConfig"]
