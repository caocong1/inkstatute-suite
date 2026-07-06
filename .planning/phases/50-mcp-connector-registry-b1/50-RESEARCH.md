# Phase 50: MCP Connector Registry (B1) - Research

**Researched:** 2026-07-06
**Domain:** MCP connector registry, cursor pagination, JSON Schema tool schemas, semantic versioning, soft-delete, router tool-resolution join
**Confidence:** HIGH

## Summary

Phase 50 creates a new `packages/mcp-registry/` package providing a read-only `McpRegistryPort` for discovering MCP tool connectors. The frozen contract surface `McpServerDescriptor` already exists in `platform_contract.events` (lines 116-122) with fields `server_id`, `name`, `transport`, `capability_refs`, `secret_refs`, and `metadata`. The `mcp_registry_enabled` feature flag was already added in Phase 45 (feature_flags.py:29) and defaults to `False`. The router service already joins skill `required_tool_refs` into `RouteDecision.required_tools` at decision time (service.py:65, 131, 163), so the MCP tool-resolution join extends this by resolving `required_tool_refs` → MCP `capability_refs` at read time without modifying frozen `RouteDecision` or `NeutralSkillDescriptor` schemas.

The skill-registry package (`packages/skill-registry/`) provides the closest architectural analog: a read-only `SkillRegistryPort` Protocol with `list_skills`, `get_skill`, `search` methods, backed by an in-memory `SkillRegistry` constructed from pre-loaded descriptors. The MCP registry follows the same pattern but adds cursor pagination on `list_servers` and `search`, plus a registration/administration layer (write port) that supports JSON Schema tool schemas, semantic versioning, and soft-delete. Registration does NOT auto-execute — an admission review step is required before a connector is marked active and discoverable.

**Primary recommendation:** Create `packages/mcp-registry/` following the skill-registry layout (src/inkstatute_mcp_registry/, tests/, pyproject.toml with `dependencies = []`). Define `McpRegistryPort` as a read-only Protocol with `list_servers(cursor, limit)`, `get_server(server_id)`, and `search(query, cursor, limit)` — all returning `McpServerDescriptor` records with opaque cursor pagination. Define `McpRegistryAdminPort` as a separate write Protocol for `register_server`, `update_version`, `deactivate_server`, and `approve_server` (admission review). The `mcp` SDK is lazy-imported only inside methods that need it (transport validation), preserving `dependencies = []`. The router join is a pure function `resolve_tool_refs(skills, mcp_registry)` that maps `required_tool_refs` → `capability_refs` at read time, producing a `ToolResolutionMap` without modifying frozen schemas.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per `workflow.skip_discuss`. All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Claude's Discretion
All implementation choices are at Claude's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCPREG-01 | `McpRegistryPort` implements read-only operations (`list_servers`, `get_server`, `search`) with cursor pagination, returning `McpServerDescriptor` records matching the frozen contract shape | §Architecture Patterns (read-only port pattern from skill-registry), §Code Examples (cursor pagination), §FROZEN Contract Surfaces (McpServerDescriptor) |
| MCPREG-02 | MCP registry supports registration with JSON Schema tool schemas, versioning (semantic version tracking), and soft-delete (connectors marked inactive, not removed); no auto-execution on registration — admission review required before execution | §Architecture Patterns (admin port + admission review), §Code Examples (soft-delete, versioning), §Common Pitfalls (auto-execution) |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.** MCP `secret_refs` are references only, never inline secrets. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it.** `dependencies = []` invariant must be preserved; `mcp` SDK is lazy-imported only inside methods. [VERIFIED: AGENTS.md §Coding Rules, skill-registry pyproject.toml pattern]
- **Keep changes scoped to the active GSD phase and its plan.** [VERIFIED: AGENTS.md §Coding Rules]
- **Add tests before or with behavior changes, especially for schemas, mappers, event ordering, dedupe, and fixture replay.** [VERIFIED: AGENTS.md §Coding Rules]
- **Prefer structured parsers and schema validators over ad hoc string parsing.** JSON Schema validation for tool schemas. [VERIFIED: AGENTS.md §Coding Rules]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MCP server descriptor storage | mcp-registry (InMemoryMcpRegistry) | — | Registry owns connector metadata; in-memory for Phase 50 |
| Read-only discovery (list/get/search) | mcp-registry (McpRegistryPort) | — | Read-only Protocol, structural enforcement (no write methods) |
| Registration + versioning + soft-delete | mcp-registry (McpRegistryAdminPort) | — | Separate write Protocol; admission review gates activation |
| Cursor pagination | mcp-registry | — | Opaque cursor encoding; limit-based page size |
| JSON Schema tool schema validation | mcp-registry | — | Validate tool schemas at registration time |
| Router tool-resolution join | router-service (ToolResolver) | mcp-registry | Pure function joining skill required_tool_refs → MCP capability_refs at read time |
| Feature flag gating | platform-runtime (feature_flags) | — | `mcp_registry_enabled` defaults to False (Phase 45) |

