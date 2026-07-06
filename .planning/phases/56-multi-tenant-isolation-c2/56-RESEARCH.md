# Phase 56: Multi-Tenant Isolation (C2) - Research

**Researched:** 2026-07-06
**Domain:** Multi-tenant data isolation, tenant-scoped query enforcement, partitioned contract logs, namespaced cache, Hindsight bank isolation, migration safety
**Confidence:** HIGH

## Summary

Phase 56 introduces multi-tenant isolation as an opt-in platform-runtime library behind the existing `multi_tenant_enabled` feature flag (added in Phase 45, defaults to `False`). The core components are:

1. **`TenantScopeResolver`** — resolves `tenant_id` from request context using a priority chain: (a) auth token claims (via RBAC `Identity.tenant_id`), (b) channel metadata (`RunRequest.tenant_id` / `SessionScope.tenant_id`), (c) explicit header (`X-Tenant-Id`). Returns a `TenantScope` dataclass carrying `tenant_id` and optional `workspace_id`.

2. **`TenantGuard`** — enforces that every read-model query carries a `tenant_id` filter. The guard wraps read-model stores with a `ScopedQueryFilter` that injects `tenant_id` (and `workspace_id` when present) into every query. Queries without a resolved `tenant_id` are rejected when `multi_tenant_enabled=True` — no query can bypass tenant scoping.

3. **`TenantScopedContractLogStore`** — a `ContractLogStore` wrapper that partitions contract log entries by `tenant_id`/`workspace_id` path. Each `append()` call derives a partition path from the event's tenant scope and stores the entry under that path. Retrieval methods scope by the same path, preventing one tenant's logs from bleeding into another's.

4. **`TenantNamespacedCache`** — a cache wrapper that prefixes every cache key with `tenant:{tenant_id}:`, ensuring no cross-tenant cache leakage. Cache get/set/delete operations transparently namespace keys.

5. **Hindsight bank isolation** — the existing `HindsightMemory._bank_id()` method (hindsight_memory.py:107-113) already maps `(tenant_id, workspace_id, user_id)` to a Hindsight `bank_id`. This phase adds an explicit `TenantGuard` enforcement check that verifies the bank_id contains the resolved `tenant_id` before any retain/recall/reflect operation, preventing bank-id spoofing.

6. **Migration test** — a test that asserts no null `tenant_id` in any persisted record (contract logs, memory records, cache keys) when `multi_tenant_enabled=True`. The test constructs tenant-scoped stores, writes records, and verifies every record carries a non-null `tenant_id`.

The `multi_tenant_enabled` flag already exists in `RuntimeFeatureFlags` (feature_flags.py:36) and defaults to `False`. When disabled, all behavior is unchanged from v1.6 — the new classes are purely additive and opt-in. No frozen contract surfaces are modified. The `dependencies = []` invariant is preserved — all new code uses only stdlib and existing project packages.

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
| TENANT-01 | `TenantScopeResolver` resolves `tenant_id` from request context (auth token claims, channel metadata, or explicit header); `TenantGuard` injects `tenant_id` filter into every read-model query — no query can bypass tenant scoping | §Architecture Patterns (TenantScopeResolver priority chain, TenantGuard scoped query filter), §Code Examples |
| TENANT-02 | Contract logs partitioned by `tenant_id`/`workspace_id` path; cache keys namespaced by `tenant_id`; Hindsight bank isolation enforced per tenant; migration test asserts no null `tenant_id` | §Architecture Patterns (TenantScopedContractLogStore, TenantNamespacedCache, Hindsight bank guard, migration test) |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.** Tenant IDs are structural identifiers, not secrets — but tenant-scoped paths must not embed raw legal text. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it.** All new code is library-only in `packages/platform-runtime/`. `dependencies = []` invariant preserved — stdlib only. [VERIFIED: AGENTS.md §Coding Rules]
- **Keep changes scoped to the active GSD phase and its plan.** [VERIFIED: AGENTS.md §Coding Rules]
- **Add tests before or with behavior changes.** TenantScopeResolver, TenantGuard, TenantScopedContractLogStore, TenantNamespacedCache, and migration test all get unit tests. [VERIFIED: AGENTS.md §Coding Rules]
- **Prefer structured parsers and schema validators over ad hoc string parsing.** Tenant scope resolution uses structured dataclasses and explicit priority chains, not string parsing. [VERIFIED: AGENTS.md §Coding Rules]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| TenantScopeResolver | `packages/platform-runtime/` (tenant_scope.py) | — | Runtime owns tenant scope resolution from request context |
| TenantGuard | `packages/platform-runtime/` (tenant_scope.py) | — | Guard owns query-level tenant filter enforcement |
| TenantScopedContractLogStore | `packages/platform-runtime/` (tenant_contract_log.py) | — | Wraps ContractLogStore with tenant partition paths |
| TenantNamespacedCache | `packages/platform-runtime/` (tenant_cache.py) | — | Wraps cache with tenant-namespaced keys |
| Hindsight bank isolation guard | `packages/platform-runtime/` (hindsight_memory.py) | — | Extends existing _bank_id with explicit tenant guard |
| Migration test | `packages/platform-runtime/tests/` (test_tenant_migration.py) | — | Asserts no null tenant_id in persisted records |
| Feature flag gating | `packages/platform-runtime/` (feature_flags.py) | — | `multi_tenant_enabled` already exists, defaults False |

