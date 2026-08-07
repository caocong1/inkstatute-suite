"""In-memory per-run event buffer for SSE Last-Event-ID reconnection.

When a client disconnects from a ``GET /v1/runs/{id}/events`` SSE stream and
reconnects with a ``Last-Event-ID`` header, the Gateway replays all events with
``seq > last_event_id`` from this buffer, then continues streaming new events.

The buffer is purely in-memory (no persistent storage, no external
dependencies). This is sufficient for single-firm scale (<=50 lawyers) per
Key Decision #4 in the Phase 91 context.

Buffer size is capped at ``max_events_per_run`` (default 1000) per run. When a
run reaches terminal state (``run.state_changed`` with status ``succeeded``,
``failed``, or ``cancelled``), the buffer retains events for
``terminal_retention_seconds`` (default 300 = 5 minutes) before cleanup.

Thread-safe via ``threading.Lock`` — the Gateway may serve multiple concurrent
SSE connections.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List

from platform_contract.enums import RunEventType
from platform_runtime.protocols import RunEvent

# Terminal run statuses that trigger buffer retention countdown.
_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


@dataclass
class BufferedEvent:
    """A RunEvent wrapped with buffer metadata.

    Attributes:
        event: The original RunEvent.
        buffered_at: Timestamp (time.time()) when the event was added to the buffer.
    """

    event: RunEvent
    buffered_at: float


class RunEventBuffer:
    """In-memory event buffer per run_id with seq-based replay.

    Stores events per ``run_id`` with their ``seq`` numbers. On reconnection
    with ``Last-Event-ID``, the Gateway calls :meth:`replay` to get events
    with ``seq > last_seq``, ordered by ``seq`` ascending.

    The buffer is thread-safe (uses ``threading.Lock``).
    """

    def __init__(
        self,
        *,
        max_events_per_run: int = 1000,
        terminal_retention_seconds: float = 300.0,
    ) -> None:
        self._max_events_per_run = max_events_per_run
        self._terminal_retention_seconds = terminal_retention_seconds
        self._buffers: Dict[str, List[BufferedEvent]] = {}
        self._terminal_at: Dict[str, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, run_id: str, event: RunEvent) -> None:
        """Append an event to the buffer for ``run_id``.

        If the buffer exceeds ``max_events_per_run``, the oldest events are
        evicted (FIFO). If the event indicates a terminal state, the run is
        marked terminal with a timestamp.
        """
        with self._lock:
            buf = self._buffers.setdefault(run_id, [])
            buf.append(BufferedEvent(event=event, buffered_at=time.time()))
            # FIFO eviction when over capacity
            while len(buf) > self._max_events_per_run:
                buf.pop(0)
            # Check for terminal state
            if _is_terminal_event(event):
                self._terminal_at.setdefault(run_id, time.time())

    def replay(self, run_id: str, last_seq: int) -> list[RunEvent]:
        """Return events for ``run_id`` with ``seq > last_seq``, ordered by seq.

        Returns an empty list if no events match or the buffer has been
        cleaned up.
        """
        with self._lock:
            buf = self._buffers.get(run_id)
            if buf is None:
                return []
            events = [be.event for be in buf if be.event.seq > last_seq]
            events.sort(key=lambda e: e.seq)
            return events

    def get_buffered_events(self, run_id: str) -> list[RunEvent]:
        """Return all buffered events for ``run_id`` (for testing/debugging)."""
        with self._lock:
            buf = self._buffers.get(run_id)
            if buf is None:
                return []
            return [be.event for be in buf]

    def is_terminal(self, run_id: str) -> bool:
        """Return ``True`` if the run has reached terminal state."""
        with self._lock:
            return run_id in self._terminal_at

    def cleanup_expired(self, now: float | None = None) -> int:
        """Remove buffers for terminal runs whose retention period has expired.

        Returns the count of removed run buffers.
        """
        if now is None:
            now = time.time()
        removed = 0
        with self._lock:
            expired = [
                run_id
                for run_id, terminal_at in self._terminal_at.items()
                if (now - terminal_at) >= self._terminal_retention_seconds
            ]
            for run_id in expired:
                self._buffers.pop(run_id, None)
                self._terminal_at.pop(run_id, None)
                removed += 1
        return removed

    def clear_run(self, run_id: str) -> None:
        """Remove the buffer for a specific run.

        Used when a run is cancelled or explicitly cleaned up.
        """
        with self._lock:
            self._buffers.pop(run_id, None)
            self._terminal_at.pop(run_id, None)


def _is_terminal_event(event: RunEvent) -> bool:
    """Check if the event indicates a terminal run state.

    A terminal event has ``event_type == "run.state_changed"`` and a payload
    with ``status`` in ``{succeeded, failed, cancelled}``.
    """
    event_type_str = str(event.event_type)
    if event_type_str != RunEventType.RUN_STATE_CHANGED.value:
        return False
    payload = event.payload or {}
    status = payload.get("status")
    if status is None:
        return False
    return str(status) in _TERMINAL_STATUSES


__all__ = [
    "BufferedEvent",
    "RunEventBuffer",
]