## Standard Stack

### Core

No new external packages are installed. This phase uses only the existing Python standard library and existing project packages.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `json` | 3.14+ | JSON Schema validation (basic structural checks) | Already used throughout [VERIFIED: codebase] |
| Python stdlib `base64` | 3.14+ | Opaque cursor encoding | Standard encoding for pagination cursors |
| `platform-contract` | existing | `McpServerDescriptor`, `NeutralSkillDescriptor`, `RouteDecision` | Frozen contract — no modifications [VERIFIED: events.py:116-122] |
| `platform-runtime` | existing | `RuntimeFeatureFlags`, `require_enabled` | Feature flag gating [VERIFIED: feature_flags.py:29] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `inkstatute_skill_registry` | existing | `SkillRegistryPort`, `NeutralSkillDescriptor` | Router join reads skill required_tool_refs |
| `inkstatute_router_service` | existing | `RouterService`, `RouteDecision` | Tool-resolution join extends router read-time behavior |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-memory registry | SQLite-backed registry | Rejected for Phase 50 — in-memory matches skill-registry pattern; SQLite can be added later without changing the Port |
| Opaque base64 cursor | Offset-based integer pagination | Rejected — opaque cursors are more robust against insertion/deletion changes between pages |
| Separate McpRegistryAdminPort | Single Port with both read and write | Rejected — read-only enforcement is structural when split; matches skill-registry read-only pattern |
| Full JSON Schema validator library | Basic structural validation | Rejected — `dependencies = []` invariant; basic validation (type, required fields) is sufficient for Phase 50 |

**Installation:**
```bash
# No packages to install — this phase uses only existing project packages and Python stdlib
```

**Version verification:** Not applicable — no new packages installed. Python 3.14 confirmed on the target machine.

## Package Legitimacy Audit

> No external packages are installed in this phase. All work uses existing project packages and Python stdlib. The `dependencies = []` invariant on the new `packages/mcp-registry/pyproject.toml` must be preserved. The `mcp` SDK is lazy-imported only inside methods that perform transport validation, never at module top level.

## Architecture Patterns

### System Architecture Diagram

```
Operator (admin)
    │
    ▼
McpRegistryAdminPort.register_server(spec)
    │  [validate JSON Schema tool schemas]
    │  [store as inactive, version=1.0.0]
    │  [NO auto-execution]
    │
    ▼
McpRegistryAdminPort.approve_server(server_id)  ← admission review
    │  [mark active=True]
    │
    ▼
InMemoryMcpRegistry (store)
    │
    ▼
McpRegistryPort.list_servers(cursor, limit)  ← read-only
McpRegistryPort.get_server(server_id)        ← read-only
McpRegistryPort.search(query, cursor, limit) ← read-only
    │  [cursor pagination, returns McpServerDescriptor]
    │  [only active servers returned by default]
    │
    ▼
RouterService (tool-resolution join)
    │  resolve_tool_refs(skills, mcp_registry)
    │  skill.required_tool_refs → mcp.capability_refs
    │
    ▼
ToolResolutionMap (unified, read-time only)
    │  [no modification to RouteDecision or NeutralSkillDescriptor]
```

