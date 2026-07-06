# Phase 50: MCP Connector Registry (B1) - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can register and discover MCP tool connectors via a read-only `McpRegistryPort` in a new `packages/mcp-registry/` package, with cursor pagination, JSON Schema tool schemas, versioning, soft-delete, and router tool-resolution joining skill `required_tool_refs` to MCP `capability_refs` at read time.

**Depends on:** Phase 45
**Requirements:** MCPREG-01, MCPREG-02

**Success Criteria** (what must be TRUE):
1. `McpRegistryPort` implements read-only operations (`list_servers`, `get_server`, `search`) with cursor pagination, returning `McpServerDescriptor` records matching the frozen contract shape.
2. MCP registry supports registration with JSON Schema tool schemas, versioning (semantic version tracking), and soft-delete (connectors marked inactive, not removed); no auto-execution on registration — admission review required before execution.
3. Router joins skill `required_tool_refs` → MCP server `capability_refs` at read time, producing a unified tool-resolution map without modifying frozen `RouteDecision` or `NeutralSkillDescriptor` schemas.
4. `mcp_registry_enabled` defaults to `False`; the package uses optional `mcp` SDK lazy import with `dependencies = []` invariant preserved.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
