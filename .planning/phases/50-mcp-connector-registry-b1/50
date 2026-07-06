---
phase: 50-mcp-connector-registry-b1
verified: 2026-07-06T09:34:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 50: MCP Connector Registry (B1) Verification Report

**Phase Goal:** Operator can register and discover MCP tool connectors via a read-only `McpRegistryPort` in a new `packages/mcp-registry/` package, with cursor pagination, JSON Schema tool schemas, versioning, soft-delete, and router tool-resolution joining skill `required_tool_refs` to MCP `capability_refs` at read time.
**Verified:** 2026-07-06T09:34:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Roadmap Success Criteria are the non-negotiable contract; PLAN frontmatter must-haves add plan-specific detail. Both are merged below.

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | `McpRegistryPort` implements read-only operations (`list_servers`, `get_server`, `search`) with cursor pagination, returning `McpServerDescriptor` records matching the frozen contract shape | ✓ VERIFIED | `packages/mcp-registry/src/inkstatute_mcp_registry/registry.py:80-101` defines `McpRegistryPort` Protocol with exactly 3 read methods. `InMemoryMcpRegistry` (lines 104-171) implements `list_servers` (active-only, sorted by server_id, cursor pagination), `get_server` (any server, returns descriptor or None), `search` (active-only, case-insensitive substring on server_id/name/capability_refs). `McpServerPage` (lines 26-32) is a frozen dataclass with `items`, `next_cursor`, `has_more`. `McpServerRecord.to_descriptor()` (lines 58-77) produces a `McpServerDescriptor` with admin state in `metadata`. `test_registry_read.py` (21 tests) + `test_read_only_enforcement.py` (3 tests) pass. |
| 2 | MCP registry supports registration with JSON Schema tool schemas, versioning (semantic version tracking), and soft-delete (connectors marked inactive, not removed); no auto-execution on registration — admission review required before execution | ✓ VERIFIED | `packages/mcp-registry/src/inkstatute_mcp_registry/admin.py:46-68` defines `McpRegistryAdminPort` with 4 write methods. `register_server` (lines 82-111) validates tool schemas via `validate_tool_schemas`, creates records with `active=False` / `admission_status="pending"`, and never invokes the `mcp` SDK. `update_version` (lines 113-141) enforces strictly-greater semantic versions and tracks `version_history`. `deactivate_server` (lines 143-149) sets `active=False` without removing the record. `approve_server` (lines 151-164) sets `active=True` / `admission_status="approved"` and rejects already-approved or non-pending servers. `schema_validator.py` performs basic structural validation (name, input_schema with type) with no external library. `test_admin.py` (22 tests) + `test_schema_validator.py` (9 tests) pass, including `test_register_server_no_auto_execution`. |
| 3 | Router joins skill `required_tool_refs` → MCP server `capability_refs` at read time, producing a unified tool-resolution map without modifying frozen `RouteDecision` or `NeutralSkillDescriptor` schemas | ✓ VERIFIED | `packages/router-service/src/inkstatute_router_service/tool_resolver.py:24-36` defines `ToolResolutionMap` (frozen dataclass: skill_id, required_tool_refs, resolved_servers, unresolved_refs). `resolve_tool_refs` (lines 55-91) iterates `skill.required_tool_refs`, calls `mcp_registry.search(tool_ref)` per ref, deduplicates resolved servers by `server_id`, and collects unresolved refs — pure function, no mutation of `skill` or `RouteDecision`. `resolve_all_tool_refs` (lines 94-105) resolves multiple skills. `__init__.py` (line 11) exports all three symbols. `test_tool_resolver.py` (12 tests) pass, including `test_resolve_tool_refs_does_not_modify_skill` and `test_tool_resolution_map_is_frozen`. `NeutralSkillDescriptor` and `RouteDecision` schemas unchanged. |
| 4 | `mcp_registry_enabled` defaults to `False`; the package uses optional `mcp` SDK lazy import with `dependencies = []` invariant preserved | ✓ VERIFIED | `packages/platform-runtime/src/platform_runtime/feature_flags.py:29` defines `mcp_registry_enabled: bool = False`. `packages/mcp-registry/pyproject.toml:10` has `dependencies = []` and `default_off_flag = "mcp_registry_enabled"` (line 17). No top-level `mcp` SDK import in any module (`registry.py`, `admin.py`, `schema_validator.py`, `cursor.py`, `__init__.py` import only stdlib + `platform_contract` + relative). `tool_resolver.py` uses `TYPE_CHECKING` for `McpRegistryPort` and a structural `_McpRegistryLike` Protocol — no runtime dependency on mcp-registry. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `packages/mcp-registry/pyproject.toml` | `dependencies=[]`, `default_off_flag="mcp_registry_enabled"` | ✓ VERIFIED | lines 6-17 |
| `packages/mcp-registry/src/inkstatute_mcp_registry/__init__.py` | Re-exports read port, admin port, cursor helpers, schema validator | ✓ VERIFIED | lines 9-35 |
| `packages/mcp-registry/src/inkstatute_mcp_registry/registry.py` | `McpRegistryPort`, `McpServerPage`, `McpServerRecord`, `InMemoryMcpRegistry` | ✓ VERIFIED | lines 26-204 |
| `packages/mcp-registry/src/inkstatute_mcp_registry/cursor.py` | `encode_cursor` / `decode_cursor` base64 urlsafe | ✓ VERIFIED | 4 tests pass |
| `packages/mcp-registry/src/inkstatute_mcp_registry/admin.py` | `McpRegistryAdminPort`, `McpServerRegistrationSpec`, `InMemoryMcpRegistryAdmin` | ✓ VERIFIED | lines 27-191 |
| `packages/mcp-registry/src/inkstatute_mcp_registry/schema_validator.py` | `validate_tool_schema` / `validate_tool_schemas` | ✓ VERIFIED | lines 13-55 |
| `packages/mcp-registry/tests/test_cursor.py` | Cursor round-trip / opacity tests | ✓ VERIFIED | 4 tests pass |
| `packages/mcp-registry/tests/test_registry_read.py` | Read + pagination tests | ✓ VERIFIED | 21 tests pass |
| `packages/mcp-registry/tests/test_read_only_enforcement.py` | Read-only structural enforcement | ✓ VERIFIED | 3 tests pass |
| `packages/mcp-registry/tests/test_admin.py` | Registration / versioning / soft-delete / admission tests | ✓ VERIFIED | 22 tests pass |
| `packages/mcp-registry/tests/test_schema_validator.py` | JSON Schema validation tests | ✓ VERIFIED | 9 tests pass |
| `packages/router-service/src/inkstatute_router_service/tool_resolver.py` | `ToolResolutionMap`, `resolve_tool_refs`, `resolve_all_tool_refs` | ✓ VERIFIED | lines 24-112 |
| `packages/router-service/src/inkstatute_router_service/__init__.py` | Exports tool-resolution symbols | ✓ VERIFIED | line 11, `__all__` lines 13-21 |
| `packages/router-service/tests/test_tool_resolver.py` | Tool-resolution join tests | ✓ VERIFIED | 12 tests pass |
| `scripts/run_v2_gates.py` | mcp-registry gate + router-service PYTHONPATH includes mcp-registry | ✓ VERIFIED | mcp-registry gate `OK`, router-service gate `OK` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `NeutralSkillDescriptor.required_tool_refs` | `McpServerDescriptor.capability_refs` | `resolve_tool_refs` → `mcp_registry.search(tool_ref)` | ✓ VERIFIED | `tool_resolver.py:74-84`; `test_resolve_tool_refs_all_resolved` / `test_resolve_tool_refs_partial` pass |
| `McpRegistryAdminPort.register_server` | `McpRegistryPort.list_servers`/`search` (active-only) | shared `_records` dict; `approve_server` flips `active=True` | ✓ VERIFIED | `admin.py:110` writes to `registry._records`; `registry.py:132-133` filters `r.active`; `test_approve_server_sets_active` + `test_list_servers_returns_active_only` pass |
| `mcp_registry_enabled` flag | mcp-registry package activation | `feature_flags.py` default `False` + `pyproject.toml` `default_off_flag` | ✓ VERIFIED | `feature_flags.py:29`, `pyproject.toml:17` |

