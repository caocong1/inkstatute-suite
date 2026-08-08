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

from fixtures.mcp_law_fixtures import LAW_FIXTURE_RESPONSES


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
        """Registry with emitter should have read_file, search_laws, ask_user, and generate_review_docx."""
        emitter = EventEmitter(run_id="test-run")
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        self.assertTrue(registry.has_tool("read_file"))
        self.assertTrue(registry.has_tool("search_laws"))
        self.assertTrue(registry.has_tool("ask_user"))
        self.assertTrue(registry.has_tool("generate_review_docx"))

    def test_registry_without_emitter(self) -> None:
        """Registry without emitter should not have ask_user or generate_review_docx."""
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        self.assertTrue(registry.has_tool("read_file"))
        self.assertTrue(registry.has_tool("search_laws"))
        self.assertFalse(registry.has_tool("ask_user"))
        self.assertFalse(registry.has_tool("generate_review_docx"))

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
        self.assertEqual(len(definitions), 4)

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
        self.assertEqual(names, {"read_file", "search_laws", "ask_user", "generate_review_docx"})

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

    def test_document_generate_registered_with_emitter(self) -> None:
        """generate_review_docx should be registered when emitter is provided."""
        emitter = EventEmitter(run_id="test-run")
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        self.assertTrue(registry.has_tool("generate_review_docx"))
        handler = registry.get_handler("generate_review_docx")
        self.assertIsNotNone(handler)

    def test_document_generate_not_registered_without_emitter(self) -> None:
        """generate_review_docx should NOT be registered when emitter is None."""
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        self.assertFalse(registry.has_tool("generate_review_docx"))

    def test_document_generate_in_tool_definitions(self) -> None:
        """get_tool_definitions() should include the document_generate definition."""
        emitter = EventEmitter(run_id="test-run")
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )

        definitions = registry.get_tool_definitions()
        names = {d["function"]["name"] for d in definitions}
        self.assertIn("generate_review_docx", names)

    def test_trackchanges_script_path_parameter(self) -> None:
        """trackchanges_script_path should be accepted and used."""
        emitter = EventEmitter(run_id="test-run")
        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
            trackchanges_script_path="/custom/path/to/script.py",
        )

        # The tool should be registered (the script path is only used at call time)
        self.assertTrue(registry.has_tool("generate_review_docx"))


if __name__ == "__main__":
    unittest.main()
