"""Tests for the ProcessSupervisor orchestrator."""

from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
import time
import unittest

from admin_console_api.process_registry import ProcessRecord
from admin_console_api.process_supervisor import ProcessSupervisor


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ProcessSupervisorTests(unittest.TestCase):
    """Integration tests for starting, stopping, and probing WeCom/QQBot hosts."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.state_path = os.path.join(self.tmpdir.name, "state.json")
        self.log_dir = os.path.join(self.tmpdir.name, "logs")
        self.port = _find_free_port()
        self.env = {
            "INKSTATUTE_PROCESS_STATE_PATH": self.state_path,
            "INKSTATUTE_PROCESS_LOG_DIR": self.log_dir,
            "WECOM_HOST_HOST": "127.0.0.1",
            "WECOM_HOST_PORT": str(self.port),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        }

    def _supervisor(self) -> ProcessSupervisor:
        supervisor = ProcessSupervisor(env=self.env)
        self.addCleanup(supervisor.shutdown_all)
        return supervisor

    def _wait_for_status(self, supervisor: ProcessSupervisor, name: str, target: str, timeout: int = 15) -> ProcessRecord:
        deadline = time.time() + timeout
        record = supervisor.status(name)
        while record.status != target and time.time() < deadline:
            time.sleep(0.2)
            record = supervisor.status(name)
        return record

    def test_start_stop_and_status(self) -> None:
        supervisor = self._supervisor()
        record = supervisor.start("wecom")
        self.assertEqual(record.status, "starting")
        self.assertIsNotNone(record.pid)

        running = self._wait_for_status(supervisor, "wecom", "running")
        self.assertEqual(running.status, "running")
        self.assertEqual(running.port, self.port)

        stopped = supervisor.stop("wecom")
        self.assertEqual(stopped.status, "stopped")
        self.assertIsNone(stopped.pid)
        self.assertIsNotNone(stopped.last_exit_code)

    def test_start_is_idempotent_when_running(self) -> None:
        supervisor = self._supervisor()
        first = supervisor.start("wecom")
        running = self._wait_for_status(supervisor, "wecom", "running")
        self.assertEqual(running.status, "running")

        second = supervisor.start("wecom")
        self.assertEqual(first.pid, second.pid)

    def test_restart_replaces_process(self) -> None:
        supervisor = self._supervisor()
        first = supervisor.start("wecom")
        self._wait_for_status(supervisor, "wecom", "running")

        restarted = supervisor.restart("wecom")
        self._wait_for_status(supervisor, "wecom", "running")
        self.assertNotEqual(first.pid, restarted.pid)

    def test_status_all_returns_both_channels(self) -> None:
        supervisor = self._supervisor()
        all_records = supervisor.status_all()
        names = {record.name for record in all_records}
        self.assertEqual(names, {"wecom", "qqbot"})

    def test_stop_idempotent_when_not_running(self) -> None:
        supervisor = self._supervisor()
        record = supervisor.stop("wecom")
        self.assertEqual(record.status, "stopped")

    def test_reconcile_marks_unknown_pids_orphaned(self) -> None:
        state = {
            "wecom": {
                "name": "wecom",
                "status": "running",
                "pid": 999999,
                "started_at": "2026-01-01T00:00:00Z",
                "host": "127.0.0.1",
                "port": self.port,
                "log_path": os.path.join(self.log_dir, "wecom-host.log"),
                "metadata": {},
            }
        }
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)

        supervisor = self._supervisor()
        supervisor.reconcile_on_startup()
        record = supervisor._registry.get("wecom")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.status, "orphaned")
        self.assertEqual(record.pid, 999999)

    def test_persist_reloads_state(self) -> None:
        supervisor = self._supervisor()
        supervisor.start("wecom")
        self._wait_for_status(supervisor, "wecom", "running")
        supervisor.stop("wecom")

        second = ProcessSupervisor(env=self.env)
        self.addCleanup(second.shutdown_all)
        second.reconcile_on_startup()
        record = second._registry.get("wecom")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.status, "stopped")


if __name__ == "__main__":
    unittest.main()
