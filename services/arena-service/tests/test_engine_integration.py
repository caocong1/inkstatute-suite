"""Engine integration tests — ArenaEventEmitter + ArenaServiceEngine wiring.

Tests the 13 behaviors from Plan 05 Task 1:

1.  ArenaEventEmitter implements the EventEmitter protocol
2.  emit appends to buffer with seq and forwards to queue
3.  Monotonically increasing seq numbers
4.  Preserves metadata.agent_slot
5.  dispatch POST /v1/arena returns {arena_id, status: created} + background run
6.  stream() yields SSE frames with agent_slot
7.  stream() with Last-Event-ID replays buffered events with seq > last
8.  dispatch POST /v1/arena/{id}/cancel calls engine.cancel
9.  dispatch POST /v1/arena/{id}/action calls engine.submit_user_action
10. dispatch GET /v1/arena/{id}/status calls engine.query_status
11. ArenaSseStream constructed with ArenaOutputBoundary — blocked events dropped
12. SubprocessController cleanup wired to engine.cancel
13. StaggeredStartupSemaphore wraps adapter.submit_run
"""

from __future__ import annotations

import asyncio
import json
import unittest
from datetime import UTC, datetime
from typing import Any

from arena_engine.mock_acp import MockACPBackendAdapter
from platform_contract.arena_contract import ArenaWorkflowConfig
from platform_contract.enums import RunEventType
from platform_runtime.protocols import RunRequest, SolutionBinding
from platform_contract.events import AgentTurn

from arena_service.app import ArenaServiceApp
from arena_service.auth import ArenaServiceAuth, ArenaServiceAuthError
from arena_service.config import ArenaServiceConfig
from arena_service.engine_integration import (
    ArenaEventEmitter,
    ArenaServiceEngine,
    _StaggeredAdapter,
)
from arena_service.event_buffer import ArenaEventBuffer
from arena_service.output_boundary import ArenaOutputBoundary
from arena_service.sse import ArenaSseStream
from arena_service.staggered_startup import StaggeredStartupSemaphore
from arena_service.subprocess_control import SubprocessController


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class V3MockAdapter(MockACPBackendAdapter):
    """MockACPBackendAdapter that emits V3 event types.

    The standard MockACPBackendAdapter emits V2 event types
    (``"message_delta"``) which are blocked by the ACP output boundary
    (not in :data:`ACP_ALLOWED_EVENT_TYPES`).  This subclass maps them
    to V3 types (``"message.delta"``) which are in the allowlist.
    """

    def _append_event(self, run_id, event_type, *, payload=None):
        type_str = str(event_type)
        if type_str == "message_delta":
            event_type = "message.delta"
        return super()._append_event(run_id, event_type, payload=payload)


def _make_adapter_factory(
    responses: list[str] | None = None,
    adapter_cls: type = V3MockAdapter,
) -> Any:
    """Create an adapter factory that returns mock adapters per slot."""

    def factory(slot_id: str, body: dict) -> Any:
        return adapter_cls(
            backend_id=f"mock-{slot_id}",
            responses=responses or ["test response from " + slot_id],
            agent_slot=slot_id,
        )

    return factory


def _make_engine(
    config: ArenaServiceConfig | None = None,
    adapter_factory: Any = None,
) -> ArenaServiceEngine:
    cfg = config or ArenaServiceConfig(token="secret")
    return ArenaServiceEngine(cfg, adapter_factory=adapter_factory or _make_adapter_factory())


def _make_app(
    engine: ArenaServiceEngine | None = None,
    token: str = "secret",
    config: ArenaServiceConfig | None = None,
) -> ArenaServiceApp:
    cfg = config or ArenaServiceConfig(token=token)
    auth = ArenaServiceAuth(config=cfg)
    return ArenaServiceApp(config=cfg, auth=auth, engine=engine)


