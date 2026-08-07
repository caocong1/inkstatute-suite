"""Tests for McpClient — JSON-RPC 2.0 over stdio with mock subprocess.

Tests the JSON-RPC protocol logic, request/response matching, error
handling, and schema conversion without requiring Node.js.  Uses a
fake subprocess that simulates the MCP connector's line-delimited
JSON-RPC protocol.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from inkstatute_agent_core.tools.mcp_client import (
    MCP_PROTOCOL_VERSION,
    McpClient,
    McpError,
    mcp_input_schema_to_openai_parameters,
    mcp_tool_to_openai_definition,
)


# ---------------------------------------------------------------------------
# Fake subprocess for testing — simulates a Node.js MCP connector
# ---------------------------------------------------------------------------


class FakeStdin:
    """Fake stdin that captures written data and can be closed."""

    def __init__(self) -> None:
        self.written: list[bytes] = []
        self._closed = False

    def write(self, data: bytes) -> None:
        if not self._closed:
            self.written.append(data)

    def close(self) -> None:
        self._closed = True


class FakeStdout:
    """Fake stdout that yields pre-loaded lines."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)
        self._index = 0

    async def readline(self) -> bytes:
        if self._index < len(self._lines):
            line = self._lines[self._index]
            self._index += 1
            return line
        return b""  # EOF


class FakeStderr:
    """Fake stderr (unused in tests but needed for the process interface)."""

    async def readline(self) -> bytes:
        return b""


class FakeProcess:
    """Fake asyncio subprocess for testing McpClient."""

    def __init__(self, responses: list[dict]) -> None:
        """Initialize with a list of response dicts to send.

        Each response is sent as a JSON line on stdout in order.
        """
        lines = [(json.dumps(r) + "\n").encode("utf-8") for r in responses]
        self.stdin = FakeStdin()
        self.stdout = FakeStdout(lines)
        self.stderr = FakeStderr()
        self.terminated = False
        self.killed = False
        self._wait_event = asyncio.Event()
        self._wait_event.set()  # Process is already "exited"

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        await self._wait_event.wait()
        return 0


def _make_initialize_response(req_id: int) -> dict:
    """Create a standard MCP initialize response."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "law-database", "version": "1.0.0"},
        },
    }


def _make_tools_list_response(req_id: int, tools: list[dict]) -> dict:
    """Create a tools/list response."""
    return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}


def _make_tools_call_response(
    req_id: int, text: str, is_error: bool = False
) -> dict:
    """Create a tools/call response."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        },
    }


