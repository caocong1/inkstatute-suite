"""Tests for SubprocessLifecycleManager — session-end, timeout, crash, orphan detection.

All tests use the echo agent fixture (stdlib only, no network or external agents).
Tests explicitly assert no orphan processes remain after:
  (a) normal session close, (b) timeout, (c) crash, (d) multiple sessions.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import unittest

from inkstatute_acp_client.lifecycle import (
    SubprocessLifecycleManager,
    assert_no_orphans,
)

ECHO_AGENT = "packages/acp-client/tests/fixtures/echo_agent.py"

# A tiny inline script that ignores SIGTERM — used to simulate a process
# that resists graceful shutdown, so we can test orphan detection.
_SIGTERM_IGNORER = (
    "import signal, sys, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "sys.stdout.write('alive\\n')\n"
    "sys.stdout.flush()\n"
    "time.sleep(30)\n"
)


def _spawn_echo() -> asyncio.subprocess.Process:
    """Spawn the echo agent fixture subprocess."""
    return asyncio.create_subprocess_exec(
        "python",
        ECHO_AGENT,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


def _spawn_sigterm_ignorer_popen() -> subprocess.Popen:
    """Spawn a SIGTERM-ignoring process via subprocess.Popen.

    Uses Popen (not asyncio) so the process is not tracked by the asyncio
    event loop.  This ensures the process survives SIGTERM, allowing us
    to test that ``assert_no_orphans`` detects it as an orphan.
    """
    return subprocess.Popen(
        ["python", "-c", _SIGTERM_IGNORER],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _pid_dead(pid: int) -> bool:
    """Return True if the given PID is no longer alive."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


