"""MCP Client — JSON-RPC 2.0 over stdio for MCP connector subprocesses.

Implements the Model Context Protocol (MCP) for communicating with
Node.js connector subprocesses (e.g., ``law-database``, ``wenshu``).

Protocol contract (matches ``connectors/_lib/rpc.js``):
- One JSON object per line on stdin, exactly one JSON object per line on stdout
- ``initialize`` → ``{protocolVersion, capabilities, serverInfo}``
- ``notifications/initialized`` → no response (notification, no id)
- ``tools/list`` → ``{tools: [{name, description, inputSchema}]}``
- ``tools/call`` → ``{content: [{type: "text", text}], isError: false}``
- Unknown method with id → error ``{code: -32601, message: "method not found"}``

The connector path is **configured at construction time** (not
user-supplied) — this is a controlled subprocess, not arbitrary shell
execution.  The MCP client spawns a specific Node.js script with
stdio JSON-RPC, matching the Phase 90 security defaults.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

JsonObject = dict[str, Any]

# MCP protocol version (standard, matching connectors/_lib/rpc.js).
MCP_PROTOCOL_VERSION = "2024-11-05"


class McpError(Exception):
    """Raised when an MCP tool call returns ``isError=true`` or a JSON-RPC error."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Schema conversion utilities
# ---------------------------------------------------------------------------


def mcp_input_schema_to_openai_parameters(input_schema: dict) -> dict:
    """Convert MCP ``inputSchema`` to OpenAI ``parameters`` format.

    Both formats use JSON Schema ``{"type": "object", "properties": ...,
    "required": ...}``.  This is a direct passthrough — the conversion
    is a no-op because MCP and OpenAI use the same schema format for
    tool parameters.

    Args:
        input_schema: The MCP tool's ``inputSchema`` dict.

    Returns:
        The same schema dict, suitable for the OpenAI ``parameters`` field.
    """
    return dict(input_schema)


def mcp_tool_to_openai_definition(tool: dict) -> dict:
    """Wrap an MCP tool descriptor into OpenAI function-calling format.

    Converts ``{name, description, inputSchema}`` (MCP format) to
    ``{"type": "function", "function": {"name": ..., "description": ...,
    "parameters": ...}}`` (OpenAI format).

    Args:
        tool: MCP tool descriptor with ``name``, ``description``, ``inputSchema``.

    Returns:
        OpenAI function-calling tool definition dict.
    """
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": mcp_input_schema_to_openai_parameters(
                tool.get("inputSchema", {"type": "object", "properties": {}})
            ),
        },
    }


# ---------------------------------------------------------------------------
# McpClient — JSON-RPC 2.0 over stdio
# ---------------------------------------------------------------------------


