"""Unit tests for the Gateway SSE encoding with output boundary.

Tests GatewaySseStream using encode_sse_event (inlined from the retired
web_sse channel package), output boundary enforcement per event, forbidden
payload key rejection, and Last-Event-ID parsing.

The output boundary is the second enforcement point (AGENTS.md: "Output
boundary is enforced twice: at the ACP event bridge and at the Gateway").
"""

from __future__ import annotations

import unittest

from platform_runtime.protocols import RunEvent

from gateway.sse import GatewaySseStream, encode_sse_event, parse_last_event_id


def _make_event(
    event_id: str = "evt-1",
    event_type: str = "message.delta",
    run_id: str = "run-1",
    seq: int = 1,
    payload: dict | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "run_id": run_id,
        "seq": seq,
        "occurred_at": "2026-01-01T00:00:00Z",
        "payload": payload or {"message_delta": "hello"},
    }


class TestGatewaySse(unittest.TestCase):

    def test_encode_event_basic(self) -> None:
        stream = GatewaySseStream()
        result = stream.encode_event(_make_event())
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("id: evt-1"))
        self.assertIn("event: message.delta", result)
        self.assertIn("data: ", result)

    def test_encode_event_runevent_dataclass(self) -> None:
        stream = GatewaySseStream()
        event = RunEvent(
            event_id="evt-dc",
            run_id="run-1",
            event_type="message.delta",
            occurred_at="2026-01-01T00:00:00Z",
            seq=1,
            payload={"message_delta": "hello"},
        )
        result = stream.encode_event(event)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("id: evt-dc"))
        self.assertIn("event: message.delta", result)

    def test_encode_event_forbidden_keys(self) -> None:
        stream = GatewaySseStream()
        event = _make_event(payload={"rawpayload": "secret"})
        with self.assertRaises(ValueError):
            stream.encode_event(event)

    def test_encode_event_blocked_by_boundary(self) -> None:
        stream = GatewaySseStream()
        event = _make_event(
            event_id="blk-1",
            payload={"message_delta": "stack trace occurred in the backend"},
        )
        result = stream.encode_event(event)
        self.assertIsNone(result)

    def test_encode_event_rewritten_by_boundary(self) -> None:
        stream = GatewaySseStream()
        event = _make_event(
            event_id="rw-1",
            payload={"message_delta": "debug information here"},
        )
        result = stream.encode_event(event)
        self.assertIsNotNone(result)
        self.assertNotIn("debug", result)

    def test_encode_events_skips_blocked(self) -> None:
        stream = GatewaySseStream()
        events = [
            _make_event(event_id="e1", payload={"message_delta": "hello"}),
            _make_event(event_id="e2", payload={"message_delta": "stack trace in backend"}),
            _make_event(event_id="e3", payload={"message_delta": "world"}),
        ]
        frames = list(stream.encode_events(events))
        self.assertEqual(len(frames), 2)

    def test_encode_stream_response(self) -> None:
        stream = GatewaySseStream()
        events = [
            _make_event(event_id="e1", payload={"message_delta": "hello"}),
            _make_event(event_id="e2", payload={"message_delta": "world"}),
        ]
        response = stream.encode_stream_response(events)
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
        self.assertIn("id: e1", response)
        self.assertIn("id: e2", response)

    def test_parse_last_event_id_valid(self) -> None:
        self.assertEqual(parse_last_event_id({"Last-Event-ID": "42"}), 42)

    def test_parse_last_event_id_missing(self) -> None:
        self.assertIsNone(parse_last_event_id({}))

    def test_parse_last_event_id_invalid(self) -> None:
        self.assertIsNone(parse_last_event_id({"Last-Event-ID": "abc"}))

    def test_sse_format_matches_encode_sse_event(self) -> None:
        """Gateway SSE format matches web_sse's encode_sse_event exactly."""
        stream = GatewaySseStream()
        event = _make_event(event_id="evt-x", payload={"message_delta": "hello"})
        expected = encode_sse_event(event)
        actual = stream.encode_event(event)
        self.assertEqual(actual, expected)

    def test_output_boundary_enforced_per_event(self) -> None:
        """No blocked content reaches the SSE stream (second enforcement point)."""
        stream = GatewaySseStream()
        events = [
            _make_event(event_id="clean-1", payload={"message_delta": "Legal advice: ..."}),
            _make_event(event_id="noise-1", payload={"message_delta": "function call result here"}),
            _make_event(event_id="clean-2", payload={"message_delta": "More legal text"}),
            _make_event(event_id="noise-2", payload={"message_delta": "stack trace debug info"}),
        ]
        frames = list(stream.encode_events(events))
        for frame in frames:
            self.assertNotIn("function call", frame)
            self.assertNotIn("stack trace", frame)
            self.assertNotIn("debug", frame)
        # Only the 2 clean events should pass
        self.assertEqual(len(frames), 2)


if __name__ == "__main__":
    unittest.main()
