# Plan 50-02 Summary: Registration with JSON Schema Tool Schemas + Admission Review

## Objective

Add `McpRegistryAdminPort` (write Protocol) and `InMemoryMcpRegistryAdmin` (implementation) to the mcp-registry package, supporting registration with JSON Schema tool schemas, semantic versioning, soft-delete, and admission review. No auto-execution occurs on registration — the `mcp` SDK is never invoked during registration. This satisfies MCPREG-02.

## Tasks Completed

### Task 1: JSON Schema tool schema validator

**Files modified:**
- `packages/mcp-registry/src/inkstatute_mcp_registry/schema_validator.py` — `validate_tool_schema(schema: dict) -> list[str]` and `validate_tool_schemas(schemas: list[dict]) -> list[str]` performing basic structural validation (name required, input_schema dict with `type` key, description optional). No external JSON Schema library imported.
- `packages/mcp-registry/tests/test_schema_validator.py` — 9 tests: valid schema, valid without description, missing name, missing input_schema, input_schema missing type, empty schema list, multiple schemas aggregate errors, schema not dict.

### Task 2: McpRegistryAdminPort, McpServerRegistrationSpec, and InMemoryMcpRegistryAdmin

**Files modified:**
- `packages/mcp-registry/src/inkstatute_mcp_registry/admin.py` — `McpServerRegistrationSpec` (frozen dataclass, version defaults to `"1.0.0"`), `McpRegistryAdminPort` Protocol (4 write methods: register_server, update_version, deactivate_server, approve_server), `InMemoryMcpRegistryAdmin` sharing the registry's `_records` dict, `_compare_versions` semantic-version helper. Registration validates tool schemas, creates records with `active=False` / `admission_status="pending"`, and never invokes the `mcp` SDK.
- `packages/mcp-registry/src/inkstatute_mcp_registry/__init__.py` — Re-exports `McpRegistryAdminPort`, `McpServerRegistrationSpec`, `InMemoryMcpRegistryAdmin`, `validate_tool_schema`, `validate_tool_schemas`.
- `packages/mcp-registry/tests/test_admin.py` — 22 tests covering registration (inactive/pending, schema validation, no auto-execution, descriptor return), approval (sets active, already-approved raises, unknown raises), soft-delete (active=False, record retained, idempotent), version bump (greater version, lower raises, equal raises, optional tool_schemas update, version history tracking).

**Commit:** `6ddca3d` — `feat(50-02): registration with JSON Schema tool schemas, versioning, soft-delete, admission review`

## Deviations

- **[Non-blocking]** The `admin.py` and `schema_validator.py` source modules were committed in Plan 01 (`0e27e3c`) to avoid import errors from `__init__.py` re-exports. The test files (`test_admin.py`, `test_schema_validator.py`) were committed in Plan 02 (`6ddca3d`). All Plan 02 behavior is fully tested; only the commit boundary differs from the plan.
- **[Non-blocking]** `validate_tool_schemas` prefixes each error with `tool[i]:` for traceability, a minor enhancement over the plan's error message wording.

## Test Results

- **test_schema_validator.py:** 9 tests pass
- **test_admin.py:** 22 tests pass
- **mcp-registry package total:** 56 tests pass
  - `PYTHONPATH="packages/mcp-registry/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest discover -s packages/mcp-registry/tests` — OK

## FROZEN Contract Surfaces Verified

- `McpServerDescriptor` — 6 fields (unchanged); admin state carried in `metadata`
- `mcp_registry_enabled` — defaults to False (unchanged, Phase 45)
- `dependencies = []` invariant preserved — no external imports at module top level; `mcp` SDK never imported during registration

## Key Design Decisions

1. **No auto-execution on registration** — `register_server` validates schemas and stores a record only; the `mcp` SDK is never imported or invoked. Admission review (`approve_server`) is a separate, explicit step before a connector becomes discoverable via `McpRegistryPort`.
2. **Soft-delete, not removal** — `deactivate_server` sets `active=False` but retains the record so `get_server` still returns it for admin audit.
3. **Semantic version enforcement** — `update_version` rejects versions that are not strictly greater than the current version; `version_history` tracks the full version lineage.
4. **Shared store** — `InMemoryMcpRegistryAdmin` mutates the same `_records` dict as `InMemoryMcpRegistry`, keeping `McpRegistryPort` structurally read-only while allowing admin writes through a separate port.
