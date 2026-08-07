"""Tests for the regulation search tool — via MCP client and fixture mode.

Covers: successful search, empty results, MCP error handling, fixture
mode responses, argument mapping.  All tests use fixture mode or mock
MCP client — no real MCP subprocess or network.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from inkstatute_agent_core.tools.mcp_client import McpError
from inkstatute_agent_core.tools.regulation_search import (
    REGULATION_SEARCH_TOOL_DEFINITION,
    create_fixture_regulation_search_tool,
    create_regulation_search_tool,
    _map_arguments,
)
from inkstatute_agent_core.turn_loop import ToolResult

from tests.fixtures.mcp_law_fixtures import LAW_FIXTURE_RESPONSES


class TestArgumentMapping(unittest.TestCase):
    """Tests for _map_arguments — snake_case to camelCase conversion."""

    def test_keyword_mapped(self) -> None:
        result = _map_arguments({"keyword": "合同法"})
        self.assertEqual(result["keyword"], "合同法")

    def test_law_type_mapped_to_lawType(self) -> None:
        result = _map_arguments({"law_type": "法律"})
        self.assertEqual(result["lawType"], "法律")

    def test_issuing_authority_mapped_to_issuingAuthority(self) -> None:
        result = _map_arguments({"issuing_authority": "全国人大"})
        self.assertEqual(result["issuingAuthority"], "全国人大")

    def test_status_mapped(self) -> None:
        result = _map_arguments({"status": "现行有效"})
        self.assertEqual(result["status"], "现行有效")

    def test_all_arguments_mapped(self) -> None:
        result = _map_arguments({
            "keyword": "民法典",
            "law_type": "法律",
            "issuing_authority": "全国人大",
            "status": "现行有效",
        })
        self.assertEqual(result["keyword"], "民法典")
        self.assertEqual(result["lawType"], "法律")
        self.assertEqual(result["issuingAuthority"], "全国人大")
        self.assertEqual(result["status"], "现行有效")

    def test_empty_arguments(self) -> None:
        result = _map_arguments({})
        self.assertEqual(result, {})


class TestRegulationSearchTool(unittest.TestCase):
    """Tests for the regulation search tool with mock MCP client."""

    def _run(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def test_successful_search(self) -> None:
        """A successful MCP call should return results as ToolResult.content."""
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(return_value="## 搜索结果: 合同法\n...")
        handler = create_regulation_search_tool(mock_client)

        result = self._run(handler({"keyword": "合同法"}))

        self.assertIsNone(result.error)
        self.assertIn("搜索结果", result.content)
        mock_client.call_tool.assert_called_once_with(
            "search_laws", {"keyword": "合同法"}
        )

    def test_search_with_all_arguments(self) -> None:
        """All arguments should be mapped and passed to the MCP client."""
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(return_value="results")
        handler = create_regulation_search_tool(mock_client)

        result = self._run(handler({
            "keyword": "民法典",
            "law_type": "法律",
            "issuing_authority": "全国人大",
            "status": "现行有效",
        }))

        self.assertIsNone(result.error)
        mock_client.call_tool.assert_called_once_with(
            "search_laws",
            {
                "keyword": "民法典",
                "lawType": "法律",
                "issuingAuthority": "全国人大",
                "status": "现行有效",
            },
        )

    def test_empty_results(self) -> None:
        """An empty string result should still be returned as ToolResult."""
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(return_value="")
        handler = create_regulation_search_tool(mock_client)

        result = self._run(handler({"keyword": "不存在的法规"}))

        self.assertIsNone(result.error)
        self.assertEqual(result.content, "")

    def test_mcp_error_handling(self) -> None:
        """McpError should be caught and returned as error ToolResult."""
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(side_effect=McpError("内部错误: timeout"))
        handler = create_regulation_search_tool(mock_client)

        result = self._run(handler({"keyword": "合同法"}))

        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "mcp_tool_error")
        self.assertIn("法规检索失败", result.content)

    def test_connection_error_handling(self) -> None:
        """Non-McpError exceptions should be caught as connection errors."""
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(side_effect=ConnectionError("subprocess died"))
        handler = create_regulation_search_tool(mock_client)

        result = self._run(handler({"keyword": "合同法"}))

        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "mcp_connection_error")
        self.assertIn("法规检索连接失败", result.content)

    def test_missing_keyword(self) -> None:
        """Missing keyword should return an error ToolResult."""
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(return_value="should not be called")
        handler = create_regulation_search_tool(mock_client)

        result = self._run(handler({}))

        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "missing_keyword")
        mock_client.call_tool.assert_not_called()

    def test_tool_definition_format(self) -> None:
        """REGULATION_SEARCH_TOOL_DEFINITION should be valid OpenAI format."""
        self.assertEqual(REGULATION_SEARCH_TOOL_DEFINITION["type"], "function")
        func = REGULATION_SEARCH_TOOL_DEFINITION["function"]
        self.assertEqual(func["name"], "search_laws")
        self.assertIn("description", func)
        self.assertIn("parameters", func)
        params = func["parameters"]
        self.assertEqual(params["type"], "object")
        self.assertIn("keyword", params["properties"])
        self.assertIn("law_type", params["properties"])
        self.assertIn("issuing_authority", params["properties"])
        self.assertIn("status", params["properties"])
        self.assertIn("keyword", params["required"])


class TestFixtureRegulationSearchTool(unittest.TestCase):
    """Tests for the fixture-mode regulation search tool."""

    def _run(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def test_fixture_mode_returns_canned_response(self) -> None:
        """Fixture mode should return canned responses by keyword."""
        handler = create_fixture_regulation_search_tool(LAW_FIXTURE_RESPONSES)

        result = self._run(handler({"keyword": "合同法"}))

        self.assertIsNone(result.error)
        self.assertIn("合同法", result.content)
        self.assertIn("民法典", result.content)

    def test_fixture_mode_different_keywords(self) -> None:
        """Different keywords should return different canned responses."""
        handler = create_fixture_regulation_search_tool(LAW_FIXTURE_RESPONSES)

        result1 = self._run(handler({"keyword": "民法典"}))
        result2 = self._run(handler({"keyword": "公司法"}))

        self.assertIn("民法典", result1.content)
        self.assertIn("公司法", result2.content)
        self.assertNotEqual(result1.content, result2.content)

    def test_fixture_mode_unknown_keyword(self) -> None:
        """Unknown keywords should return a 'no results' message."""
        handler = create_fixture_regulation_search_tool(LAW_FIXTURE_RESPONSES)

        result = self._run(handler({"keyword": "不存在的关键词"}))

        self.assertIsNone(result.error)
        self.assertIn("未找到", result.content)

    def test_fixture_mode_no_mcp_call(self) -> None:
        """Fixture mode should not call any MCP client."""
        handler = create_fixture_regulation_search_tool(LAW_FIXTURE_RESPONSES)

        # Should work without any MCP client at all
        result = self._run(handler({"keyword": "劳动法"}))

        self.assertIsNone(result.error)
        self.assertIn("劳动法", result.content)

    def test_fixture_mode_missing_keyword(self) -> None:
        """Missing keyword should return an error in fixture mode too."""
        handler = create_fixture_regulation_search_tool(LAW_FIXTURE_RESPONSES)

        result = self._run(handler({}))

        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "missing_keyword")

    def test_fixture_mode_with_arguments(self) -> None:
        """Fixture mode should accept (and ignore) extra arguments."""
        handler = create_fixture_regulation_search_tool(LAW_FIXTURE_RESPONSES)

        result = self._run(handler({
            "keyword": "民法典",
            "law_type": "法律",
            "issuing_authority": "全国人大",
            "status": "现行有效",
        }))

        self.assertIsNone(result.error)
        self.assertIn("民法典", result.content)

    def test_fixture_mode_empty_responses(self) -> None:
        """Empty fixture responses dict should return 'no results' for any keyword."""
        handler = create_fixture_regulation_search_tool({})

        result = self._run(handler({"keyword": "anything"}))

        self.assertIsNone(result.error)
        self.assertIn("未找到", result.content)


if __name__ == "__main__":
    unittest.main()
