"""Tests for ToolRegistry and dispatching ToolExecutor.

Covers: registration, lookup, get_tool_definitions output format,
dispatching executor success, dispatching executor unknown tool,
dispatching executor handler exception.
"""

from __future__ import annotations

import asyncio
import unittest

from platform_contract.enums import ErrorCategory

from inkstatute_agent_core.tools.executor import create_dispatching_executor
from inkstatute_agent_core.tools.registry import ToolHandler, ToolRegistry
from inkstatute_agent_core.turn_loop import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _echo_handler(arguments: dict) -> ToolResult:
    """Echo the arguments as a ToolResult."""
    import json
    return ToolResult(content=json.dumps(arguments, ensure_ascii=False))


async def _error_handler(arguments: dict) -> ToolResult:
    """Always raise an exception."""
    raise RuntimeError("handler boom")


async def _terminate_handler(arguments: dict) -> ToolResult:
    """Return a ToolResult with terminate_turn metadata."""
    return ToolResult(
        content="turn terminated",
        metadata={"terminate_turn": True},
    )


# ---------------------------------------------------------------------------
# ToolRegistry tests
# ---------------------------------------------------------------------------


class TestToolRegistryRegistration(unittest.TestCase):
    """ToolRegistry.register() stores handlers and definitions."""

    def test_register_stores_handler(self):
        registry = ToolRegistry()
        registry.register("echo", _echo_handler, "Echo tool", {"type": "object"})
        self.assertTrue(registry.has_tool("echo"))

    def test_register_stores_definition(self):
        registry = ToolRegistry()
        registry.register("echo", _echo_handler, "Echo tool", {"type": "object", "properties": {}})
        defs = registry.get_tool_definitions()
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0]["type"], "function")
        self.assertEqual(defs[0]["function"]["name"], "echo")
        self.assertEqual(defs[0]["function"]["description"], "Echo tool")
        self.assertEqual(defs[0]["function"]["parameters"]["type"], "object")

    def test_duplicate_register_raises(self):
        registry = ToolRegistry()
        registry.register("echo", _echo_handler, "Echo tool", {"type": "object"})
        with self.assertRaises(ValueError):
            registry.register("echo", _echo_handler, "Echo tool 2", {"type": "object"})

    def test_register_multiple_tools(self):
        registry = ToolRegistry()
        registry.register("echo", _echo_handler, "Echo", {"type": "object"})
        registry.register("terminate", _terminate_handler, "Terminate", {"type": "object"})
        self.assertTrue(registry.has_tool("echo"))
        self.assertTrue(registry.has_tool("terminate"))
        self.assertEqual(len(registry.get_tool_definitions()), 2)


class TestToolRegistryLookup(unittest.TestCase):
    """get_handler() and has_tool() lookups."""

    def test_get_handler_returns_registered_handler(self):
        registry = ToolRegistry()
        registry.register("echo", _echo_handler, "Echo", {"type": "object"})
        handler = registry.get_handler("echo")
        self.assertIsNotNone(handler)
        self.assertIs(handler, _echo_handler)

    def test_get_handler_returns_none_for_unregistered(self):
        registry = ToolRegistry()
        self.assertIsNone(registry.get_handler("nonexistent"))

    def test_has_tool_false_for_unregistered(self):
        registry = ToolRegistry()
        self.assertFalse(registry.has_tool("nonexistent"))


