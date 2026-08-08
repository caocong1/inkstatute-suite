"""Unit tests for Arena Service SSE multiplexing (SVC-03).

Tests ``ArenaSseStream`` and ``encode_arena_sse_event`` for N-agent
multiplexing on a single SSE connection. Each event is tagged with
``metadata.agent_slot`` and the tag must be preserved through encoding
so the client can demultiplex by slot.
"""

from __future__ import annotations

import json
import unittest

from arena_service.sse import (
    ArenaSseStream,
    encode_arena_sse_event,
    parse_last_event_id,
)


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


class SSEMultiplexingTests(unittest.TestCase):
    """SVC-03: N agents' events multiplexed on a single SSE connection."""

    # -- Test 1: encode_arena_sse_event basic frame + agent_slot in JSON --
    def test_encode_arena_sse_event_frame_and_agent_slot(self) -> None:
        event = _make_event(
            event_id="evt-1",
            event_type="message.delta",
            seq=1,
            payload={"text": "hello"},
            metadata={"agent_slot": "slot-0"},
        )
        result = encode_arena_sse_event(event)
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("id: evt-1\nevent: message.delta\n"))
        self.assertIn('"agent_slot":"slot-0"', result)

    # -- Test 2: SSE frame ends with double newline --
    def test_sse_frame_ends_with_double_newline(self) -> None:
        result = encode_arena_sse_event(_make_event())
        self.assertTrue(result.endswith("\n\n"))

    # -- Test 3: ArenaSseStream.encode_event preserves agent_slot --
    def test_encode_event_preserves_agent_slot(self) -> None:
        stream = ArenaSseStream()
        event = _make_event(metadata={"agent_slot": "slot-1"})
        result = stream.encode_event(event)
        self.assertIsNotNone(result)
        self.assertIn('"agent_slot":"slot-1"', result)

    # -- Test 4: event with no agent_slot still encodes --
    def test_encode_event_no_agent_slot(self) -> None:
        stream = ArenaSseStream()
        event = _make_event(metadata={})
        result = stream.encode_event(event)
        self.assertIsNotNone(result)
        # Should not crash; agent_slot simply absent from JSON
        self.assertIn("id: evt-1", result)

    # -- Test 5: multiple slots encoded in sequence keep correct slot --
    def test_multiple_slots_preserve_identity(self) -> None:
        stream = ArenaSseStream()
        event_slot0 = _make_event(event_id="e0", metadata={"agent_slot": "slot-0"})
        event_slot1 = _make_event(event_id="e1", metadata={"agent_slot": "slot-1"})
        event_slot2 = _make_event(event_id="e2", metadata={"agent_slot": "slot-2"})

        frame0 = stream.encode_event(event_slot0)
        frame1 = stream.encode_event(event_slot1)
        frame2 = stream.encode_event(event_slot2)

        self.assertIn('"agent_slot":"slot-0"', frame0)
        self.assertIn('"agent_slot":"slot-1"', frame1)
        self.assertIn('"agent_slot":"slot-2"', frame2)
        # Ensure slots are not mixed up
        self.assertNotIn('"agent_slot":"slot-1"', frame0)
        self.assertNotIn('"agent_slot":"slot-0"', frame1)

    # -- Test 6: encode_events yields ordered frames with correct slots --
    def test_encode_events_multiplexing_order(self) -> None:
        stream = ArenaSseStream()
        events = [
            _make_event(event_id="e0", seq=1, metadata={"agent_slot": "slot-0"}),
            _make_event(event_id="e1", seq=2, metadata={"agent_slot": "slot-1"}),
            _make_event(event_id="e2", seq=3, metadata={"agent_slot": "slot-0"}),
        ]
        frames = list(stream.encode_events(events))
        self.assertEqual(len(frames), 3)
        # Verify each frame has the correct agent_slot in order
        self.assertIn('"agent_slot":"slot-0"', frames[0])
        self.assertIn('"agent_slot":"slot-1"', frames[1])
        self.assertIn('"agent_slot":"slot-0"', frames[2])
        # Verify event IDs are in order
        self.assertIn("id: e0", frames[0])
        self.assertIn("id: e1", frames[1])
        self.assertIn("id: e2", frames[2])

    # -- Test 7: arena lifecycle events with orchestrator slot --
    def test_arena_lifecycle_event_orchestrator_slot(self) -> None:
        stream = ArenaSseStream()
        event = _make_event(
            event_id="life-1",
            event_type="arena.workflow_started",
            seq=0,
            payload={"arena_id": "arena-1", "mode": "mode1_parallel"},
            metadata={"agent_slot": "orchestrator", "arena_id": "arena-1"},
        )
        result = stream.encode_event(event)
        self.assertIsNotNone(result)
        self.assertIn("event: arena.workflow_started", result)
        self.assertIn('"agent_slot":"orchestrator"', result)

    # -- Test 8: parse_last_event_id --
    def test_parse_last_event_id(self) -> None:
        self.assertEqual(parse_last_event_id({"Last-Event-ID": "42"}), 42)
        self.assertIsNone(parse_last_event_id({}))
        self.assertIsNone(parse_last_event_id({"Last-Event-ID": "abc"}))

    # -- Test 8b: parse_last_event_id case-insensitive --
    def test_parse_last_event_id_case_insensitive(self) -> None:
        self.assertEqual(parse_last_event_id({"last-event-id": "7"}), 7)
        self.assertEqual(parse_last_event_id({"LAST-EVENT-ID": "99"}), 99)

    # -- Test 9: output filter blocks events returning None --
    def test_output_filter_blocks_event(self) -> None:
        class BlockFilter:
            def filter_event(self, event_type, content, metadata):
                class D:
                    action = "BLOCK"
                return D()

        stream = ArenaSseStream(output_filter=BlockFilter())
        result = stream.encode_event(_make_event())
        self.assertIsNone(result)

    # -- Test 9b: output filter rewrites content --
    def test_output_filter_rewrites_content(self) -> None:
        class RewriteFilter:
            def filter_event(self, event_type, content, metadata):
                class D:
                    action = "REWRITE"
                    visible_text = "REDACTED"
                return D()

        stream = ArenaSseStream(output_filter=RewriteFilter())
        event = _make_event(payload={"text": "secret"})
        result = stream.encode_event(event)
        self.assertIsNotNone(result)
        self.assertIn("REDACTED", result)
        self.assertNotIn("secret", result)

    # -- Test 9c: encode_events skips blocked events --
    def test_encode_events_skips_blocked(self) -> None:
        class BlockAllFilter:
            def filter_event(self, event_type, content, metadata):
                class D:
                    action = "BLOCK"
                return D()

        stream = ArenaSseStream(output_filter=BlockAllFilter())
        events = [_make_event(event_id="e0"), _make_event(event_id="e1")]
        frames = list(stream.encode_events(events))
        self.assertEqual(len(frames), 0)

    # -- Test 10: encode_stream_response joins all frames --
    def test_encode_stream_response(self) -> None:
        stream = ArenaSseStream()
        events = [
            _make_event(event_id="e0", seq=1, metadata={"agent_slot": "slot-0"}),
            _make_event(event_id="e1", seq=2, metadata={"agent_slot": "slot-1"}),
        ]
        result = stream.encode_stream_response(events)
        self.assertIn("id: e0", result)
        self.assertIn("id: e1", result)
        # Two frames, each ending with \n\n
        self.assertEqual(result.count("\n\n"), 2)

    # -- Test 11: JSON data is valid and parseable --
    def test_json_data_is_valid(self) -> None:
        event = _make_event(
            event_id="evt-x",
            event_type="message.delta",
            seq=5,
            payload={"text": "world"},
            metadata={"agent_slot": "slot-3", "arena_id": "arena-9"},
        )
        frame = encode_arena_sse_event(event)
        # Extract the data line
        data_line = None
        for line in frame.strip().split("\n"):
            if line.startswith("data: "):
                data_line = line[len("data: "):]
                break
        self.assertIsNotNone(data_line)
        parsed = json.loads(data_line)
        self.assertEqual(parsed["event_id"], "evt-x")
        self.assertEqual(parsed["event_type"], "message.delta")
        self.assertEqual(parsed["seq"], 5)
        self.assertEqual(parsed["metadata"]["agent_slot"], "slot-3")
        self.assertEqual(parsed["metadata"]["arena_id"], "arena-9")


if __name__ == "__main__":
    unittest.main()
