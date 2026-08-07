"""Tool layer for the InkStatute agent core.

This sub-package contains the tool registry, dispatching executor,
and individual tool implementations.

Phase 101-01: ToolRegistry, dispatching ToolExecutor, clarification (ask_user) tool.
Phase 101-02: PathSandbox, file_read, MCP client, regulation search, builtin_registry.
Phase 101-03: document_generate (planned).
"""

from __future__ import annotations

from .registry import ToolHandler, ToolRegistry
from .executor import create_dispatching_executor
from .path_sandbox import PathSandbox
from .file_read import create_file_read_tool, FILE_READ_TOOL_DEFINITION
from .mcp_client import (
    McpClient,
    McpError,
    mcp_input_schema_to_openai_parameters,
    mcp_tool_to_openai_definition,
)
from .regulation_search import (
    create_regulation_search_tool,
    create_fixture_regulation_search_tool,
    REGULATION_SEARCH_TOOL_DEFINITION,
)
from .builtin_registry import create_builtin_registry

__all__ = [
    "ToolRegistry",
    "ToolHandler",
    "create_dispatching_executor",
    "PathSandbox",
    "create_file_read_tool",
    "FILE_READ_TOOL_DEFINITION",
    "McpClient",
    "McpError",
    "mcp_input_schema_to_openai_parameters",
    "mcp_tool_to_openai_definition",
    "create_regulation_search_tool",
    "create_fixture_regulation_search_tool",
    "REGULATION_SEARCH_TOOL_DEFINITION",
    "create_builtin_registry",
]
