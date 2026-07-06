# Plan 50-03 Summary: Router Tool-Resolution Join

## Objective

Add a pure `resolve_tool_refs` function to the router-service package that joins skill `required_tool_refs` → MCP server `capability_refs` at read time, producing a `ToolResolutionMap` without modifying frozen `RouteDecision` or `NeutralSkillDescriptor` schemas. This satisfies success criterion 3.

## Tasks Completed

### Task 1: ToolResolutionMap and resolve_tool_refs function

**Files modified:**
- `packages/router-service/src/inkstatute_router_service/tool_resolver.py` — `ToolResolutionMap` (frozen dataclass: skill_id, required_tool_refs, resolved_servers, unresolved_refs), `resolve_tool_refs(skill, mcp_registry) -> ToolResolutionMap` (searches the MCP registry per tool ref, deduplicates resolved servers by server_id, collects unresolved refs), `resolve_all_tool_refs(skills, mcp_registry) -> list[ToolResolutionMap]`. Uses `TYPE_CHECKING` import for `McpRegistryPort` and a structural `_McpRegistryLike` Protocol to avoid a hard runtime dependency on the mcp-registry package.
- `packages/router-service/src/inkstatute_router_service/__init__.py` — Re-exports `resolve_tool_refs`, `resolve_all_tool_refs`, `ToolResolutionMap` from `.tool_resolver`; added to `__all__`.
- `packages/router-service/tests/test_tool_resolver.py` — 12 tests: all resolved, none resolved, partial, no required tools, deduplication, skill not mutated, multiple skills, empty skills, frozen dataclass, empty registry, plus a fake `McpRegistryPort` implementing the Protocol interface.
- `scripts/run_v2_gates.py` — `mcp_registry_src` added to the router-service gate's PYTHONPATH so router-service tests can import the mcp-registry package.

**Commit:** `95ed6a1` — `feat(50-03): router tool-resolution join (skill required_tool_refs → MCP capability_refs)`

## Deviations

- None. All must-haves from the plan frontmatter are satisfied.

## Test Results

- **test_tool_resolver.py:** 12 tests pass
- **router-service package total:** 45 tests pass (all existing router-service tests remain green)
  - `PYTHONPATH="packages/router-service/src:packages/mcp-registry/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest discover -s packages/router-service/tests` — OK
- **V2 gate suite:** router-service gate and mcp-registry gate both report `OK`.

## FROZEN Contract Surfaces Verified

- `NeutralSkillDescriptor` — unchanged; `resolve_tool_refs` reads `required_tool_refs` without mutation
- `RouteDecision` — unchanged; not referenced or modified by the tool resolver
- `McpServerDescriptor` — unchanged; consumed read-only as `resolved_servers` entries
- `McpRegistryPort` — unchanged; consumed read-only via structural Protocol

## Key Design Decisions

1. **Read-time join only** — `resolve_tool_refs` is a pure function: it reads the MCP registry and produces a new `ToolResolutionMap`. No inputs (`skill`, `RouteDecision`, registry state) are mutated.
2. **Structural Protocol over hard dependency** — A `_McpRegistryLike` Protocol and `TYPE_CHECKING` import for `McpRegistryPort` keep the router-service package free of a runtime dependency on mcp-registry. Any object with a `search(query, cursor, limit)` method returning an object with an `items` list satisfies the interface.
3. **Deduplication by server_id** — When multiple tool refs resolve to the same MCP server, the server appears only once in `resolved_servers`.
4. **Unresolved refs surfaced** — Tool refs with no matching active server are collected in `unresolved_refs` so callers can report coverage gaps without a second pass.
