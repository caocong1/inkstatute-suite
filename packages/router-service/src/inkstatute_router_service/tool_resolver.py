"""Router tool-resolution join — skill required_tool_refs → MCP capability_refs.

Provides a pure ``resolve_tool_refs`` function that joins
``NeutralSkillDescriptor.required_tool_refs`` to MCP server
``capability_refs`` at read time, producing a ``ToolResolutionMap``
without modifying frozen ``RouteDecision`` or ``NeutralSkillDescriptor``
schemas.

The join is read-time only: it reads from the MCP registry and produces
a new data structure.  No inputs are mutated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from platform_contract import McpServerDescriptor, NeutralSkillDescriptor

if TYPE_CHECKING:
    from inkstatute_mcp_registry import McpRegistryPort


@dataclass(frozen=True, slots=True)
class ToolResolutionMap:
    """Result of joining a skill's required_tool_refs to MCP servers.

    Maps a single skill's required tool references to the MCP servers
    that provide them.  ``unresolved_refs`` lists tool refs that have
    no matching MCP server.
    """

    skill_id: str
    required_tool_refs: list[str] = field(default_factory=list)
    resolved_servers: list[McpServerDescriptor] = field(default_factory=list)
    unresolved_refs: list[str] = field(default_factory=list)


class _McpRegistryLike(Protocol):
    """Structural protocol for the MCP registry read interface.

    This avoids a hard runtime dependency on the mcp-registry package.
    Any object with a ``search(query, cursor, limit)`` method returning
    an object with an ``items`` list satisfies this protocol.
    """

    def search(
        self,
        query: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> object: ...


def resolve_tool_refs(
    skill: NeutralSkillDescriptor,
    mcp_registry: _McpRegistryLike,
) -> ToolResolutionMap:
    """Join a skill's required_tool_refs to MCP capability_refs at read time.

    For each tool ref in ``skill.required_tool_refs``, searches the MCP
    registry for active servers whose ``capability_refs`` contain the
    tool ref.  Matching servers are collected and deduplicated by
    ``server_id``.  Tool refs with no matching server are listed in
    ``unresolved_refs``.

    This function is pure — it does NOT modify ``skill`` or any
    ``RouteDecision``.  It produces a new ``ToolResolutionMap``.
    """
    resolved: list[McpServerDescriptor] = []
    seen_server_ids: set[str] = set()
    unresolved: list[str] = []

    for tool_ref in skill.required_tool_refs:
        page = mcp_registry.search(tool_ref, limit=100)
        items = getattr(page, "items", [])
        found = False
        for server in items:
            if server.server_id not in seen_server_ids:
                seen_server_ids.add(server.server_id)
                resolved.append(server)
            found = True
        if not found:
            unresolved.append(tool_ref)

    return ToolResolutionMap(
        skill_id=skill.skill_id,
        required_tool_refs=list(skill.required_tool_refs),
        resolved_servers=resolved,
        unresolved_refs=unresolved,
    )


def resolve_all_tool_refs(
    skills: list[NeutralSkillDescriptor],
    mcp_registry: _McpRegistryLike,
) -> list[ToolResolutionMap]:
    """Resolve tool refs for multiple skills in a single call.

    Calls ``resolve_tool_refs`` for each skill and returns a list of
    ``ToolResolutionMap`` entries, one per skill.
    """
    return [
        resolve_tool_refs(skill, mcp_registry) for skill in skills
    ]


__all__ = [
    "ToolResolutionMap",
    "resolve_all_tool_refs",
    "resolve_tool_refs",
]