### Read-Only Port Pattern (from skill-registry)

The skill-registry package defines `SkillRegistryPort` as a Protocol with only read methods (`list_skills`, `get_skill`, `search`). The `McpRegistryPort` follows the same pattern but adds cursor pagination:

```python
class McpRegistryPort(Protocol):
    def list_servers(
        self, cursor: str | None = None, limit: int = 50
    ) -> McpServerPage: ...

    def get_server(self, server_id: str) -> McpServerDescriptor | None: ...

    def search(
        self, query: str, cursor: str | None = None, limit: int = 50
    ) -> McpServerPage: ...
```

`McpServerPage` is a frozen dataclass with `items: list[McpServerDescriptor]`, `next_cursor: str | None`, and `has_more: bool`.

### Cursor Pagination Pattern

Cursors are opaque base64-encoded strings encoding the last seen position. The registry encodes the sort key (server_id) into the cursor:

```python
def _encode_cursor(server_id: str) -> str:
    return base64.urlsafe_b64encode(server_id.encode()).decode()

def _decode_cursor(cursor: str) -> str:
    return base64.urlsafe_b64decode(cursor.encode()).decode()
```

### Soft-Delete Pattern

Servers are never removed from the registry. Deactivation sets `active=False` in the internal record. Read operations (`list_servers`, `search`) only return active servers by default. `get_server` returns the descriptor regardless of active status (for admin audit), but the descriptor's `metadata` includes `active` status.

### Versioning Pattern

Each server record tracks a semantic version string (`"1.0.0"`). When a server is re-registered with changed tool schemas, the version is bumped. The version is stored in `metadata["version"]` on the `McpServerDescriptor` to avoid modifying the frozen dataclass.

### Admission Review Pattern

Registration creates a server record with `active=False` and `admission_status="pending"`. An operator must call `approve_server(server_id)` to set `active=True` and `admission_status="approved"`. Only active servers are discoverable via `McpRegistryPort`. No auto-execution occurs on registration — the MCP SDK is never invoked during registration.

### Router Tool-Resolution Join Pattern

The router already populates `RouteDecision.required_tools` from `NeutralSkillDescriptor.required_tool_refs` (service.py:65, 131, 163). Phase 50 adds a pure function `resolve_tool_refs` that joins skill `required_tool_refs` → MCP server `capability_refs` at read time:

```python
def resolve_tool_refs(
    skills: list[NeutralSkillDescriptor],
    mcp_registry: McpRegistryPort,
) -> ToolResolutionMap:
    """Join skill required_tool_refs to MCP capability_refs at read time."""
```

`ToolResolutionMap` is a frozen dataclass mapping `skill_id → list[McpServerDescriptor]` — the MCP servers that provide the tools required by each skill. This is a read-time join; it does NOT modify `RouteDecision` or `NeutralSkillDescriptor`.

## Code Examples

### McpServerDescriptor (FROZEN — already exists)

```python
@dataclass(frozen=True, slots=True)
class McpServerDescriptor:
    server_id: str
    name: str
    transport: str
    capability_refs: list[str] = field(default_factory=list)
    secret_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```

### McpServerPage (new — pagination envelope)

```python
@dataclass(frozen=True, slots=True)
class McpServerPage:
    items: list[McpServerDescriptor]
    next_cursor: str | None = None
    has_more: bool = False
```

### ToolResolutionMap (new — router join result)

```python
@dataclass(frozen=True, slots=True)
class ToolResolutionMap:
    skill_id: str
    required_tool_refs: list[str]
    resolved_servers: list[McpServerDescriptor]
    unresolved_refs: list[str]  # tool refs with no matching MCP server
```

### Cursor Pagination Implementation