## Standard Stack

### Core

No new external packages. All new code uses only the Python standard library and existing project packages.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `dataclasses` | 3.11+ | Frozen dataclasses for TenantScope, ScopedQueryFilter | Already used throughout platform-runtime |
| Python stdlib `typing` | 3.11+ | Protocol, TypeAlias, Mapping | Already used |
| Python stdlib `pathlib` | 3.11+ | Tenant partition path construction | Already used in protocols.py |
| `platform-runtime` | existing | `RuntimeFeatureFlags`, `ContractLogStore`, `SessionScope` | Flag already present (Phase 45) |
| `platform-contract` | existing | `JsonObject` | Already used |
| `rbac` | existing (Phase 51) | `Identity.tenant_id` from token claims | RBAC dependency for tenant claim extraction |

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| Database-level row-level security (RLS) | Introduces a runtime dependency; platform-runtime is library-only. Tenant scoping at the query/filter layer is the appropriate abstraction level. |
| Middleware decorator pattern | The existing architecture uses explicit guard objects (RbacGuard pattern from Phase 51), not decorators. Consistency with RbacGuard. |
| Separate tenant_id column in contract log schema | Modifies frozen contract surfaces. Instead, tenant_id is carried in event metadata and used to derive partition paths. |
| Redis/memcached for tenant cache | Introduces a runtime dependency. In-memory dict-based cache with tenant key namespacing is sufficient for the library layer. |

## Architecture Patterns

### 1. TenantScopeResolver — Priority Chain Resolution

`TenantScopeResolver.resolve(context)` resolves `tenant_id` using a priority chain:
1. **Auth token claims** — if the context carries an RBAC `Identity`, use `identity.tenant_id`
2. **Channel metadata** — if the context carries a `RunRequest` or `SessionScope`, use its `tenant_id`
3. **Explicit header** — if the context carries headers, check `X-Tenant-Id`

The resolver returns a `TenantScope(tenant_id, workspace_id)` dataclass. When `multi_tenant_enabled=False`, the resolver returns `TenantScope.NONE` (a sentinel with `tenant_id=None`), preserving v1.6 behavior.

```python
@dataclass(frozen=True, slots=True)
class TenantScope:
    tenant_id: str | None = None
    workspace_id: str | None = None

    NONE: ClassVar["TenantScope"]  # sentinel for disabled mode

    @property
    def is_resolved(self) -> bool:
        return self.tenant_id is not None
```

### 2. TenantGuard — No-Bypass Query Filter Enforcement

`TenantGuard` wraps read-model stores. When `multi_tenant_enabled=True`, every query must carry the resolved `tenant_id`. The guard injects a `ScopedQueryFilter` into every query call. Queries that lack a `tenant_id` when the flag is enabled raise `TenantScopeError`.

```python
class TenantGuard:
    def __init__(self, *, feature_flags: RuntimeFeatureFlags) -> None:
        self._feature_flags = feature_flags

    def enforce(self, scope: TenantScope) -> ScopedQueryFilter:
        if not self._feature_flags.multi_tenant_enabled:
            return ScopedQueryFilter.disabled()
        if not scope.is_resolved:
            raise TenantScopeError("multi_tenant_enabled requires resolved tenant_id")
        return ScopedQueryFilter(tenant_id=scope.tenant_id, workspace_id=scope.workspace_id)
```

`ScopedQueryFilter` is a frozen dataclass that read-model stores accept as an optional parameter. When present, the store filters results by `tenant_id`. When `disabled()`, no filtering occurs (v1.6 behavior).

### 3. TenantScopedContractLogStore — Partitioned Contract Logs

`TenantScopedContractLogStore` wraps a `ContractLogStore` and partitions entries by `tenant_id`/`workspace_id` path. Each `append()` call:
1. Extracts `tenant_id` from the event (or from an explicit scope parameter)
2. Derives a partition path: `tenants/{tenant_id}/workspaces/{workspace_id}/`
3. Tags the stored entry with `tenant_id` and `workspace_id` in metadata
4. Delegates to the wrapped store

