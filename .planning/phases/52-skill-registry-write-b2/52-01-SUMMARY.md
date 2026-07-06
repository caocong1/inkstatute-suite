# Plan 52-01 Summary: WritableSkillRegistry Core

## Objective

Create a new `write.py` module in the skill-registry package implementing `SkillRegistryWritePort` Protocol and `WritableSkillRegistry` class with CRUD operations (create, update, deactivate), immutable versioning (every write creates a new version), rollback to any prior version, human-review two-person rule on every write path, and per-tenant skill namespaces.

## Tasks Completed

### Task 1: Create write.py with SkillRegistryWritePort, dataclasses, and WritableSkillRegistry

**Files modified:**
- `packages/skill-registry/src/inkstatute_skill_registry/write.py` — New module with:
  - `SkillRegistryWriteError` exception class
  - `HumanReviewRecord` frozen dataclass (reviewer, reviewed_at, decision, comment)
  - `SkillVersion` frozen dataclass (skill_id, tenant_id, name, version, description, input_schema_ref, output_schema_ref, required_tool_refs, metadata, status, created_by, created_at, review)
  - `WriteRequest` frozen dataclass (request_id, skill_id, tenant_id, operation, requested_by, requested_at, payload, target_version, review, status)
  - `SkillRegistryWritePort` Protocol with 11 methods (submit_create, submit_update, submit_deactivate, submit_rollback, approve_write, reject_write, list_versions, get_version, get_current, list_skills, list_pending_writes)
  - `WritableSkillRegistry` class implementing all 11 methods with in-memory storage
  - Immutable versioning: every committed write creates a new `SkillVersion` with incrementing version number; existing versions are never mutated
  - Rollback: creates a new version from a prior version's content; history is never deleted
  - Two-person rule: `approve_write` requires `reviewer != requested_by`; self-approval raises `SkillRegistryWriteError`
  - Per-tenant namespaces: skills keyed by `"{tenant_id}/{name}"`; cross-tenant access rejected
- `packages/skill-registry/src/inkstatute_skill_registry/__init__.py` — Added exports for `SkillRegistryWritePort`, `WritableSkillRegistry`, `SkillVersion`, `HumanReviewRecord`, `WriteRequest`, `SkillRegistryWriteError`, `handle_post`, `handle_put`, `handle_delete`
- `packages/skill-registry/tests/test_write.py` — 42 tests covering:
  - Create path (submit + approve, version 1, list_skills, get_current, no auto-apply, duplicate detection)
  - Update path (version 2, get_current, get_version unchanged, nonexistent/deactivated errors)
  - Deactivate path (deactivated version, not in list_skills, in list_versions, double-deactivate error)
  - Rollback path (new version with old content, history preserved, nonexistent version/skill errors)
  - Immutable versioning (object identity preserved, fields unchanged)
  - Two-person rule (self-approval rejected, no auto-apply, nonexistent/already-approved errors, reject creates no version)
  - Per-tenant isolation (not visible to other tenants, cross-tenant read/write/rollback rejected, same name in different tenants)
  - Read operations (list_versions, list_pending_writes, get_version/get_current nonexistent)
  - Protocol compliance (all 11 methods present)
  - Frozen dataclass immutability (SkillVersion, HumanReviewRecord, WriteRequest)

**Commit:** `ee648ef` — `feat(52-01): WritableSkillRegistry with immutable versioning, rollback, two-person rule, per-tenant namespaces`

## Deviations

- **`get_current` cross-tenant behavior**: Returns `None` for cross-tenant access (treated as "not found") rather than raising `SkillRegistryWriteError`. This is consistent with the read-only `SkillRegistry.get_skill()` returning `None` for unknown IDs. `list_versions` and `get_version` still raise on cross-tenant access (explicit access denied).

## Test Results

- **Skill registry package tests:** 97 tests pass (35 existing + 42 new write + 20 new write_api)
  - `python3 -m unittest discover -s packages/skill-registry/tests -v` — OK

## FROZEN Contract Surfaces Verified

- `SkillRegistryPort` Protocol: 3 methods (unchanged) — `write.py` is a separate new module
- `NeutralSkillDescriptor` dataclass: unchanged — `SkillVersion` is a new separate dataclass
- `dependencies = []` invariant preserved — stdlib only (`uuid`, `dataclasses`, `typing`)

## Key Design Decisions

1. **Separate `SkillRegistryWritePort` Protocol** — not modifying the frozen `SkillRegistryPort` (3 read methods). The write protocol has 11 methods (6 write + 5 read).
2. **Submit → Approve flow** — every write path creates a pending `WriteRequest` that must be approved by a different human before committing. No auto-apply.
3. **Immutable `SkillVersion`** — frozen dataclass; every committed write appends a new version to the version list. Old versions are never mutated or removed.
4. **Rollback creates new version** — rollback to version N creates version N+1 with version N's content. History is never deleted.
5. **Per-tenant namespacing** — `skill_id = "{tenant_id}/{name}"`. Cross-tenant writes raise `SkillRegistryWriteError`. `get_current` returns `None` for cross-tenant (not found). `list_skills` only returns skills for the specified tenant.
6. **`_check_tenant` helper** — validates `skill_id` prefix matches `tenant_id` for all explicit read/write operations.
