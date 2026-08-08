"""SubprocessController — liveness, per-run timeout, partial-result acceptance.

Implements SVC-06 subprocess control for the Arena Service:

- **Liveness check:** :meth:`SubprocessController.check_liveness` calls
  ``adapter.get_active_pids()`` and probes each PID with
  ``os.kill(pid, 0)`` to detect dead subprocesses.
- **Per-run timeout:** :meth:`SubprocessController.run_with_timeout` wraps
  a coroutine in ``asyncio.wait_for``.  On timeout it invokes the
  registered cleanup callback (wired to ``ArenaEngine.cancel()`` in
  Plan 05) and re-raises ``asyncio.TimeoutError``.
- **Partial-result acceptance:** :meth:`accept_partial_result` converts a
  :class:`SlotResult` (from ``arena_engine.slot_runner``) into a
  :class:`PartialResult`.  Results from ``"timeout"`` or ``"failed"``
  slots are accepted and marked as partial; successful results are
  accepted but not marked.

This module never lets an agent crash or timeout hang the run — the
cleanup callback ensures all subprocesses are terminated.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from arena_engine.slot_runner import SlotResult

__all__ = ["PartialResult", "SubprocessController"]


# ---------------------------------------------------------------------------
# PartialResult — frozen slotted dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PartialResult:
    """Outcome of :meth:`SubprocessController.accept_partial_result`.

    Attributes
    ----------
    accepted
        Whether the result was accepted (always ``True`` for
        ``success``, ``timeout``, and ``failed`` statuses).
    status
        The original ``SlotResult.status`` value.
    content
        The original ``SlotResult.content`` (may be ``None``).
    marked
        ``True`` when the result is a *partial* result (from timeout or
        crash).  ``False`` for fully successful results.
    metadata
        Additional metadata copied from the ``SlotResult``.
    """

    accepted: bool
    status: str
    content: str | None
    marked: bool
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# SubprocessController
# ---------------------------------------------------------------------------


CleanupCallback = Callable[[], Awaitable[None]]


class SubprocessController:
    """Liveness check + per-run timeout + partial-result acceptance.

    Parameters
    ----------
    timeout_seconds
        Default per-run timeout in seconds (default ``300.0``).
    liveness_check_interval
        Interval between periodic liveness checks in seconds (default
        ``5.0``).  Stored for use by the periodic liveness loop wired in
        Plan 05.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 300.0,
        liveness_check_interval: float = 5.0,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._liveness_check_interval = liveness_check_interval
        self._cleanup_callback: CleanupCallback | None = None

    # ------------------------------------------------------------------
    # Liveness
    # ------------------------------------------------------------------

    def check_liveness(self, adapter: Any) -> bool:
        """Check whether all active subprocess sessions are alive.

        Calls ``adapter.get_active_pids()`` and probes each PID with
        ``os.kill(pid, 0)``.  Returns ``True`` when all PIDs are alive
        (or when no sessions are active).  Returns ``False`` as soon as
        any PID is found to be dead (``ProcessLookupError``).
        """
        pids: set[int] = adapter.get_active_pids()
        for pid in pids:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                # Process is dead
                return False
            except PermissionError:
                # Process exists but we lack permission — treat as alive
                continue
        return True

    # ------------------------------------------------------------------
    # Per-run timeout
    # ------------------------------------------------------------------

    def set_cleanup_callback(self, callback: CleanupCallback) -> None:
        """Register a cleanup callback invoked on timeout.

        The callback (typically ``ArenaEngine.cancel``) is awaited after
        a :meth:`run_with_timeout` times out, before the
        ``TimeoutError`` is re-raised.  This ensures no orphaned
        subprocesses remain.
        """
        self._cleanup_callback = callback

    async def run_with_timeout(
        self,
        coro: Awaitable[Any],
        timeout_seconds: float | None = None,
    ) -> Any:
        """Run *coro* with a timeout, triggering cleanup on expiry.

        Wraps the coroutine in ``asyncio.wait_for``.  If the timeout
        elapses, the registered cleanup callback (if any) is awaited,
        then ``asyncio.TimeoutError`` is re-raised.

        Parameters
        ----------
        coro
            The awaitable to run.
        timeout_seconds
            Override for the default timeout.  When ``None``, uses the
            controller's ``timeout_seconds`` from construction.
        """
        effective_timeout = timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        try:
            return await asyncio.wait_for(coro, timeout=effective_timeout)
        except asyncio.TimeoutError:
            if self._cleanup_callback is not None:
                try:
                    await self._cleanup_callback()
                except Exception:
                    # Cleanup failures must not mask the timeout.
                    pass
            raise

    # ------------------------------------------------------------------
    # Partial-result acceptance
    # ------------------------------------------------------------------

    def accept_partial_result(self, slot_result: "SlotResult") -> PartialResult:
        """Convert a :class:`SlotResult` into a :class:`PartialResult`.

        - ``"timeout"`` and ``"failed"`` → accepted, marked as partial.
        - ``"success"`` → accepted, not marked.
        - Any other status → not accepted, not marked.
        """
        status = slot_result.status
        content = slot_result.content
        metadata = dict(slot_result.metadata)

        if status in ("timeout", "failed"):
            return PartialResult(
                accepted=True,
                status=status,
                content=content,
                marked=True,
                metadata=metadata,
            )
        if status == "success":
            return PartialResult(
                accepted=True,
                status="success",
                content=content,
                marked=False,
                metadata=metadata,
            )
        return PartialResult(
            accepted=False,
            status=status,
            content=content,
            marked=False,
            metadata=metadata,
        )
