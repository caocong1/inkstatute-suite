"""Feature-flag helpers for operator-config mutate paths (CFG-02)."""

from __future__ import annotations

from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)

from .errors import OperatorConfigDisabledError

__all__ = ["require_operator_config_writable"]


def require_operator_config_writable(flags: RuntimeFeatureFlags) -> None:
    """Refuse mutate/save when ``operator_config_enabled`` is OFF.

    Wraps ``RuntimeFeatureDisabledError`` as ``OperatorConfigDisabledError``
    so package callers get a clear CFG-02 signal without importing platform
    runtime error types at every call site.
    """
    try:
        flags.require_enabled("operator_config_enabled")
    except RuntimeFeatureDisabledError as exc:
        raise OperatorConfigDisabledError(
            "operator_config_enabled flag is False"
        ) from exc
