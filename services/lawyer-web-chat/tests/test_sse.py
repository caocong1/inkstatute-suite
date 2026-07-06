"""Tests for SseStream — SSE encoding with output boundary."""

from __future__ import annotations

import unittest

from lawyer_web_chat.boundary import ChatBoundary
from lawyer_web_chat.sse import SseStream


class SseStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = SseStream()

    def test_encode_event_with_business_text(self) -> None:
        event = {
            "event_id": "e1",
            "run_id": "run-1",
            "event_type": "message_delta",
            "occurred_at": "2026-07-06T12:00:00Z",
            "seq": 1,
            "payload": {"message_delta": "Your case analysis is ready."},
        }
        frame = self.stream.encode_event(event)
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertIn("id: e1", frame)
        self.assertIn("event: message_delta", frame)
        self.assertIn("Your case analysis is ready.", frame)

    def test_encode_event_blocks_model_name(self) -> None:
        event = {
            "event_id": "e2",
            "run_id": "run-1",
            "event_type": "message_delta",
            "occurred_at": "2026-07-06T12:00:00Z",
            "seq": 2,
            "payload": {"message_delta": "model: gpt-4 processing"},
        }
        frame = self.stream.encode_event(event)
        self.assertIsNone(frame)

    def test_encode_event_blocks_api_error(self) -> None:
        event = {
            "event_id": "e3",
            "run_id": "run-1",
            "event_type": "message_delta",
            "occurred_at": "2026-07-06T12:00:00Z",
            "seq": 3,
            "payload": {"message_delta": "api key invalid: quota exceeded"},
        }
        frame = self.stream.encode_event(event)
        self.assertIsNone(frame)

    def test_encode_event_rewrites_backend_lifecycle(self) -> None:
        event = {
            "event_id": "e4",
            "run_id": "run-1",
            "event_type": "message_delta",
            "occurred_at": "2026-07-06T12:00:00Z",
            "seq": 4,
            "payload": {"message_delta": "self-update in progress, restarting"},
        }
        frame = self.stream.encode_event(event)
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertIn("InkStatute", frame)
        self.assertNotIn("restarting", frame)

    def test_encode_events_skips_blocked(self) -> None:
        events = [
            {
                "event_id": "e1",
                "run_id": "run-1",
                "event_type": "message_delta",
                "occurred_at": "2026-07-06T12:00:00Z",
                "seq": 1,
                "payload": {"message_delta": "Hello"},
            },
            {
                "event_id": "e2",
                "run_id": "run-1",
                "event_type": "message_delta",
                "occurred_at": "2026-07-06T12:00:00Z",
                "seq": 2,
                "payload": {"message_delta": "model: gpt-4 leak"},
            },
            {
                "event_id": "e3",
                "run_id": "run-1",
                "event_type": "message_delta",
                "occurred_at": "2026-07-06T12:00:00Z",
                "seq": 3,
                "payload": {"message_delta": "World"},
            },
        ]
        frames = list(self.stream.encode_events(events))
        self.assertEqual(len(frames), 2)  # blocked event skipped
        self.assertIn("Hello", frames[0])
        self.assertIn("World", frames[1])

    def test_encode_stream_response_concatenates_frames(self) -> None:
        events = [
            {
                "event_id": "e1",
                "run_id": "run-1",
                "event_type": "message_delta",
                "occurred_at": "2026-07-06T12:00:00Z",
                "seq": 1,
                "payload": {"message_delta": "Hello"},
            },
            {
                "event_id": "e2",
                "run_id": "run-1",
                "event_type": "message_delta",
                "occurred_at": "2026-07-06T12:00:00Z",
                "seq": 2,
                "payload": {"message_delta": "World"},
            },
        ]
        response = self.stream.encode_stream_response(events)
        self.assertIn("id: e1", response)
        self.assertIn("id: e2", response)
        self.assertIn("Hello", response)
        self.assertIn("World", response)

    def test_html_escape_in_sse_content(self) -> None:
        event = {
            "event_id": "e1",
            "run_id": "run-1",
            "event_type": "message_delta",
            "occurred_at": "2026-07-06T12:00:00Z",
            "seq": 1,
            "payload": {"message_delta": "Result: <script>alert(1)</script>"},
        }
        frame = self.stream.encode_event(event)
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertIn("&lt;script&gt;", frame)
        self.assertNotIn("<script>alert(1)</script>", frame)


if __name__ == "__main__":
    unittest.main()
