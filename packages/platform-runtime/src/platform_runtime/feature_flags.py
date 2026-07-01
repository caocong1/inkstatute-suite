"""Default-off feature flags for Phase 10 runtime lanes."""

from __future__ import annotations

from dataclasses import dataclass, fields


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

    def require_enabled(self, flag_name: str) -> None:
        known_flags = {field.name for field in fields(self)}
        if flag_name not in known_flags:
            raise RuntimeFeatureDisabledError(f"unknown runtime feature flag: {flag_name}")
        if not getattr(self, flag_name):
            raise RuntimeFeatureDisabledError(f"runtime feature flag disabled: {flag_name}")


__all__ = [
    "RuntimeFeatureDisabledError",
    "RuntimeFeatureFlags",
]
