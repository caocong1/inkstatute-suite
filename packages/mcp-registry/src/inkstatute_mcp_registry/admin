"""MCP Registry Admin Port — write operations for connector management.

Defines ``McpRegistryAdminPort`` (write Protocol) and
``InMemoryMcpRegistryAdmin`` (implementation) for registration with
JSON Schema tool schemas, semantic versioning, soft-delete, and
admission review.

Registration does NOT auto-execute — the ``mcp`` SDK is never invoked
during registration.  An admission review step (``approve_server``) is
required before a connector is marked active and discoverable via
``McpRegistryPort``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from platform_contract import McpServerDescriptor

from .registry import InMemoryMcpRegistry, McpServerRecord
from .schema_validator import validate_tool_schemas

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class McpServerRegistrationSpec:
    """Specification for registering a new MCP server connector.

    Carries the data needed to create a ``McpServerRecord``: identity,
    transport, capability/secret references, JSON Schema tool schemas,
    and initial metadata.  The initial version defaults to ``"1.0.0"``.
    """

    server_id: str
    name: str
    transport: str
    capability_refs: list[str] = field(default_factory=list)
    secret_refs: list[str] = field(default_factory=list)
    tool_schemas: list[dict[str, Any]] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
    version: str = "1.0.0"


class McpRegistryAdminPort(Protocol):
    """Write Protocol for MCP connector management.

    All methods return ``McpServerDescriptor`` records.  Registration
    creates inactive records (``active=False``, ``admission_status=
    "pending"``); ``approve_server`` is required before a connector is
    discoverable via ``McpRegistryPort``.
    """

    def register_server(
        self, spec: McpServerRegistrationSpec
    ) -> McpServerDescriptor: ...

    def update_version(
        self,
        server_id: str,
        version: str,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> McpServerDescriptor: ...

    def deactivate_server(self, server_id: str) -> McpServerDescriptor: ...

    def approve_server(self, server_id: str) -> McpServerDescriptor: ...


class InMemoryMcpRegistryAdmin:
    """Concrete admin implementation sharing the registry's ``_records`` dict.

    All write operations modify the ``InMemoryMcpRegistry._records`` dict
    in-place.  The admin port is the only way to mutate registry state;
    ``McpRegistryPort`` remains read-only.
    """

    def __init__(self, registry: InMemoryMcpRegistry) -> None:
        self._registry = registry

    def register_server(
        self, spec: McpServerRegistrationSpec
    ) -> McpServerDescriptor:
        """Register a new MCP server connector.

        Validates tool schemas, creates a record with ``active=False``
        and ``admission_status="pending"``, and returns the descriptor.
        Does NOT invoke the ``mcp`` SDK — no auto-execution.
        """
        errors = validate_tool_schemas(spec.tool_schemas)
        if errors:
            raise ValueError(
                "tool schema validation failed: " + "; ".join(errors)
            )
        record = McpServerRecord(
            server_id=spec.server_id,
            name=spec.name,
            transport=spec.transport,
            capability_refs=list(spec.capability_refs),
            secret_refs=list(spec.secret_refs),
            metadata=dict(spec.metadata),
            active=False,
            version=spec.version,
            admission_status="pending",
            registered_at="",
            tool_schemas=list(spec.tool_schemas),
            version_history=[spec.version],
        )
        self._registry._records[spec.server_id] = record
        return record.to_descriptor()

    def update_version(
        self,
        server_id: str,
        version: str,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> McpServerDescriptor:
        """Update the semantic version of an existing server.

        The new version must be greater than the current version.
        Optionally updates tool schemas (validated before applying).
        """
        record = self._registry._records.get(server_id)
        if record is None:
            raise ValueError(f"server not found: {server_id}")
        if _compare_versions(version, record.version) <= 0:
            raise ValueError(
                f"new version {version} must be greater than "
                f"current version {record.version}"
            )
        if tool_schemas is not None:
            errors = validate_tool_schemas(tool_schemas)
            if errors:
                raise ValueError(
                    "tool schema validation failed: " + "; ".join(errors)
                )
            record.tool_schemas = list(tool_schemas)
        record.version = version
        record.version_history.append(version)
        return record.to_descriptor()

    def deactivate_server(self, server_id: str) -> McpServerDescriptor:
        """Soft-delete a server — marks ``active=False``, does not remove."""
        record = self._registry._records.get(server_id)
        if record is None:
            raise ValueError(f"server not found: {server_id}")
        record.active = False
        return record.to_descriptor()

    def approve_server(self, server_id: str) -> McpServerDescriptor:
        """Approve a pending server — sets ``active=True``, ``admission_status=approved``."""
        record = self._registry._records.get(server_id)
        if record is None:
            raise ValueError(f"server not found: {server_id}")
        if record.admission_status == "approved":
            raise ValueError(f"server already approved: {server_id}")
        if record.admission_status != "pending":
            raise ValueError(
                f"server not pending approval (status={record.admission_status}): {server_id}"
            )
        record.active = True
        record.admission_status = "approved"
        return record.to_descriptor()


def _compare_versions(v1: str, v2: str) -> int:
    """Compare two semantic version strings (major.minor.patch).

    Returns negative if v1 < v2, zero if equal, positive if v1 > v2.
    """
    parts1 = [int(p) for p in v1.split(".")]
    parts2 = [int(p) for p in v2.split(".")]
    # Pad shorter list with zeros
    while len(parts1) < len(parts2):
        parts1.append(0)
    while len(parts2) < len(parts1):
        parts2.append(0)
    for a, b in zip(parts1, parts2):
        if a < b:
            return -1
        if a > b:
            return 1
    return 0


__all__ = [
    "InMemoryMcpRegistryAdmin",
    "McpRegistryAdminPort",
    "McpServerRegistrationSpec",
]
