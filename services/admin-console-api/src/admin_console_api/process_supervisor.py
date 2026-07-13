"""Process orchestrator for WeCom and QQBot host processes.

``ProcessSupervisor`` starts/stops/restarts ``python -m wecom_service`` and
``python -m qqbot_service`` as subprocesses, health-probes them via ``GET
/health``, and persists the process table so it can be reconciled after an
admin-console-api restart.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .process_registry import ProcessRecord, ProcessRegistry

__all__ = ["ProcessSupervisor"]

_PROCESS_NAMES = {"wecom", "qqbot"}

_ALLOWED_ACTIONS = {"start", "stop", "restart"}


class ProcessSupervisor:
    """Manages WeCom/QQBot host subprocesses and exposes their status."""

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        *,
        config_store: Any = None,
    ) -> None:
        self._env = dict(env) if env is not None else dict(os.environ)
        self._config_store = config_store
        self._registry = ProcessRegistry()
        self._procs: dict[str, subprocess.Popen] = {}
        self._state_path = self._resolve_state_path()
        self._log_dir = self._resolve_log_dir()
        self._lock = threading.Lock()

    def _resolve_state_path(self) -> Path:
        raw = self._env.get("INKSTATUTE_PROCESS_STATE_PATH")
        if raw:
            return Path(raw)
        return Path.home() / ".inkstatute" / "process-state.json"

    def _resolve_log_dir(self) -> Path:
        raw = self._env.get("INKSTATUTE_PROCESS_LOG_DIR")
        if raw:
            return Path(raw)
        return Path.home() / ".inkstatute" / "process-logs"

    def _module_name(self, name: str) -> str:
        return "wecom_service" if name == "wecom" else "qqbot_service"

    def _port_env_name(self, name: str) -> str:
        return "WECOM_HOST_PORT" if name == "wecom" else "QQBOT_HOST_PORT"

    def _host_env_name(self, name: str) -> str:
        return "WECOM_HOST_HOST" if name == "wecom" else "QQBOT_HOST_HOST"

    def _channel_enabled_env_name(self, name: str) -> str:
        return (
            "INKSTATUTE_WECOM_CHANNEL_ENABLED"
            if name == "wecom"
            else "INKSTATUTE_QQBOT_CHANNEL_ENABLED"
        )

    def _is_pid_alive(self, pid: int | None) -> bool:
        if pid is None or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _default_pythonpath(self) -> str:
        """Return the canonical source-root PYTHONPATH for child hosts.

        The repo root is derived from ``process_supervisor.py`` location;
        ``parents[4]`` is the repository root because the file lives at
        ``services/admin-console-api/src/admin_console_api/process_supervisor.py``.
        """
        repo_root = Path(__file__).resolve().parents[4]
        paths = [
            repo_root,
            repo_root / "services" / "wecom-service" / "src",
            repo_root / "services" / "qqbot-service" / "src",
            repo_root / "packages" / "platform-runtime" / "src",
            repo_root / "packages" / "platform-contract" / "src",
            repo_root / "packages" / "channel-core" / "src",
            repo_root / "packages" / "channels" / "wecom" / "src",
            repo_root / "packages" / "channels" / "qqbot" / "src",
            repo_root / "packages" / "operator-config" / "src",
        ]
        return os.pathsep.join(str(p) for p in paths)

    def _pythonpath_for_child(self) -> str:
        """Combine any inherited PYTHONPATH with the canonical source roots."""
        existing = self._env.get("PYTHONPATH", "")
        parts = [p for p in existing.split(os.pathsep) if p]
        for candidate in self._default_pythonpath().split(os.pathsep):
            if candidate not in parts:
                parts.append(candidate)
        return os.pathsep.join(parts)

    def _persist(self) -> None:
        state = {record.name: asdict(record) for record in self._registry.list()}
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with open(self._state_path, "w", encoding="utf-8") as fh:
                json.dump(state, fh, ensure_ascii=False, sort_keys=True, indent=2)

    def _ensure_log_dir(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def reconcile_on_startup(self) -> None:
        """Reload persisted state and warn about unknown PIDs.

        PIDs that are not alive are marked ``stopped``. PIDs that are alive but
        were not launched by this supervisor instance are marked ``orphaned``;
        the operator must explicitly restart them before the supervisor takes
        ownership.
        """
        if not self._state_path.is_file():
            return
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                state = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return

        if not isinstance(state, dict):
            return

        for name, data in state.items():
            if name not in _PROCESS_NAMES or not isinstance(data, dict):
                continue
            record = ProcessRecord(**data)
            if record.pid is None:
                record = replace(record, status="stopped")
                self._registry.add(name, record)
                continue
            alive = self._is_pid_alive(record.pid)
            record = replace(record, status="orphaned")
            self._registry.add(name, record)
            print(
                f"warning: process {name} (pid={record.pid}) is not owned by this "
                f"supervisor (alive={alive}); marked orphaned",
                file=sys.stderr,
            )
        self._persist()

    def start(self, name: str) -> ProcessRecord:
        """Start a managed channel host subprocess."""
        if name not in _PROCESS_NAMES:
            raise ValueError(f"unknown process name: {name}")

        host = self._env.get(self._host_env_name(name), "127.0.0.1")
        port = int(
            self._env.get(
                self._port_env_name(name), "8082" if name == "wecom" else "8080"
            )
        )

        child_env = dict(self._env)
        child_env["PYTHONPATH"] = self._pythonpath_for_child()
        child_env[self._channel_enabled_env_name(name)] = "true"
        if name == "wecom":
            child_env["INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED"] = "true"
        child_env["INKSTATUTE_RUN_RUNTIME_ENABLED"] = "true"
        child_env[self._host_env_name(name)] = host
        child_env[self._port_env_name(name)] = str(port)

        with self._lock:
            existing = self._registry.get(name)
            if (
                existing is not None
                and existing.pid is not None
                and existing.status in ("running", "starting", "degraded")
                and self._is_pid_alive(existing.pid)
            ):
                if name in self._procs:
                    proc = self._procs[name]
                    if proc.poll() is None:
                        return existing
                    del self._procs[name]

            if name in self._procs:
                proc = self._procs[name]
                if proc.poll() is None:
                    # A live process is not reflected in the registry.
                    # Kill it so the new child can own the port.
                    try:
                        proc.kill()
                        proc.wait()
                    except OSError:
                        pass
                del self._procs[name]

            if existing is not None and self._is_pid_alive(existing.pid):
                # Defensive: an orphaned or stale process is still alive; try to
                # terminate it before we bind the port.
                try:
                    os.kill(existing.pid, signal.SIGTERM)
                except OSError:
                    pass
                deadline = time.time() + 5
                while self._is_pid_alive(existing.pid) and time.time() < deadline:
                    time.sleep(0.1)

            self._ensure_log_dir()
            log_path = self._log_dir / f"{name}-host.log"
            log_file = open(log_path, "ab")
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-m", self._module_name(name)],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    env=child_env,
                    start_new_session=True,
                )
            finally:
                log_file.close()

            self._procs[name] = proc
            record = ProcessRecord(
                name=name,
                status="starting",
                pid=proc.pid,
                started_at=self._now(),
                host=host,
                port=port,
                log_path=str(log_path),
                metadata={},
            )
            self._registry.add(name, record)

        self._persist()
        return record

    def stop(self, name: str, *, timeout: int = 5) -> ProcessRecord:
        """Stop a managed channel host subprocess."""
        if name not in _PROCESS_NAMES:
            raise ValueError(f"unknown process name: {name}")

        with self._lock:
            record = self._registry.get(name)
            if record is None:
                record = ProcessRecord(name=name, status="stopped")
                self._registry.replace(name, record)
            elif name in self._procs:
                proc = self._procs[name]
                try:
                    proc.terminate()
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                        proc.wait()
                    except OSError:
                        pass
                except OSError:
                    pass
                exit_code = proc.poll()
                del self._procs[name]
                record = replace(
                    record,
                    status="stopped",
                    pid=None,
                    last_exit_code=exit_code,
                )
                self._registry.replace(name, record)
            elif record.pid is not None and self._is_pid_alive(record.pid):
                try:
                    os.kill(record.pid, signal.SIGTERM)
                except OSError:
                    pass
                record = replace(
                    record,
                    status="stopped",
                    pid=None,
                    last_exit_code=None,
                )
                self._registry.replace(name, record)
            else:
                record = replace(record, status="stopped", pid=None)
                self._registry.replace(name, record)

        self._persist()
        return record

    def restart(self, name: str, *, timeout: int = 5) -> ProcessRecord:
        """Stop then start a managed channel host subprocess."""
        self.stop(name, timeout=timeout)
        return self.start(name)

    def status(self, name: str) -> ProcessRecord:
        """Return the current status for a process, probing /health when alive."""
        if name not in _PROCESS_NAMES:
            raise ValueError(f"unknown process name: {name}")

        with self._lock:
            record = self._registry.get(name)
            if record is None:
                return ProcessRecord(name=name, status="stopped")

            if name in self._procs:
                proc = self._procs[name]
                exit_code = proc.poll()
                if exit_code is not None:
                    del self._procs[name]
                    record = replace(
                        record,
                        status="stopped",
                        pid=None,
                        last_exit_code=exit_code,
                    )
                    self._registry.replace(name, record)
            elif not self._is_pid_alive(record.pid):
                record = replace(record, status="stopped", pid=None)
                self._registry.replace(name, record)

        if record.status == "stopped":
            self._persist()
            return record

        health_url = f"http://{record.host}:{record.port}/health"
        try:
            response = urllib.request.urlopen(health_url, timeout=2)
            payload = response.read()
            try:
                health = json.loads(payload)
            except json.JSONDecodeError:
                health = {"ok": False, "raw": payload.decode("utf-8", "replace")}
            status = "running" if health.get("ok") else "degraded"
            record = replace(
                record,
                status=status,
                metadata={
                    **record.metadata,
                    "health": health,
                    "last_probe_at": self._now(),
                },
            )
        except urllib.error.HTTPError as exc:
            record = replace(
                record,
                status="degraded",
                metadata={
                    **record.metadata,
                    "health": {"status_code": exc.code, "ok": False},
                    "last_probe_at": self._now(),
                },
            )
        except urllib.error.URLError as exc:
            record = replace(
                record,
                status="degraded",
                metadata={
                    **record.metadata,
                    "health": {"ok": False, "reason": str(exc.reason)},
                    "last_probe_at": self._now(),
                },
            )

        with self._lock:
            current = self._registry.get(name)
            if current is not None and current.pid == record.pid:
                self._registry.replace(name, record)

        self._persist()
        return record

    def status_all(self) -> list[ProcessRecord]:
        """Return the status for all managed channel hosts."""
        return [self.status(name) for name in sorted(_PROCESS_NAMES)]

    def shutdown_all(self) -> None:
        """Stop every managed process."""
        for record in self._registry.list():
            self.stop(record.name)

    def restart_for_channels(
        self,
        old_channels: Mapping[str, Any],
        new_channels: Mapping[str, Any],
    ) -> list[ProcessRecord]:
        """Restart the channel host for any channel whose config changed.

        ``old_channels`` and ``new_channels`` are the ``channels`` section of
        the operator config before and after the save. Only the WeCom and QQBot
        hosts are considered.
        """

        def _dump(value: Any) -> str:
            return json.dumps(value, sort_keys=True, default=str)

        restarted: list[ProcessRecord] = []
        for channel in ("wecom", "qqbot"):
            old = old_channels.get(channel)
            new = new_channels.get(channel)
            if _dump(old) != _dump(new):
                restarted.append(self.restart(channel))
        return restarted