```python
def list_servers(
    self, cursor: str | None = None, limit: int = 50
) -> McpServerPage:
    active = [r for r in self._records.values() if r.active]
    active.sort(key=lambda r: r.server_id)
    start_idx = 0
    if cursor is not None:
        last_id = _decode_cursor(cursor)
        start_idx = next(
            (i for i, r in enumerate(active) if r.server_id > last_id),
            len(active),
        )
    page = active[start_idx:start_idx + limit]
    has_more = start_idx + limit < len(active)
    next_cursor = _encode_cursor(page[-1].server_id) if has_more and page else None
    return McpServerPage(
        items=[r.to_descriptor() for r in page],
        next_cursor=next_cursor,
        has_more=has_more,
    )
```

## FROZEN Contract Surfaces Verified

- `McpServerDescriptor` — 6 fields (server_id, name, transport, capability_refs, secret_refs, metadata) — UNCHANGED [VERIFIED: events.py:116-122]
- `NeutralSkillDescriptor` — 6 fields (skill_id, name, description, input_schema_ref, output_schema_ref, required_tool_refs, metadata) — UNCHANGED [VERIFIED: events.py:105-112]
- `RouteDecision` — 15 fields — UNCHANGED [VERIFIED: events.py:207-222]
- `RuntimeFeatureFlags.mcp_registry_enabled` — defaults to False — UNCHANGED [VERIFIED: feature_flags.py:29]
- `SkillRegistryPort` — 3 read methods — UNCHANGED [VERIFIED: registry.py:16-28]
- `RouterPort` — 1 method (decide) — UNCHANGED [VERIFIED: port.py:15-29]

## Common Pitfalls

1. **Auto-execution on registration** — The MCP SDK must NEVER be invoked during registration. Registration only stores metadata; execution requires a separate admission review + explicit tool call. [VERIFIED: success criterion 2]
2. **Modifying frozen schemas** — `RouteDecision`, `NeutralSkillDescriptor`, and `McpServerDescriptor` must NOT be modified. Versioning data goes in `metadata`. [VERIFIED: success criterion 3, contract freeze tests]
3. **Top-level `mcp` import** — The `mcp` SDK must be lazy-imported only inside methods, never at module top level. `dependencies = []` must be preserved. [VERIFIED: success criterion 4]
4. **Cursor stability** — Cursors must be opaque and stable across insertions. Using server_id as the sort key ensures cursors remain valid even if new servers are added between pages.
5. **Soft-delete vs hard-delete** — Deactivation must mark `active=False`, never remove the record. This preserves audit history. [VERIFIED: success criterion 2]
6. **Read-only enforcement** — `McpRegistryPort` must have NO write methods. Write operations are on `McpRegistryAdminPort` only. Structural enforcement via Protocol method inspection (same pattern as skill-registry test_registry.py:91-99).

## Key Design Decisions

1. **Separate read/write Ports** — `McpRegistryPort` (read-only) and `McpRegistryAdminPort` (write) are separate Protocols. Read-only enforcement is structural (no write methods on the read Port).
2. **Cursor pagination on list and search** — `list_servers` and `search` both accept `cursor` and `limit` parameters, returning `McpServerPage`. `get_server` is a direct lookup (no pagination).
3. **Version in metadata** — Semantic version is stored in `metadata["version"]` on `McpServerDescriptor` to avoid modifying the frozen dataclass.
4. **Active filter on reads** — `list_servers` and `search` only return active servers. `get_server` returns any server (for admin audit) but includes `active` in metadata.
5. **ToolResolutionMap is read-time only** — The router join produces a new data structure; it does NOT modify `RouteDecision` or `NeutralSkillDescriptor`.
6. **`mcp` SDK lazy import** — Transport validation (e.g., checking stdio/SSE transport types) may optionally use the `mcp` SDK via `importlib.import_module("mcp")` inside methods. This is never required for Phase 50 functionality.
7. **In-memory store** — Phase 50 uses an in-memory store (`InMemoryMcpRegistry`), matching the skill-registry pattern. SQLite can be added later without changing the Port interface.