class McpClient:
    """MCP client that communicates with a Node.js connector over stdio.

    The connector path is configured at construction time — this is a
    **controlled subprocess**, not arbitrary shell execution.  The client
    spawns ``node <connector_path>`` with stdin/stdout pipes for
    line-delimited JSON-RPC 2.0 communication.

    Lifecycle:
    1. ``start()`` — spawns the subprocess, performs ``initialize``
       handshake (protocol version "2024-11-05"), sends
       ``notifications/initialized``.
    2. ``list_tools()`` — calls ``tools/list`` and returns tool descriptors.
    3. ``call_tool(name, arguments)`` — calls ``tools/call`` and returns
       the text content.
    4. ``close()`` — terminates the subprocess.

    Also supports async context manager: ``async with McpClient(...) as client:``.
    """

    def __init__(
        self,
        connector_path: str,
        env: dict[str, str] | None = None,
        timeout: float = 40.0,
    ) -> None:
        """Initialize the MCP client.

        Args:
            connector_path: Path to the Node.js connector script (e.g.,
                ``/path/to/law-database/index.js``).  This is a configured
                path, not user-supplied.
            env: Optional environment variables for the subprocess.
            timeout: Default timeout for JSON-RPC requests in seconds
                (default 40.0, matching the law-database connector budget).
        """
        self._connector_path = connector_path
        self._env = env
        self._timeout = timeout
        self._process: asyncio.subprocess.Process | None = None
        self._next_id: int = 1
        self._response_queue: asyncio.Queue[dict] | None = None
        self._reader_task: asyncio.Task | None = None
        self._started = False

    async def start(self) -> None:
        """Spawn the Node.js connector and perform the MCP handshake.

        1. Spawns ``node <connector_path>`` with stdin/stdout/stderr pipes.
        2. Starts a background reader task that reads stdout line by line
           and puts responses into an ``asyncio.Queue``.
        3. Sends ``initialize`` request and waits for the response.
        4. Sends ``notifications/initialized`` notification (no response expected).
        """
        self._process = await asyncio.create_subprocess_exec(
            "node",
            self._connector_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        self._response_queue = asyncio.Queue()
        self._reader_task = asyncio.create_task(self._read_loop())
        self._started = True

        # Perform initialize handshake
        result = await self._request("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "inkstatute-agent-core", "version": "1.0.0"},
        })

        # Send notifications/initialized (no id, no response expected)
        self._notify("notifications/initialized", {})

    async def _read_loop(self) -> None:
        """Background task: read stdout line by line and queue responses.

        Each line is a JSON object.  Responses (with ``id``) are put into
        the response queue.  Notifications (without ``id``) are ignored
        (MCP connectors don't send notifications to the client in the
        current protocol).
        """
        assert self._process is not None
        assert self._process.stdout is not None
        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                try:
                    msg = json.loads(line_str)
                except json.JSONDecodeError:
                    continue  # Ignore parse errors (matching rpc.js behavior)
                if "id" in msg:
                    await self._response_queue.put(msg)
        except asyncio.CancelledError:
            pass

    def _send(self, msg: dict) -> None:
        """Send a JSON-RPC message to the connector's stdin."""
        assert self._process is not None
        assert self._process.stdin is not None
        data = (json.dumps(msg) + "\n").encode("utf-8")
        self._process.stdin.write(data)

    def _notify(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    async def _request(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and wait for the response.

        Args:
            method: The JSON-RPC method name.
            params: The parameters dict.

        Returns:
            The ``result`` field from the response.

        Raises:
            McpError: If the response contains an ``error`` field.
            asyncio.TimeoutError: If the response is not received within
                the timeout.
        """
        assert self._response_queue is not None
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})

        # Wait for the matching response
        while True:
            try:
                msg = await asyncio.wait_for(
                    self._response_queue.get(),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                raise asyncio.TimeoutError(
                    f"MCP request timed out after {self._timeout}s: {method}"
                )

            if msg.get("id") == request_id:
                if "error" in msg:
                    err = msg["error"]
                    raise McpError(
                        err.get("message", "unknown error"),
                        err.get("code"),
                    )
                return msg.get("result", {})

    async def list_tools(self) -> list[dict]:
        """Call ``tools/list`` and return the list of tool descriptors.

        Returns:
            List of tool descriptor dicts, each with ``name``,
            ``description``, and ``inputSchema``.
        """
        result = await self._request("tools/list", {})
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call ``tools/call`` and return the text content.

        Args:
            name: The tool name (e.g., ``"search_laws"``).
            arguments: The arguments dict to pass to the tool.

        Returns:
            The text content from the response.

        Raises:
            McpError: If the response has ``isError=true`` or contains
                an error.
        """
        result = await self._request("tools/call", {"name": name, "arguments": arguments})

        # Check isError flag
        if result.get("isError", False):
            # Extract error text from content
            content = result.get("content", [])
            error_text = ""
            for item in content:
                if item.get("type") == "text":
                    error_text = item.get("text", "")
                    break
            raise McpError(error_text or "tool call returned isError=true")

        # Extract text content
        content = result.get("content", [])
        for item in content:
            if item.get("type") == "text":
                return item.get("text", "")

        return ""

    async def close(self) -> None:
        """Terminate the subprocess and clean up.

        Cancels the reader task, terminates the process, and waits for
        it to exit.
        """
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._process is not None:
            if self._process.stdin is not None:
                self._process.stdin.close()
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass
            self._process = None

        self._started = False

    async def __aenter__(self) -> McpClient:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


__all__ = [
    "McpClient",
    "McpError",
    "MCP_PROTOCOL_VERSION",
    "mcp_input_schema_to_openai_parameters",
    "mcp_tool_to_openai_definition",
]