def _make_error_response(req_id: int, code: int, message: str) -> dict:
    """Create a JSON-RPC error response."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


# ---------------------------------------------------------------------------
# Schema conversion tests
# ---------------------------------------------------------------------------


class TestSchemaConversion(unittest.TestCase):
    """Tests for MCP-to-OpenAI schema conversion functions."""

    def test_mcp_input_schema_to_openai_parameters_passthrough(self) -> None:
        """MCP inputSchema should pass through directly to OpenAI parameters."""
        input_schema = {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["keyword"],
        }
        result = mcp_input_schema_to_openai_parameters(input_schema)
        self.assertEqual(result["type"], "object")
        self.assertIn("keyword", result["properties"])
        self.assertIn("keyword", result["required"])

    def test_mcp_input_schema_returns_copy(self) -> None:
        """The conversion should return a copy, not the original dict."""
        input_schema = {"type": "object", "properties": {}}
        result = mcp_input_schema_to_openai_parameters(input_schema)
        result["type"] = "modified"
        self.assertEqual(input_schema["type"], "object")

    def test_mcp_tool_to_openai_definition(self) -> None:
        """An MCP tool descriptor should be wrapped in OpenAI function-calling format."""
        mcp_tool = {
            "name": "search_laws",
            "description": "根据关键词搜索法律法规",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                },
                "required": [],
            },
        }
        result = mcp_tool_to_openai_definition(mcp_tool)
        self.assertEqual(result["type"], "function")
        func = result["function"]
        self.assertEqual(func["name"], "search_laws")
        self.assertEqual(func["description"], "根据关键词搜索法律法规")
        self.assertIn("parameters", func)
        self.assertEqual(func["parameters"]["type"], "object")

    def test_mcp_tool_to_openai_definition_missing_description(self) -> None:
        """Missing description should default to empty string."""
        mcp_tool = {"name": "test_tool", "inputSchema": {"type": "object", "properties": {}}}
        result = mcp_tool_to_openai_definition(mcp_tool)
        self.assertEqual(result["function"]["description"], "")

    def test_mcp_tool_to_openai_definition_missing_input_schema(self) -> None:
        """Missing inputSchema should default to empty object schema."""
        mcp_tool = {"name": "test_tool", "description": "test"}
        result = mcp_tool_to_openai_definition(mcp_tool)
        params = result["function"]["parameters"]
        self.assertEqual(params["type"], "object")
        self.assertEqual(params["properties"], {})


# ---------------------------------------------------------------------------
# McpClient protocol tests (with fake subprocess)
# ---------------------------------------------------------------------------


class TestMcpClientProtocol(unittest.TestCase):
    """Tests for McpClient JSON-RPC protocol logic."""

    def _run(self, coro):
        """Run an async coroutine in a fresh event loop."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _create_client_with_fake(
        self, responses: list[dict]
    ) -> tuple[McpClient, FakeProcess]:
        """Create an McpClient with a fake subprocess.

        Returns the client and the fake process for inspection.
        """
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        # Patch asyncio.create_subprocess_exec
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            # We need to start the client within an event loop
            async def setup():
                await client.start()
                return fake_process

            loop = asyncio.new_event_loop()
            try:
                proc = loop.run_until_complete(setup())
            finally:
                # Don't close the loop yet — we need it for further operations
                pass

        return client, fake_process, loop

    def test_start_handshake(self) -> None:
        """start() should send initialize and notifications/initialized."""
        responses = [_make_initialize_response(1)]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                await client.start()

            # Check that initialize was sent
            sent_lines = [
                json.loads(line.decode("utf-8"))
                for line in fake_process.stdin.written
            ]
            # First message should be initialize
            self.assertEqual(sent_lines[0]["method"], "initialize")
            self.assertEqual(
                sent_lines[0]["params"]["protocolVersion"],
                MCP_PROTOCOL_VERSION,
            )
            # Second message should be notifications/initialized
            self.assertEqual(sent_lines[1]["method"], "notifications/initialized")
            self.assertNotIn("id", sent_lines[1])  # Notifications have no id

            await client.close()

        self._run(run_test())

    def test_list_tools(self) -> None:
        """list_tools() should return tool descriptors."""
        tools = [
            {
                "name": "search_laws",
                "description": "搜索法律法规",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_law_detail",
                "description": "获取法规详情",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
        responses = [
            _make_initialize_response(1),
            _make_tools_list_response(2, tools),
        ]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                await client.start()
                result_tools = await client.list_tools()

            self.assertEqual(len(result_tools), 2)
            self.assertEqual(result_tools[0]["name"], "search_laws")
            self.assertEqual(result_tools[1]["name"], "get_law_detail")

            await client.close()

        self._run(run_test())

    def test_call_tool_success(self) -> None:
        """call_tool() should return the text content on success."""
        responses = [
            _make_initialize_response(1),
            _make_tools_call_response(2, "Found 3 laws: ..."),
        ]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                await client.start()
                text = await client.call_tool("search_laws", {"keyword": "合同法"})

            self.assertEqual(text, "Found 3 laws: ...")

            await client.close()

        self._run(run_test())

    def test_call_tool_is_error_raises(self) -> None:
        """call_tool() should raise McpError when isError=true."""
        responses = [
            _make_initialize_response(1),
            _make_tools_call_response(2, "内部错误: network timeout", is_error=True),
        ]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                await client.start()
                with self.assertRaises(McpError) as ctx:
                    await client.call_tool("search_laws", {"keyword": "test"})
                self.assertIn("内部错误", str(ctx.exception))

            await client.close()

        self._run(run_test())

    def test_jsonrpc_error_response_raises(self) -> None:
        """A JSON-RPC error response should raise McpError."""
        responses = [
            _make_initialize_response(1),
            _make_error_response(2, -32601, "method not found"),
        ]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                await client.start()
                with self.assertRaises(McpError) as ctx:
                    await client.call_tool("unknown_tool", {})
                self.assertEqual(ctx.exception.code, -32601)

            await client.close()

        self._run(run_test())

    def test_auto_incrementing_request_id(self) -> None:
        """Request IDs should auto-increment starting from 1."""
        responses = [
            _make_initialize_response(1),
            _make_tools_list_response(2, []),
            _make_tools_call_response(3, "result"),
        ]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                await client.start()
                await client.list_tools()
                await client.call_tool("search_laws", {})

            # Check sent messages have IDs 1, 2, 3
            sent_lines = [
                json.loads(line.decode("utf-8"))
                for line in fake_process.stdin.written
                if "id" in json.loads(line.decode("utf-8"))
            ]
            ids = [msg["id"] for msg in sent_lines]
            self.assertEqual(ids, [1, 2, 3])

            await client.close()

        self._run(run_test())

    def test_close_terminates_process(self) -> None:
        """close() should terminate the subprocess."""
        responses = [_make_initialize_response(1)]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                await client.start()
            await client.close()
            self.assertTrue(fake_process.terminated)

        self._run(run_test())

    def test_async_context_manager(self) -> None:
        """async with should start and close the client."""
        responses = [_make_initialize_response(1)]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                async with client:
                    self.assertTrue(client._started)
            # After exiting, should be closed
            self.assertFalse(client._started)

        self._run(run_test())

    def test_connector_path_configured(self) -> None:
        """The connector path should be stored at construction time."""
        client = McpClient("/configured/path/to/connector.js")
        self.assertEqual(client._connector_path, "/configured/path/to/connector.js")

    def test_default_timeout_40_seconds(self) -> None:
        """Default timeout should be 40.0 seconds (matching law-database budget)."""
        client = McpClient("/path/to/connector.js")
        self.assertEqual(client._timeout, 40.0)

    def test_custom_timeout(self) -> None:
        """Custom timeout should be accepted."""
        client = McpClient("/path/to/connector.js", timeout=10.0)
        self.assertEqual(client._timeout, 10.0)

    def test_env_passed_to_subprocess(self) -> None:
        """Environment variables should be stored for the subprocess."""
        env = {"LAW_DB_FIXTURES": "1", "NODE_PATH": "/custom"}
        client = McpClient("/path/to/connector.js", env=env)
        self.assertEqual(client._env, env)

    def test_call_tool_arguments_passed(self) -> None:
        """call_tool() should pass arguments to the tools/call request."""
        responses = [
            _make_initialize_response(1),
            _make_tools_call_response(2, "result"),
        ]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                await client.start()
                await client.call_tool(
                    "search_laws",
                    {"keyword": "民法典", "lawType": "法律"},
                )

            # Check the tools/call request has the correct arguments
            sent_lines = [
                json.loads(line.decode("utf-8"))
                for line in fake_process.stdin.written
            ]
            tools_call_msg = next(
                msg for msg in sent_lines if msg.get("method") == "tools/call"
            )
            self.assertEqual(tools_call_msg["params"]["name"], "search_laws")
            self.assertEqual(tools_call_msg["params"]["arguments"]["keyword"], "民法典")
            self.assertEqual(tools_call_msg["params"]["arguments"]["lawType"], "法律")

            await client.close()

        self._run(run_test())

    def test_empty_content_returns_empty_string(self) -> None:
        """A tools/call response with empty content should return empty string."""
        responses = [
            _make_initialize_response(1),
            {"jsonrpc": "2.0", "id": 2, "result": {"content": [], "isError": False}},
        ]
        fake_process = FakeProcess(responses)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake_process

        client = McpClient("/fake/path/index.js", timeout=5.0)

        async def run_test():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                await client.start()
                text = await client.call_tool("search_laws", {})
            self.assertEqual(text, "")

            await client.close()

        self._run(run_test())


if __name__ == "__main__":
    unittest.main()
