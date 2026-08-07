"""Tests for the builtin_registry factory — composes all Phase 101 tools.

Covers: registry with all tools, registry without emitter (no ask_user),
fixture mode fallback, tool definitions format.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.tools.builtin_registry import create_builtin_registry
from inkstatute_agent_core.tools.registry import ToolRegistry

from tests.fixtures.mcp_law_fixtures import LAW_FIXTURE_RESPONSES


class TestBuiltinRegistry(unittest.TestCase):
    """Tests for create_builtin_registry factory."""

    def setUp(self) -> None:
        """Create a temporary directory for sandbox roots."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        (self.root / "test.txt").write_text("test", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_registry_with_all_tools(self) -> None:
        """Registry with emitter should have read_file, search_laws, and ask_user."""
        emitter = EventEmitter(run_id="test-run")
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        self.assertTrue(registry.has_tool("read_file"))
        self.assertTrue(registry.has_tool("search_laws"))
        self.assertTrue(registry.has_tool("ask_user"))

    def test_registry_without_emitter(self) -> None:
        """Registry without emitter should not have ask_user."""
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        self.assertTrue(registry.has_tool("read_file"))
        self.assertTrue(registry.has_tool("search_laws"))
        self.assertFalse(registry.has_tool("ask_user"))

    def test_registry_returns_tool_registry(self) -> None:
        """create_builtin_registry should return a ToolRegistry instance."""
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )
        self.assertIsInstance(registry, ToolRegistry)

    def test_tool_definitions_format(self) -> None:
        """get_tool_definitions() should return OpenAI-format definitions."""
        emitter = EventEmitter(run_id="test-run")
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        definitions = registry.get_tool_definitions()
        self.assertEqual(len(definitions), 3)

        # Each definition should be OpenAI function-calling format
        for defn in definitions:
            self.assertEqual(defn["type"], "function")
            self.assertIn("function", defn)
            func = defn["function"]
            self.assertIn("name", func)
            self.assertIn("description", func)
            self.assertIn("parameters", func)

    def test_tool_definition_names(self) -> None:
        """Tool definitions should have correct names."""
        emitter = EventEmitter(run_id="test-run")
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        definitions = registry.get_tool_definitions()
        names = {d["function"]["name"] for d in definitions}
        self.assertEqual(names, {"read_file", "search_laws", "ask_user"})

    def test_fixture_mode_fallback(self) -> None:
        """When mcp_connector_path is None, fixture mode should be used."""
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            mcp_connector_path=None,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        # search_laws should be registered and work in fixture mode
        self.assertTrue(registry.has_tool("search_laws"))

        # Verify the handler works by dispatching through the registry
        import asyncio

        handler = registry.get_handler("search_laws")
        result = asyncio.new_event_loop().run_until_complete(
            handler({"keyword": "合同法"})
        )
        self.assertIn("合同法", result.content)

    def test_fixture_mode_default_empty_responses(self) -> None:
        """When no fixture_responses provided, default to empty dict."""
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            mcp_connector_path=None,
        )

        self.assertTrue(registry.has_tool("search_laws"))

        import asyncio

        handler = registry.get_handler("search_laws")
        result = asyncio.new_event_loop().run_until_complete(
            handler({"keyword": "anything"})
        )
        self.assertIn("未找到", result.content)

    def test_file_read_tool_works(self) -> None:
        """The registered file_read tool should work through the registry."""
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        import asyncio

        handler = registry.get_handler("read_file")
        result = asyncio.new_event_loop().run_until_complete(
            handler({"path": str(self.root / "test.txt")})
        )
        self.assertIsNone(result.error)
        self.assertEqual(result.content, "test")

    def test_mcp_connector_path_creates_mcp_handler(self) -> None:
        """When mcp_connector_path is provided, a real MCP handler is created."""
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            mcp_connector_path="/fake/path/to/connector.js",
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        # search_laws should be registered (with MCP handler, not fixture)
        self.assertTrue(registry.has_tool("search_laws"))
        # The handler should exist (we don't call it since it would need a real subprocess)
        handler = registry.get_handler("search_laws")
        self.assertIsNotNone(handler)


if __name__ == "__main__":
    unittest.main()