def _auth_headers(token: str = "secret") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_run_request(arena_id: str = "test", slot_id: str = "slot-0") -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id=f"{arena_id}-{slot_id}-round0",
            conversation_id=f"{arena_id}-conv",
            channel="web",
            user_id="arena-user",
            message_type="text",
            received_at=datetime.now(UTC).isoformat(),
            content="test task",
        ),
        solution=SolutionBinding(solution_id=f"arena-{arena_id}"),
    )


async def _collect_stream(gen: Any, timeout: float = 10.0) -> list[str]:
    """Collect all frames from an async generator with a timeout."""
    frames: list[str] = []

    async def _collect() -> None:
        async for frame in gen:
            frames.append(frame)

    try:
        await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    return frames


async def _wait_for_status(
    engine: ArenaServiceEngine,
    arena_id: str,
    target: set[str],
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Poll status_arena until status is in *target* or timeout."""
    for _ in range(int(timeout / 0.01)):
        status = await engine.status_arena(arena_id)
        if status["status"] in target:
            return status
        await asyncio.sleep(0.01)
    return await engine.status_arena(arena_id)


# ---------------------------------------------------------------------------
# Tests 1-4: ArenaEventEmitter unit tests
# ---------------------------------------------------------------------------


class ArenaEventEmitterTests(unittest.IsolatedAsyncioTestCase):
    """Tests 1-4: ArenaEventEmitter protocol, seq, buffer, queue, agent_slot."""

    async def test_emitter_implements_event_emitter_protocol(self):
        # Test 1: ArenaEventEmitter has async emit(event_type, payload, metadata).
        buffer = ArenaEventBuffer()
        queue: asyncio.Queue = asyncio.Queue()
        emitter = ArenaEventEmitter("arena-1", buffer, queue)
        self.assertTrue(hasattr(emitter, "emit"))
        self.assertTrue(callable(emitter.emit))

    async def test_emit_appends_to_buffer_and_forwards_to_queue(self):
        # Test 2: emit appends event to buffer with seq and puts into queue.
        buffer = ArenaEventBuffer()
        queue: asyncio.Queue = asyncio.Queue()
        emitter = ArenaEventEmitter("arena-1", buffer, queue)

        await emitter.emit("message.delta", {"text": "hello"}, {"agent_slot": "slot-0"})

        # Buffer has 1 event with seq=1
        events = buffer.get_buffered_events("arena-1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["seq"], 1)
        self.assertEqual(events[0]["event_type"], "message.delta")

        # Queue has 1 event
        self.assertEqual(queue.qsize(), 1)
        queued = queue.get_nowait()
        self.assertEqual(queued["seq"], 1)
        self.assertEqual(queued["event_type"], "message.delta")

    async def test_emit_assigns_monotonically_increasing_seq(self):
        # Test 3: first event seq=1, second seq=2, etc.
        buffer = ArenaEventBuffer()
        queue: asyncio.Queue = asyncio.Queue()
        emitter = ArenaEventEmitter("arena-1", buffer, queue)

        await emitter.emit("message.delta", {"text": "a"}, {"agent_slot": "s0"})
        await emitter.emit("message.delta", {"text": "b"}, {"agent_slot": "s1"})
        await emitter.emit("message.completed", {"content": "c"}, {"agent_slot": "s0"})

        events = buffer.get_buffered_events("arena-1")
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["seq"], 1)
        self.assertEqual(events[1]["seq"], 2)
        self.assertEqual(events[2]["seq"], 3)
        self.assertEqual(emitter.seq, 3)

    async def test_emit_preserves_agent_slot_in_metadata(self):
        # Test 4: metadata.agent_slot is preserved in the buffered event.
        buffer = ArenaEventBuffer()
        queue: asyncio.Queue = asyncio.Queue()
        emitter = ArenaEventEmitter("arena-1", buffer, queue)

        await emitter.emit("message.delta", {"text": "hello"}, {"agent_slot": "slot-7"})

        events = buffer.get_buffered_events("arena-1")
        self.assertEqual(events[0]["metadata"]["agent_slot"], "slot-7")

        queued = queue.get_nowait()
        self.assertEqual(queued["metadata"]["agent_slot"], "slot-7")


# ---------------------------------------------------------------------------
# Tests 5-10: ArenaServiceApp dispatch + stream with ArenaServiceEngine
# ---------------------------------------------------------------------------


class ArenaServiceEngineDispatchTests(unittest.IsolatedAsyncioTestCase):
    """Tests 5-10: dispatch handlers delegate to ArenaServiceEngine."""

    async def test_dispatch_create_arena_returns_created_and_starts_run(self):
        # Test 5: POST /v1/arena returns {arena_id, status: created} and
        # starts a background arena run.
        engine = _make_engine()
        app = _make_app(engine=engine)
        headers = _auth_headers()
        body = {
            "mode": "mode1_parallel",
            "agent_slots": ["slot-0", "slot-1"],
            "task": "analyze contract",
        }
        result = await app.dispatch("POST", "/v1/arena", headers, body)
        self.assertEqual(result["status"], 201)
        self.assertEqual(result["body"]["status"], "created")
        arena_id = result["body"]["arena_id"]
        self.assertTrue(arena_id)

        # Wait for background run to start — event queue should exist.
        await asyncio.sleep(0.1)
        self.assertIn(arena_id, engine._event_queues)

        # Wait for run to complete.
        status = await _wait_for_status(engine, arena_id, {"completed", "cancelled"})
        self.assertIn(status["status"], ("completed", "cancelled"))

    async def test_stream_yields_sse_frames_with_agent_slot(self):
        # Test 6: stream() yields SSE frames with agent_slot in JSON data.
        engine = _make_engine()
        app = _make_app(engine=engine)
        headers = _auth_headers()
        body = {
            "mode": "mode1_parallel",
            "agent_slots": ["slot-0", "slot-1"],
            "task": "test task",
        }
        result = await app.dispatch("POST", "/v1/arena", headers, body)
        arena_id = result["body"]["arena_id"]

        # Wait for background run to start.
        await asyncio.sleep(0.1)

        # Collect SSE frames.
        frames = await _collect_stream(
            app.stream("GET", f"/v1/arena/{arena_id}/stream", headers, "127.0.0.1"),
        )

        # Verify frames are non-empty and contain agent_slot.
        self.assertTrue(len(frames) > 0, "Expected at least one SSE frame")

        # Parse each frame and verify agent_slot is present.
        agent_slots_seen: set[str] = set()
        for frame in frames:
            self.assertIn("data: ", frame)
            data_line = frame.split("data: ", 1)[1].split("\n", 1)[0]
            data = json.loads(data_line)
            slot = data.get("metadata", {}).get("agent_slot")
            if slot:
                agent_slots_seen.add(slot)

        # Both slots should appear (message.completed events pass the filter).
        self.assertIn("slot-0", agent_slots_seen)
        self.assertIn("slot-1", agent_slots_seen)

    async def test_stream_with_last_event_id_replays_buffered_events(self):
        # Test 7: stream() with Last-Event-ID replays seq > last_seq.
        engine = _make_engine()
        arena_id = "arena-reconnect-test"

        # Manually emit 5 events to the buffer only (use a throwaway queue
        # for the emitter so events don't also go into the stream queue).
        buffer = engine.event_buffer
        throwaway_queue: asyncio.Queue = asyncio.Queue()
        emitter = ArenaEventEmitter(arena_id, buffer, throwaway_queue)
        for i in range(5):
            await emitter.emit(
                "message.delta",
                {"message_delta": f"event {i + 1}"},
                {"agent_slot": "slot-0"},
            )

        # Set up the stream queue with just the sentinel to end after replay.
        stream_queue: asyncio.Queue = asyncio.Queue()
        await stream_queue.put(None)
        engine._event_queues[arena_id] = stream_queue

        # Reconnect with Last-Event-ID: 3 — should replay events 4 and 5.
        app = _make_app(engine=engine)
        headers = {**_auth_headers(), "Last-Event-ID": "3"}
        frames = await _collect_stream(
            app.stream("GET", f"/v1/arena/{arena_id}/stream", headers, "127.0.0.1"),
        )

        # Events 4 and 5 should be replayed (both message.delta, in allowlist).
        self.assertEqual(len(frames), 2)
        for frame in frames:
            data_line = frame.split("data: ", 1)[1].split("\n", 1)[0]
            data = json.loads(data_line)
            self.assertGreater(data["seq"], 3)

    async def test_dispatch_cancel_arena_calls_engine_cancel(self):
        # Test 8: POST /v1/arena/{id}/cancel calls engine.cancel and returns
        # {arena_id, status: cancelled}.
        engine = _make_engine()
        app = _make_app(engine=engine)
        headers = _auth_headers()

        # Create an arena first.
        create_result = await app.dispatch(
            "POST", "/v1/arena", headers,
            {"mode": "mode1_parallel", "agent_slots": ["slot-0"], "task": "test"},
        )
        arena_id = create_result["body"]["arena_id"]
        await asyncio.sleep(0.05)

        # Cancel it.
        result = await app.dispatch(
            "POST", f"/v1/arena/{arena_id}/cancel", headers, {},
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"]["status"], "cancelled")
        self.assertEqual(result["body"]["arena_id"], arena_id)

    async def test_dispatch_user_action_calls_engine_submit_action(self):
        # Test 9: POST /v1/arena/{id}/action with {action: stop} calls
        # engine.submit_user_action and returns the updated handle.
        engine = _make_engine()
        app = _make_app(engine=engine)
        headers = _auth_headers()

        # Create an arena first.
        create_result = await app.dispatch(
            "POST", "/v1/arena", headers,
            {"mode": "mode2_iteration", "agent_slots": ["slot-0"], "task": "test"},
        )
        arena_id = create_result["body"]["arena_id"]
        await asyncio.sleep(0.05)

        # Submit a stop action.
        result = await app.dispatch(
            "POST", f"/v1/arena/{arena_id}/action", headers,
            {"action": "stop"},
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"]["status"], "stopped")

    async def test_dispatch_status_arena_calls_engine_query_status(self):
        # Test 10: GET /v1/arena/{id}/status calls engine.query_status.
        engine = _make_engine()
        app = _make_app(engine=engine)
        headers = _auth_headers()

        # Create an arena first.
        create_result = await app.dispatch(
            "POST", "/v1/arena", headers,
            {"mode": "mode1_parallel", "agent_slots": ["slot-0"], "task": "test"},
        )
        arena_id = create_result["body"]["arena_id"]

        # Query status.
        result = await app.dispatch(
            "GET", f"/v1/arena/{arena_id}/status", headers, None,
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"]["arena_id"], arena_id)
        self.assertIn(result["body"]["status"], ("running", "completed", "cancelled"))


# ---------------------------------------------------------------------------
# Tests 11-13: Component wiring tests
# ---------------------------------------------------------------------------


class ArenaComponentWiringTests(unittest.IsolatedAsyncioTestCase):
    """Tests 11-13: output boundary, subprocess cleanup, staggered startup."""

    def test_sse_stream_constructed_with_output_boundary(self):
        # Test 11: ArenaSseStream is constructed with ArenaOutputBoundary.
        engine = _make_engine()
        self.assertIsInstance(engine.sse_stream, ArenaSseStream)
        self.assertIsInstance(engine.sse_stream._output_filter, ArenaOutputBoundary)

    def test_output_boundary_drops_blocked_events(self):
        # Test 11b: blocked events (meta/gateway/system noise) are dropped.
        engine = _make_engine()
        event = {
            "event_id": "test-1",
            "event_type": "message.delta",
            "seq": 1,
            "payload": {"message_delta": "meta: internal info"},
            "metadata": {"agent_slot": "slot-0"},
        }
        frame = engine.sse_stream.encode_event(event)
        self.assertIsNone(frame, "meta: content should be blocked by output boundary")

    def test_output_boundary_allows_clean_events(self):
        # Test 11c: clean events pass through the output boundary.
        engine = _make_engine()
        event = {
            "event_id": "test-2",
            "event_type": "message.delta",
            "seq": 1,
            "payload": {"message_delta": "clean response text"},
            "metadata": {"agent_slot": "slot-0"},
        }
        frame = engine.sse_stream.encode_event(event)
        self.assertIsNotNone(frame, "clean content should pass the output boundary")
        self.assertIn("agent_slot", frame)

    async def test_subprocess_cleanup_wired_to_engine_cancel(self):
        # Test 12: SubprocessController cleanup callback is wired to
        # engine.cancel() — on per-run timeout, the arena is cancelled.
        cfg = ArenaServiceConfig(
            token="secret",
            per_run_timeout_seconds=300.0,
        )
        engine = _make_engine(config=cfg)

        # Start an arena + background run to wire the cleanup callback.
        arena_config = ArenaWorkflowConfig(
            arena_id="arena-cleanup-test",
            mode="mode1_parallel",
            agent_slots=["slot-0"],
            task_instruction="test",
        )
        await engine.arena_engine.start(arena_config)
        adapters = {
            "slot-0": V3MockAdapter(
                backend_id="mock-0",
                responses=["test"],
                agent_slot="slot-0",
            ),
        }
        asyncio.create_task(engine.run_arena_background("arena-cleanup-test", adapters))
        await asyncio.sleep(0.1)

        # Verify cleanup callback is set.
        self.assertIsNotNone(engine.subprocess_controller._cleanup_callback)

        # Call cleanup callback and verify arena is cancelled.
        await engine.subprocess_controller._cleanup_callback()
        status = await engine.status_arena("arena-cleanup-test")
        self.assertEqual(status["status"], "cancelled")

    async def test_staggered_startup_wraps_submit_run(self):
        # Test 13: StaggeredStartupSemaphore wraps adapter.submit_run —
        # at most max_concurrent agents initialize simultaneously.
        staggered = StaggeredStartupSemaphore(max_concurrent=2)
        adapter = V3MockAdapter(
            backend_id="mock-0",
            responses=["test"],
            agent_slot="slot-0",
        )
        wrapped = _StaggeredAdapter(adapter, staggered)

        # Verify submit_run is wrapped (not the original).
        self.assertNotEqual(wrapped.submit_run, adapter.submit_run)

        # Verify it still works — call submit_run through the wrapper.
        req = _make_run_request()
        handle = await wrapped.submit_run(req)
        self.assertIsNotNone(handle)
        self.assertTrue(handle.run_id)  # mock generates its own run_id

        # Verify __getattr__ delegates other methods.
        self.assertEqual(wrapped.backend_id(), "mock-0")

    async def test_staggered_startup_limits_concurrent_initializations(self):
        # Test 13b: at most max_concurrent agents initialize simultaneously.
        max_concurrent = 2
        cfg = ArenaServiceConfig(
            token="secret",
            max_concurrent_initializations=max_concurrent,
        )
        engine = _make_engine(config=cfg)
        self.assertEqual(engine.staggered_startup.max_concurrent, max_concurrent)

        # Create 4 adapters with a small delay in submit_run to hold the semaphore.
        observations: list[int] = []
        staggered = engine.staggered_startup

        class TrackingAdapter(V3MockAdapter):
            async def submit_run(self, req):
                observations.append(staggered.current_concurrent)
                await asyncio.sleep(0.05)
                observations.append(staggered.current_concurrent)
                return await super().submit_run(req)

        adapters = {
            f"slot-{i}": TrackingAdapter(
                backend_id=f"mock-{i}",
                responses=[f"response {i}"],
                agent_slot=f"slot-{i}",
            )
            for i in range(4)
        }

        # Start arena + background run.
        arena_config = ArenaWorkflowConfig(
            arena_id="arena-stagger-test",
            mode="mode1_parallel",
            agent_slots=list(adapters.keys()),
            task_instruction="test",
        )
        await engine.arena_engine.start(arena_config)
        await engine.run_arena_background("arena-stagger-test", adapters)

        # Verify max concurrent never exceeded the limit.
        self.assertTrue(len(observations) > 0)
        self.assertLessEqual(max(observations), max_concurrent)


if __name__ == "__main__":
    unittest.main()
