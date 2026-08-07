"""Regulation search tool — calls law-database MCP connector via McpClient.

The regulation search tool is a thin wrapper that calls the
``search_laws`` tool on the ``law-database`` MCP connector.  It:

1. Receives arguments: ``keyword`` (str), ``law_type`` (str, optional),
   ``issuing_authority`` (str, optional), ``status`` (str, optional).
2. Maps the arguments to the MCP connector's parameter names:
   ``keyword`` → ``keyword``, ``law_type`` → ``lawType``,
   ``issuing_authority`` → ``issuingAuthority``, ``status`` → ``status``.
3. Calls ``McpClient.call_tool("search_laws", mcp_arguments)``.
4. Returns the search results text as ``ToolResult(content=results_text)``.
5. MCP client errors are caught and returned as error ``ToolResult``
   (not exceptions).

The ``create_regulation_search_tool(mcp_client)`` factory captures the
MCP client and returns a ``ToolHandler`` callable.

**Fixture mode:** ``create_fixture_regulation_search_tool(fixture_responses)``
returns a handler that returns canned responses based on the keyword,
enabling testing without MCP subprocess or network.
"""

from __future__ import annotations

from typing import Any

from platform_contract.enums import ErrorCategory
from platform_contract.events import ErrorInfo

from ..turn_loop import ToolResult
from .mcp_client import McpClient, McpError

JsonObject = dict[str, Any]

# OpenAI function-calling tool definition for the regulation search tool.
REGULATION_SEARCH_TOOL_DEFINITION: dict = {
    "type": "function",
    "function": {
        "name": "search_laws",
        "description": (
            "根据关键词、法规类型、发布机构等条件搜索法律法规。"
            "数据来源为国家法律法规数据库 (flk.npc.gov.cn)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词",
                },
                "law_type": {
                    "type": "string",
                    "enum": [
                        "法律",
                        "行政法规",
                        "部门规章",
                        "地方性法规",
                        "地方政府规章",
                        "司法解释",
                        "规范性文件",
                    ],
                    "description": "法规类型",
                },
                "issuing_authority": {
                    "type": "string",
                    "description": "发布机构（如：全国人大、国务院、最高人民法院）",
                },
                "status": {
                    "type": "string",
                    "enum": ["现行有效", "已修改", "已废止", "尚未生效"],
                    "description": "法规状态",
                },
            },
            "required": ["keyword"],
        },
    },
}


def _map_arguments(arguments: dict) -> dict:
    """Map tool arguments to MCP connector parameter names.

    The tool uses snake_case (Python convention) while the MCP connector
    uses camelCase (JavaScript convention).

    Args:
        arguments: The tool call arguments dict.

    Returns:
        A dict with MCP connector parameter names.
    """
    mcp_args: dict = {}
    if "keyword" in arguments:
        mcp_args["keyword"] = arguments["keyword"]
    if "law_type" in arguments:
        mcp_args["lawType"] = arguments["law_type"]
    if "issuing_authority" in arguments:
        mcp_args["issuingAuthority"] = arguments["issuing_authority"]
    if "status" in arguments:
        mcp_args["status"] = arguments["status"]
    return mcp_args


def create_regulation_search_tool(mcp_client: McpClient):
    """Create a regulation search tool handler bound to an McpClient.

    The returned handler is a ``ToolHandler`` —
    ``Callable[[dict], Awaitable[ToolResult]]``.  It calls
    ``search_laws`` via the MCP client and returns the results text.

    Args:
        mcp_client: The ``McpClient`` to use for calling the law-database
            connector.

    Returns:
        An async callable ``(arguments: dict) -> ToolResult``.
    """

    async def regulation_search_handler(arguments: dict) -> ToolResult:
        keyword = arguments.get("keyword", "")
        if not keyword:
            return ToolResult(
                content="",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="missing_keyword",
                    message="keyword argument is required",
                    retryable=False,
                ),
            )

        mcp_args = _map_arguments(arguments)

        try:
            text = await mcp_client.call_tool("search_laws", mcp_args)
            return ToolResult(content=text)
        except McpError as exc:
            return ToolResult(
                content=f"法规检索失败: {exc}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="mcp_tool_error",
                    message=str(exc),
                    retryable=True,
                ),
            )
        except Exception as exc:
            return ToolResult(
                content=f"法规检索连接失败: {exc}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="mcp_connection_error",
                    message=str(exc),
                    retryable=True,
                ),
            )

    return regulation_search_handler


def create_fixture_regulation_search_tool(
    fixture_responses: dict[str, str],
):
    """Create a fixture-mode regulation search tool handler.

    This handler returns canned responses based on the keyword, enabling
    testing without a real MCP subprocess or network.  When the keyword
    is not in ``fixture_responses``, returns an empty results message.

    Args:
        fixture_responses: Dict mapping keyword → canned response text.

    Returns:
        An async callable ``(arguments: dict) -> ToolResult``.
    """

    async def fixture_handler(arguments: dict) -> ToolResult:
        keyword = arguments.get("keyword", "")
        if not keyword:
            return ToolResult(
                content="",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="missing_keyword",
                    message="keyword argument is required",
                    retryable=False,
                ),
            )

        # Look up canned response by keyword
        text = fixture_responses.get(keyword, "")
        if not text:
            text = f"未找到与「{keyword}」相关的法规。"

        return ToolResult(content=text)

    return fixture_handler


__all__ = [
    "create_regulation_search_tool",
    "create_fixture_regulation_search_tool",
    "REGULATION_SEARCH_TOOL_DEFINITION",
]
