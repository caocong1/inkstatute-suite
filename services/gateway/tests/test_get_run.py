"""Tests for the Gateway GET /v1/runs/{id} endpoint.

Verifies:
- get_run returns run info (200) when runtime has get_run
- get_run returns 404 for nonexistent run
- get_run requires auth (401)
"""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass

from gateway.app import GatewayApp
from gateway.auth import GatewayAuth
from gateway.config import GatewayConfig
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from rbac.session import InMemorySessionStore

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@dataclass
class MockRun:
    """Minimal mock run object for testing _serialize_run."""
    run_id: str
    status: str = "running"
    tenant_id: str = "default"


class MockRuntime:
    """Mock runtime with get_run support."""

    def __init__(self) -> None:
        self._runs: dict[str, MockRun] = {}

    def get_run(self, run_id: str) -> MockRun | None:
        return self._runs.get(run_id)

    def add_run(self, run: MockRun) -> None:
        self._runs[run.run_id] = run


def _make_app(runtime: object | None = None) -> GatewayApp:
    config = GatewayConfig(enabled=True)
    auth = GatewayAuth(rbac_enabled=False, static_token="test-token")
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()
    return GatewayApp(
        config,
        runtime=runtime or object(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
    )


class TestGetRun(unittest.TestCase):
    """Tests for GET /v1/runs/{run_id}."""

    def test_get_run_returns_run_info(self) -> None:
        """Create a run in the mock runtime, GET it → 200 with run fields."""
        runtime = MockRuntime()
        runtime.add_run(MockRun(run_id="run-1", status="running"))
        app = _make_app(runtime=runtime)

        result = asyncio.run(app.dispatch("GET", "/v1/runs/run-1", AUTH_HEADERS, None))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["run_id"], "run-1")
        self.assertIn("status", result)
        self.assertIn("tenant_id", result)

    def test_get_run_not_found(self) -> None:
        """GET /v1/runs/nonexistent → 404."""
        runtime = MockRuntime()
        app = _make_app(runtime=runtime)

        result = asyncio.run(app.dispatch("GET", "/v1/runs/nonexistent", AUTH_HEADERS, None))
        self.assertEqual(result["status"], 404)
        self.assertEqual(result["error"]["code"], "not_found")

    def test_get_run_requires_auth(self) -> None:
        """GET /v1/runs/{id} without auth → 401."""
        app = _make_app()
        result = asyncio.run(app.dispatch("GET", "/v1/runs/some-id", {}, None))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")


if __name__ == "__main__":
    unittest.main()
