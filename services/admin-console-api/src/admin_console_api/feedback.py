"""Thread-safe feedback queue wrapper for concurrent access.

A snapshot of the underlying list is returned under the lock so iteration is
safe even while other threads append or replace the queue.
"""

from __future__ import annotations

import threading
from typing import Any, Iterable


class ThreadSafeFeedbackQueue:
    """Snapshot-under-lock list of pending feedback items.

    Accepts ``list[dict]``-like access: ``for item in queue`` iterates a
    snapshot, ``bool(queue)`` is true when non-empty, and ``append``/``replace``
    mutate the queue under a lock.
    """

    def __init__(self, items: Iterable[dict[str, Any]] | None = None) -> None:
        self._items: list[dict[str, Any]] = list(items) if items else []
        self._lock = threading.Lock()

    def __iter__(self) -> Any:
        with self._lock:
            return iter(list(self._items))

    def __bool__(self) -> bool:
        with self._lock:
            return bool(self._items)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def append(self, item: dict[str, Any]) -> None:
        with self._lock:
            self._items.append(item)

    def replace(self, items: Iterable[dict[str, Any]]) -> None:
        with self._lock:
            self._items = list(items)


__all__ = ["ThreadSafeFeedbackQueue"]
