# Plan 51-01 Summary: RBAC Roles, Permissions Matrix, and RbacGuard

## Objective

Create the `packages/rbac/` package following the existing src-layout pattern. Define a `Role` enum with 4 roles (admin, operator, lawyer, viewer), a declarative `PERMISSIONS_MATRIX` mapping admin API endpoint prefixes to allowed roles, and an `RbacGuard` with a `check(role, endpoint)` method enforcing default-deny (unannotated endpoints are denied). This satisfies RBAC-01 for the role/matrix/guard primitives.

## Tasks Completed

### Task 1: Scaffold packages/rbac/ package with Role enum and permissions matrix

**Files created:**
- `packages/rbac/pyproject.toml` — `name="inkstatute-rbac"`, `dependencies=[]`, src-layout, `py.typed` package-data. Follows the platform-runtime pyproject pattern.
- `packages/rbac/src/rbac/__init__.py` — Package exports: `Role`, `PERMISSIONS_MATRIX`, `RbacGuard`.
- `packages/rbac/src/rbac/roles.py` — `Role(str, Enum)` with 4 members: `ADMIN="admin"`, `OPERATOR="operator"`, `LAWYER="lawyer"`, `VIEWER="viewer"`.
- `packages/rbac/src/rbac/matrix.py` — `PERMISSIONS_MATRIX: dict[str, frozenset[Role]]` mapping 5 endpoint prefixes to allowed roles: `/sessions` → all 4 roles, `/tasks` → all 4 roles, `/feedback` → {ADMIN, OPERATOR}, `/health` → {ADMIN, OPERATOR}, `/gates` → {ADMIN}.
- `packages/rbac/src/rbac/py.typed` — PEP 561 marker file.
- `packages/rbac/tests/__init__.py` — Test package init.
- `packages/rbac/tests/test_roles.py` — 4 tests: role count is 4, role values match, Role is str enum, lookup by value.
- `packages/rbac/tests/test_matrix.py` — 7 tests: all admin routes annotated, /gates admin-only, /feedback admin+operator, /sessions all roles, /tasks all roles, /health admin+operator, matrix values are frozensets.
- `packages/rbac/tests/test_package_invariants.py` — 3 tests: pyproject dependencies empty, package imports cleanly, no external runtime imports at top level.

**Commit:** `5539c84` — `feat(51-01): add packages/rbac with 4 roles, permissions matrix, and RbacGuard`

### Task 2: Implement RbacGuard with default-deny and longest-prefix match

**Files created:**
- `packages/rbac/src/rbac/guard.py` — `RbacGuard` class with `check(role, endpoint) -> bool` and `_resolve(endpoint) -> frozenset[Role] | None`. Default-deny: endpoints with no matching matrix prefix return `False`. Longest-prefix match: a prefix matches when endpoint equals it, starts with `prefix + "/"`, or starts with `prefix + "?"`. Constructor accepts an optional custom matrix for testing.
- `packages/rbac/tests/test_guard.py` — 15 tests: admin/viewer access sessions, viewer denied feedback, operator accesses feedback, lawyer/admin gates access, unannotated endpoint denied, longest-prefix match, exact match, query-string suffix match, subpath match, custom matrix, default matrix, operator denied gates, lawyer accesses tasks.

**Commit:** `5539c84` — `feat(51-01): add packages/rbac with 4 roles, permissions matrix, and RbacGuard`

## Deviations

- None. All must-haves met as specified in the PLAN.

## Test Results

- **rbac package tests:** 29 tests pass (4 roles + 7 matrix + 15 guard + 3 invariants)
  - `PYTHONPATH="packages/rbac/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest discover -s packages/rbac/tests` — OK

## FROZEN Contract Surfaces Verified

- `dependencies = []` invariant preserved — stdlib only (enum, typing, dataclasses), no external imports
- `py.typed` marker present for PEP 561 type checking support

## Key Design Decisions

1. **Role is `str, Enum`** — allows `Role("admin")` lookup by value and direct string comparison, matching the token claim format.
2. **PERMISSIONS_MATRIX uses `frozenset[Role]` values** — immutable, hashable, prevents accidental modification of the access control policy.
3. **RbacGuard uses longest-prefix match** — enables future nested route policies (e.g., `/sessions/special` can override `/sessions`) while defaulting to the broadest matching prefix.
4. **Default-deny semantics** — `_resolve()` returns `None` for unannotated endpoints, and `check()` returns `False` when `allowed is None`. This is the security-critical default.
5. **Custom matrix injection via constructor** — enables unit testing with synthetic matrices without modifying the production `PERMISSIONS_MATRIX`.