Retrieval methods (`entries()`, `entries_for_run()`) accept an optional `TenantScope` and filter results to only entries matching the scope.

### 4. TenantNamespacedCache — Namespaced Cache Keys

`TenantNamespacedCache` wraps a simple dict-based cache. Every key is prefixed with `tenant:{tenant_id}:`. When `multi_tenant_enabled=False`, no prefix is applied (v1.6 behavior).

```python
class TenantNamespacedCache:
    def _namespaced_key(self, scope: TenantScope, key: str) -> str:
        if not self._feature_flags.multi_tenant_enabled:
            return key
        if not scope.is_resolved:
            raise TenantScopeError("cache access requires resolved tenant_id")
        return f"tenant:{scope.tenant_id}:{key}"
```

### 5. Hindsight Bank Isolation Enforcement

The existing `HindsightMemory._bank_id()` (hindsight_memory.py:107-113) already maps `(tenant_id, workspace_id, user_id)` to a bank_id. This phase adds an explicit `TenantGuard.enforce()` call at the start of each `aretain`/`arecall`/`areflect` method, verifying that the input's `tenant_id` matches the resolved scope. This prevents bank-id spoofing where a caller could craft a `MemoryRetainInput` with a different `tenant_id`.

### 6. Migration Test — No Null tenant_id

A dedicated test (`test_tenant_migration.py`) constructs tenant-scoped stores with `multi_tenant_enabled=True`, writes records (contract logs, memory records, cache entries), and asserts that every persisted record carries a non-null `tenant_id`. The test also verifies that when `multi_tenant_enabled=False`, records can have null `tenant_id` (v1.6 behavior preserved).

## Code Examples

### TenantScopeResolver Usage

```python
resolver = TenantScopeResolver(feature_flags=flags)
scope = resolver.resolve(
    identity=Identity(role=Role.ADMIN, tenant_id="firm-001"),
    request=run_request,
    headers={"X-Tenant-Id": "firm-001"},
)
# scope.tenant_id == "firm-001" (from identity, highest priority)
```

### TenantGuard Usage

```python
guard = TenantGuard(feature_flags=flags)
filter = guard.enforce(scope)
# filter.tenant_id == "firm-001"
# filter.is_active == True
```

### TenantScopedContractLogStore Usage

```python
store = TenantScopedContractLogStore(
    delegate=InMemoryContractLogStore(),
    feature_flags=flags,
)
store.append("agent_turn", event, scope=scope)
# entry stored with tenant_id="firm-001" in metadata
entries = store.entries(scope=scope)
# only entries for tenant "firm-001" returned
```

## Frozen Surface Verification

- **BackendAdapter**: 9 methods — unchanged (no new methods added)
- **ChannelAdapter**: 6 methods — unchanged
- **RunRequest**: `tenant_id` and `workspace_id` fields already exist (protocols.py:111-112)
- **SessionScope**: `tenant_id` and `workspace_id` fields already exist (session_resolver.py:30-31)
- **ContractLogStore Protocol**: 1 method (`append`) — unchanged; `TenantScopedContractLogStore` is a wrapper, not a Protocol modification
- **RuntimeFeatureFlags**: `multi_tenant_enabled` already exists (feature_flags.py:36) — no change
- **`dependencies = []`**: preserved — all new code is stdlib + existing project packages only

## Key Design Decisions

1. **Library-only, no service coupling** — All new classes live in `packages/platform-runtime/`. Services can optionally use them, but the platform-runtime package has no service dependencies.

2. **Opt-in via feature flag** — `multi_tenant_enabled` defaults to `False`. When disabled, `TenantScopeResolver` returns `TenantScope.NONE`, `TenantGuard.enforce()` returns a disabled filter, and all behavior is identical to v1.6.

3. **Priority chain for tenant resolution** — Auth token claims > channel metadata > explicit header. This matches the security principle that authenticated identity is more trustworthy than request metadata.

4. **No frozen surface modifications** — `TenantScopedContractLogStore` wraps `ContractLogStore`; it does not modify the Protocol. `TenantGuard` is a standalone guard object, not a Protocol change.

5. **ScopedQueryFilter as a value object** — The filter is a frozen dataclass that stores accept as an optional parameter. This keeps the filtering logic in the guard, not scattered across store implementations.

6. **Partition path format** — `tenants/{tenant_id}/workspaces/{workspace_id}/` — deterministic, filesystem-safe, and human-auditable. When `workspace_id` is absent, the path is `tenants/{tenant_id}/`.
