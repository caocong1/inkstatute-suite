"""Subprocess lifecycle management for ACP per-session mode.

Provides :class:`SubprocessLifecycleManager` — the safety net that makes
``per_session`` mode production-usable at single-firm scale (≤50 lawyers).

Lifecycle controls implemented:

- **Session-end recovery:** ``cleanup`` sends ``SIGTERM``, waits 5 s,
  sends ``SIGKILL`` if still alive, removes from registry.
- **Timeout recovery:** ``check_timeouts`` finds inactive subprocesses
  (``time.monotonic() - last_activity > timeout_seconds``) and cleans them up.
- **Crash restart:** ``detect_crash`` finds unexpectedly exited processes;
  ``restart_if_needed`` respawns within ``max_restarts`` limit.
- **No process leaks:** ``atexit`` handler + context manager + orphan
  detection (:func:`assert_no_orphans`).

Reversibility checkpoint (Plan 89-03-01):
  Verified that the echo agent subprocess can be spawned via
  ``asyncio.create_subprocess_exec``, its PID recorded from ``process.pid``,
  killed with ``SIGKILL``, and detected as dead via ``os.kill(pid, 0)``
  raising ``ProcessLookupError``.  The process object has ``.kill()``,
  ``.wait()``, and ``.terminate()`` methods as expected.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import os
import signal
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SubprocessInfo:
    """Tracks a single registered subprocess.

    Attributes
    ----------
    pid
        Operating-system process ID.
    session_id
        Optional ACP session ID associated with this subprocess.
    started_at
        ``time.monotonic()`` timestamp when the subprocess was registered.
    last_activity
        ``time.monotonic()`` timestamp of the most recent ``touch`` call
        (or ``started_at`` if never touched).
    process
        The :class:`asyncio.subprocess.Process` object, if available.
        May be ``None`` when only the PID is known (e.g. external process).
    """

    pid: int
    session_id: str | None = None
    started_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    process: asyncio.subprocess.Process | None = None


# ---------------------------------------------------------------------------
# SubprocessLifecycleManager
# ---------------------------------------------------------------------------


class SubprocessLifecycleManager:
    """Controls per-session subprocess lifecycle.

    Manages registration, session-end cleanup, timeout recovery, crash
    detection, and crash restart for ACP per-session subprocesses.

    An ``atexit`` handler is registered at construction time to ensure
    best-effort SIGKILL of any remaining processes at interpreter exit.
    The handler is idempotent — safe to call multiple times.

    The manager is also usable as an async context manager::

        async with SubprocessLifecycleManager() as mgr:
            mgr.register("sess-1", pid, process)
            # ... use subprocess ...
        # __aexit__ calls cleanup_all()
    """

    def __init__(
        self,
        timeout_seconds: float = 300.0,
        restart_on_crash: bool = True,
        max_restarts: int = 1,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.restart_on_crash = restart_on_crash
        self.max_restarts = max_restarts
        self._subprocesses: dict[str, SubprocessInfo] = {}
        self._restart_counts: dict[str, int] = {}
        self._atexit_registered: bool = False
        self._register_atexit()

    # -- atexit -----------------------------------------------------------

    def _register_atexit(self) -> None:
        """Register the atexit handler (idempotent)."""
        if not self._atexit_registered:
            atexit.register(self._atexit_cleanup)
            self._atexit_registered = True

    def _atexit_cleanup(self) -> None:
        """Synchronous atexit handler — best-effort SIGKILL of survivors.

        This runs at interpreter exit.  It cannot use ``await`` so it
        sends ``SIGKILL`` directly via :func:`os.kill`.
        """
        for lifecycle_id, info in list(self._subprocesses.items()):
            try:
                os.kill(info.pid, signal.SIGKILL)
                logger.warning(
                    "atexit: sent SIGKILL to orphan subprocess "
                    "lifecycle_id=%s pid=%d",
                    lifecycle_id,
                    info.pid,
                )
            except ProcessLookupError:
                # Already dead — fine
                pass
            except OSError as exc:
                logger.error(
                    "atexit: failed to kill subprocess "
                    "lifecycle_id=%s pid=%d: %s",
                    lifecycle_id,
                    info.pid,
                    exc,
                )

    # -- registration -----------------------------------------------------

    def register(
        self,
        lifecycle_id: str,
        pid: int,
        process: asyncio.subprocess.Process | None = None,
        session_id: str | None = None,
    ) -> None:
        """Register a subprocess for lifecycle tracking.

        Parameters
        ----------
        lifecycle_id
            Unique key for this subprocess (e.g. session ID or run ID).
        pid
            Operating-system process ID.
        process
            The :class:`asyncio.subprocess.Process` object, if available.
        session_id
            Optional ACP session ID.
        """
        now = time.monotonic()
        self._subprocesses[lifecycle_id] = SubprocessInfo(
            pid=pid,
            session_id=session_id,
            started_at=now,
            last_activity=now,
            process=process,
        )
        logger.debug(
            "Registered subprocess lifecycle_id=%s pid=%d", lifecycle_id, pid
        )

    def touch(self, lifecycle_id: str) -> None:
        """Update ``last_activity`` for the given lifecycle_id.

        Raises
        ------
        KeyError
            If ``lifecycle_id`` is not registered.
        """
        info = self._subprocesses[lifecycle_id]
        info.last_activity = time.monotonic()

    # -- cleanup ----------------------------------------------------------

    async def cleanup(self, lifecycle_id: str) -> None:
        """Perform session-end recovery for a single subprocess.

        Sequence:
        1. Look up :class:`SubprocessInfo`.
        2. If process is available, send ``SIGTERM`` via ``process.terminate()``.
        3. Wait up to 5 seconds for the process to exit.
        4. If still alive, send ``SIGKILL`` via ``process.kill()``.
        5. Wait up to 2 more seconds.
        6. Remove from ``_subprocesses``.

        Catches ``ProcessLookupError`` (already dead — fine).
        """
        info = self._subprocesses.pop(lifecycle_id, None)
        if info is None:
            logger.debug("cleanup: lifecycle_id=%s not registered", lifecycle_id)
            return

        process = info.process
        if process is None:
            logger.debug(
                "cleanup: lifecycle_id=%s pid=%d — no process object, "
                "attempting os.kill SIGTERM",
                lifecycle_id,
                info.pid,
            )
            try:
                os.kill(info.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            return

        try:
            # Step 2: SIGTERM
            process.terminate()
            logger.debug(
                "cleanup: sent SIGTERM to lifecycle_id=%s pid=%d",
                lifecycle_id,
                info.pid,
            )

            # Step 3: wait up to 5 seconds
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Step 4: SIGKILL
                logger.warning(
                    "cleanup: SIGTERM timeout for lifecycle_id=%s pid=%d, "
                    "sending SIGKILL",
                    lifecycle_id,
                    info.pid,
                )
                process.kill()
                # Step 5: wait up to 2 more seconds
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.error(
                        "cleanup: SIGKILL timeout for lifecycle_id=%s pid=%d",
                        lifecycle_id,
                        info.pid,
                    )
        except ProcessLookupError:
            # Already dead — fine
            logger.debug(
                "cleanup: lifecycle_id=%s pid=%d already dead",
                lifecycle_id,
                info.pid,
            )

        logger.info(
            "cleanup: completed for lifecycle_id=%s pid=%d",
            lifecycle_id,
            info.pid,
        )

    async def cleanup_all(self) -> None:
        """Call :meth:`cleanup` for every registered lifecycle_id."""
        lifecycle_ids = list(self._subprocesses.keys())
        for lifecycle_id in lifecycle_ids:
            await self.cleanup(lifecycle_id)

    # -- timeout recovery -------------------------------------------------

    async def check_timeouts(self) -> list[str]:
        """Find and clean up inactive subprocesses.

        Returns
        -------
        list[str]
            Lifecycle IDs that exceeded the timeout and were cleaned up.
        """
        now = time.monotonic()
        timed_out: list[str] = []
        for lifecycle_id, info in list(self._subprocesses.items()):
            if now - info.last_activity > self.timeout_seconds:
                timed_out.append(lifecycle_id)

        for lifecycle_id in timed_out:
            logger.info(
                "check_timeouts: lifecycle_id=%s exceeded timeout %.1fs",
                lifecycle_id,
                self.timeout_seconds,
            )
            await self.cleanup(lifecycle_id)

        return timed_out

    # -- crash detection & restart ----------------------------------------

    async def detect_crash(self, lifecycle_id: str) -> bool:
        """Check if a subprocess has exited unexpectedly.

        Returns ``True`` if the process has exited (``returncode is not
        None``) but was not explicitly cleaned up (still in
        ``_subprocesses``).
        """
        info = self._subprocesses.get(lifecycle_id)
        if info is None:
            return False
        if info.process is None:
            return False
        return info.process.returncode is not None

    async def restart_if_needed(
        self,
        lifecycle_id: str,
        restart_command: tuple[str, ...],
        env: dict[str, str] | None = None,
    ) -> int | None:
        """Restart the subprocess if a crash is detected.

        Parameters
        ----------
        lifecycle_id
            The lifecycle ID to check and potentially restart.
        restart_command
            Command tuple to spawn the new subprocess.
        env
            Optional environment variables for the new subprocess.

        Returns
        -------
        int or None
            The new PID if restarted, or ``None`` if no restart was
            needed or ``max_restarts`` was exceeded.
        """
        crashed = await self.detect_crash(lifecycle_id)
        if not crashed:
            return None

        if not self.restart_on_crash:
            logger.info(
                "restart_if_needed: crash detected but restart_on_crash=False"
            )
            await self.cleanup(lifecycle_id)
            return None

        restart_count = self._restart_counts.get(lifecycle_id, 0)
        if restart_count >= self.max_restarts:
            logger.warning(
                "restart_if_needed: max_restarts=%d exceeded for "
                "lifecycle_id=%s",
                self.max_restarts,
                lifecycle_id,
            )
            await self.cleanup(lifecycle_id)
            return None

        # Clean up the old process
        await self.cleanup(lifecycle_id)

        # Spawn a new subprocess
        import os as _os

        proc_env = dict(_os.environ)
        if env:
            proc_env.update(env)

        process = await asyncio.create_subprocess_exec(
            *restart_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=proc_env,
        )

        new_pid = process.pid
        self._restart_counts[lifecycle_id] = restart_count + 1
        self.register(lifecycle_id, new_pid, process=process)

        logger.info(
            "restart_if_needed: restarted lifecycle_id=%s new_pid=%d "
            "(restart #%d)",
            lifecycle_id,
            new_pid,
            restart_count + 1,
        )
        return new_pid

    # -- introspection ----------------------------------------------------

    def get_active_pids(self) -> list[int]:
        """Return PIDs of all registered subprocesses."""
        return [info.pid for info in self._subprocesses.values()]

    # -- context manager --------------------------------------------------

    async def __aenter__(self) -> SubprocessLifecycleManager:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.cleanup_all()


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------


async def assert_no_orphans(
    manager: SubprocessLifecycleManager,
    grace_seconds: float = 2.0,
) -> None:
    """Assert that no orphan processes remain after cleanup.

    1. Records all currently-registered PIDs.
    2. Calls ``await manager.cleanup_all()``.
    3. Waits ``grace_seconds`` for processes to fully exit.
    4. For each PID that was registered before cleanup, checks
       ``os.kill(pid, 0)`` — if any PID is still alive, raises
       :class:`RuntimeError`.

    Raises
    ------
    RuntimeError
        If any PID is still alive after cleanup + grace period.
    """
    pids_before = manager.get_active_pids()
    await manager.cleanup_all()
    await asyncio.sleep(grace_seconds)

    for pid in pids_before:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            # Dead — good
            continue
        except PermissionError:
            # Process may exist but we lack permission — treat as alive
            raise RuntimeError(
                f"orphan process detected: pid {pid} still alive after cleanup"
            ) from None
        else:
            # os.kill(pid, 0) succeeded — process is still alive
            raise RuntimeError(
                f"orphan process detected: pid {pid} still alive after cleanup"
            ) from None


__all__ = [
    "SubprocessInfo",
    "SubprocessLifecycleManager",
    "assert_no_orphans",
]
