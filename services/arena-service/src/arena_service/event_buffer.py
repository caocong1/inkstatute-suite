"""In-memory per-arena event buffer for SSE Last-Event-ID reconnection.

When a client disconnects from an arena SSE stream and reconnects with a
``Last-Event-ID`` header, the Arena Service replays all events with
``seq > last_event_id`` from this buffer, then continues streaming new
events.

The buffer is purely in-memory (no persistent storage, no external
dependencies). This is sufficient for single-firm scale (<=50 lawyers)
per Key Decision #4.

Buffer size is capped at ``max_events_per_arena`` (default 1000) per
arena. When an arena reaches terminal state
(``arena.workflow_completed``, ``arena.workflow_cancelled``, or
``arena.workflow_failed``), the buffer retains events for
``terminal_retention_seconds`` (default 300 = 5 minutes) before cleanup.

Thread-safe via ``threading.Lock`` — the Arena Service may serve
multiple concurrent SSE connections.

SVC-07: seq-based replay guarantees no duplication and no loss. The
client reconnects with ``Last-Event-ID`` (parsed by
:func:`arena_service.sse.parse_last_event_id`), and
:meth:`ArenaEventBuffer.replay` returns exactly the events with
``seq > last_seq``.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

# Terminal arena event types that trigger buffer retention countdown.
_ARENA_TERMINAL_EVENT_TYPES = frozenset(
    {
        "arena.workflow_completed",
        "arena.workflow_cancelled",
        "arena.workflow_failed",
    }
)


@dataclass
class BufferedArenaEvent:
    """An arena event wrapped with buffer metadata.

    Attributes
    ----------
    event
        The original event dict (with ``seq``, ``event_type``,
        ``event_id``, ``payload``, ``metadata``, etc.).
    buffered_at
        Timestamp (``time.time()``) when the event was added to the
        buffer.
    """

    event: dict[str, Any]
    buffered_at: float


class ArenaEventBuffer:
    """In-memory event buffer per ``arena_id`` with seq-based replay.

    Stores events per ``arena_id`` with their ``seq`` numbers. On
    reconnection with ``Last-Event-ID``, the Arena Service calls
    :meth:`replay` to get events with ``seq > last_seq``, ordered by
    ``seq`` ascending.

    The buffer is thread-safe (uses ``threading.Lock``).
    """

    def __init__(
        self,
        *,
        max_events_per_arena: int = 1000,
        terminal_retention_seconds: float = 300.0,
    ) -> None:
        """Initialize the buffer.

        Parameters
        ----------
        max_events_per_arena
            Maximum number of events to retain per arena. When exceeded,
            the oldest events are evicted (FIFO). Default 1000.
        terminal_retention_seconds
            How long to retain a terminal arena's buffer before cleanup.
            Default 300.0 (5 minutes).
        """
        self._max_events_per_arena = max_events_per_arena
        self._terminal_retention_seconds = terminal_retention_seconds
        self._buffers: Dict[str, List[BufferedArenaEvent]] = {}
        self._terminal_at: Dict[str, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, arena_id: str, event: Mapping[str, Any]) -> None:
        """Append an event to the buffer for ``arena_id``.

        If the buffer exceeds ``max_events_per_arena``, the oldest
        events are evicted (FIFO). If the event indicates a terminal
        state, the arena is marked terminal with a timestamp.

        Parameters
        ----------
        arena_id
            The arena workflow identifier.
        event
            The event dict (must contain ``seq`` and ``event_type``).
        """
        with self._lock:
            buf = self._buffers.setdefault(arena_id, [])
            buf.append(
                BufferedArenaEvent(event=dict(event), buffered_at=time.time())
            )
            # FIFO eviction when over capacity
            while len(buf) > self._max_events_per_arena:
                buf.pop(0)
            # Check for terminal state
            if _is_terminal_event(event):
                self._terminal_at.setdefault(arena_id, time.time())

    def replay(self, arena_id: str, last_seq: int) -> list[dict[str, Any]]:
        """Return events for ``arena_id`` with ``seq > last_seq``, ordered by seq.

        Returns an empty list if no events match or the buffer has been
        cleaned up. Guarantees no duplication (only ``seq > last_seq``)
        and no loss (all matching events are returned).

        Parameters
        ----------
        arena_id
            The arena workflow identifier.
        last_seq
            The last sequence number the client received (from
            ``Last-Event-ID`` header).

        Returns
        -------
        list[dict[str, Any]]
            Events with ``seq > last_seq``, sorted by ``seq`` ascending.
        """
        with self._lock:
            buf = self._buffers.get(arena_id)
            if buf is None:
                return []
            events = [
                dict(be.event)
                for be in buf
                if be.event.get("seq", 0) > last_seq
            ]
            events.sort(key=lambda e: e.get("seq", 0))
            return events

    def get_buffered_events(self, arena_id: str) -> list[dict[str, Any]]:
        """Return all buffered events for ``arena_id`` (for testing/debugging).

        Returns events in insertion order (not sorted by seq).
        """
        with self._lock:
            buf = self._buffers.get(arena_id)
            if buf is None:
                return []
            return [be.event for be in buf]

    def is_terminal(self, arena_id: str) -> bool:
        """Return ``True`` if the arena has reached terminal state."""
        with self._lock:
            return arena_id in self._terminal_at

    def cleanup_expired(self, now: float | None = None) -> int:
        """Remove buffers for terminal arenas whose retention period has expired.

        Parameters
        ----------
        now
            Current timestamp. Defaults to ``time.time()``.

        Returns
        -------
        int
            The count of removed arena buffers.
        """
        if now is None:
            now = time.time()
        removed = 0
        with self._lock:
            expired = [
                arena_id
                for arena_id, terminal_at in self._terminal_at.items()
                if (now - terminal_at) >= self._terminal_retention_seconds
            ]
            for arena_id in expired:
                self._buffers.pop(arena_id, None)
                self._terminal_at.pop(arena_id, None)
                removed += 1
        return removed

    def clear_arena(self, arena_id: str) -> None:
        """Remove the buffer for a specific arena.

        Used when an arena is cancelled or explicitly cleaned up.
        """
        with self._lock:
            self._buffers.pop(arena_id, None)
            self._terminal_at.pop(arena_id, None)


def _is_terminal_event(event: Mapping[str, Any]) -> bool:
    """Check if the event indicates a terminal arena state.

    A terminal event has ``event_type`` in
    ``{arena.workflow_completed, arena.workflow_cancelled,
    arena.workflow_failed}``.
    """
    event_type = str(event.get("event_type", ""))
    return event_type in _ARENA_TERMINAL_EVENT_TYPES


__all__ = [
    "ArenaEventBuffer",
    "BufferedArenaEvent",
]
