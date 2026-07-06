# Plan 56-01 Summary: TenantScopeResolver, TenantGuard, and Tenant-Scoped Stores

## Objective

Create the core multi-tenant isolation primitives in `packages/platform-runtime/`: `TenantScopeResolver` (resolves `tenant_id` from request context via priority chain), `TenantGuard` (enforces `tenant_id` filter on every query when enabled), `TenantScopedContractLogStore` (partitions contract logs by tenant path), and `TenantNamespacedCache` (namespaces cache keys by tenant). All components are opt-in via `multi_tenant_enabled` and default to v1.6 behavior when disabled.

## Tasks Completed

### Task 1: TenantScopeResolver + TenantGuard + ScopedQueryFilter

**Files modified:**
- `packages/platform-runtime/src/platform_runtime/tenant_scope.py` — Created `TenantScope` (frozen dataclass with `tenant_id`, `workspace_id`, `is_resolved` property, `partition_path` property, `NONE` sentinel), `ScopedQueryFilter` (frozen dataclass with `tenant_id`, `workspace_id`, `active`, `disabled()` classmethod, `is_active` property), `TenantScopeError` (RuntimeError), `TenantScopeRequestContext` (frozen dataclass carrying optional resolution inputs), `TenantScopeResolver` (priority chain: identity > scope > request > headers), `TenantGuard` (enforce method returning active filter or raising TenantScopeError).
- `packages/platform-runtime/src/platform_runtime/__init__.py` — Added imports and exports for all 6 new names.
- `packages/platform-runtime/tests/test_tenant_scope.py` — 25 tests: TenantScope (7), ScopedQueryFilter (3), TenantScopeResolver (10), TenantGuard (5).

**Commit:** `67751cc` — `feat(56-01): add TenantScopeResolver, TenantGuard, and tenant-scoped stores`

### Task 2: TenantScopedContractLogStore — partitioned contract logs

**Files modified:**
- `packages/platform-runtime/src/platform_runtime/tenant_contract_log.py` — Created `TenantScopedContractLogStore` wrapping a `ContractLogStore` delegate. When enabled, `append()` injects `tenant_id`/`workspace_id`/`_tenant_partition` into event metadata; `entries()`/`entries_for_run()` filter by tenant. When disabled, delegates directly (v1.6 behavior). Raises `TenantScopeError` when enabled but scope is unresolved.
- `packages/platform-runtime/tests/test_tenant_contract_log.py` — 17 tests: disabled mode (3), enabled mode (14 including cross-tenant leakage test).

### Task 3: TenantNamespacedCache — namespaced cache keys

**Files modified:**
- `packages/platform-runtime/src/platform_runtime/tenant_cache.py` — Created `TenantNamespacedCache` with `get`/`set`/`delete`/`keys`/`clear` methods. When enabled, keys are prefixed with `tenant:{tenant_id}:`. When disabled, no prefix (v1.6 behavior). Raises `TenantScopeError` when enabled but scope is unresolved.
- `packages/platform-runtime/tests/test_tenant_cache.py` — 14 tests: disabled mode (4), enabled mode (10 including cross-tenant leakage test).

## Deviations

- **TenantScope.NONE**: The plan specified `TenantScope.NONE` as a class-level sentinel. Python 3.11+ removed `@classmethod @property` combination, so `NONE` is set as a class attribute after the frozen dataclass definition (`TenantScope.NONE = _NONE_SCOPE`). This preserves the `TenantScope.NONE` access pattern without API change.
- **Header case-insensitivity**: The resolver performs case-insensitive header lookup for `X-Tenant-Id` (checking `key.lower() == "x-tenant-id"`), which is an implementation detail not explicitly in the plan but follows HTTP header semantics.

## Test Results

- **Plan 01 tests:** 56 tests pass
  - `test_tenant_scope.py` — 25 tests OK
  - `test_tenant_contract_log.py` — 17 tests OK
  - `test_tenant_cache.py` — 14 tests OK

## FROZEN Contract Surfaces Verified

- BackendAdapter: 9 methods (unchanged)
- ChannelAdapter: 6 methods (unchanged)
- RunRequest: `tenant_id`/`workspace_id` fields already existed (unchanged)
- SessionScope: `tenant_id`/`workspace_id` fields already existed (unchanged)
- ContractLogStore Protocol: 1 method (unchanged — `TenantScopedContractLogStore` is a wrapper)
- RuntimeFeatureFlags: `multi_tenant_enabled` already existed (unchanged)
- `dependencies = []` invariant preserved — stdlib + existing project packages only

## Key Design Decisions

1. **Priority chain for tenant resolution** — Auth token claims (identity) > channel metadata (scope) > request metadata (request) > explicit header (`X-Tenant-Id`). Security principle: authenticated identity is more trustworthy than request metadata.
2. **TenantScope.NONE as class attribute** — Set after frozen dataclass definition to avoid `@classmethod @property` incompatibility in Python 3.11+.
3. **Partition path format** — `tenants/{tenant_id}/workspaces/{workspace_id}/` — deterministic, filesystem-safe, human-auditable.
4. **ScopedQueryFilter as value object** — Frozen dataclass that stores accept as an optional parameter. Filtering logic lives in the guard, not scattered across store implementations.
5. **Defense-in-depth on all stores** — When enabled, all stores raise `TenantScopeError` for unresolved scopes, preventing any query from bypassing tenant scoping.
