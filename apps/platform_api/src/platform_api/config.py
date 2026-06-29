"""Configuration for the default-off platform API host."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class PlatformApiConfig:
    """Platform API host settings.

    The host is disabled by default and must be explicitly enabled through
    the ``INKSTATUTE_PLATFORM_API_ENABLED`` environment variable. The host
    remains a thin, ref/secret-ref-first surface that depends only on an
    injected :class:`RunRuntime`.
    """

    api_id: str = "platform-api"
    enabled: bool = False
    base_path: str = "/v1"
    max_run_create_bytes: int = 16 * 1024
    secret_refs: tuple[str, ...] = field(default_factory=tuple)
    metadata: JsonObject = field(default_factory=dict)

    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "PlatformApiConfig":
        value = mapping.get("INKSTATUTE_PLATFORM_API_ENABLED", "")
        base_path = mapping.get("INKSTATUTE_PLATFORM_API_BASE_PATH", "/v1").strip() or "/v1"
        secret_refs = tuple(
            ref.strip()
            for ref in mapping.get("INKSTATUTE_PLATFORM_API_SECRET_REFS", "").split(",")
            if ref.strip()
        )
        return cls(
            enabled=value.lower() in {"1", "true", "yes"},
            base_path=base_path,
            secret_refs=secret_refs,
        )


__all__ = ["PlatformApiConfig"]
