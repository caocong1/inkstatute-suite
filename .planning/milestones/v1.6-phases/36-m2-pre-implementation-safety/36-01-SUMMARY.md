---
phase: 36
plan: 01
title: "Selection Gate Bypass Fix + M2 Feature Flags Default-OFF"
wave: 1
requirements:
  - SAFETY-01
  - SAFETY-04
status: complete
---

# Plan 01 Summary: Selection Gate Bypass Fix + M2 Feature Flags Default-OFF

## Tasks Completed

### Task 01: Remove selection gate bypass (SAFETY-01)

**Commit:** `fa0c3f3`

- Deleted lines 50-51 in `services/wecom-service/src/wecom_service/agent_backend.py` — the override that set `live_acceptance_allowed=True` for non-Hermes modes when `metadata.production_ready` was `True`.
- Line 49 (`live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value`) remains as the sole logic.
- Added test `test_non_hermes_manifest_production_ready_bypass_is_blocked` to `AgentBackendSelectorTests` in `services/wecom-service/tests/test_agent_backend.py`, iterating over CODEX and PROVIDER_MODEL modes with `production_ready=True` and asserting `live_acceptance_allowed=False`.

### Task 02: Add 6 M2 feature flags defaulting to False (SAFETY-04)

**Commit:** `0612bc4`

- Added 6 new fields to `RuntimeFeatureFlags` dataclass in `packages/platform-runtime/src/platform_runtime/feature_flags.py`, all defaulting to `False`:
  - `router_service_enabled`
  - `skill_registry_enabled`
  - `admin_api_enabled`
  - `qqbot_channel_enabled`
  - `codex_backend_enabled`
  - `provider_model_backend_enabled`
- Updated `test_all_runtime_lanes_default_to_false` with 6 new `assertFalse` assertions.
- Added `test_all_m2_flags_default_to_false_via_introspection` using `dataclasses.fields` to iterate all fields and assert every default is `False` via `subTest`.
- `RuntimeFeatureFlags` now has 12 total fields (6 existing V2 + 6 new M2), all defaulting to `False`.

## Test Results

| Test Suite | Command | Result |
|------------|---------|--------|
| SAFETY-01 bypass test | `pytest services/wecom-service/tests/test_agent_backend.py -k bypass` | 1 passed, 2 subtests passed |
| wecom-service full suite | `python -m unittest discover -s services/wecom-service/tests` | 72 passed, 0 failed |
| SAFETY-04 m2 test | `pytest packages/platform-runtime/tests/test_feature_flags.py -k m2` | 1 passed, 12 subtests passed |
| platform-runtime feature_flags | `python -m unittest discover -s packages/platform-runtime/tests -p test_feature_flags.py` | 5 passed, 0 failed |
| platform-runtime full suite | `python -m unittest discover -s packages/platform-runtime/tests` | 236 passed, 2 errors (pre-existing, unrelated — hindsight client aiohttp ResourceWarning in test_long_term_memory.py) |

## Files Modified

1. `services/wecom-service/src/wecom_service/agent_backend.py` — removed 2-line bypass override
2. `services/wecom-service/tests/test_agent_backend.py` — added bypass-blocking test
3. `packages/platform-runtime/src/platform_runtime/feature_flags.py` — added 6 M2 feature flag fields
4. `packages/platform-runtime/tests/test_feature_flags.py` — added 6 assertions + introspection test

## Deviations from Plan

None. All tasks executed exactly as specified in the plan.

## Pre-existing Issues (not caused by this plan)

- `test_long_term_memory.py` has 2 errors from hindsight client aiohttp connection issues (ResourceWarning: Unclosed client session). These are pre-existing and unrelated to the feature flags changes.

## EXECUTION COMPLETE