class TestToolRegistryDefinitions(unittest.TestCase):
    """get_tool_definitions() returns OpenAI function-calling format."""

    def test_definitions_are_openai_format(self):
        registry = ToolRegistry()
        registry.register(
            "search",
            _echo_handler,
            "Search for laws",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        )
        defs = registry.get_tool_definitions()
        self.assertEqual(len(defs), 1)
        d = defs[0]
        self.assertEqual(d["type"], "function")
        self.assertEqual(d["function"]["name"], "search")
        self.assertEqual(d["function"]["description"], "Search for laws")
        self.assertEqual(d["function"]["parameters"]["properties"]["query"]["type"], "string")
        self.assertEqual(d["function"]["parameters"]["required"], ["query"])

    def test_definitions_returns_copy(self):
        """get_tool_definitions returns a copy — mutating it doesn't affect the registry."""
        registry = ToolRegistry()
        registry.register("echo", _echo_handler, "Echo", {"type": "object"})
        defs = registry.get_tool_definitions()
        defs.clear()
        # Registry still has the definition
        self.assertEqual(len(registry.get_tool_definitions()), 1)

    def test_register_definition_with_pre_built_dict(self):
        registry = ToolRegistry()
        definition = {
            "type": "function",
            "function": {
                "name": "custom_tool",
                "description": "A custom tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        registry.register_definition("custom_tool", _echo_handler, definition)
        self.assertTrue(registry.has_tool("custom_tool"))
        defs = registry.get_tool_definitions()
        self.assertEqual(defs[0], definition)


# ---------------------------------------------------------------------------
# Dispatching executor tests
# ---------------------------------------------------------------------------


class TestDispatchingExecutorSuccess(unittest.TestCase):
    """create_dispatching_executor dispatches to registry handlers."""

    def test_dispatch_success(self):
        registry = ToolRegistry()
        registry.register("echo", _echo_handler, "Echo", {"type": "object"})
        executor = create_dispatching_executor(registry)

        result = asyncio.run(executor("tc-1", "echo", {"key": "value"}))
        self.assertIsNone(result.error)
        self.assertIn("key", result.content)
        self.assertIn("value", result.content)

    def test_dispatch_returns_tool_result(self):
        registry = ToolRegistry()
        registry.register("terminate", _terminate_handler, "Terminate", {"type": "object"})
        executor = create_dispatching_executor(registry)

        result = asyncio.run(executor("tc-1", "terminate", {}))
        self.assertIsInstance(result, ToolResult)
        self.assertTrue(result.metadata.get("terminate_turn"))


class TestDispatchingExecutorUnknownTool(unittest.TestCase):
    """Unknown tool name produces a ToolResult with ErrorInfo (not an exception)."""

    def test_unknown_tool_returns_error_result(self):
        registry = ToolRegistry()
        executor = create_dispatching_executor(registry)

        result = asyncio.run(executor("tc-1", "nonexistent", {}))
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "unknown_tool")
        self.assertIn("nonexistent", result.content)
        self.assertFalse(result.error.retryable)

    def test_unknown_tool_does_not_raise(self):
        """The executor must not raise — it returns an error ToolResult."""
        registry = ToolRegistry()
        executor = create_dispatching_executor(registry)

        # This should not raise
        result = asyncio.run(executor("tc-1", "missing", {}))
        self.assertIsInstance(result, ToolResult)


class TestDispatchingExecutorHandlerException(unittest.TestCase):
    """Handler exceptions are caught and returned as error ToolResult."""

    def test_handler_exception_returns_error_result(self):
        registry = ToolRegistry()
        registry.register("boom", _error_handler, "Boom", {"type": "object"})
        executor = create_dispatching_executor(registry)

        result = asyncio.run(executor("tc-1", "boom", {}))
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "tool_handler_exception")
        self.assertIn("handler boom", result.content)
        self.assertTrue(result.error.retryable)

    def test_handler_exception_does_not_raise(self):
        """The executor catches exceptions — the turn loop is not disrupted."""
        registry = ToolRegistry()
        registry.register("boom", _error_handler, "Boom", {"type": "object"})
        executor = create_dispatching_executor(registry)

        result = asyncio.run(executor("tc-1", "boom", {}))
        self.assertIsInstance(result, ToolResult)


# ---------------------------------------------------------------------------
# ToolHandler type alias test
# ---------------------------------------------------------------------------


class TestToolHandlerType(unittest.TestCase):
    """ToolHandler type alias is Callable[[dict], Awaitable[ToolResult]]."""

    def test_tool_handler_is_callable(self):
        """A registered handler is callable and async."""
        registry = ToolRegistry()
        registry.register("echo", _echo_handler, "Echo", {"type": "object"})
        handler = registry.get_handler("echo")
        self.assertTrue(callable(handler))


if __name__ == "__main__":
    unittest.main()
