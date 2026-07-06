# Phase 52: Skill Registry Write (B2) — Research

**Gathered:** 2026-07-06
**Status:** Complete

## 1. Existing Skill Registry (Read-Only)

### Package Structure
- `packages/skill-registry/src/inkstatute_skill_registry/` — single package, stdlib-only
- `pyproject.toml`: `dependencies = []` invariant, `default_off_flag = "skill_registry_enabled"`
- Modules: `registry.py`, `api.py`, `mapper.py`, `discovery.py`, `__init__.py`
- Tests: `test_registry.py`, `test_api.py`, `test_mapper.py`, `test_discovery.py` — 35 tests pass

### `SkillRegistryPort` (FROZEN — 3 methods)
```python
class SkillRegistryPort(Protocol):
    def list_skills(self) -> list[NeutralSkillDescriptor]: ...
    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None: ...
    def search(self, tag=None, category=None, name_substring=None) -> list[NeutralSkillDescriptor]: ...
```
- **Contract-count freeze test** (`test_contract_count_freeze.py:71-79`) asserts `SKILL_REGISTRY_PORT_METHOD_COUNT = 3`
- **MUST NOT modify** `SkillRegistryPort` — any new write protocol must be a separate Protocol

### `SkillRegistry` (Read-Only Implementation)
- Stores `list[NeutralSkillDescriptor]` at construction time
- `list_skills()` returns a copy
- `get_skill()` returns from `_by_id` dict
- `search()` filters by tag/category/name_substring
- **Read-only enforcement test** (`test_registry.py:91-99`): no method starting with write prefixes (`add_`, `create_`, `update_`, `delete_`, `remove_`, `put_`, `post_`)
- **MUST NOT add write methods to `SkillRegistry`** — write logic goes in a new `WritableSkillRegistry` class

### `NeutralSkillDescriptor` (FROZEN contract dataclass)
```python
@dataclass(frozen=True, slots=True)
class NeutralSkillDescriptor:
    skill_id: str
    name: str
    description: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    required_tool_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```
- Defined in `platform_contract/events.py:105-112`
- **MUST NOT modify** — frozen contract surface

### API Handler (`api.py`)
- `handle_get()` — pure function returning `(status_code, body)` tuples
- Feature flag: `flags.require_enabled("skill_registry_enabled")` (default-off)
- **No write handlers** — `handle_post`, `handle_put`, `handle_delete` do not exist (enforced by test)

## 2. RBAC Package (Phase 51 — Complete)

### `Role` Enum
- `ADMIN = "admin"`, `OPERATOR = "operator"`, `LAWYER = "lawyer"`, `VIEWER = "viewer"`

### `RbacGuard`
- `check(role, endpoint) -> bool` — longest-prefix match against `PERMISSIONS_MATRIX`
- Default-deny: endpoints with no matching prefix are denied

### `PERMISSIONS_MATRIX`
```python
PERMISSIONS_MATRIX = {
    "/sessions": frozenset({ADMIN, OPERATOR, LAWYER, VIEWER}),
    "/tasks": frozenset({ADMIN, OPERATOR, LAWYER, VIEWER}),
    "/feedback": frozenset({ADMIN, OPERATOR}),
    "/health": frozenset({ADMIN, OPERATOR}),
    "/gates": frozenset({ADMIN}),
}
```
- **Need to add** `/skills-write` prefix → `frozenset({Role.ADMIN})` for write endpoints

### `Identity`
- `Identity(role: Role, tenant_id: str)` — frozen dataclass
- `resolve_identity()` extracts role+tenant from Bearer token

### RBAC CI Scan
- `scripts/scan_rbac_annotations.py` checks `ROUTE_PREFIXES` from `admin_console_api.routes` against `PERMISSIONS_MATRIX`
- Only checks admin-console-api routes, NOT skill-registry routes
- Skill-registry write API will use `RbacGuard.check()` directly at handler level

## 3. Feature Flags

