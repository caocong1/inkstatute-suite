"""Dispatching ToolExecutor — composes ToolRegistry with the Phase 100 turn loop.

``create_dispatching_executor(registry)`` returns a ``ToolExecutor`` callable
(the same ``Callable[[str, str, dict], Awaitable[ToolResult]]`` interface that
``run_turn()`` expects).  The dispatching executor:

1. Receives ``(tool_call_id, tool_name, arguments)``.
2. Looks up the handler in the registry via ``get_handler(tool_name)``.
3. If not found, returns a ``ToolResult`` with an ``ErrorInfo`` (not an
   exception — the turn loop handles this gracefully).
4. If found, calls ``await handler(arguments)`` and returns the ``ToolResult``.
5. Catches exceptions and returns a ``ToolResult`` with ``ErrorInfo`` — a
   secondary safety net (the turn loop already has its own try/except).
"""

from __future__ import annotations

from platform_contract.enums import ErrorCategory
from platform_contract.events import ErrorInfo

from ..turn_loop import ToolExecutor, ToolResult
from .registry import ToolRegistry


def create_dispatching_executor(registry: ToolRegistry) -> ToolExecutor:
    """Create a ``ToolExecutor`` that dispatches to registry handlers.

    Args:
        registry: The ``ToolRegistry`` containing registered tool handlers.

    Returns:
        A ``ToolExecutor`` callable ``(tool_call_id, tool_name, arguments)
        -> Awaitable[ToolResult]``.
    """

    async def dispatching_executor(
        tool_call_id: str,
        tool_name: str,
        arguments: dict,
    ) -> ToolResult:
        handler = registry.get_handler(tool_name)
        if handler is None:
            error = ErrorInfo(
                category=ErrorCategory.RUNTIME_ERROR,
                code="unknown_tool",
                message=f"Unknown tool: {tool_name}",
                retryable=False,
            )
            return ToolResult(
                content=f"Unknown tool: {tool_name}",
                error=error,
            )

        try:
            return await handler(arguments)
        except Exception as exc:
            error = ErrorInfo(
                category=ErrorCategory.RUNTIME_ERROR,
                code="tool_handler_exception",
                message=str(exc),
                retryable=True,
            )
            return ToolResult(
                content=str(exc),
                error=error,
            )

    return dispatching_executor


__all__ = ["create_dispatching_executor"]
