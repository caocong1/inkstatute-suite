"""Error hierarchy for the operator-config package."""

from __future__ import annotations

__all__ = [
    "OperatorConfigError",
    "OperatorConfigValidationError",
]


class OperatorConfigError(Exception):
    """Base error for operator-config failures."""


class OperatorConfigValidationError(OperatorConfigError):
    """Document or field validation failed (message must not echo secrets)."""
