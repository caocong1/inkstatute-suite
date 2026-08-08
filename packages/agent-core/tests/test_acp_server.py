"""Tests for the ACP server entry point — ``inkstatute-agent acp``.

Covers:
- ``initialize`` protocol response (protocolVersion, agentInfo, capabilities)
- ``session/new``, ``session/prompt``, ``session/cancel``, ``session/close``
- Reverse event mapping (RunEvent → ACP session/update)
- ``--check`` flag (exit 0 when OK, non-zero when provider unavailable)
- Elicitation and permission request forwarding
- Dangerous permission safety (never auto-approved)
- Full ACP round-trip with FixtureProvider
- Integration: ACPClient driving the agent-core ACP server via subprocess
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import sys
import unittest

from platform_contract.enums import RunEventType
from platform_contract.events import ErrorInfo, RunEvent
from platform_contract.unified_events import (
    ElicitationQuestion,
    ElicitationRequestedPayload,
    MessageCompletedPayload,
    MessageDeltaPayload,
    PermissionRequestedPayload,
    ThoughtDeltaPayload,
    ToolCallCompletedPayload,
    ToolCallDeltaPayload,
    ToolCallStartedPayload,
)

from inkstatute_agent_core.acp_server import (
    AGENT_CAPABILITIES,
    AGENT_NAME,
    AGENT_VERSION,
    PROTOCOL_VERSION,
    ACPServer,
    map_run_event_to_acp_request,
    map_run_event_to_acp_update,
    run_check,
)
from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.provider import (
    ContentDelta,
    FinishDelta,
    ToolCallDelta,
)
from inkstatute_agent_core.__main__ import main as cli_main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    event_type: str,
    payload: dict,
    run_id: str = "run-test",
    seq: int = 0,
) -> RunEvent:
    """Build a RunEvent with the given type and payload."""
    return RunEvent(
        event_id="evt-1",
        run_id=run_id,
        event_type=event_type,
        occurred_at="2026-01-01T00:00:00Z",
        seq=seq,
        payload=payload,
        metadata={},
    )


def _make_provider_with_text(text: str) -> FixtureProvider:
    """Create a FixtureProvider that streams the given text in one round."""
    return FixtureProvider([
        TurnScript(deltas=[
            ContentDelta(content=text),
            FinishDelta(finish_reason="stop"),
        ]),
    ])


class _FakeStdin:
    """A fake stdin that yields pre-loaded lines."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)
        self._index = 0

    def readline(self) -> str:
        if self._index >= len(self._lines):
            return ""  # EOF
        line = self._lines[self._index]
        self._index += 1
        return line + "\n"


def _run_server(
    provider_factory,
    messages: list[dict],
    config: AgentCoreConfig | None = None,
) -> list[dict]:
    """Run the ACP server with the given input messages and collect output.

    Returns a list of parsed JSON-RPC response/notification dicts.
    """
    stdout = io.StringIO()
    stdin = _FakeStdin([json.dumps(m) for m in messages])
    server = ACPServer(
        provider_factory=provider_factory,
        config=config or AgentCoreConfig(),
        stdin=stdin,
        stdout=stdout,
    )
    server.run_sync()
    output = stdout.getvalue()
    results = []
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        results.append(json.loads(line))
    return results


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------


