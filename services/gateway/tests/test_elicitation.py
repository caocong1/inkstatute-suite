"""Tests for the Gateway POST /v1/runs/{id}/elicitation endpoint.

Verifies:
- submit_elicitation returns success with status "submitted"
- submit_elicitation returns 400 for missing interrupt_id
- submit_elicitation returns 400 for empty answers
- submit_elicitation requires auth (401)
- submit_elicitation stores answers in the handler's internal state
"""

from __future__ import annotations

import asyncio
import unittest

from gateway.app import GatewayApp
from gateway.auth import GatewayAuth
from gateway.config import GatewayConfig
from gateway.elicitation import GatewayElicitationHandler
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from rbac.session import InMemorySessionStore

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def _make_app(handler: GatewayElicitationHandler | None = None) -> GatewayApp:
    config = GatewayConfig(enabled=True)
    auth = GatewayAuth(rbac_enabled=False, static_token="test-token")
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()
    return GatewayApp(
        config,
        runtime=object(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
        elicitation_handler=handler or GatewayElicitationHandler(),
    )


class TestElicitation(unittest.TestCase):
    """Tests for POST /v1/runs/{run_id}/elicitation."""

    def test_submit_elicitation_returns_success(self) -> None:
        """POST with interrupt_id and answers → 200 with status: 'submitted'."""
        app = _make_app()
        body = {
            "interrupt_id": "i1",
            "answers": [{"question_id": "q1", "answer": "yes"}],
        }
        result = asyncio.run(app.dispatch("POST", "/v1/runs/run-1/elicitation", AUTH_HEADERS, body))
        self.assertNotIn("error", result, f"Expected success, got: {result}")
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["run_id"], "run-1")
        self.assertEqual(result["interrupt_id"], "i1")

    def test_submit_elicitation_missing_interrupt_id(self) -> None:
        """POST without interrupt_id → 400."""
        app = _make_app()
        body = {
            "answers": [{"question_id": "q1", "answer": "yes"}],
        }
        result = asyncio.run(app.dispatch("POST", "/v1/runs/run-1/elicitation", AUTH_HEADERS, body))
        self.assertEqual(result["status"], 400)
        self.assertEqual(result["error"]["code"], "invalid_request")

    def test_submit_elicitation_empty_answers(self) -> None:
        """POST with empty answers array → 400."""
        app = _make_app()
        body = {
            "interrupt_id": "i1",
            "answers": [],
        }
        result = asyncio.run(app.dispatch("POST", "/v1/runs/run-1/elicitation", AUTH_HEADERS, body))
        self.assertEqual(result["status"], 400)
        self.assertEqual(result["error"]["code"], "invalid_request")

    def test_submit_elicitation_requires_auth(self) -> None:
        """No auth → 401."""
        app = _make_app()
        body = {
            "interrupt_id": "i1",
            "answers": [{"question_id": "q1", "answer": "yes"}],
        }
        result = asyncio.run(app.dispatch("POST", "/v1/runs/run-1/elicitation", {}, body))
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["error"]["code"], "unauthorized")

    def test_submit_elicitation_stores_answers(self) -> None:
        """Submit, then verify the handler has stored the answers (internal state check)."""
        handler = GatewayElicitationHandler()
        app = _make_app(handler=handler)
        body = {
            "interrupt_id": "i1",
            "answers": [{"question_id": "q1", "answer": "yes"}],
        }
        asyncio.run(app.dispatch("POST", "/v1/runs/run-1/elicitation", AUTH_HEADERS, body))

        # Verify the handler stored the submission
        stored = handler.get_submission("run-1", "i1")
        self.assertIsNotNone(stored, "Submission should be stored in the handler")
        self.assertEqual(stored["interrupt_id"], "i1")
        self.assertEqual(len(stored["answers"]), 1)
        self.assertEqual(stored["answers"][0]["question_id"], "q1")
        self.assertEqual(stored["answers"][0]["answer"], "yes")


if __name__ == "__main__":
    unittest.main()
