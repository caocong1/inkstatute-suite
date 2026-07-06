"""inkstatute-mcp-registry: read-only MCP Connector Registry library.

Re-exports the read-only McpRegistryPort Protocol, InMemoryMcpRegistry,
McpServerPage pagination envelope, McpServerRecord internal record,
cursor pagination helpers, the McpRegistryAdminPort write Protocol,
and the JSON Schema tool schema validator.
"""

from .admin import (
    InMemoryMcpRegistryAdmin,
    McpRegistryAdminPort,
    McpServerRegistrationSpec,
)
from .cursor import decode_cursor, encode_cursor
from .registry import (
    InMemoryMcpRegistry,
    McpRegistryPort,
    McpServerPage,
    McpServerRecord,
)
from .schema_validator import validate_tool_schema, validate_tool_schemas

__all__ = [
    "InMemoryMcpRegistry",
    "InMemoryMcpRegistryAdmin",
    "McpRegistryAdminPort",
    "McpRegistryPort",
    "McpServerPage",
    "McpServerRecord",
    "McpServerRegistrationSpec",
    "decode_cursor",
    "encode_cursor",
    "validate_tool_schema",
    "validate_tool_schemas",
]
