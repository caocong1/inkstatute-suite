"""ToolRegistry — maps tool names to callable handlers and stores OpenAI-format definitions.

The ``ToolRegistry`` is the central registration point for all agent-core
tools.  Each tool is registered with:

- A **name** (string, matching the OpenAI function-calling ``name`` field).
- A **handler** — an async callable ``Callable[[dict], Awaitable[ToolResult]]``
  that receives the parsed arguments dict and returns a ``ToolResult``.
- An OpenAI function-calling **definition** (``{"type": "function",
  "function": {"name": ..., "description": ..., "parameters": {...}}}``).

The registry produces the list of tool definitions for the ``ChatRequest.tools``
parameter via ``get_tool_definitions()``.

Phase 101 plans 101-02 and 101-03 register additional tools (file_read,
mcp_client, regulation_search, document_generate) into the same registry.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from platform_contract.enums import ErrorCategory
from platform_contract.events import ErrorInfo

from ..turn_loop import ToolResult

JsonObject = dict[str, Any]

# Per-tool handler signature: receives parsed arguments dict, returns ToolResult.
ToolHandler = Callable[[dict], Awaitable[ToolResult]]


class ToolRegistry:
    """Maps tool names to handlers and stores OpenAI-format tool definitions.

    Attributes:
        _handlers: Dict mapping tool name → handler callable.
        _definitions: List of OpenAI function-calling tool definition dicts.
        _definition_map: Dict mapping tool name → its definition dict.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._definitions: list[dict] = []
        self._definition_map: dict[str, dict] = {}

    def register(
        self,
        name: str,
        handler: ToolHandler,
        description: str,
        parameters: dict,
    ) -> None:
        """Register a tool with its OpenAI-format definition.

        Args:
            name: Tool name (must be unique within the registry).
            handler: Async callable ``(arguments: dict) -> ToolResult``.
            description: Human-readable description for the LLM.
            parameters: JSON Schema dict for the tool parameters
                (OpenAI ``parameters`` field).
        """
        definition = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }
        self.register_definition(name, handler, definition)

    def register_definition(
        self,
        name: str,
        handler: ToolHandler,
        definition: dict,
    ) -> None:
        """Register a tool with a pre-built OpenAI function-calling definition.

        Args:
            name: Tool name (must be unique within the registry).
            handler: Async callable ``(arguments: dict) -> ToolResult``.
            definition: Pre-built OpenAI function-calling definition dict
                (``{"type": "function", "function": {"name": ..., ...}}``).
        """
        if name in self._handlers:
            raise ValueError(f"Tool already registered: {name}")
        self._handlers[name] = handler
        self._definitions.append(definition)
        self._definition_map[name] = definition

    def get_handler(self, name: str) -> ToolHandler | None:
        """Look up a handler by tool name.

        Returns ``None`` if the tool is not registered.
        """
        return self._handlers.get(name)

    def get_tool_definitions(self) -> list[dict]:
        """Return the list of OpenAI-format tool definitions.

        Suitable for passing as the ``tools`` parameter to ``ChatRequest``.
        """
        return list(self._definitions)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._handlers


__all__ = [
    "ToolRegistry",
    "ToolHandler",
]
