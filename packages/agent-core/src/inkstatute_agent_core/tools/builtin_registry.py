"""Builtin tool registry factory — composes all Phase 101 tools into one registry.

``create_builtin_registry()`` creates a ``ToolRegistry`` and registers
all builtin tools from Phase 101 plans 101-01 and 101-02:

- ``read_file`` — file reading tool (via ``create_file_read_tool``)
- ``search_laws`` — regulation search tool (via
  ``create_regulation_search_tool`` or fixture mode if no connector path)
- ``ask_user`` — clarification tool (via ``create_clarification_tool``)
  — only if an ``EventEmitter`` is provided

This factory composes the tools into a single registry that can be
passed to ``create_dispatching_executor()`` and used with ``run_turn()``.
"""

from __future__ import annotations

from typing import Any

from ..event_emitter import EventEmitter
from .clarification import (
    CLARIFICATION_TOOL_DEFINITION,
    create_clarification_tool,
)
from .file_read import (
    FILE_READ_TOOL_DEFINITION,
    create_file_read_tool,
)
from .path_sandbox import PathSandbox
from .regulation_search import (
    REGULATION_SEARCH_TOOL_DEFINITION,
    create_fixture_regulation_search_tool,
    create_regulation_search_tool,
)
from .registry import ToolRegistry

JsonObject = dict[str, Any]


def create_builtin_registry(
    *,
    sandbox_roots: list[str],
    mcp_connector_path: str | None = None,
    emitter: EventEmitter | None = None,
    fixture_responses: dict[str, str] | None = None,
) -> ToolRegistry:
    """Create a ``ToolRegistry`` with all builtin tools registered.

    Args:
        sandbox_roots: List of allowed root directories for the file
            reading tool's ``PathSandbox``.
        mcp_connector_path: Path to the law-database MCP connector
            (``index.js``).  If ``None``, the regulation search tool
            uses fixture mode (canned responses).
        emitter: The ``EventEmitter`` for the clarification tool.  If
            ``None``, the ``ask_user`` tool is not registered.
        fixture_responses: Canned responses for fixture-mode regulation
            search.  If ``None`` and ``mcp_connector_path`` is ``None``,
            an empty dict is used (all searches return "no results").

    Returns:
        A ``ToolRegistry`` with all applicable builtin tools registered.
    """
    registry = ToolRegistry()

    # 1. Register file_read tool
    sandbox = PathSandbox(sandbox_roots)
    file_read_handler = create_file_read_tool(sandbox)
    registry.register_definition(
        name="read_file",
        handler=file_read_handler,
        definition=FILE_READ_TOOL_DEFINITION,
    )

    # 2. Register search_laws tool (MCP or fixture mode)
    if mcp_connector_path is not None:
        # Real MCP mode — create McpClient lazily
        # The McpClient is created but not started here; the caller
        # is responsible for starting it (or the tool handler can
        # start it on first use).  For now, we create the handler
        # with the client — the caller manages the lifecycle.
        from .mcp_client import McpClient

        mcp_client = McpClient(mcp_connector_path)
        search_handler = create_regulation_search_tool(mcp_client)
    else:
        # Fixture mode — no MCP subprocess
        responses = fixture_responses if fixture_responses is not None else {}
        search_handler = create_fixture_regulation_search_tool(responses)

    registry.register_definition(
        name="search_laws",
        handler=search_handler,
        definition=REGULATION_SEARCH_TOOL_DEFINITION,
    )

    # 3. Register ask_user tool (only if emitter is provided)
    if emitter is not None:
        clarification_handler = create_clarification_tool(emitter)
        registry.register_definition(
            name="ask_user",
            handler=clarification_handler,
            definition=CLARIFICATION_TOOL_DEFINITION,
        )

    return registry


__all__ = ["create_builtin_registry"]
