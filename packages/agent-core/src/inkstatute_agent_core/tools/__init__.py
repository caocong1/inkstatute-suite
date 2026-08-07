"""Tool layer for the InkStatute agent core.

This sub-package contains the tool registry, dispatching executor,
and individual tool implementations.

Phase 101-01: ToolRegistry, dispatching ToolExecutor, clarification (ask_user) tool.
Phase 101-02: file_read, MCP client, regulation search (planned).
Phase 101-03: document_generate (planned).
"""

from __future__ import annotations

from .registry import ToolHandler, ToolRegistry
from .executor import create_dispatching_executor

__all__ = [
    "ToolRegistry",
    "ToolHandler",
    "create_dispatching_executor",
]
