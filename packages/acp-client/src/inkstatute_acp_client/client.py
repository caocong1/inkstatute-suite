"""ACP stdio client — initialize, session lifecycle, and streaming.

Provides :class:`ACPClient` that speaks ACP v1 over stdio using
:class:`StdioACPTransport`.  The client locks protocol v1 at
``initialize``, negotiates capabilities, and streams
``session/update`` notifications as unified :class:`RunEvent` objects.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, AsyncIterator, Protocol

from platform_runtime.protocols import RunEvent

from .capability_negotiation import (
    CapabilityMismatchError,
    CapabilityNegotiationResult,
    RequiredCapabilities,
    negotiate,
)
from .event_mapping import map_acp_update_to_run_event

logger = logging.getLogger(__name__)

JsonObject = dict[str, Any]


# ---------------------------------------------------------------------------
# Transport Protocol
# ---------------------------------------------------------------------------


class ACPTransport(Protocol):
    """Transport abstraction for ACP stdio communication."""

    async def start(
        self,
        command: tuple[str, ...],
        env: dict[str, str] | None = None,
    ) -> None: ...

    async def send(self, message: dict) -> None: ...

    async def receive(self) -> dict: ...

    async def receive_notification(self) -> dict | None: ...

    async def close(self) -> None: ...

    @property
    def pid(self) -> int | None: ...


# ---------------------------------------------------------------------------
# Stdio transport implementation
# ---------------------------------------------------------------------------


class StdioACPTransport:
    """Stdio-based ACP transport using :mod:`asyncio.subprocess`.

    Spawns a child process, sends JSON-RPC messages as newline-delimited
    JSON on stdin, and reads responses/notifications from stdout.
    """

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._notification_buffer: list[dict] = []
        self._response_buffer: list[dict] = []

    async def start(
        self,
        command: tuple[str, ...],
        env: dict[str, str] | None = None,
    ) -> None:
        """Spawn the ACP agent subprocess."""
        import os

        proc_env = dict(os.environ)
        if env:
            proc_env.update(env)

        self._process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=proc_env,
        )
        logger.debug("ACP subprocess started: pid=%d, command=%s", self._process.pid, command)

    async def send(self, message: dict) -> None:
        """Send a JSON-RPC message as newline-delimited JSON on stdin."""
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Transport not started or stdin closed")
        line = json.dumps(message) + "\n"
        self._process.stdin.write(line.encode("utf-8"))
        await self._process.stdin.drain()

    async def receive(self) -> dict:
        """Read a JSON-RPC response (has ``id``) from stdout.

        Skips notifications (messages without ``id``) until a response
        is found.  Notifications are buffered for later retrieval via
        :meth:`receive_notification`.
        """
        while True:
            msg = await self._read_line()
            if msg is None:
                raise RuntimeError("ACP subprocess stdout closed")
            if "id" in msg and "method" not in msg:
                # This is a response (has id, no method)
                return msg
            # It's a notification — buffer it
            self._notification_buffer.append(msg)

    async def receive_notification(self) -> dict | None:
        """Read a JSON-RPC notification (has ``method``, no ``id``) from stdout.

        Returns ``None`` if no notification is currently available.
        First checks the buffer (notifications read during :meth:`receive`).
        """
        if self._notification_buffer:
            return self._notification_buffer.pop(0)

        # Try to read a line with a very short timeout
        msg = await self._read_line_nonblocking()
        if msg is None:
            return None
        if "method" in msg:
            return msg
        # It's a response — buffer it for receive()
        self._response_buffer.append(msg)
        return None

    async def _read_line(self) -> dict | None:
        """Read and parse one line from stdout (blocking)."""
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("Transport not started or stdout closed")
        line_bytes = await self._process.stdout.readline()
        if not line_bytes:
            return None
        line = line_bytes.decode("utf-8").strip()
        if not line:
            return await self._read_line()
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Unparseable line from ACP stdout: %s", line[:200])
            return await self._read_line()

    async def _read_line_nonblocking(self) -> dict | None:
        """Try to read a line from stdout with a short timeout."""
        if self._process is None or self._process.stdout is None:
            return None
        try:
            line_bytes = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=0.05,
            )
        except asyncio.TimeoutError:
            return None
        if not line_bytes:
            return None
        line = line_bytes.decode("utf-8").strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    async def close(self) -> None:
        """Terminate and kill the subprocess."""
        if self._process is None:
            return
        proc = self._process
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        except ProcessLookupError:
            pass
        self._process = None

    @property
    def pid(self) -> int | None:
        if self._process is None:
            return None
        return self._process.pid



# ---------------------------------------------------------------------------
# ACP Client
# ---------------------------------------------------------------------------


class ACPClient:
    """ACP v1 client that drives an agent over stdio.

    Locks protocol v1 at ``initialize``, negotiates capabilities, and
    streams ``session/update`` notifications as unified :class:`RunEvent`
    objects.
    """

    def __init__(
        self,
        transport: ACPTransport,
        required_capabilities: RequiredCapabilities,
    ) -> None:
        self._transport = transport
        self._required_capabilities = required_capabilities
        self._next_id: int = 1
        self._negotiation_result: CapabilityNegotiationResult | None = None

    def _next_request_id(self) -> int:
        rid = self._next_id
        self._next_id += 1
        return rid

    def _make_request(self, method: str, params: dict | None = None) -> dict:
        req: dict = {"jsonrpc": "2.0", "id": self._next_request_id(), "method": method}
        if params is not None:
            req["params"] = params
        return req

    async def initialize(self) -> CapabilityNegotiationResult:
        """Send ``initialize`` and negotiate capabilities.

        Sends ``protocolVersion: 1`` and negotiates capabilities.  If
        the agent lacks required capabilities, closes the transport and
        raises :class:`CapabilityMismatchError`.
        """
        request = self._make_request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientInfo": {"name": "inkstatute-acp-client", "version": "0.1.0"},
            },
        )
        await self._transport.send(request)
        response = await self._transport.receive()

        result = response.get("result", response)
        try:
            self._negotiation_result = negotiate(result, self._required_capabilities)
        except CapabilityMismatchError:
            await self._transport.close()
            raise

        return self._negotiation_result

    async def new_session(
        self,
        cwd: str | None = None,
        mcp_servers: list | None = None,
    ) -> str:
        """Send ``session/new`` and return the session_id."""
        params: dict = {}
        if cwd is not None:
            params["cwd"] = cwd
        if mcp_servers is not None:
            params["mcpServers"] = mcp_servers

        request = self._make_request("session/new", params if params else None)
        await self._transport.send(request)
        response = await self._transport.receive()
        result = response.get("result", {})
        session_id = result.get("sessionId", "")
        return session_id

    async def prompt(self, session_id: str, content: str) -> str:
        """Send ``session/prompt`` and return the prompt request id.

        Does NOT wait for all updates — caller uses :meth:`stream_updates`
        to receive the streaming events.
        """
        request = self._make_request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": content}],
            },
        )
        prompt_id = request["id"]
        await self._transport.send(request)
        return str(prompt_id)

    async def stream_updates(
        self,
        session_id: str,
        run_id: str = "",
        timeout: float = 30.0,
    ) -> AsyncIterator[RunEvent]:
        """Async generator yielding :class:`RunEvent` from ACP notifications.

        Reads notifications from the transport, maps them to unified
        events via :func:`map_acp_update_to_run_event`, and yields them.
        Stops when a ``message.completed`` event is yielded (indicating
        the prompt response is complete) or when the timeout is reached.
        """
        if not run_id:
            run_id = session_id

        seq = 0
        deadline = asyncio.get_event_loop().time() + timeout
        got_completed = False

        while not got_completed:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break

            notification = await self._transport.receive_notification()
            if notification is None:
                # No data available — yield nothing, continue polling
                await asyncio.sleep(0.01)
                continue

            occurred_at = ""  # Will be set from notification if available
            seq += 1

            event = map_acp_update_to_run_event(notification, run_id, seq, occurred_at)
            if event is not None:
                yield event
                if event.event_type == "message.completed":
                    got_completed = True

    async def cancel(self, session_id: str) -> None:
        """Send ``session/cancel``."""
        request = self._make_request("session/cancel", {"sessionId": session_id})
        await self._transport.send(request)
        await self._transport.receive()

    async def close_session(self, session_id: str) -> None:
        """Send ``session/close``."""
        request = self._make_request("session/close", {"sessionId": session_id})
        await self._transport.send(request)
        await self._transport.receive()

    async def shutdown(self) -> None:
        """Close the transport (terminate subprocess)."""
        await self._transport.close()


__all__ = [
    "ACPClient",
    "ACPTransport",
    "StdioACPTransport",
]
