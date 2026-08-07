"""Integration tests for ACPClient with the echo agent fixture."""

from __future__ import annotations

import asyncio
import os
import unittest
from pathlib import Path

from inkstatute_acp_client.capability_negotiation import (
    CapabilityMismatchError,
    RequiredCapabilities,
)
from inkstatute_acp_client.client import ACPClient, StdioACPTransport

ECHO_AGENT = str(Path(__file__).resolve().parent / "fixtures" / "echo_agent.py")


class TestACPClient(unittest.IsolatedAsyncioTestCase):
    """Tests using the in-repo echo agent fixture — no network, no external agents."""

    transport: StdioACPTransport | None = None

    def _make_transport(self, capabilities: dict | None = None) -> StdioACPTransport:
        """Create a transport with optional custom capabilities env."""
        env: dict[str, str] = {}
        if capabilities is not None:
            import json
            env["ECHO_AGENT_CAPABILITIES"] = json.dumps(capabilities)
        transport = StdioACPTransport()
        # We need to pass env to start() — but start() takes env param
        # Store for use in async setup
        transport._test_env = env  # type: ignore[attr-defined]
        return transport

    async def _start_transport(self, transport: StdioACPTransport) -> None:
        env = getattr(transport, "_test_env", None)
        await transport.start(("python", ECHO_AGENT), env=env)

    async def asyncTearDown(self) -> None:
        if self.transport is not None:
            try:
                await self.transport.close()
            except Exception:
                pass
            self.transport = None

    async def test_initialize_success(self) -> None:
        """Spawn echo agent, call initialize(), assert protocol_version == 1 and agent_name == 'echo'."""
        self.transport = self._make_transport()
        await self._start_transport(self.transport)
        client = ACPClient(self.transport, RequiredCapabilities(streaming=True))
        result = await client.initialize()
        self.assertEqual(result.protocol_version, 1)
        self.assertEqual(result.agent_name, "echo")

    async def test_initialize_capability_mismatch(self) -> None:
        """Spawn echo agent with streaming=false, assert CapabilityMismatchError and transport closed."""
        self.transport = self._make_transport(
            capabilities={"streaming": False, "elicitation": False, "permissions": False}
        )
        await self._start_transport(self.transport)
        client = ACPClient(self.transport, RequiredCapabilities(streaming=True))
        with self.assertRaises(CapabilityMismatchError):
            await client.initialize()
        # Transport should be closed after mismatch
        self.assertIsNone(self.transport._process)
        self.transport = None  # Already closed

    async def test_new_session_returns_id(self) -> None:
        """After initialize, call new_session(), assert non-empty string."""
        self.transport = self._make_transport()
        await self._start_transport(self.transport)
        client = ACPClient(self.transport, RequiredCapabilities(streaming=True))
        await client.initialize()
        session_id = await client.new_session()
        self.assertTrue(session_id)
        self.assertIsInstance(session_id, str)

    async def test_prompt_streams_message_delta(self) -> None:
        """After initialize and new_session, prompt + stream_updates yields message.delta."""
        self.transport = self._make_transport()
        await self._start_transport(self.transport)
        client = ACPClient(self.transport, RequiredCapabilities(streaming=True))
        await client.initialize()
        session_id = await client.new_session()
        await client.prompt(session_id, "hello")
        events = []
        async for event in client.stream_updates(session_id, run_id="test-run", timeout=10.0):
            events.append(event)
        delta_events = [e for e in events if e.event_type == "message.delta"]
        self.assertGreaterEqual(len(delta_events), 1)

    async def test_prompt_streams_message_completed(self) -> None:
        """After initialize and new_session, prompt + stream_updates yields message.completed."""
        self.transport = self._make_transport()
        await self._start_transport(self.transport)
        client = ACPClient(self.transport, RequiredCapabilities(streaming=True))
        await client.initialize()
        session_id = await client.new_session()
        await client.prompt(session_id, "hello world")
        events = []
        async for event in client.stream_updates(session_id, run_id="test-run", timeout=10.0):
            events.append(event)
        completed_events = [e for e in events if e.event_type == "message.completed"]
        self.assertGreaterEqual(len(completed_events), 1)

    async def test_cancel_session(self) -> None:
        """Call cancel(session_id), assert no exception."""
        self.transport = self._make_transport()
        await self._start_transport(self.transport)
        client = ACPClient(self.transport, RequiredCapabilities(streaming=True))
        await client.initialize()
        session_id = await client.new_session()
        await client.cancel(session_id)

    async def test_close_session(self) -> None:
        """Call close_session(session_id), assert no exception."""
        self.transport = self._make_transport()
        await self._start_transport(self.transport)
        client = ACPClient(self.transport, RequiredCapabilities(streaming=True))
        await client.initialize()
        session_id = await client.new_session()
        await client.close_session(session_id)

    async def test_shutdown_terminates_subprocess(self) -> None:
        """Record transport.pid, call shutdown(), assert pid no longer exists after 2 seconds."""
        self.transport = self._make_transport()
        await self._start_transport(self.transport)
        client = ACPClient(self.transport, RequiredCapabilities(streaming=True))
        await client.initialize()
        pid = self.transport.pid
        self.assertIsNotNone(pid)
        await client.shutdown()
        # Wait for process to terminate
        await asyncio.sleep(2)
        try:
            os.kill(pid, 0)  # type: ignore[arg-type]
            self.fail(f"Process {pid} still exists after shutdown")
        except ProcessLookupError:
            pass  # Expected — process is gone
        self.transport = None  # Already closed by shutdown


if __name__ == "__main__":
    unittest.main()
