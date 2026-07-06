"""Read-only MCP Connector Registry with cursor pagination.

Defines ``McpRegistryPort`` (read-only Protocol), ``McpServerPage``
(pagination envelope), ``McpServerRecord`` (internal mutable record),
and ``InMemoryMcpRegistry`` (concrete implementation).

The registry is read-only by structural enforcement: ``McpRegistryPort``
exposes only ``list_servers``, ``get_server``, and ``search`` — no write
methods.  Write operations (registration, versioning, soft-delete,
admission review) are on the separate ``McpRegistryAdminPort`` defined
in ``admin.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from platform_contract import McpServerDescriptor

from .cursor import decode_cursor, encode_cursor

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class McpServerPage:
    """A page of MCP server descriptors with cursor pagination metadata."""

    items: list[McpServerDescriptor]
    next_cursor: str | None = None
    has_more: bool = False


@dataclass(slots=True)
class McpServerRecord:
    """Internal mutable record for an MCP server connector.

    Stores administration state (active, version, admission_status) that
    is not part of the frozen ``McpServerDescriptor`` contract.  The
    ``to_descriptor()`` method maps this record to a
    ``McpServerDescriptor``, placing admin fields into ``metadata``.
    """

    server_id: str
    name: str
    transport: str
    capability_refs: list[str] = field(default_factory=list)
    secret_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
    active: bool = False
    version: str = "1.0.0"
    admission_status: str = "pending"
    registered_at: str = ""
    tool_schemas: list[dict[str, Any]] = field(default_factory=list)
    version_history: list[str] = field(default_factory=list)

    def to_descriptor(self) -> McpServerDescriptor:
        """Convert this record to a frozen ``McpServerDescriptor``.

        Administration fields (``version``, ``active``,
        ``admission_status``, ``registered_at``) are placed into
        ``metadata`` to avoid modifying the frozen contract dataclass.
        """
        merged_metadata: JsonObject = dict(self.metadata)
        merged_metadata["version"] = self.version
        merged_metadata["active"] = self.active
        merged_metadata["admission_status"] = self.admission_status
        merged_metadata["registered_at"] = self.registered_at
        return McpServerDescriptor(
            server_id=self.server_id,
            name=self.name,
            transport=self.transport,
            capability_refs=list(self.capability_refs),
            secret_refs=list(self.secret_refs),
            metadata=merged_metadata,
        )


class McpRegistryPort(Protocol):
    """Read-only MCP Registry protocol — no write methods.

    All read operations return ``McpServerDescriptor`` records matching
    the frozen contract shape.  ``list_servers`` and ``search`` use
    cursor pagination; ``get_server`` is a direct lookup.
    """

    def list_servers(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> McpServerPage: ...

    def get_server(self, server_id: str) -> McpServerDescriptor | None: ...

    def search(
        self,
        query: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> McpServerPage: ...


class InMemoryMcpRegistry:
    """Concrete read-only MCP Registry backed by an in-memory dict.

    The registry stores ``McpServerRecord`` instances internally and
    exposes only read methods via the ``McpRegistryPort`` Protocol.
    Write operations are performed through ``InMemoryMcpRegistryAdmin``
    (defined in ``admin.py``), which shares the same ``_records`` dict.

    Only active servers are returned by ``list_servers`` and ``search``.
    ``get_server`` returns any server (active or inactive) for admin
    audit purposes.
    """

    def __init__(
        self,
        records: list[McpServerRecord] | None = None,
    ) -> None:
        self._records: dict[str, McpServerRecord] = {}
        if records is not None:
            for record in records:
                self._records[record.server_id] = record

    def list_servers(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> McpServerPage:
        """List active servers with cursor pagination, sorted by server_id."""
        active = sorted(
            (r for r in self._records.values() if r.active),
            key=lambda r: r.server_id,
        )
        return _paginate(active, cursor, limit)

    def get_server(self, server_id: str) -> McpServerDescriptor | None:
        """Return the descriptor for *server_id*, or ``None`` if not found.

        Returns any server (active or inactive) — used for admin audit.
        """
        record = self._records.get(server_id)
        if record is None:
            return None
        return record.to_descriptor()

    def search(
        self,
        query: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> McpServerPage:
        """Search active servers by case-insensitive substring match.

        Matches against ``server_id``, ``name``, and ``capability_refs``.
        Results are sorted by ``server_id`` and paginated via cursor.
        """
        needle = query.lower()
        active = sorted(
            (r for r in self._records.values() if r.active),
            key=lambda r: r.server_id,
        )
        matched = [
            r
            for r in active
            if needle in r.server_id.lower()
            or needle in r.name.lower()
            or any(needle in cap.lower() for cap in r.capability_refs)
        ]
        return _paginate(matched, cursor, limit)


def _paginate(
    records: list[McpServerRecord],
    cursor: str | None,
    limit: int,
) -> McpServerPage:
    """Apply cursor pagination to a sorted list of records."""
    start_idx = 0
    if cursor is not None:
        last_id = decode_cursor(cursor)
        start_idx = next(
            (i for i, r in enumerate(records) if r.server_id > last_id),
            len(records),
        )
    page = records[start_idx : start_idx + limit]
    has_more = start_idx + limit < len(records)
    next_cursor = (
        encode_cursor(page[-1].server_id) if has_more and page else None
    )
    return McpServerPage(
        items=[r.to_descriptor() for r in page],
        next_cursor=next_cursor,
        has_more=has_more,
    )


__all__ = [
    "InMemoryMcpRegistry",
    "McpRegistryPort",
    "McpServerPage",
    "McpServerRecord",
]
