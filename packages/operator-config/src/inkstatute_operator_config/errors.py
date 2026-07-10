"""Error hierarchy for the operator-config package."""

from __future__ import annotations

__all__ = [
    "OperatorConfigError",
    "OperatorConfigValidationError",
    "OperatorConfigDisabledError",
    "OperatorConfigStoreError",
]


class OperatorConfigError(Exception):
    """Base error for operator-config failures."""


class OperatorConfigValidationError(OperatorConfigError):
    """Document or field validation failed (message must not echo secrets)."""


class OperatorConfigDisabledError(OperatorConfigError):
    """Raised when operator_config_enabled is OFF and a mutate path is attempted."""


class OperatorConfigStoreError(OperatorConfigError):
    """Store load/save failures unrelated to validation or feature flags."""
