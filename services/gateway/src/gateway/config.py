"""Configuration for the unified InkStatute Gateway.

The Gateway is disabled by default and must be explicitly enabled through
the ``INKSTATUTE_GATEWAY_ENABLED`` environment variable. It is a thin,
ref/secret-ref-first surface that depends only on an injected
:class:`RunRuntime`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class GatewayConfig:
    """Gateway settings.

    The ``default_tenant_id`` field supports self-hosted single-tenant
    deployments (GW-03: "自用形态可用单租户默认值，但契约字段不省略").
    """

    api_id: str = "gateway"
    enabled: bool = False
    base_path: str = "/v1"
    max_run_create_bytes: int = 16 * 1024
    secret_refs: tuple[str, ...] = field(default_factory=tuple)
    default_tenant_id: str = "default"
    metadata: JsonObject = field(default_factory=dict)

    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "GatewayConfig":
        value = mapping.get("INKSTATUTE_GATEWAY_ENABLED", "")
        base_path = mapping.get("INKSTATUTE_GATEWAY_BASE_PATH", "/v1").strip() or "/v1"
        secret_refs = tuple(
            ref.strip()
            for ref in mapping.get("INKSTATUTE_GATEWAY_SECRET_REFS", "").split(",")
            if ref.strip()
        )
        default_tenant_id = mapping.get("INKSTATUTE_GATEWAY_DEFAULT_TENANT_ID", "default").strip() or "default"
        return cls(
            enabled=value.lower() in {"1", "true", "yes"},
            base_path=base_path,
            secret_refs=secret_refs,
            default_tenant_id=default_tenant_id,
        )


__all__ = ["GatewayConfig"]