class TestInitialize(unittest.TestCase):
    """Tests for the ``initialize`` protocol method."""

    def test_initialize_responds_with_protocol_version_1(self):
        """initialize response must have protocolVersion 1."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "initialize"}],
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["result"]["protocolVersion"], 1)

    def test_initialize_responds_with_agent_info(self):
        """initialize response must have agentInfo with name and version."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "initialize"}],
        )
        agent_info = results[0]["result"]["agentInfo"]
        self.assertEqual(agent_info["name"], AGENT_NAME)
        self.assertEqual(agent_info["version"], AGENT_VERSION)

    def test_initialize_declares_streaming_capability(self):
        """initialize must declare streaming=true."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "initialize"}],
        )
        caps = results[0]["result"]["capabilities"]
        self.assertTrue(caps.get("streaming"))

    def test_initialize_declares_elicitation_capability(self):
        """initialize must declare elicitation=true."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "initialize"}],
        )
        caps = results[0]["result"]["capabilities"]
        self.assertTrue(caps.get("elicitation"))

    def test_initialize_declares_permissions_capability(self):
        """initialize must declare permissions=true."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "initialize"}],
        )
        caps = results[0]["result"]["capabilities"]
        self.assertTrue(caps.get("permissions"))

    def test_initialize_does_not_declare_fs(self):
        """initialize must NOT declare any fs/* capability."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "initialize"}],
        )
        caps = results[0]["result"]["capabilities"]
        for key in caps:
            self.assertFalse(key.startswith("fs/"), f"fs/* capability declared: {key}")

    def test_initialize_does_not_declare_terminal(self):
        """initialize must NOT declare any terminal/* capability."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "initialize"}],
        )
        caps = results[0]["result"]["capabilities"]
        for key in caps:
            self.assertFalse(key.startswith("terminal/"), f"terminal/* capability declared: {key}")


# ---------------------------------------------------------------------------
# session/new
# ---------------------------------------------------------------------------


class TestSessionNew(unittest.TestCase):
    """Tests for the ``session/new`` protocol method."""

    def test_session_new_returns_session_id(self):
        """session/new must respond with a non-empty sessionId."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "session/new"}],
        )
        self.assertEqual(len(results), 1)
        session_id = results[0]["result"]["sessionId"]
        self.assertTrue(session_id, "sessionId must be non-empty")


# ---------------------------------------------------------------------------
# session/prompt
# ---------------------------------------------------------------------------


class TestSessionPrompt(unittest.TestCase):
    """Tests for the ``session/prompt`` protocol method."""

    def test_session_prompt_emits_agent_message_chunk_notifications(self):
        """session/prompt must emit agent_message_chunk notifications for streaming deltas."""
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "session/new"},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "session/prompt",
                "params": {
                    "sessionId": "__placeholder__",
                    "prompt": [{"type": "text", "text": "Hello"}],
                },
            },
        ]
        # We need the real session ID from session/new.  Run step by step.
        stdout = io.StringIO()
        stdin = _FakeStdin([json.dumps(m) for m in messages])
        server = ACPServer(
            provider_factory=lambda: _make_provider_with_text("Hello world"),
            stdin=stdin,
            stdout=stdout,
        )

        async def _run():
            # Manually drive the server for each message
            for raw in messages:
                req = raw
                method = req.get("method")
                if method == "session/new":
                    server.handle_session_new(req)
                elif method == "session/prompt":
                    # Patch the sessionId with the one from session/new
                    session_id = list(server._sessions.keys())[0]
                    req["params"]["sessionId"] = session_id
                    await server.handle_session_prompt(req)

        asyncio.run(_run())
        output = stdout.getvalue()
        parsed = [json.loads(l) for l in output.strip().split("\n") if l.strip()]

        # Find agent_message_chunk notifications
        chunks = [
            n for n in parsed
            if n.get("method") == "session/update"
            and n.get("params", {}).get("update", {}).get("type") == "agent_message_chunk"
        ]
        self.assertTrue(len(chunks) > 0, "Must emit at least one agent_message_chunk")

    def test_session_prompt_emits_agent_message_final(self):
        """session/prompt must emit a final agent_message notification."""
        stdout = io.StringIO()
        stdin = _FakeStdin([])
        server = ACPServer(
            provider_factory=lambda: _make_provider_with_text("Final answer"),
            stdin=stdin,
            stdout=stdout,
        )

        async def _run():
            server.handle_session_new({"jsonrpc": "2.0", "id": 1, "method": "session/new"})
            session_id = list(server._sessions.keys())[0]
            await server.handle_session_prompt({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "session/prompt",
                "params": {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": "Hello"}],
                },
            })

        asyncio.run(_run())
        output = stdout.getvalue()
        parsed = [json.loads(l) for l in output.strip().split("\n") if l.strip()]

        final_msgs = [
            n for n in parsed
            if n.get("method") == "session/update"
            and n.get("params", {}).get("update", {}).get("type") == "agent_message"
        ]
        self.assertTrue(len(final_msgs) >= 1, "Must emit at least one agent_message")
        self.assertEqual(final_msgs[-1]["params"]["update"]["content"], "Final answer")

    def test_session_prompt_responds_with_empty_result(self):
        """session/prompt must respond with an empty result dict after streaming."""
        stdout = io.StringIO()
        stdin = _FakeStdin([])
        server = ACPServer(
            provider_factory=lambda: _make_provider_with_text("test"),
            stdin=stdin,
            stdout=stdout,
        )

        async def _run():
            server.handle_session_new({"jsonrpc": "2.0", "id": 1, "method": "session/new"})
            session_id = list(server._sessions.keys())[0]
            await server.handle_session_prompt({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "session/prompt",
                "params": {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": "Hello"}],
                },
            })

        asyncio.run(_run())
        output = stdout.getvalue()
        parsed = [json.loads(l) for l in output.strip().split("\n") if l.strip()]

        # The last message should be the response with id=2 and empty result
        responses = [n for n in parsed if "id" in n and "method" not in n]
        self.assertTrue(len(responses) >= 1)
        # The response for session/prompt (id=2) should have empty result
        prompt_response = [r for r in responses if r["id"] == 2]
        self.assertEqual(len(prompt_response), 1)
        self.assertEqual(prompt_response[0]["result"], {})


# ---------------------------------------------------------------------------
# session/cancel and session/close
# ---------------------------------------------------------------------------


class TestSessionCancelClose(unittest.TestCase):
    """Tests for session/cancel and session/close."""

    def test_session_cancel_responds(self):
        """session/cancel must respond with an empty result."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "session/cancel", "params": {"sessionId": "x"}}],
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["result"], {})

    def test_session_close_responds(self):
        """session/close must respond with an empty result."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "session/close", "params": {"sessionId": "x"}}],
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["result"], {})


# ---------------------------------------------------------------------------
# Unknown method
# ---------------------------------------------------------------------------


class TestUnknownMethod(unittest.TestCase):
    """Tests for unknown method handling."""

    def test_unknown_method_returns_method_not_found_error(self):
        """Unknown methods must return a -32601 method-not-found error."""
        results = _run_server(
            _make_provider_with_text("hello"),
            [{"jsonrpc": "2.0", "id": 1, "method": "unknown/method"}],
        )
        self.assertEqual(len(results), 1)
        self.assertIn("error", results[0])
        self.assertEqual(results[0]["error"]["code"], -32601)


# ---------------------------------------------------------------------------
# --check flag
# ---------------------------------------------------------------------------


class TestCheckFlag(unittest.TestCase):
    """Tests for the ``--check`` flag."""

    def test_check_flag_exits_zero_when_ok(self):
        """--check must exit 0 when the provider factory succeeds."""
        def good_factory():
            return _make_provider_with_text("test")

        exit_code = run_check(good_factory)
        self.assertEqual(exit_code, 0)

    def test_check_flag_exits_nonzero_when_provider_unavailable(self):
        """--check must exit non-zero when the provider factory raises."""
        def bad_factory():
            raise RuntimeError("No API key configured")

        exit_code = run_check(bad_factory)
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(exit_code, 1)


# ---------------------------------------------------------------------------
# Reverse event mapping
# ---------------------------------------------------------------------------


class TestReverseEventMapping(unittest.TestCase):
    """Tests for RunEvent → ACP session/update reverse mapping."""

    def test_reverse_event_mapping_message_delta(self):
        """message.delta → agent_message_chunk with content and messageId."""
        event = _make_event(
            RunEventType.MESSAGE_DELTA_V3.value,
            {"delta": "Hello", "message_id": "msg-1"},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNotNone(update)
        self.assertEqual(update["type"], "agent_message_chunk")
        self.assertEqual(update["content"], "Hello")
        self.assertEqual(update["messageId"], "msg-1")

    def test_reverse_event_mapping_message_completed(self):
        """message.completed → agent_message with content and messageId."""
        event = _make_event(
            RunEventType.MESSAGE_COMPLETED.value,
            {"content": "Final answer", "message_id": "msg-1"},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNotNone(update)
        self.assertEqual(update["type"], "agent_message")
        self.assertEqual(update["content"], "Final answer")
        self.assertEqual(update["messageId"], "msg-1")

    def test_reverse_event_mapping_thought_delta(self):
        """thought.delta → agent_thought_chunk with content."""
        event = _make_event(
            RunEventType.THOUGHT_DELTA.value,
            {"delta": "Thinking..."},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNotNone(update)
        self.assertEqual(update["type"], "agent_thought_chunk")
        self.assertEqual(update["content"], "Thinking...")

    def test_reverse_event_mapping_tool_call_started(self):
        """tool_call.started → tool_call_update with status=started."""
        event = _make_event(
            RunEventType.TOOL_CALL_STARTED_V3.value,
            {"tool_call_id": "tc-1", "tool_name": "legal_search"},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNotNone(update)
        self.assertEqual(update["type"], "tool_call_update")
        self.assertEqual(update["toolCallId"], "tc-1")
        self.assertEqual(update["toolName"], "legal_search")
        self.assertEqual(update["status"], "started")

    def test_reverse_event_mapping_tool_call_delta(self):
        """tool_call.delta → tool_call_update with content."""
        event = _make_event(
            RunEventType.TOOL_CALL_DELTA.value,
            {"tool_call_id": "tc-1", "content": "executing..."},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNotNone(update)
        self.assertEqual(update["type"], "tool_call_update")
        self.assertEqual(update["toolCallId"], "tc-1")
        self.assertEqual(update["content"], "executing...")

    def test_reverse_event_mapping_tool_call_completed(self):
        """tool_call.completed → tool_call_update with status=completed."""
        event = _make_event(
            RunEventType.TOOL_CALL_COMPLETED_V3.value,
            {"tool_call_id": "tc-1", "status": "succeeded", "content": "result text"},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNotNone(update)
        self.assertEqual(update["type"], "tool_call_update")
        self.assertEqual(update["toolCallId"], "tc-1")
        self.assertEqual(update["status"], "completed")
        self.assertEqual(update["content"], "result text")

    def test_reverse_event_mapping_plan_updated(self):
        """plan.updated → plan with plan list."""
        event = _make_event(
            RunEventType.PLAN_UPDATED.value,
            {"plan": [{"step": "search"}]},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNotNone(update)
        self.assertEqual(update["type"], "plan")
        self.assertEqual(update["plan"], [{"step": "search"}])

    def test_reverse_event_mapping_phase_changed(self):
        """phase.changed → plan (folded) with phase info."""
        event = _make_event(
            RunEventType.PHASE_CHANGED.value,
            {"phase": "drafting", "previous_phase": "research"},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNotNone(update)
        self.assertEqual(update["type"], "plan")
        self.assertEqual(update["plan"], [{"phase": "drafting"}])

    def test_reverse_event_mapping_error(self):
        """error → error with message."""
        event = _make_event(
            RunEventType.ERROR.value,
            {"error": {"category": "runtime_error", "code": "test", "message": "Something broke"}},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNotNone(update)
        self.assertEqual(update["type"], "error")
        self.assertEqual(update["message"], "Something broke")

    def test_reverse_event_mapping_run_state_changed_returns_none(self):
        """run.state_changed should not be forwarded as session/update."""
        event = _make_event(
            RunEventType.RUN_STATE_CHANGED.value,
            {"status": "succeeded"},
        )
        update = map_run_event_to_acp_update(event)
        self.assertIsNone(update)


# ---------------------------------------------------------------------------
# Elicitation and permission request mapping
# ---------------------------------------------------------------------------


class TestElicitationPermissionMapping(unittest.TestCase):
    """Tests for elicitation and permission request forwarding."""

    def test_elicitation_create_sent_when_turn_loop_requests(self):
        """elicitation.requested → elicitation/create JSON-RPC request."""
        event = _make_event(
            RunEventType.ELICITATION_REQUESTED.value,
            {
                "interrupt_id": "int-1",
                "intro": "Please answer",
                "questions": [{"id": "q1", "question": "Who?"}],
            },
        )
        request = map_run_event_to_acp_request(event, req_id=10)
        self.assertIsNotNone(request)
        self.assertEqual(request["jsonrpc"], "2.0")
        self.assertEqual(request["id"], 10)
        self.assertEqual(request["method"], "elicitation/create")
        self.assertEqual(request["params"]["id"], "int-1")
        self.assertEqual(request["params"]["intro"], "Please answer")

    def test_permission_request_sent_when_turn_loop_requests(self):
        """permission.requested → session/request_permission JSON-RPC request."""
        event = _make_event(
            RunEventType.PERMISSION_REQUESTED.value,
            {
                "permission_id": "perm-1",
                "tool_call_id": "tc-1",
                "description": "Run shell command",
                "kind": "terminal",
            },
        )
        request = map_run_event_to_acp_request(event, req_id=20)
        self.assertIsNotNone(request)
        self.assertEqual(request["jsonrpc"], "2.0")
        self.assertEqual(request["id"], 20)
        self.assertEqual(request["method"], "session/request_permission")
        self.assertEqual(request["params"]["id"], "perm-1")
        self.assertEqual(request["params"]["tool_call_id"], "tc-1")
        self.assertEqual(request["params"]["kind"], "terminal")

    def test_dangerous_permission_never_auto_approved(self):
        """Dangerous permission requests must NOT include auto_approve or default_decision."""
        for kind in ("terminal", "execute_code"):
            event = _make_event(
                RunEventType.PERMISSION_REQUESTED.value,
                {
                    "permission_id": "perm-1",
                    "tool_call_id": "tc-1",
                    "description": "dangerous",
                    "kind": kind,
                },
            )
            request = map_run_event_to_acp_request(event, req_id=30)
            self.assertIsNotNone(request)
            params = request["params"]
            # CRITICAL: must never include auto_approve or default_decision
            self.assertNotIn("auto_approve", params, f"auto_approve present for {kind}")
            self.assertNotIn("default_decision", params, f"default_decision present for {kind}")

    def test_non_elicitation_event_returns_none_from_request_mapping(self):
        """Non-elicitation/permission events should return None from request mapping."""
        event = _make_event(
            RunEventType.MESSAGE_DELTA_V3.value,
            {"delta": "hello"},
        )
        request = map_run_event_to_acp_request(event, req_id=40)
        self.assertIsNone(request)


# ---------------------------------------------------------------------------
# Full ACP round-trip with FixtureProvider
# ---------------------------------------------------------------------------


class TestFullRoundTrip(unittest.TestCase):
    """Full round-trip: initialize → session/new → session/prompt."""

    def test_full_acp_round_trip_with_fixture_provider(self):
        """A complete ACP round-trip produces chunks + final message + response."""
        provider = FixtureProvider([
            TurnScript(deltas=[
                ContentDelta(content="Hello "),
                ContentDelta(content="world"),
                FinishDelta(finish_reason="stop"),
            ]),
        ])

        stdout = io.StringIO()
        stdin = _FakeStdin([])
        server = ACPServer(
            provider_factory=lambda: provider,
            stdin=stdin,
            stdout=stdout,
        )

        async def _run():
            # initialize
            server.handle_initialize({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
            # session/new
            server.handle_session_new({"jsonrpc": "2.0", "id": 2, "method": "session/new"})
            session_id = list(server._sessions.keys())[0]
            # session/prompt
            await server.handle_session_prompt({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "session/prompt",
                "params": {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": "Say hello"}],
                },
            })

        asyncio.run(_run())
        output = stdout.getvalue()
        parsed = [json.loads(l) for l in output.strip().split("\n") if l.strip()]

        # 1. initialize response
        init_resp = [r for r in parsed if r.get("id") == 1]
        self.assertEqual(len(init_resp), 1)
        self.assertEqual(init_resp[0]["result"]["protocolVersion"], 1)

        # 2. session/new response
        new_resp = [r for r in parsed if r.get("id") == 2]
        self.assertEqual(len(new_resp), 1)
        self.assertTrue(new_resp[0]["result"]["sessionId"])

        # 3. session/update notifications
        updates = [n for n in parsed if n.get("method") == "session/update"]
        chunk_types = [u["params"]["update"]["type"] for u in updates]
        self.assertIn("agent_message_chunk", chunk_types)
        self.assertIn("agent_message", chunk_types)

        # 4. session/prompt response (empty result)
        prompt_resp = [r for r in parsed if r.get("id") == 3]
        self.assertEqual(len(prompt_resp), 1)
        self.assertEqual(prompt_resp[0]["result"], {})


# ---------------------------------------------------------------------------
# Integration: ACPClient driving the agent-core ACP server
# ---------------------------------------------------------------------------


class TestACPClientIntegration(unittest.TestCase):
    """Integration test: use ACPClient from acp-client to drive the server.

    This test is skipped when ``inkstatute_acp_client`` is not importable
    (e.g. when the V2 gate runner does not include ``acp-client/src`` in
    the PYTHONPATH).  When run with the full PYTHONPATH (including
    ``packages/acp-client/src``), the test executes the full ACP
    round-trip via subprocess.
    """

    def test_acp_server_can_be_driven_by_acp_client(self):
        """ACPClient can initialize, create session, and prompt the agent-core ACP server."""
        # Skip if inkstatute_acp_client is not importable
        try:
            from inkstatute_acp_client.client import ACPClient, StdioACPTransport
            from inkstatute_acp_client.capability_negotiation import RequiredCapabilities
        except ImportError:
            self.skipTest("inkstatute_acp_client not available on PYTHONPATH")

        # Build the PYTHONPATH for the subprocess
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        src_paths = [
            os.path.join(repo_root, "packages", "agent-core", "src"),
            os.path.join(repo_root, "packages", "platform-contract", "src"),
            os.path.join(repo_root, "packages", "platform-runtime", "src"),
            os.path.join(repo_root, "packages", "model-gateway", "src"),
            os.path.join(repo_root, "packages", "acp-client", "src"),
        ]
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(src_paths + [env.get("PYTHONPATH", "")])

        # Use a fixture provider via env var so the subprocess can create it
        # We'll use a small inline script that creates the server with a fixture
        script = (
            "import sys; "
            "from inkstatute_agent_core.acp_server import ACPServer; "
            "from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript; "
            "from inkstatute_agent_core.model.provider import ContentDelta, FinishDelta; "
            "provider = FixtureProvider([TurnScript(deltas=["
            "ContentDelta(content='Integration test response'), "
            "FinishDelta(finish_reason='stop')])]); "
            "ACPServer(provider_factory=lambda: provider).run_sync()"
        )

        command = (sys.executable, "-c", script)

        async def _run():
            transport = StdioACPTransport()
            client = ACPClient(
                transport,
                RequiredCapabilities(streaming=True),
            )
            try:
                await transport.start(command, env=env)
                # initialize
                result = await client.initialize()
                self.assertEqual(result.protocol_version, 1)
                self.assertEqual(result.agent_name, "inkstatute-agent")

                # session/new
                session_id = await client.new_session()
                self.assertTrue(session_id)

                # session/prompt
                await client.prompt(session_id, "Hello")

                # stream updates
                events = []
                async for event in client.stream_updates(session_id, timeout=10.0):
                    events.append(event)
                    if event.event_type == "message.completed":
                        break

                # Should have at least one message.completed
                completed = [e for e in events if e.event_type == "message.completed"]
                self.assertTrue(len(completed) >= 1, "Must receive message.completed")
                self.assertEqual(completed[0].payload["content"], "Integration test response")

                # close session
                await client.close_session(session_id)
            finally:
                await client.shutdown()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


class TestCLIEntryPoint(unittest.TestCase):
    """Tests for the CLI entry point (argparse)."""

    def test_cli_version_flag(self):
        """--version should print the version and exit 0."""
        try:
            cli_main(["--version"])
        except SystemExit as e:
            self.assertEqual(e.code, 0)

    def test_cli_no_subcommand_prints_help(self):
        """No subcommand should print help and return 0."""
        result = cli_main([])
        self.assertEqual(result, 0)

    def test_cli_acp_check_with_no_provider(self):
        """acp --check with no provider env should exit non-zero."""
        # Ensure no provider is configured
        env_backup = os.environ.pop("INKSTATUTE_MODEL_PROVIDER", None)
        try:
            result = cli_main(["acp", "--check"])
            self.assertNotEqual(result, 0)
        finally:
            if env_backup is not None:
                os.environ["INKSTATUTE_MODEL_PROVIDER"] = env_backup


if __name__ == "__main__":
    unittest.main()
