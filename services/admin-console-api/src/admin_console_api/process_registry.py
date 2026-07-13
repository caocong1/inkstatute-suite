"""Guarded in-process process table for Phase 80 orchestration."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProcessRecord:
    """Snapshot of a managed channel host process."""

    name: str
    status: str = "stopped"
    pid: int | None = None
    started_at: str | None = None
    last_exit_code: int | None = None
    host: str = "127.0.0.1"
    port: int = 0
    log_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ProcessRegistry:
    """Thread-safe process table for WeCom/QQBot host orchestration.

    Phase 79 creates the guarded table; Phase 80 will start/stop processes
    through this registry.
    """

    def __init__(self) -> None:
        self._records: dict[str, ProcessRecord] = {}
        self._lock = threading.Lock()

    def add(self, name: str, record: ProcessRecord) -> None:
        with self._lock:
            self._records[name] = record

    def remove(self, name: str) -> ProcessRecord | None:
        with self._lock:
            return self._records.pop(name, None)

    def get(self, name: str) -> ProcessRecord | None:
        with self._lock:
            return self._records.get(name)

    def list(self) -> list[ProcessRecord]:
        with self._lock:
            return list(self._records.values())

    def replace(self, name: str, record: ProcessRecord) -> None:
        with self._lock:
            self._records[name] = record


__all__ = ["ProcessRecord", "ProcessRegistry"]
