"""Backend process mode configuration — per_session implemented, pooled/remote reserved.

V3 implements only ``PER_SESSION`` (one ACP subprocess per session).
``POOLED`` and ``REMOTE`` are reserved for V4 (SCALE-01..03) and raise
:class:`NotImplementedError` when used.
"""

from __future__ import annotations

from dataclasses import dataclass

from platform_contract.agent_adapter import BackendProcessMode


@dataclass(frozen=True, slots=True)
class ProcessModeConfig:
    """Configuration for ACP backend subprocess management.

    Only ``PER_SESSION`` mode is implemented in V3.

    Attributes
    ----------
    mode
        The process mode. Defaults to ``PER_SESSION``.
    timeout_seconds
        Subprocess idle timeout in seconds.
    restart_on_crash
        Whether to restart the subprocess if it crashes unexpectedly.
    max_restarts
        Maximum number of crash restarts before failing the run.
    """

    mode: BackendProcessMode = BackendProcessMode.PER_SESSION
    timeout_seconds: float = 300.0
    restart_on_crash: bool = True
    max_restarts: int = 1


def validate_process_mode(mode: BackendProcessMode) -> None:
    """Validate that the given process mode is implemented.

    Parameters
    ----------
    mode
        The process mode to validate.

    Raises
    ------
    NotImplementedError
        If the mode is ``POOLED`` or ``REMOTE`` (reserved for V4).
    """
    if mode == BackendProcessMode.PER_SESSION:
        return
    if mode == BackendProcessMode.POOLED:
        raise NotImplementedError(
            "backend_process_mode 'pooled' is reserved for V4 (SCALE-01); use 'per_session'"
        )
    if mode == BackendProcessMode.REMOTE:
        raise NotImplementedError(
            "backend_process_mode 'remote' is reserved for V4 (SCALE-02); use 'per_session'"
        )
    raise NotImplementedError(
        f"backend_process_mode '{mode}' is not recognized; use 'per_session'"
    )


def is_mode_implemented(mode: BackendProcessMode) -> bool:
    """Return ``True`` if the given mode is implemented in V3.

    Only ``PER_SESSION`` is implemented.
    """
    return mode == BackendProcessMode.PER_SESSION


IMPLEMENTED_MODES: frozenset[BackendProcessMode] = frozenset({BackendProcessMode.PER_SESSION})

UNIMPLEMENTED_MODES: frozenset[BackendProcessMode] = frozenset(
    {BackendProcessMode.POOLED, BackendProcessMode.REMOTE}
)


__all__ = [
    "IMPLEMENTED_MODES",
    "ProcessModeConfig",
    "UNIMPLEMENTED_MODES",
    "is_mode_implemented",
    "validate_process_mode",
]
