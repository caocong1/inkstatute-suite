"""Unit tests for RunEventBuffer — in-memory per-run event buffer.

Tests seq-based replay, FIFO eviction, terminal state detection, cleanup,
thread safety, and isolation between runs.

The buffer is the foundation for SSE Last-Event-ID reconnection (GW-02):
events with seq > last_seq are replayed on reconnection, no duplicates, no loss.
"""

from __future__ import annotations

import threading
import time
import unittest

from platform_runtime.protocols import RunEvent

from gateway.event_buffer import RunEventBuffer


def _make_event(
    run_id: str = "run-1",
    seq: int = 1,
    event_type: str = "message.delta",
    payload: dict | None = None,
    event_id: str | None = None,
) -> RunEvent:
    """Construct a RunEvent for testing."""
    return RunEvent(
        event_id=event_id or f"evt-{run_id}-{seq}",
        run_id=run_id,
        event_type=event_type,
        occurred_at=f"2026-01-01T00:00:{seq:02d}Z",
        seq=seq,
        payload=payload or {"message_delta": f"content-{seq}"},
        metadata={},
    )


class TestRunEventBuffer(unittest.TestCase):
    """Unit tests for RunEventBuffer."""

    def test_append_and_replay(self) -> None:
        """Append 1 event with seq=1. replay(run_id, 0) returns 1 event. replay(run_id, 1) returns 0."""
        buf = RunEventBuffer()
        buf.append("run-1", _make_event(seq=1))
        self.assertEqual(len(buf.replay("run-1", 0)), 1)
        self.assertEqual(len(buf.replay("run-1", 1)), 0)

    def test_replay_orders_by_seq(self) -> None:
        """Append events with seq 3, 1, 2 (out of order). replay returns seq order 1, 2, 3."""
        buf = RunEventBuffer()
        for seq in (3, 1, 2):
            buf.append("run-1", _make_event(seq=seq))
        events = buf.replay("run-1", 0)
        self.assertEqual([e.seq for e in events], [1, 2, 3])

    def test_replay_filters_by_last_seq(self) -> None:
        """Append events with seq 1-5. replay(run_id, 2) returns events with seq 3, 4, 5."""
        buf = RunEventBuffer()
        for seq in range(1, 6):
            buf.append("run-1", _make_event(seq=seq))
        events = buf.replay("run-1", 2)
        self.assertEqual([e.seq for e in events], [3, 4, 5])

    def test_replay_empty_buffer(self) -> None:
        """replay('nonexistent', 0) returns empty list."""
        buf = RunEventBuffer()
        self.assertEqual(buf.replay("nonexistent", 0), [])

    def test_max_events_per_run_eviction(self) -> None:
        """Buffer with max_events_per_run=3. Append 5 events. get_buffered_events returns last 3 (FIFO)."""
        buf = RunEventBuffer(max_events_per_run=3)
        for seq in range(1, 6):
            buf.append("run-1", _make_event(seq=seq))
        events = buf.get_buffered_events("run-1")
        self.assertEqual(len(events), 3)
        self.assertEqual([e.seq for e in events], [3, 4, 5])

    def test_terminal_event_detection(self) -> None:
        """Append a run.state_changed event with status succeeded. is_terminal returns True."""
        buf = RunEventBuffer()
        buf.append("run-1", _make_event(
            seq=1,
            event_type="run.state_changed",
            payload={"status": "succeeded"},
        ))
        self.assertTrue(buf.is_terminal("run-1"))

    def test_non_terminal_event(self) -> None:
        """Append a message.delta event. is_terminal returns False."""
        buf = RunEventBuffer()
        buf.append("run-1", _make_event(seq=1, event_type="message.delta"))
        self.assertFalse(buf.is_terminal("run-1"))

    def test_cleanup_expired(self) -> None:
        """Append a terminal event, set terminal time to 10 min ago, cleanup_expired removes it."""
        buf = RunEventBuffer(terminal_retention_seconds=300.0)
        buf.append("run-1", _make_event(
            seq=1,
            event_type="run.state_changed",
            payload={"status": "succeeded"},
        ))
        # Manually set terminal timestamp to 10 minutes ago
        with buf._lock:
            buf._terminal_at["run-1"] = time.time() - 600
        removed = buf.cleanup_expired()
        self.assertEqual(removed, 1)
        self.assertEqual(buf.replay("run-1", 0), [])

    def test_cleanup_not_yet_expired(self) -> None:
        """Append a terminal event, cleanup_expired immediately. Buffer NOT removed."""
        buf = RunEventBuffer(terminal_retention_seconds=300.0)
        buf.append("run-1", _make_event(
            seq=1,
            event_type="run.state_changed",
            payload={"status": "succeeded"},
        ))
        removed = buf.cleanup_expired()
        self.assertEqual(removed, 0)
        self.assertEqual(len(buf.replay("run-1", 0)), 1)

    def test_clear_run(self) -> None:
        """Append events, clear_run(run_id). replay(run_id, 0) returns empty."""
        buf = RunEventBuffer()
        buf.append("run-1", _make_event(seq=1))
        buf.append("run-1", _make_event(seq=2))
        buf.clear_run("run-1")
        self.assertEqual(buf.replay("run-1", 0), [])

    def test_multiple_runs_isolated(self) -> None:
        """Append events to run-1 and run-2. replay returns only the respective run's events."""
        buf = RunEventBuffer()
        buf.append("run-1", _make_event(run_id="run-1", seq=1))
        buf.append("run-1", _make_event(run_id="run-1", seq=2))
        buf.append("run-2", _make_event(run_id="run-2", seq=1))
        buf.append("run-2", _make_event(run_id="run-2", seq=2))
        buf.append("run-2", _make_event(run_id="run-2", seq=3))

        r1 = buf.replay("run-1", 0)
        r2 = buf.replay("run-2", 0)
        self.assertEqual(len(r1), 2)
        self.assertEqual(len(r2), 3)
        for e in r1:
            self.assertEqual(e.run_id, "run-1")
        for e in r2:
            self.assertEqual(e.run_id, "run-2")

    def test_thread_safety(self) -> None:
        """Append 100 events from multiple threads. All stored, replay returns 100 in seq order."""
        buf = RunEventBuffer()

        def append_batch(start: int, count: int) -> None:
            for i in range(start, start + count):
                buf.append("run-1", _make_event(seq=i + 1))

        threads = []
        batch_size = 20
        num_batches = 5
        for batch_idx in range(num_batches):
            t = threading.Thread(
                target=append_batch,
                args=(batch_idx * batch_size, batch_size),
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        events = buf.replay("run-1", 0)
        self.assertEqual(len(events), 100)
        # Verify seq order
        seqs = [e.seq for e in events]
        self.assertEqual(seqs, sorted(seqs))

    def test_replay_no_duplicates(self) -> None:
        """Append events with seq 1, 2, 3. replay(run_id, 0) returns exactly 3. replay(run_id, 1) returns exactly 2."""
        buf = RunEventBuffer()
        for seq in (1, 2, 3):
            buf.append("run-1", _make_event(seq=seq))

        events_all = buf.replay("run-1", 0)
        self.assertEqual(len(events_all), 3)
        event_ids_all = [e.event_id for e in events_all]
        self.assertEqual(len(set(event_ids_all)), 3, "No duplicate event_ids in replay")

        events_partial = buf.replay("run-1", 1)
        self.assertEqual(len(events_partial), 2)
        event_ids_partial = [e.event_id for e in events_partial]
        self.assertEqual(len(set(event_ids_partial)), 2, "No duplicate event_ids in partial replay")

    def test_get_buffered_events(self) -> None:
        """Append 3 events. get_buffered_events(run_id) returns 3 events."""
        buf = RunEventBuffer()
        for seq in (1, 2, 3):
            buf.append("run-1", _make_event(seq=seq))
        events = buf.get_buffered_events("run-1")
        self.assertEqual(len(events), 3)


if __name__ == "__main__":
    unittest.main()
