---
phase: 37
plan: 02
title: "Discovery endpoint, API route handler, and feature flag integration"
wave: 2
requirements:
  - SKILL-02
  - SKILL-01
status: complete
---

# Plan 37-02 — Summary

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 01 | Create discovery index builder following Cloudflare RFC v0.2.0 | `92c223a` |
| 02 | Create API route handler with feature flag integration and read-only enforcement | `cb3c5dc` |

## Test Results

| Test File | Test Count | Passed | Failed | Status |
|-----------|------------|--------|--------|--------|
| `test_discovery.py` | 9 | 9 | 0 | ✅ |
| `test_api.py` | 12 | 12 | 0 | ✅ |
| **Plan 37-02 Total** | **21** | **21** | **0** | ✅ |
| **Full Suite (37-01 + 37-02)** | **35** | **35** | **0** | ✅ |

### Verification Commands Run

- `PYTHONPATH=packages/skill-registry/src:packages/platform-contract/src python -m unittest discover -s packages/skill-registry/tests -p "test_discovery.py"` — exit 0, 9 tests pass
- `PYTHONPATH=packages/skill-registry/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/skill-registry/tests -p "test_api.py"` — exit 0, 12 tests pass
- `PYTHONPATH=packages/skill-registry/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/skill-registry/tests` — exit 0, 35 tests pass (test_mapper + test_registry + test_discovery + test_api)
- `python -m compileall packages/skill-registry/src` — exit 0, no syntax errors

## Files Created

| File | Purpose |
|------|---------|
| `packages/skill-registry/src/inkstatute_skill_registry/discovery.py` | `build_discovery_index()` — Cloudflare RFC v0.2.0 discovery index builder with `SCHEMA_URI` constant, `_normalize_skill_name()`, `_descriptor_to_dict()` |
| `packages/skill-registry/src/inkstatute_skill_registry/api.py` | `handle_get()` — pure route handler with feature flag integration, `_split_path_query()`, `_not_found()`, `parse_query_string()` |
| `packages/skill-registry/tests/test_discovery.py` | Discovery index unit tests (9 test cases) |
| `packages/skill-registry/tests/test_api.py` | API route handler unit tests (12 test cases) |

## Files Modified

| File | Change |
|------|--------|
| `packages/skill-registry/src/inkstatute_skill_registry/__init__.py` | Added re-exports for `build_discovery_index` (Task 01) and `handle_get` (Task 02); updated `__all__` |

## Key Implementation Details

- **`build_discovery_index(skills)`** produces a Cloudflare RFC v0.2.0 compliant index:
  - `$schema` = `"https://schemas.agentskills.io/discovery/0.2.0/schema.json"`
  - `skills[]` array with 8 entries (4 lawfirm + 4 demo_non_legal)
  - Each entry has exactly 5 keys: `name`, `type`, `description`, `url`, `digest`
  - `name` is normalized: underscores → hyphens, lowercased (e.g., `case_qa` → `case-qa`)
  - `type` is always `"skill-md"`
  - `url` follows `/.well-known/agent-skills/{normalized_name}/SKILL.md`
  - `digest` is `sha256:<hex>` over canonical JSON of the descriptor (deterministic)
  - `description` truncated to 1024 chars max

- **`handle_get(path, query, registry, flags=None)`** is a pure route handler:
  - `GET /.well-known/agent-skills/index.json` → discovery index (200)
  - `GET /skills` → list all skills with `items`, `count`, `metadata.read_only` (200)
  - `GET /skills/search?tag=&category=&name=` → filtered search (200)
  - `GET /skills/{skill_id}` → single skill (200) or 404
  - Unknown routes → 404
  - `/skills/search` is checked before `/skills/{skill_id}` to avoid prefix collision
  - Feature flag: when `flags` is provided, `require_enabled("skill_registry_enabled")` is called first; default-off raises `RuntimeFeatureDisabledError`
  - Read-only: only `handle_get` exists — no `handle_post`, `handle_put`, `handle_delete`, `handle_patch`

## Deviations from Plan

None. All tasks executed as specified in the plan.

## Contract Freeze Preservation

No files in `packages/platform-contract/` or `packages/platform-runtime/` were modified. The `NeutralSkillDescriptor` dataclass (events.py:104-112) was used as-is, and `RuntimeFeatureFlags` (feature_flags.py) was imported without modification, preserving the SAFETY-06 contract freeze from Phase 36.

## EXECUTION COMPLETE