class TestSubprocessLifecycle(unittest.IsolatedAsyncioTestCase):
    """Tests for SubprocessLifecycleManager lifecycle controls."""

    async def asyncSetUp(self) -> None:
        """Track managers created during tests for tearDown cleanup."""
        self._managers: list[SubprocessLifecycleManager] = []
        self._extra_pids: list[int] = []
        self._extra_popens: list[subprocess.Popen] = []

    async def asyncTearDown(self) -> None:
        """Clean up any remaining processes and managers."""
        for mgr in self._managers:
            try:
                await asyncio.wait_for(mgr.cleanup_all(), timeout=10.0)
            except Exception:
                pass
        # Force-kill any extra PIDs that were manually spawned
        for pid in self._extra_pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        # Reap and close Popen objects to avoid ResourceWarning
        for popen in self._extra_popens:
            try:
                popen.kill()
                popen.wait(timeout=5.0)
            except Exception:
                pass
            try:
                popen.stdin.close()
            except Exception:
                pass
            try:
                popen.stdout.close()
            except Exception:
                pass
            try:
                popen.stderr.close()
            except Exception:
                pass

    def _make_manager(self, **kwargs) -> SubprocessLifecycleManager:
        """Create a manager and track it for tearDown."""
        mgr = SubprocessLifecycleManager(**kwargs)
        self._managers.append(mgr)
        return mgr

    # ------------------------------------------------------------------
    # (1) register and cleanup
    # ------------------------------------------------------------------

    async def test_register_and_cleanup(self) -> None:
        """Spawn echo agent, register, cleanup — PID removed and dead."""
        mgr = self._make_manager()
        proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
        pid = proc.pid
        mgr.register("s1", pid, process=proc)

        self.assertIn(pid, mgr.get_active_pids())

        await asyncio.wait_for(mgr.cleanup("s1"), timeout=10.0)

        self.assertNotIn(pid, mgr.get_active_pids())
        self.assertTrue(_pid_dead(pid), f"pid {pid} still alive after cleanup")

    # ------------------------------------------------------------------
    # (2) cleanup_all removes everything
    # ------------------------------------------------------------------

    async def test_cleanup_all_removes_everything(self) -> None:
        """Spawn 3 echo agents, register all, cleanup_all — all dead."""
        mgr = self._make_manager()
        pids = []
        for i in range(3):
            proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
            pids.append(proc.pid)
            mgr.register(f"s{i}", proc.pid, process=proc)

        self.assertEqual(len(mgr.get_active_pids()), 3)

        await asyncio.wait_for(mgr.cleanup_all(), timeout=10.0)

        self.assertEqual(mgr.get_active_pids(), [])
        for pid in pids:
            self.assertTrue(_pid_dead(pid), f"pid {pid} still alive after cleanup_all")

    # ------------------------------------------------------------------
    # (3) no orphans after cleanup
    # ------------------------------------------------------------------

    async def test_no_orphans_after_cleanup(self) -> None:
        """Spawn echo agent, register, assert_no_orphans — no exception."""
        mgr = self._make_manager()
        proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
        mgr.register("s1", proc.pid, process=proc)

        # Should not raise
        await asyncio.wait_for(assert_no_orphans(mgr), timeout=10.0)

    # ------------------------------------------------------------------
    # (4) orphan detection raises
    # ------------------------------------------------------------------

    async def test_orphan_detection_raises(self) -> None:
        """Spawn SIGTERM-ignoring process via Popen, register with process=None,
        assert_no_orphans — should raise RuntimeError.

        The process is spawned via ``subprocess.Popen`` (not asyncio) so it
        is not tracked by the event loop.  It ignores SIGTERM, so when
        ``cleanup_all`` sends SIGTERM via ``os.kill``, the process survives.
        ``assert_no_orphans`` then detects it as still alive and raises.
        """
        mgr = self._make_manager()
        proc = _spawn_sigterm_ignorer_popen()
        pid = proc.pid
        self._extra_pids.append(pid)
        self._extra_popens.append(proc)

        # Wait for the process to set up its signal handler
        await asyncio.sleep(0.3)

        # Register with process=None so cleanup can only os.kill SIGTERM
        # (the process ignores SIGTERM, so it survives cleanup_all)
        mgr.register("orphan", pid, process=None)

        with self.assertRaises(RuntimeError) as ctx:
            await asyncio.wait_for(assert_no_orphans(mgr, grace_seconds=1.0), timeout=10.0)

        self.assertIn("orphan process", str(ctx.exception))

    # ------------------------------------------------------------------
    # (5) timeout recovery
    # ------------------------------------------------------------------

    async def test_timeout_recovery(self) -> None:
        """Create manager with timeout_seconds=0.1, spawn, wait, check_timeouts."""
        mgr = self._make_manager(timeout_seconds=0.1)
        proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
        mgr.register("t1", proc.pid, process=proc)

        await asyncio.sleep(0.2)

        timed_out = await asyncio.wait_for(mgr.check_timeouts(), timeout=10.0)

        self.assertIn("t1", timed_out)
        self.assertTrue(_pid_dead(proc.pid), "process should be dead after timeout cleanup")

    # ------------------------------------------------------------------
    # (6) crash detection
    # ------------------------------------------------------------------

    async def test_crash_detection(self) -> None:
        """Spawn echo agent, kill externally, detect_crash returns True."""
        mgr = self._make_manager()
        proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
        mgr.register("c1", proc.pid, process=proc)

        os.kill(proc.pid, signal.SIGKILL)
        await asyncio.wait_for(proc.wait(), timeout=10.0)

        crashed = await asyncio.wait_for(mgr.detect_crash("c1"), timeout=10.0)

        self.assertTrue(crashed, "detect_crash should return True for killed process")

    # ------------------------------------------------------------------
    # (7) restart after crash
    # ------------------------------------------------------------------

    async def test_restart_after_crash(self) -> None:
        """Spawn echo agent, kill it, restart_if_needed returns new alive PID."""
        mgr = self._make_manager(max_restarts=1)
        proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
        mgr.register("r1", proc.pid, process=proc)

        os.kill(proc.pid, signal.SIGKILL)
        await asyncio.wait_for(proc.wait(), timeout=10.0)

        new_pid = await asyncio.wait_for(
            mgr.restart_if_needed("r1", ("python", ECHO_AGENT)),
            timeout=10.0,
        )

        self.assertIsNotNone(new_pid, "restart_if_needed should return a new PID")
        self.assertNotEqual(new_pid, proc.pid, "new PID should differ from old")
        # Verify new process is alive
        try:
            os.kill(new_pid, 0)
        except (ProcessLookupError, PermissionError):
            self.fail(f"new process pid {new_pid} is not alive")

    # ------------------------------------------------------------------
    # (8) max restarts exceeded
    # ------------------------------------------------------------------

    async def test_max_restarts_exceeded(self) -> None:
        """Create manager with max_restarts=0, kill process, restart returns None."""
        mgr = self._make_manager(max_restarts=0)
        proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
        mgr.register("m1", proc.pid, process=proc)

        os.kill(proc.pid, signal.SIGKILL)
        await asyncio.wait_for(proc.wait(), timeout=10.0)

        result = await asyncio.wait_for(
            mgr.restart_if_needed("m1", ("python", ECHO_AGENT)),
            timeout=10.0,
        )

        self.assertIsNone(result, "restart_if_needed should return None when max_restarts=0")

    # ------------------------------------------------------------------
    # (9) context manager cleans up
    # ------------------------------------------------------------------

    async def test_context_manager_cleans_up(self) -> None:
        """Use async with manager, spawn inside, exit — process dead."""
        mgr = self._make_manager()
        proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
        mgr.register("ctx1", proc.pid, process=proc)
        pid = proc.pid

        # Use the context manager protocol
        async with mgr:
            # Process should be registered inside the context
            self.assertIn(pid, mgr.get_active_pids())

        # After __aexit__, process should be dead and registry empty
        self.assertEqual(mgr.get_active_pids(), [])
        self.assertTrue(_pid_dead(pid), f"pid {pid} still alive after context exit")

    # ------------------------------------------------------------------
    # (10) multiple sessions no leak
    # ------------------------------------------------------------------

    async def test_multiple_sessions_no_leak(self) -> None:
        """Spawn 5 echo agents, register each, cleanup all, assert_no_orphans."""
        mgr = self._make_manager()
        pids = []
        for i in range(5):
            proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
            pids.append(proc.pid)
            mgr.register(f"multi-{i}", proc.pid, process=proc)

        self.assertEqual(len(mgr.get_active_pids()), 5)

        # Should not raise — all processes properly cleaned up
        await asyncio.wait_for(assert_no_orphans(mgr), timeout=15.0)

        for pid in pids:
            self.assertTrue(_pid_dead(pid), f"pid {pid} still alive — process leak!")

    # ------------------------------------------------------------------
    # (11) touch updates last_activity
    # ------------------------------------------------------------------

    async def test_touch_updates_last_activity(self) -> None:
        """Register a process, record last_activity, touch, assert increased."""
        mgr = self._make_manager()
        proc = await asyncio.wait_for(_spawn_echo(), timeout=10.0)
        mgr.register("touch1", proc.pid, process=proc)

        old_activity = mgr._subprocesses["touch1"].last_activity
        await asyncio.sleep(0.05)
        mgr.touch("touch1")
        new_activity = mgr._subprocesses["touch1"].last_activity

        self.assertGreater(new_activity, old_activity,
                           "touch should update last_activity to a later time")

    # ------------------------------------------------------------------
    # (12) atexit handler registered
    # ------------------------------------------------------------------

    async def test_atexit_handler_registered(self) -> None:
        """Import the module, create manager — _atexit_registered should be True."""
        mgr = self._make_manager()
        self.assertTrue(mgr._atexit_registered,
                        "atexit handler should be registered after construction")

    # ------------------------------------------------------------------
    # (13) touch raises KeyError for unregistered lifecycle_id
    # ------------------------------------------------------------------

    async def test_touch_raises_keyerror(self) -> None:
        """touch on unregistered lifecycle_id should raise KeyError."""
        mgr = self._make_manager()
        with self.assertRaises(KeyError):
            mgr.touch("nonexistent")


if __name__ == "__main__":
    unittest.main()
