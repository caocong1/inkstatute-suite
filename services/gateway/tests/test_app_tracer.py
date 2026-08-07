"""End-to-end tracer slice tests for the InkStatute Gateway.

Tests the full tracer: POST /v1/sessions → POST /v1/runs →
GET /v1/runs/{id}/events (SSE) → DELETE /v1/runs/{id}.

All tests use FakeRunRuntime and fixture data — no network or external
services required.
"""

from __future__ import annotations

import asyncio
import json
import os
import unittest
from typing import AsyncIterator

from platform_contract.enums import AsyncTaskState
from platform_runtime.protocols import Run, RunEvent, RunRequest

from gateway.app import GatewayApp, OPERATIONS
from gateway.auth import GatewayAuth, GatewayAuthError
from gateway.config import GatewayConfig
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from rbac.session import InMemorySessionStore


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture_events() -> list[dict]:
    with open(os.path.join(FIXTURES_DIR, "gateway_events.json"), encoding="utf-8") as f:
        return json.load(f)


class FakeRunRuntime:
    """In-memory FakeRunRuntime for Gateway tests."""

    def __init__(self) -> None:
        self.runs: dict[str, Run] = {}
        self.events: dict[str, list[RunEvent]] = {}
        self._next_id = 1

    async def create_run(self, req: RunRequest) -> Run:
        run_id = f"run-{self._next_id:03d}"
        self._next_id += 1
        run = Run(
            run_id=run_id,
            status=AsyncTaskState.QUEUED,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata=dict(req.metadata),
        )
        self.runs[run_id] = run
        # Load fixture events for this run
        fixture_events = _load_fixture_events()
        self.events[run_id] = [
            RunEvent(
                event_id=e["event_id"],
                run_id=run_id,
                event_type=e["event_type"],
                occurred_at=e["occurred_at"],
                seq=e["seq"],
                payload=e["payload"],
                metadata=e.get("metadata", {}),
            )
            for e in fixture_events
        ]
        return run

    async def poll(self, run_id: str) -> Run:
        return self.runs.get(run_id, Run(
            run_id=run_id, status=AsyncTaskState.FAILED,
            turn_id="", solution_id="",
        ))

    async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
        for event in self.events.get(run_id, []):
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

    async def approve(self, run_id: str, approval: object) -> Run:
        return self.runs.get(run_id, Run(
            run_id=run_id, status=AsyncTaskState.FAILED,
            turn_id="", solution_id="",
        ))


class FakeNoisyRuntime(FakeRunRuntime):
    """Runtime that emits events with backend noise for boundary testing."""

    async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
        yield RunEvent(
            event_id="noise-1", run_id=run_id, event_type="message.delta",
            occurred_at="2026-01-01T00:00:00Z", seq=1,
            payload={"message_delta": "stack trace occurred in the backend"},
            metadata={},
        )
        yield RunEvent(
            event_id="clean-1", run_id=run_id, event_type="message.delta",
            occurred_at="2026-01-01T00:00:01Z", seq=2,
            payload={"message_delta": "Hello, lawyer!"},
            metadata={},
        )


