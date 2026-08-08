"""Unit tests for Arena Service SSE reconnection (SVC-07).

Tests ``ArenaEventBuffer`` for seq-based replay by ``arena_id``.
Reconnection with ``Last-Event-ID`` must return exactly events with
``seq > last_seq`` — no duplication, no loss. FIFO eviction caps memory
at ``max_events_per_arena``. Terminal arenas are retained for
``terminal_retention_seconds`` then cleaned up.
"""

from __future__ import annotations

import threading
import time
import unittest

from arena_service.event_buffer import ArenaEventBuffer, BufferedArenaEvent


def _make_event(
    event_id: str = "evt-1",
    event_type: str = "message.delta",
    seq: int = 1,
    payload: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "seq": seq,
        "payload": payload or {"text": "hello"},
        "metadata": metadata or {"agent_slot": "slot-0"},
    }


class SSEReconnectionTests(unittest.TestCase):
    """SVC-07: seq-based replay by arena_id — no dup, no loss."""

    # -- Test 1: default construction --
    def test_default_construction(self) -> None:
        buffer = ArenaEventBuffer()
        self.assertEqual(buffer._max_events_per_arena, 1000)
        self.assertEqual(buffer._terminal_retention_seconds, 300.0)

    # -- Test 2: append and get_buffered_events in seq order --
    def test_append_and_get_buffered_events(self) -> None:
        buffer = ArenaEventBuffer()
        buffer.append("arena-1", _make_event(event_id="e1", seq=1))
        buffer.append("arena-1", _make_event(event_id="e2", seq=2))
        buffer.append("arena-1", _make_event(event_id="e3", seq=3))
        events = buffer.get_buffered_events("arena-1")
        self.assertEqual(len(events), 3)
        # Events are in insertion order
        self.assertEqual(events[0]["seq"], 1)
        self.assertEqual(events[1]["seq"], 2)
        self.assertEqual(events[2]["seq"], 3)

    # -- Test 3: replay from last_seq=1 returns events with seq > 1 --
    def test_replay_from_last_seq_1(self) -> None:
        buffer = ArenaEventBuffer()
        for seq in range(1, 4):
            buffer.append("arena-1", _make_event(event_id=f"e{seq}", seq=seq))
        events = buffer.replay("arena-1", last_seq=1)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["seq"], 2)
        self.assertEqual(events[1]["seq"], 3)

    # -- Test 4: replay from last_seq=0 returns all --
    def test_replay_from_last_seq_0(self) -> None:
        buffer = ArenaEventBuffer()
        for seq in range(1, 4):
            buffer.append("arena-1", _make_event(event_id=f"e{seq}", seq=seq))
        events = buffer.replay("arena-1", last_seq=0)
        self.assertEqual(len(events), 3)

    # -- Test 5: replay from last_seq=3 returns empty --
    def test_replay_from_last_seq_3(self) -> None:
        buffer = ArenaEventBuffer()
        for seq in range(1, 4):
            buffer.append("arena-1", _make_event(event_id=f"e{seq}", seq=seq))
        events = buffer.replay("arena-1", last_seq=3)
        self.assertEqual(len(events), 0)

    # -- Test 6: replay unknown arena returns empty --
    def test_replay_unknown_arena(self) -> None:
        buffer = ArenaEventBuffer()
        events = buffer.replay("unknown-arena", 0)
        self.assertEqual(len(events), 0)

    # -- Test 7: two arenas buffered independently --
    def test_two_arenas_independent(self) -> None:
        buffer = ArenaEventBuffer()
        buffer.append("arena-A", _make_event(event_id="a1", seq=1))
        buffer.append("arena-B", _make_event(event_id="b1", seq=1))
        events_a = buffer.get_buffered_events("arena-A")
        events_b = buffer.get_buffered_events("arena-B")
        self.assertEqual(len(events_a), 1)
        self.assertEqual(len(events_b), 1)
        self.assertEqual(events_a[0]["event_id"], "a1")
        self.assertEqual(events_b[0]["event_id"], "b1")

    # -- Test 8: FIFO eviction at max_events_per_arena --
    def test_fifo_eviction(self) -> None:
        max_events = 5
        buffer = ArenaEventBuffer(max_events_per_arena=max_events)
        # Append max_events + 5 events
        for seq in range(1, max_events + 6):
            buffer.append("arena-1", _make_event(event_id=f"e{seq}", seq=seq))
        events = buffer.get_buffered_events("arena-1")
        self.assertEqual(len(events), max_events)
        # Oldest 5 should be evicted; remaining are the last max_events
        self.assertEqual(events[0]["seq"], 6)
        self.assertEqual(events[-1]["seq"], max_events + 5)

    # -- Test 9: terminal state detection --
    def test_terminal_state_detection(self) -> None:
        buffer = ArenaEventBuffer()
        buffer.append("arena-1", _make_event(event_id="e1", seq=1))
        self.assertFalse(buffer.is_terminal("arena-1"))
        buffer.append(
            "arena-1",
            _make_event(
                event_id="e2",
                seq=2,
                event_type="arena.workflow_completed",
            ),
        )
        self.assertTrue(buffer.is_terminal("arena-1"))

    # -- Test 9b: terminal state for cancelled and failed --
    def test_terminal_state_cancelled_and_failed(self) -> None:
        buffer = ArenaEventBuffer()
        buffer.append(
            "arena-c",
            _make_event(
                event_id="e1",
                seq=1,
                event_type="arena.workflow_cancelled",
            ),
        )
        self.assertTrue(buffer.is_terminal("arena-c"))

        buffer.append(
            "arena-f",
            _make_event(
                event_id="e2",
                seq=2,
                event_type="arena.workflow_failed",
            ),
        )
        self.assertTrue(buffer.is_terminal("arena-f"))

    # -- Test 10: cleanup_expired after retention period --
    def test_cleanup_expired(self) -> None:
        retention = 300.0
        buffer = ArenaEventBuffer(terminal_retention_seconds=retention)
        buffer.append("arena-1", _make_event(event_id="e1", seq=1))
        buffer.append(
            "arena-1",
            _make_event(
                event_id="e2",
                seq=2,
                event_type="arena.workflow_completed",
            ),
        )
        # Before retention period — buffer retained
        removed = buffer.cleanup_expired(now=time.time())
        self.assertEqual(removed, 0)
        self.assertEqual(len(buffer.get_buffered_events("arena-1")), 2)

        # After retention period — buffer removed
        future_time = time.time() + retention + 1
        removed = buffer.cleanup_expired(now=future_time)
        self.assertEqual(removed, 1)
        self.assertEqual(len(buffer.get_buffered_events("arena-1")), 0)

    # -- Test 10b: cleanup_expired only removes terminal arenas --
    def test_cleanup_expired_non_terminal_retained(self) -> None:
        retention = 1.0
        buffer = ArenaEventBuffer(terminal_retention_seconds=retention)
        buffer.append("arena-1", _make_event(event_id="e1", seq=1))
        # Not terminal — should not be removed even after retention
        future_time = time.time() + retention + 10
        removed = buffer.cleanup_expired(now=future_time)
        self.assertEqual(removed, 0)
        self.assertEqual(len(buffer.get_buffered_events("arena-1")), 1)

    # -- Test 11: clear_arena removes buffer --
    def test_clear_arena(self) -> None:
        buffer = ArenaEventBuffer()
        buffer.append("arena-1", _make_event(event_id="e1", seq=1))
        buffer.append("arena-1", _make_event(event_id="e2", seq=2))
        self.assertEqual(len(buffer.get_buffered_events("arena-1")), 2)
        buffer.clear_arena("arena-1")
        self.assertEqual(len(buffer.get_buffered_events("arena-1")), 0)
        self.assertFalse(buffer.is_terminal("arena-1"))

    # -- Test 12: thread-safe via threading.Lock --
    def test_thread_safe_lock_exists(self) -> None:
        buffer = ArenaEventBuffer()
        self.assertIsInstance(buffer._lock, type(threading.Lock()))

    # -- Test 12b: concurrent access does not corrupt --
    def test_concurrent_access(self) -> None:
        buffer = ArenaEventBuffer(max_events_per_arena=10000)
        errors: list[Exception] = []

        def writer(start: int) -> None:
            try:
                for seq in range(start, start + 100):
                    buffer.append("arena-concurrent", _make_event(event_id=f"e{seq}", seq=seq))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i * 100,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)
        events = buffer.get_buffered_events("arena-concurrent")
        self.assertEqual(len(events), 500)

    # -- Test 13: reconnection simulation — multiple reconnects --
    def test_reconnection_simulation(self) -> None:
        buffer = ArenaEventBuffer()
        # Append 5 events (seq 1-5)
        for seq in range(1, 6):
            buffer.append("arena-1", _make_event(event_id=f"e{seq}", seq=seq))
        # Reconnect from seq=2 → get events 3,4,5
        events = buffer.replay("arena-1", last_seq=2)
        self.assertEqual(len(events), 3)
        self.assertEqual([e["seq"] for e in events], [3, 4, 5])

        # Append 2 more events (seq 6,7)
        buffer.append("arena-1", _make_event(event_id="e6", seq=6))
        buffer.append("arena-1", _make_event(event_id="e7", seq=7))
        # Reconnect from seq=5 → get events 6,7
        events = buffer.replay("arena-1", last_seq=5)
        self.assertEqual(len(events), 2)
        self.assertEqual([e["seq"] for e in events], [6, 7])

        # Reconnect from seq=0 → get all 7
        events = buffer.replay("arena-1", last_seq=0)
        self.assertEqual(len(events), 7)
        self.assertEqual([e["seq"] for e in events], [1, 2, 3, 4, 5, 6, 7])

    # -- Test 14: BufferedArenaEvent dataclass --
    def test_buffered_arena_event_dataclass(self) -> None:
        event = _make_event(event_id="e1", seq=1)
        be = BufferedArenaEvent(event=event, buffered_at=12345.6)
        self.assertEqual(be.event, event)
        self.assertEqual(be.buffered_at, 12345.6)

    # -- Test 15: replay returns copies, not references --
    def test_replay_returns_independent_copies(self) -> None:
        buffer = ArenaEventBuffer()
        buffer.append("arena-1", _make_event(event_id="e1", seq=1))
        events1 = buffer.replay("arena-1", last_seq=0)
        events2 = buffer.replay("arena-1", last_seq=0)
        self.assertEqual(events1, events2)
        # Mutating one should not affect the other
        events1[0]["event_id"] = "mutated"
        self.assertNotEqual(events1[0]["event_id"], events2[0]["event_id"])


if __name__ == "__main__":
    unittest.main()
