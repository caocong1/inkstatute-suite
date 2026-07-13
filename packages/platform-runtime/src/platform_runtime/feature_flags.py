"""Default-off feature flags for Phase 10 runtime lanes."""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from typing import Mapping


class RuntimeFeatureDisabledError(RuntimeError):
    """Raised when a runtime lane is used without explicit opt-in."""


@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    run_runtime_enabled: bool = False
    streaming_lane_enabled: bool = False
    channel_delivery_enabled: bool = False
    approval_lane_enabled: bool = False
    contract_log_enabled: bool = False
    context_assembly_enabled: bool = False
    router_service_enabled: bool = False
    skill_registry_enabled: bool = False
    admin_api_enabled: bool = False
    qqbot_channel_enabled: bool = False
    wecom_channel_enabled: bool = False
    codex_backend_enabled: bool = False
    provider_model_backend_enabled: bool = False

    # M3 flags (9) — all default OFF, gated by require_enabled
    session_memory_enabled: bool = False
    mcp_registry_enabled: bool = False
    model_gateway_enabled: bool = False
    multi_agent_enabled: bool = False
    skill_registry_write_enabled: bool = False
    hybrid_routing_enabled: bool = False
    web_sse_channel_enabled: bool = False
    rbac_enabled: bool = False
    multi_tenant_enabled: bool = False

    # Phase 57 flags — all default OFF, gated by require_enabled
    admin_web_ui_enabled: bool = False
    lawyer_web_chat_enabled: bool = False

    # v1.10 operator config — default OFF; mutate paths require explicit opt-in
    operator_config_enabled: bool = False

    def require_enabled(self, flag_name: str) -> None:
        known_flags = {field.name for field in fields(self)}
        if flag_name not in known_flags:
            raise RuntimeFeatureDisabledError(f"unknown runtime feature flag: {flag_name}")
        if not getattr(self, flag_name):
            raise RuntimeFeatureDisabledError(f"runtime feature flag disabled: {flag_name}")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RuntimeFeatureFlags":
        """Build a flags instance from ``INKSTATUTE_<FIELD_NAME_UPPER>`` env vars.

        Missing variables fall back to ``False``.  Truthy values are ``true``,
        ``1``, ``yes``, and ``on`` (case-insensitive).
        """
        source: Mapping[str, str] = env if env is not None else os.environ
        kwargs: dict[str, bool] = {}
        for field in fields(cls):
            raw = source.get(f"INKSTATUTE_{field.name.upper()}")
            if raw is None:
                continue
            value = str(raw).strip().lower()
            kwargs[field.name] = value in ("true", "1", "yes", "on")
        return cls(**kwargs)


__all__ = [
    "RuntimeFeatureDisabledError",
    "RuntimeFeatureFlags",
]