def _make_app(runtime=None) -> GatewayApp:
    config = GatewayConfig(enabled=True)
    auth = GatewayAuth(rbac_enabled=False, static_token="test-token")
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()
    return GatewayApp(
        config,
        runtime=runtime or FakeRunRuntime(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
    )


AUTH_HEADERS = {"Authorization": "Bearer test-token"}

CREATE_RUN_BODY = {
    "turn": {
        "turn_id": "turn-test-001",
        "conversation_id": "conv-test-001",
        "channel": "web",
        "user_id": "lawyer-test",
        "message_type": "text",
        "received_at": "2026-08-07T00:00:00Z",
        "content": "fixture://turns/turn-test-001/content_ref",
    },
    "solution": {
        "solution_id": "lawyer-v1",
        "backend_id": "hermes",
    },
}


class TestGatewayTracer(unittest.TestCase):
    """End-to-end tracer slice tests."""

    def setUp(self) -> None:
        self.app = _make_app()

    def test_create_session(self) -> None:
        result = asyncio.run(self.app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "t1", "user_id": "u1", "conversation_id": "c1"},
        ))
        self.assertIn("session_id", result)
        self.assertEqual(result["tenant_id"], "t1")
        self.assertEqual(result["conversation_id"], "c1")

    def test_create_session_no_auth(self) -> None:
        result = asyncio.run(self.app.dispatch(
            "POST", "/v1/sessions", {},
            {"tenant_id": "t1", "user_id": "u1", "conversation_id": "c1"},
        ))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")

    def test_create_run(self) -> None:
        result = asyncio.run(self.app.dispatch(
            "POST", "/v1/runs", AUTH_HEADERS, CREATE_RUN_BODY,
        ))
        self.assertIn("run_id", result)
        self.assertIn("status", result)

    def test_get_run_stub(self) -> None:
        result = asyncio.run(self.app.dispatch(
            "GET", "/v1/runs/run-1", AUTH_HEADERS, None,
        ))
        self.assertEqual(result["status"], 501)

    def test_cancel_run(self) -> None:
        create_result = asyncio.run(self.app.dispatch(
            "POST", "/v1/runs", AUTH_HEADERS, CREATE_RUN_BODY,
        ))
        run_id = create_result["run_id"]
        result = asyncio.run(self.app.dispatch(
            "DELETE", f"/v1/runs/{run_id}", AUTH_HEADERS, {},
        ))
        self.assertEqual(result["run_id"], run_id)

    def test_stream_run_sse(self) -> None:
        create_result = asyncio.run(self.app.dispatch(
            "POST", "/v1/runs", AUTH_HEADERS, CREATE_RUN_BODY,
        ))
        run_id = create_result["run_id"]

        async def collect():
            frames = []
            async for frame in self.app.stream("GET", f"/v1/runs/{run_id}/events", AUTH_HEADERS):
                frames.append(frame)
            return frames

        frames = asyncio.run(collect())
        self.assertGreater(len(frames), 0)
        for frame in frames:
            self.assertTrue(frame.startswith("id: "), f"Frame should start with 'id: ', got: {frame[:20]}")
            self.assertIn("event: ", frame)
            self.assertIn("data: ", frame)

    def test_stream_run_no_auth(self) -> None:
        async def attempt():
            async for _ in self.app.stream("GET", "/v1/runs/run-1/events", {}):
                pass

        with self.assertRaises(GatewayAuthError) as ctx:
            asyncio.run(attempt())
        self.assertEqual(ctx.exception.status, 401)

    def test_stream_run_output_boundary(self) -> None:
        """Backend noise is blocked by the output boundary."""
        noisy_app = _make_app(FakeNoisyRuntime())
        create_result = asyncio.run(noisy_app.dispatch(
            "POST", "/v1/runs", AUTH_HEADERS, CREATE_RUN_BODY,
        ))
        run_id = create_result["run_id"]

        async def collect():
            frames = []
            async for frame in noisy_app.stream("GET", f"/v1/runs/{run_id}/events", AUTH_HEADERS):
                frames.append(frame)
            return frames

        frames = asyncio.run(collect())
        # The noisy event should be blocked — only the clean event passes
        self.assertEqual(len(frames), 1)
        self.assertNotIn("stack trace", frames[0])

    def test_unknown_route_404(self) -> None:
        result = asyncio.run(self.app.dispatch(
            "GET", "/v1/unknown", AUTH_HEADERS, None,
        ))
        self.assertEqual(result["status"], 404)

    def test_stubbed_endpoints_return_501(self) -> None:
        # Upload, artifact, and feedback are now implemented (Plan 91-03).
        # The remaining 5 stubs still return 501.
        stubbed = [
            ("GET", "/v1/sessions/sess-1", None),
            ("GET", "/v1/sessions/sess-1/runs", None),
            ("GET", "/v1/runs/run-1", None),
            ("POST", "/v1/runs/run-1/elicitation", {}),
            ("POST", "/v1/runs/run-1/approvals", {}),
            ("GET", "/v1/skills", None),
        ]
        for method, path, body in stubbed:
            result = asyncio.run(self.app.dispatch(method, path, AUTH_HEADERS, body))
            self.assertEqual(
                result["status"], 501,
                f"Expected 501 for {method} {path}, got: {result}",
            )

    def test_end_to_end_tracer_slice(self) -> None:
        """Full tracer: create session → create run → stream events → cancel run."""
        # 1. Create session
        session_result = asyncio.run(self.app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "t1", "user_id": "u1", "conversation_id": "c1"},
        ))
        self.assertIn("session_id", session_result)

        # 2. Create run
        run_result = asyncio.run(self.app.dispatch(
            "POST", "/v1/runs", AUTH_HEADERS, CREATE_RUN_BODY,
        ))
        run_id = run_result["run_id"]
        self.assertIsNotNone(run_id)

        # 3. Stream events
        async def collect():
            frames = []
            async for frame in self.app.stream("GET", f"/v1/runs/{run_id}/events", AUTH_HEADERS):
                frames.append(frame)
            return frames

        frames = asyncio.run(collect())
        self.assertGreater(len(frames), 0)
        for frame in frames:
            self.assertTrue(frame.startswith("id: "))

        # 4. Cancel run
        cancel_result = asyncio.run(self.app.dispatch(
            "DELETE", f"/v1/runs/{run_id}", AUTH_HEADERS, {},
        ))
        self.assertEqual(cancel_result["run_id"], run_id)

    def test_all_operations_listed(self) -> None:
        ops = self.app.operations()
        self.assertEqual(len(ops), 13)
        for op in ops:
            self.assertIn(op, OPERATIONS)

    def test_tenant_id_in_response(self) -> None:
        """GW-03: tenant_id is present in all responses (contract field not omitted)."""
        session_result = asyncio.run(self.app.dispatch(
            "POST", "/v1/sessions", AUTH_HEADERS,
            {"tenant_id": "t1", "user_id": "u1", "conversation_id": "c1"},
        ))
        self.assertIn("tenant_id", session_result)

        run_result = asyncio.run(self.app.dispatch(
            "POST", "/v1/runs", AUTH_HEADERS, CREATE_RUN_BODY,
        ))
        self.assertIn("tenant_id", run_result)


if __name__ == "__main__":
    unittest.main()
