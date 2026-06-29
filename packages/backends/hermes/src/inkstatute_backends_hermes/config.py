"""Configuration for the concrete Hermes backend adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    metadata: JsonObject = field(default_factory=dict)


__all__ = ["HermesBackendConfig"]