### `RuntimeFeatureFlags`
- `skill_registry_write_enabled: bool = False` — already exists (added in Phase 45)
- `skill_registry_enabled: bool = False` — read-only flag
- `rbac_enabled: bool = False` — RBAC flag
- `require_enabled(flag_name)` raises `RuntimeFeatureDisabledError` when flag is off

## 4. API Pattern (from admin-console-api)

### Handler Pattern
- Pure functions returning `(status_code, body)` tuples
- Feature flag gate first, then auth, then RBAC guard, then route dispatch
- No FastAPI/aiohttp dependency — tested via `unittest`

### Admin Console API Flow
1. Feature flag gate (`require_enabled("admin_api_enabled")`)
2. Auth (RBAC token or static token)
3. RBAC role guard (`RbacGuard.check(role, path)`)
4. Route dispatch

## 5. Design Decisions

### New Module: `write.py`
- `SkillRegistryWritePort` Protocol — separate from frozen `SkillRegistryPort`
- `WritableSkillRegistry` class — in-memory implementation
- `SkillVersion` frozen dataclass — immutable version record
- `HumanReviewRecord` frozen dataclass — two-person rule evidence
- `WriteRequest` frozen dataclass — pending write awaiting approval

### Immutable Versioning
- Every write (create, update, deactivate, rollback) creates a new `SkillVersion` with an incrementing `version` integer
- Old versions are never mutated or deleted
- `get_current()` returns the latest version; `get_version()` returns any historical version
- `list_versions()` returns the full version history

### Two-Person Rule
- Every write path goes through a submit → approve flow:
  1. `submit_create/submit_update/submit_deactivate/submit_rollback` creates a pending `WriteRequest`
  2. `approve_write(request_id, reviewer)` commits the write (creates new version) — reviewer must differ from requester
  3. `reject_write(request_id, reviewer)` rejects the request
- No write commits without a `HumanReviewRecord` with a different reviewer identity
- Self-approval is rejected (reviewer != requested_by)

### Per-Tenant Namespaces
- Skills are keyed by `(tenant_id, skill_id)` where `skill_id = "{tenant_id}/{name}"`
- All read/write operations require `tenant_id` parameter
- Cross-tenant access is rejected (tenant mismatch raises error)
- `list_skills(tenant_id)` only returns skills for that tenant

### Rollback
- `submit_rollback(tenant_id, skill_id, target_version, requested_by)` creates a pending rollback request
- On approval, a new version is created with the content of the target version
- History is never deleted — rollback creates a new version, never removes old ones

### Write API (`write_api.py`)
- `handle_post(path, body, registry, identity, flags)` — create/submit write
- `handle_put(path, body, registry, identity, flags)` — approve/reject/update
- `handle_delete(path, registry, identity, flags)` — deactivate
- All gated by `skill_registry_write_enabled` flag + RBAC admin role check
- Follows the same pure-function `(status_code, body)` pattern as `api.py`

### RBAC Matrix Update
- Add `/skills-write` → `frozenset({Role.ADMIN})` to `PERMISSIONS_MATRIX`
- This ensures only admin role can access write endpoints

## 6. Constraints Verified

1. ✅ `dependencies = []` — no new external dependencies needed (stdlib only)
2. ✅ `skill_registry_write_enabled` defaults to `False` — already in `RuntimeFeatureFlags`
3. ✅ `SkillRegistryPort` (3 methods) frozen — new `SkillRegistryWritePort` is separate
4. ✅ `NeutralSkillDescriptor` frozen — `SkillVersion` is a new dataclass, not modifying it
5. ✅ Read-only `registry.py` untouched — write logic in new `write.py` module
6. ✅ Read-only test (`test_registry.py:91-99`) — `WritableSkillRegistry` is a separate class
7. ✅ No write handlers test (`test_api.py:150-158`) — write handlers in new `write_api.py` module
8. ✅ RBAC guard pattern — use `RbacGuard.check()` directly in write API handlers
