# Plan 52-02 Summary: Write API Handlers with RBAC + Feature Flag Gating

## Objective

Create `write_api.py` module with `handle_post`, `handle_put`, `handle_delete` pure functions that gate on `skill_registry_write_enabled` feature flag and RBAC admin role, then route to `WritableSkillRegistry` operations. Update the RBAC permissions matrix to add `/skills-write` prefix as admin-only.

## Tasks Completed

### Task 1: Create write_api.py with RBAC + feature-flag gated write handlers

**Files modified:**
- `packages/skill-registry/src/inkstatute_skill_registry/write_api.py` — New module with:
  - `handle_post(path, body, registry, identity, flags)` — POST routes: `/skills-write/create`, `/skills-write/rollback`
  - `handle_put(path, body, registry, identity, flags)` — PUT routes: `/skills-write/approve`, `/skills-write/reject`, `/skills-write/update`
  - `handle_delete(path, registry, identity, flags)` — DELETE routes: `/skills-write/deactivate`
  - `_gate(flags, identity, route_path)` helper — checks feature flag + RBAC role; returns 403 if disabled or non-admin
  - Route handlers: `_handle_create`, `_handle_update`, `_handle_deactivate`, `_handle_rollback`, `_handle_approve`, `_handle_reject`
  - Serialization helpers: `_version_to_dict`, `_request_to_dict`, `_review_to_dict`, `_error_response`, `_not_found`
  - All handlers follow the pure-function `(status_code, body)` pattern from `api.py`
  - `SkillRegistryWriteError` caught and returned as 400 with error details
- `packages/rbac/src/rbac/matrix.py` — Added `"/skills-write": frozenset({Role.ADMIN})` to `PERMISSIONS_MATRIX`
- `packages/skill-registry/tests/test_write_api.py` — 20 tests covering:
  - Feature flag gating (disabled returns 403 for POST/PUT/DELETE)
  - RBAC role gating (operator/lawyer/viewer return 403)
  - Create (admin 201, duplicate 400, missing field 400)
  - Update (admin 201, nonexistent 400)
  - Deactivate (admin 201, missing skill_id 400)
  - Approve (admin 200, self-approval 400, nonexistent 400, missing request_id 400)
  - Reject (admin 200)
  - Rollback (admin 201)
  - Unknown routes (404 for POST/PUT/DELETE)
  - Cross-tenant rejection (admin from tenant_b cannot update tenant_a's skill)

**Commit:** `9432f8a` — `feat(52-02): write API handlers with RBAC admin gating + feature flag + permissions matrix update`

## Deviations

None — implementation followed the plan exactly.

## Test Results

- **Skill registry package tests:** 97 tests pass (35 existing + 42 new write + 20 new write_api)
  - `python3 -m unittest discover -s packages/skill-registry/tests -v` — OK

## FROZEN Contract Surfaces Verified

- `SkillRegistryPort` Protocol: 3 methods (unchanged) — `write_api.py` is a separate new module
- `PERMISSIONS_MATRIX` — additive change only (new `/skills-write` key); existing entries unchanged
- `dependencies = []` invariant preserved — no external imports

## Key Design Decisions

1. **Three handler functions** (`handle_post`, `handle_put`, `handle_delete`) — mirrors the read-only `handle_get` pattern. Each returns `(status_code, body)` tuples.
2. **`_gate` helper** — centralizes feature flag + RBAC check. Returns `(None, {})` when allowed, `(403, error_body)` when denied.
3. **`RbacGuard` with default `PERMISSIONS_MATRIX`** — uses the updated matrix with `/skills-write` → admin-only. Non-admin roles get 403.
4. **`_identity_str(identity)`** — serializes `Identity` to `"{role}:{tenant_id}"` for audit fields (requested_by, reviewer). This ensures the two-person rule can compare identities.
5. **Error handling** — `SkillRegistryWriteError` caught and returned as 400 with `{"error": {"code": "write_error", "message": ...}}`. Missing required fields return 400 with `missing_field` code.
6. **DELETE uses query params** — `skill_id` and `requested_at` passed as query string parameters (no body for DELETE).
