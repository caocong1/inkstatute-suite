"""Integration tests for SSE Last-Event-ID reconnection.

Tests the full reconnection flow: stream a run to completion (populating the
event buffer), then reconnect with a ``Last-Event-ID`` header and verify that
buffered events with ``seq > last_event_id`` are replayed correctly — no
duplicates, no loss, in seq order, with output boundary applied.

Covers GW-02: "SSE 流式传输统一事件，支持 Last-Event-ID 按 seq 断线续传，
不重复不丢失".
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import unittest
from typing import AsyncIterator

from inkstatute_channels_web_sse import encode_sse_event
from platform_contract.enums import AsyncTaskState
from platform_runtime.protocols import Run, RunEvent, RunRequest

from gateway.app import GatewayApp
from gateway.auth import GatewayAuth
from gateway.config import GatewayConfig
from gateway.event_buffer import RunEventBuffer
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from rbac.session import InMemorySessionStore

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
AUTH_HEADERS = {"Authorization": "Bearer test-token"}

CREATE_RUN_BODY = {
    "turn": {
        "turn_id": "turn-replay-001",
        "conversation_id": "conv-replay-001",
        "channel": "web",
        "user_id": "lawyer-replay",
        "message_type": "text",
        "received_at": "2026-08-07T00:00:00Z",
        "content": "fixture://turns/turn-replay-001/content_ref",
    },
    "solution": {
        "solution_id": "lawyer-v1",
        "backend_id": "hermes",
    },
}


def _load_replay_events() -> list[dict]:
    with open(os.path.join(FIXTURES_DIR, "replay_events.json"), encoding="utf-8") as f:
        return json.load(f)


def _events_from_fixture(run_id: str) -> list[RunEvent]:
    return [
        RunEvent(
            event_id=e["event_id"],
            run_id=run_id,
            event_type=e["event_type"],
            occurred_at=e["occurred_at"],
            seq=e["seq"],
            payload=e["payload"],
            metadata=e.get("metadata", {}),
        )
        for e in _load_replay_events()
    ]


class OnceRuntime:
    """Runtime that yields events only on the first stream() call.

    Subsequent stream() calls yield nothing — simulating real behavior where
    a runtime only produces new events after the initial stream is consumed.
    This lets us test reconnection: the first stream populates the buffer,
    and the reconnect only gets replayed events from the buffer (no live
    duplicates).
    """

    def __init__(self, events: list[RunEvent] | None = None) -> None:
        self._events = events or []
        self._streamed = False
        self.runs: dict[str, Run] = {}
        self._next_id = 1

    async def create_run(self, req: RunRequest) -> Run:
        run_id = f"run-replay-{self._next_id:03d}"
        self._next_id += 1
        run = Run(
            run_id=run_id,
            status=AsyncTaskState.QUEUED,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata=dict(req.metadata),
        )
        self.runs[run_id] = run
        # Reassign run_id to events
        self._events = [
            RunEvent(
                event_id=e.event_id,
                run_id=run_id,
                event_type=e.event_type,
                occurred_at=e.occurred_at,
                seq=e.seq,
                payload=dict(e.payload),
                metadata=dict(e.metadata),
            )
            for e in self._events
        ]
        return run

    async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
        if not self._streamed:
            self._streamed = True
            for event in self._events:
                yield event

    async def cancel(self, run_id: str) -> Run:
        run = self.runs.get(run_id)
        if run is not None:
            run = Run(
                run_id=run.run_id,
                status=AsyncTaskState.CANCELLED,
                turn_id=run.turn_id,
                solution_id=run.solution_id,
                metadata=run.metadata,
            )
            self.runs[run_id] = run
        return run  # type: ignore[return-value]


class ContinuationRuntime:
    """Runtime that yields events in two batches for replay-then-continue tests.

    First stream() call yields the first batch (events 1-5).
    Second stream() call yields the second batch (events 6-10).
    """

    def __init__(self) -> None:
        self._batch1: list[RunEvent] = []
        self._batch2: list[RunEvent] = []
        self._call_count = 0
        self.runs: dict[str, Run] = {}
        self._next_id = 1

    async def create_run(self, req: RunRequest) -> Run:
        run_id = f"run-cont-{self._next_id:03d}"
        self._next_id += 1
        run = Run(
            run_id=run_id,
            status=AsyncTaskState.QUEUED,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata=dict(req.metadata),
        )
        self.runs[run_id] = run
        self._batch1 = [
            RunEvent(
                event_id=f"cont-evt-{i}",
                run_id=run_id,
                event_type="message.delta",
                occurred_at=f"2026-01-01T00:00:0{i}Z",
                seq=i,
                payload={"message_delta": f"batch1-msg-{i}"},
            )
            for i in range(1, 6)
        ]
        self._batch2 = [
            RunEvent(
                event_id=f"cont-evt-{i}",
                run_id=run_id,
                event_type="message.delta",
                occurred_at=f"2026-01-01T00:00:{i:02d}Z",
                seq=i,
                payload={"message_delta": f"batch2-msg-{i}"},
            )
            for i in range(6, 11)
        ]
        return run

    async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
        self._call_count += 1
        if self._call_count == 1:
            for event in self._batch1:
                yield event
        else:
            for event in self._batch2:
                yield event


class NoisyReplayRuntime(OnceRuntime):
    """Runtime that yields events with backend noise at seq 3 and 7."""

    def __init__(self) -> None:
        events = [
            RunEvent(
                event_id="noise-evt-1",
                run_id="run-noise",
                event_type="message.delta",
                occurred_at="2026-01-01T00:00:01Z",
                seq=1,
                payload={"message_delta": "Legal advice content"},
            ),
            RunEvent(
                event_id="noise-evt-2",
                run_id="run-noise",
                event_type="message.delta",
                occurred_at="2026-01-01T00:00:02Z",
                seq=2,
                payload={"message_delta": "More legal text"},
            ),
            RunEvent(
                event_id="noise-evt-3",
                run_id="run-noise",
                event_type="message.delta",
                occurred_at="2026-01-01T00:00:03Z",
                seq=3,
                payload={"message_delta": "stack trace occurred in the backend"},
            ),
            RunEvent(
                event_id="noise-evt-4",
                run_id="run-noise",
                event_type="message.delta",
                occurred_at="2026-01-01T00:00:04Z",
                seq=4,
                payload={"message_delta": "Contract analysis"},
            ),
            RunEvent(
                event_id="noise-evt-5",
                run_id="run-noise",
                event_type="message.delta",
                occurred_at="2026-01-01T00:00:05Z",
                seq=5,
                payload={"message_delta": "Statute reference"},
            ),
            RunEvent(
                event_id="noise-evt-6",
                run_id="run-noise",
                event_type="message.delta",
                occurred_at="2026-01-01T00:00:06Z",
                seq=6,
                payload={"message_delta": "Case law citation"},
            ),
            RunEvent(
                event_id="noise-evt-7",
                run_id="run-noise",
                event_type="message.delta",
                occurred_at="2026-01-01T00:00:07Z",
                seq=7,
                payload={"message_delta": "function call result in backend"},
            ),
            RunEvent(
                event_id="noise-evt-8",
                run_id="run-noise",
                event_type="message.delta",
                occurred_at="2026-01-01T00:00:08Z",
                seq=8,
                payload={"message_delta": "Final conclusion"},
            ),
            RunEvent(
                event_id="noise-evt-9",
                run_id="run-noise",
                event_type="message.delta",
                occurred_at="2026-01-01T00:00:09Z",
                seq=9,
                payload={"message_delta": "Recommendation"},
            ),
            RunEvent(
                event_id="noise-evt-10",
                run_id="run-noise",
                event_type="run.state_changed",
                occurred_at="2026-01-01T00:00:10Z",
                seq=10,
                payload={"status": "succeeded"},
            ),
        ]
        super().__init__(events)


def _make_app(
    runtime: object | None = None,
    event_buffer: RunEventBuffer | None = None,
) -> GatewayApp:
    config = GatewayConfig(enabled=True)
    auth = GatewayAuth(rbac_enabled=False, static_token="test-token")
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()
    return GatewayApp(
        config,
        runtime=runtime or OnceRuntime(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
        event_buffer=event_buffer or RunEventBuffer(),
    )


def _create_run(app: GatewayApp) -> str:
    result = asyncio.run(app.dispatch("POST", "/v1/runs", AUTH_HEADERS, CREATE_RUN_BODY))
    return result["run_id"]


def _collect_stream(app: GatewayApp, run_id: str, headers: dict | None = None) -> list[str]:
    async def collect():
        frames = []
        async for frame in app.stream("GET", f"/v1/runs/{run_id}/events", headers or AUTH_HEADERS):
            frames.append(frame)
        return frames
    return asyncio.run(collect())


def _parse_frame_event_id(frame: str) -> str:
    """Extract the id field from an SSE frame."""
    for line in frame.strip().split("\n"):
        if line.startswith("id: "):
            return line[4:]
    return ""


class TestSseReplay(unittest.TestCase):
    """Integration tests for SSE Last-Event-ID reconnection."""

    # ------------------------------------------------------------------
    # Tests 1-7: Basic replay scenarios
    # ------------------------------------------------------------------

    def test_stream_without_last_event_id(self) -> None:
        """Stream without Last-Event-ID: all 10 events yielded, all appended to buffer."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        frames = _collect_stream(app, run_id)
        self.assertEqual(len(frames), 10)
        buffered = buf.get_buffered_events(run_id)
        self.assertEqual(len(buffered), 10)

    def test_reconnect_with_last_event_id(self) -> None:
        """Stream to completion, reconnect with Last-Event-ID: 5. Replay yields seq 6-10."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        # First stream: populate buffer
        _collect_stream(app, run_id)

        # Reconnect with Last-Event-ID: 5
        frames = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "5"})
        # Replay yields events with seq > 5 (6, 7, 8, 9, 10 = 5 events)
        # Runtime yields nothing on second call (OnceRuntime)
        self.assertEqual(len(frames), 5)

        # Verify seq order
        buffered = buf.get_buffered_events(run_id)
        replay_events = [e for e in buffered if e.seq > 5]
        replay_seqs = sorted(e.seq for e in replay_events)
        self.assertEqual(replay_seqs, [6, 7, 8, 9, 10])

        # Verify SSE frame id fields match event_ids
        for frame in frames:
            event_id = _parse_frame_event_id(frame)
            self.assertTrue(event_id.startswith("replay-evt-"))

    def test_reconnect_with_last_event_id_zero(self) -> None:
        """Stream to completion, reconnect with Last-Event-ID: 0. All 10 events replayed."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        _collect_stream(app, run_id)
        frames = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "0"})
        self.assertEqual(len(frames), 10)

    def test_reconnect_with_last_event_id_beyond_buffer(self) -> None:
        """Stream to completion, reconnect with Last-Event-ID: 100. No events replayed."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        _collect_stream(app, run_id)
        frames = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "100"})
        self.assertEqual(len(frames), 0)

    def test_replay_no_duplicates(self) -> None:
        """Stream to completion, reconnect with Last-Event-ID: 3. Events seq 4-10, each exactly once."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        _collect_stream(app, run_id)
        frames = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "3"})

        # Should be 7 events (seq 4-10)
        self.assertEqual(len(frames), 7)

        # No duplicate event_ids
        event_ids = [_parse_frame_event_id(f) for f in frames]
        self.assertEqual(len(set(event_ids)), 7)

        # No event with seq <= 3
        buffered = buf.get_buffered_events(run_id)
        id_to_seq = {e.event_id: e.seq for e in buffered}
        for eid in event_ids:
            self.assertGreater(id_to_seq[eid], 3)

    def test_replay_no_loss(self) -> None:
        """Stream to completion, reconnect with Last-Event-ID: 5. Events seq 6-10 all present."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        _collect_stream(app, run_id)
        frames = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "5"})

        self.assertEqual(len(frames), 5)
        event_ids = [_parse_frame_event_id(f) for f in frames]
        buffered = buf.get_buffered_events(run_id)
        id_to_seq = {e.event_id: e.seq for e in buffered}
        replayed_seqs = sorted(id_to_seq[eid] for eid in event_ids)
        self.assertEqual(replayed_seqs, [6, 7, 8, 9, 10])

    def test_replay_preserves_seq_order(self) -> None:
        """Reconnect with Last-Event-ID: 0. Replayed events in seq order 1-10."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        _collect_stream(app, run_id)
        frames = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "0"})

        event_ids = [_parse_frame_event_id(f) for f in frames]
        buffered = buf.get_buffered_events(run_id)
        id_to_seq = {e.event_id: e.seq for e in buffered}
        seqs = [id_to_seq[eid] for eid in event_ids]
        self.assertEqual(seqs, list(range(1, 11)))

    # ------------------------------------------------------------------
    # Test 8: Output boundary during replay
    # ------------------------------------------------------------------

    def test_replay_applies_output_boundary(self) -> None:
        """Events with backend noise at seq 3 and 7. Replay skips blocked events (8 frames)."""
        runtime = NoisyReplayRuntime()
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        # First stream: 10 events, 2 blocked by boundary → 8 frames
        frames1 = _collect_stream(app, run_id)
        self.assertEqual(len(frames1), 8)

        # Reconnect with Last-Event-ID: 0 — replay should also skip blocked events
        frames2 = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "0"})
        self.assertEqual(len(frames2), 8)

        # Verify blocked content not in replay frames
        for frame in frames2:
            self.assertNotIn("stack trace", frame)
            self.assertNotIn("function call", frame)

    # ------------------------------------------------------------------
    # Test 9: Replay then continue streaming
    # ------------------------------------------------------------------

    def test_replay_then_continue_streaming(self) -> None:
        """Stream first 5 events (populate buffer). Reconnect with Last-Event-ID: 3.
        Replay yields events 4, 5 first, then stream continues with events 6-10."""
        runtime = ContinuationRuntime()
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        # First stream: yields batch 1 (events 1-5)
        frames1 = _collect_stream(app, run_id)
        self.assertEqual(len(frames1), 5)

        # Verify buffer has 5 events
        buffered = buf.get_buffered_events(run_id)
        self.assertEqual(len(buffered), 5)

        # Reconnect with Last-Event-ID: 3
        # Replay: events with seq > 3 from buffer (seq 4, 5 = 2 events)
        # Live: batch 2 (events 6-10 = 5 events)
        frames2 = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "3"})
        # 2 replayed + 5 live = 7 frames
        self.assertEqual(len(frames2), 7)

        # Verify the first 2 frames are replayed (seq 4, 5)
        event_ids = [_parse_frame_event_id(f) for f in frames2]
        all_buffered = buf.get_buffered_events(run_id)
        id_to_seq = {e.event_id: e.seq for e in all_buffered}
        seqs = [id_to_seq.get(eid) for eid in event_ids]
        # First 2 should be seq 4, 5 (replayed)
        self.assertEqual(seqs[:2], [4, 5])
        # Last 5 should be seq 6-10 (live from batch 2)
        self.assertEqual(seqs[2:], [6, 7, 8, 9, 10])

    # ------------------------------------------------------------------
    # Test 10: Terminal run buffer retention
    # ------------------------------------------------------------------

    def test_terminal_run_buffer_retention(self) -> None:
        """Stream to terminal state. is_terminal True. cleanup_expired with future timestamp removes buffer."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer(terminal_retention_seconds=300.0)
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        _collect_stream(app, run_id)

        # Last event is run.state_changed with status succeeded
        self.assertTrue(buf.is_terminal(run_id))

        # Cleanup with future timestamp should remove the buffer
        future = time.time() + 600
        removed = buf.cleanup_expired(now=future)
        self.assertEqual(removed, 1)
        self.assertEqual(buf.replay(run_id, 0), [])

    # ------------------------------------------------------------------
    # Test 11: Replay format matches encode_sse_event
    # ------------------------------------------------------------------

    def test_replay_format_matches_encode_sse_event(self) -> None:
        """Reconnect with Last-Event-ID: 0. Each replayed frame uses encode_sse_event format."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        _collect_stream(app, run_id)
        frames = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "0"})

        # Compare each replayed frame with direct encode_sse_event output
        buffered = buf.get_buffered_events(run_id)
        id_to_event = {e.event_id: e for e in buffered}

        for frame in frames:
            event_id = _parse_frame_event_id(frame)
            event = id_to_event[event_id]
            expected = encode_sse_event(event)
            self.assertEqual(frame, expected)

    # ------------------------------------------------------------------
    # Test 12: Replay event IDs match
    # ------------------------------------------------------------------

    def test_replay_event_ids_match(self) -> None:
        """Reconnect with Last-Event-ID: 5. Replayed frames' id fields match event_id."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        _collect_stream(app, run_id)
        frames = _collect_stream(app, run_id, {**AUTH_HEADERS, "Last-Event-ID": "5"})

        buffered = buf.get_buffered_events(run_id)
        replay_events = sorted([e for e in buffered if e.seq > 5], key=lambda e: e.seq)

        self.assertEqual(len(frames), len(replay_events))
        for frame, event in zip(frames, replay_events):
            frame_id = _parse_frame_event_id(frame)
            self.assertEqual(frame_id, event.event_id)

    # ------------------------------------------------------------------
    # Test 13: No regression — tracer slice still works
    # ------------------------------------------------------------------

    def test_no_regression_tracer_slice(self) -> None:
        """Original tracer slice from Plan 91-01 still works without Last-Event-ID."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        # Stream events
        frames = _collect_stream(app, run_id)
        self.assertGreater(len(frames), 0)
        for frame in frames:
            self.assertTrue(frame.startswith("id: "))
            self.assertIn("event: ", frame)
            self.assertIn("data: ", frame)

        # Cancel run
        cancel_result = asyncio.run(app.dispatch(
            "DELETE", f"/v1/runs/{run_id}", AUTH_HEADERS, {},
        ))
        self.assertEqual(cancel_result["run_id"], run_id)

    # ------------------------------------------------------------------
    # Test 14: Buffer cleanup on cancel
    # ------------------------------------------------------------------

    def test_buffer_cleanup_on_cancel(self) -> None:
        """Create run, stream some events, cancel run. Buffer cleaned up via clear_run."""
        runtime = OnceRuntime(_events_from_fixture("run-replay-001"))
        buf = RunEventBuffer()
        app = _make_app(runtime, buf)
        run_id = _create_run(app)

        # Stream some events (populates buffer)
        _collect_stream(app, run_id)
        self.assertGreater(len(buf.get_buffered_events(run_id)), 0)

        # Cancel the run
        asyncio.run(app.dispatch("DELETE", f"/v1/runs/{run_id}", AUTH_HEADERS, {}))

        # Explicitly clear the buffer for the cancelled run
        buf.clear_run(run_id)
        self.assertEqual(buf.replay(run_id, 0), [])
        self.assertEqual(buf.get_buffered_events(run_id), [])


if __name__ == "__main__":
    unittest.main()
