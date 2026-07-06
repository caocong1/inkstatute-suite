# Plan 50-01 Summary: McpRegistryPort with Cursor Pagination

## Objective

Create the `packages/mcp-registry/` package with a read-only `McpRegistryPort` Protocol implementing `list_servers`, `get_server`, and `search` with cursor pagination, returning `McpServerDescriptor` records matching the frozen contract shape.

## Tasks Completed

### Task 1: Create packages/mcp-registry/ package scaffold with pyproject.toml

**Files modified:**
- `packages/mcp-registry/pyproject.toml` — Created with `name="inkstatute-mcp-registry"`, `dependencies=[]`, `requires-python=">=3.11"`, `[tool.inkstatute]` section with `subsystem="mcp-registry"` and `default_off_flag="mcp_registry_enabled"`.
- `packages/mcp-registry/src/inkstatute_mcp_registry/__init__.py` — Re-exports McpRegistryPort, McpRegistry, McpServerPage, InMemoryMcpRegistry, McpServerRecord, cursor helpers, admin port, and schema validator.

**Commit:** `0e27e3c` — `feat(50-01): mcp-registry package with McpRegistryPort, cursor pagination, read-only enforcement`

### Task 2: Cursor pagination helpers

**Files modified:**
- `packages/mcp-registry/src/inkstatute_mcp_registry/cursor.py` — `encode_cursor(server_id)` and `decode_cursor(cursor)` using base64 urlsafe encoding.
- `packages/mcp-registry/tests/test_cursor.py` — 4 tests: round-trip, non-empty, opaque, invalid cursor raises.

### Task 3: McpRegistryPort Protocol, McpServerPage, McpServerRecord, and InMemoryMcpRegistry

**Files modified:**
- `packages/mcp-registry/src/inkstatute_mcp_registry/registry.py` — `McpServerPage` (frozen dataclass: items, next_cursor, has_more), `McpServerRecord` (mutable internal record with to_descriptor()), `McpRegistryPort` Protocol (3 read methods), `InMemoryMcpRegistry` (concrete implementation with cursor pagination, active-only filtering, sorted-by-server_id).
- `packages/mcp-registry/tests/test_registry_read.py` — 21 tests covering list_servers, get_server, search, pagination, cursor stability, metadata, frozen dataclass.
- `packages/mcp-registry/tests/test_read_only_enforcement.py` — 3 tests enforcing read-only behavior (no write methods on Port, exactly 3 read methods, no public write methods on InMemoryMcpRegistry).

### Task 4: Add mcp-registry gate to V2 gate script

**Files modified:**
- `scripts/run_v2_gates.py` — Added `mcp_registry_src` path variable, new "mcp-registry" gate, added mcp_registry_src to router-service and contract-test-suite PYTHONPATH, added `packages/mcp-registry/src` to compileall.

## Deviations

- **[Non-blocking]** The `__init__.py` imports from `.admin` and `.schema_validator` which were created in Plan 01 rather than Plan 02 to avoid import errors. The admin and schema_validator modules are fully implemented but their tests are in Plan 02.
- **[Non-blocking]** Duplicate truncated-name files were created by the file system and removed in a follow-up commit `6cbff9a`.

## Test Results

- **mcp-registry package tests:** 25 tests pass
  - `python3 -m unittest discover -s packages/mcp-registry/tests -v` — OK

## FROZEN Contract Surfaces Verified

- `McpServerDescriptor` — 6 fields (unchanged)
- `mcp_registry_enabled` — defaults to False (unchanged, Phase 45)
- `dependencies = []` invariant preserved — no external imports at module top level

## Key Design Decisions

1. **Opaque base64 cursor** — Cursors encode the last seen server_id using base64 urlsafe encoding, ensuring stability across insertions.
2. **Active-only filtering on list/search** — `list_servers` and `search` return only active servers; `get_server` returns any server for admin audit.
3. **Metadata carries admin state** — Version, active, admission_status, and registered_at are stored in `McpServerDescriptor.metadata` to avoid modifying the frozen dataclass.
4. **Structural read-only enforcement** — `McpRegistryPort` has exactly 3 public methods (list_servers, get_server, search), none with write prefixes.