## Test Results Summary

| Suite | Tests | Result |
| ----- | ----- | ------ |
| mcp-registry package (`test_cursor`, `test_registry_read`, `test_read_only_enforcement`, `test_admin`, `test_schema_validator`) | 56 | OK |
| router-service package (incl. `test_tool_resolver`) | 45 | OK |
| V2 gate: mcp-registry | — | OK |
| V2 gate: router-service | — | OK |

Note: `scripts/run_v2_gates.py` reports pre-existing failures in the `admin-console-api` gate (`ModuleNotFoundError: No module named 'rbac'`) that are unrelated to Phase 50 and were present before this phase. All Phase 50-relevant gates (mcp-registry, router-service, platform-contract, platform-runtime) pass.

## FROZEN Contract Surfaces Verified

- `McpServerDescriptor` — 6 fields, unchanged; admin state carried in `metadata`
- `NeutralSkillDescriptor` — unchanged; read-only by `resolve_tool_refs`
- `RouteDecision` — unchanged; not referenced by tool resolver
- `McpRegistryPort` — new read-only Protocol (3 methods); no frozen surface modified
- `mcp_registry_enabled` — defaults to `False` (Phase 45 invariant preserved)
- `dependencies = []` invariant preserved in `packages/mcp-registry/pyproject.toml`

## Deviations

- **[Non-blocking]** `admin.py` and `schema_validator.py` source modules were committed in Plan 01 (`0e27e3c`) rather than Plan 02 to avoid `__init__.py` import errors; their tests were committed in Plan 02 (`6ddca3d`). All Plan 02 behavior is fully tested.
- **[Non-blocking]** Duplicate truncated-name files created by an OOM-killed subagent were removed in follow-up commit `6cbff9a`.

## Conclusion

All 4 roadmap success criteria are verified. Phase 50 is complete.
