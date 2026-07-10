---
phase: 73-operator-config-foundation
plan: 01
subsystem: operator-config
tags: [operator-config, secret-refs, frozen-dataclass, empty-deps, CFG-01]

requires: []
provides:
  - Empty-deps inkstatute-operator-config package scaffold
  - Frozen OperatorConfigDocument + channel/provider/catalog/vision docs (*_ref only)
  - Shape-only normalize_config_secret_ref (no resolve, no qqbot-service import)
affects:
  - 73-02 (validate + Hermes ban-list)
  - 73-03 (store + operator_config_enabled gate)
  - 74 (admin /config HTTP)

tech-stack:
  added: []
  patterns:
    - empty-deps packages/*/src layout (solution-loader analog)
    - frozen slots dataclasses with *_ref credentials and enabled=False
    - fail-closed secret-ref normalize without echoing rejected values

key-files:
  created:
    - packages/operator-config/pyproject.toml
    - packages/operator-config/README.md
    - packages/operator-config/src/inkstatute_operator_config/__init__.py
    - packages/operator-config/src/inkstatute_operator_config/errors.py
    - packages/operator-config/src/inkstatute_operator_config/schemas.py
    - packages/operator-config/src/inkstatute_operator_config/secrets.py
    - packages/operator-config/tests/test_schemas.py
    - packages/operator-config/tests/test_secret_refs.py
  modified: []

key-decisions:
  - "Channels nested as ChannelsDoc.qqbot/wecom (not a keyed map)"
  - "Providers stored as tuple[ProviderDoc, ...] on the root document"
  - "secret:// requires two+ slash-separated safe segments (generalized beyond QQ REF_TO_VALUE_ENV)"
  - "No resolve_secret_ref and no os.environ reads in this package"

patterns-established:
  - "Operator config docs: frozen=True, slots=True, credential fields end with _ref"
  - "InvalidSecretRefError messages name the field only — never the rejected value"

requirements-completed: [CFG-01]

duration: 2min
completed: 2026-07-10
---

# Phase 73 Plan 01: Operator Config Package Foundation Summary

**Empty-deps `inkstatute-operator-config` with frozen refs-only OperatorConfigDocument schemas and shape-only secret-ref normalize (no qqbot-service dependency)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-10T07:18:44Z
- **Completed:** 2026-07-10T07:21:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Scaffolded `packages/operator-config/` (`dependencies = []`, `operator_config_enabled` metadata, README refs-only / Hermes-not-SoT / no admin HTTP boundary)
- Defined frozen `OperatorConfigDocument` with nested qqbot/wecom channels, providers, catalog selection stub, and vision policy stub — all credential fields `*_ref`, `enabled=False`
- Lifted shape-only `normalize_config_secret_ref` with generalized `secret://` path allowlist; planted secrets rejected without echo

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold empty-deps operator-config package** - `1effc59` (feat)
2. **Task 2: Define frozen refs-only OperatorConfigDocument schemas** - `341668c` (test) → `b6a2cac` (feat)
3. **Task 3: Shape-only secret-ref normalize without qqbot-service dependency** - `8fc7ce5` (test) → `fa40484` (feat)

**Plan metadata:** (docs commit pending)

## Files Created/Modified

- `packages/operator-config/pyproject.toml` - Empty-deps package metadata
- `packages/operator-config/README.md` - Refs-only policy, path env, flag OFF, no HTTP boundary
- `packages/operator-config/src/inkstatute_operator_config/errors.py` - OperatorConfigError hierarchy
- `packages/operator-config/src/inkstatute_operator_config/schemas.py` - Frozen document types
- `packages/operator-config/src/inkstatute_operator_config/secrets.py` - Shape-only secret-ref normalize
- `packages/operator-config/src/inkstatute_operator_config/__init__.py` - Public exports
- `packages/operator-config/tests/test_schemas.py` - Defaults / refs-only / no Hermes fields
- `packages/operator-config/tests/test_secret_refs.py` - Acceptance + planted-secret no-echo

## Decisions Made

- Nested `ChannelsDoc` with `qqbot` + `wecom` fields (clearer than a keyed map for the two known channels)
- `providers` as an immutable tuple on the root document
- `secret://` path shape requires at least two slash-separated safe segments (e.g. `secret://qqbot/app-id`), not QQ-only map membership
- Resolution stays out of this package (hosts / later phases)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring literal `os.environ` failed the no-environ source scan**
- **Found during:** Task 3 (secret-ref normalize)
- **Issue:** Module docstring mentioned ``os.environ``, which `test_secrets_module_does_not_import_qqbot_or_os_environ` scans for as a string
- **Fix:** Reworded docstring to "process environment" without the literal token
- **Files modified:** `packages/operator-config/src/inkstatute_operator_config/secrets.py`
- **Verification:** Full unittest discover green (22 tests)
- **Committed in:** `fa40484` (part of task commit)

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Docstring-only; no scope creep.

## Issues Encountered

None beyond the docstring scan false positive above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 73-02 can add `validate.py` + Hermes ban-list against these schemas and `normalize_config_secret_ref`
- Plan 73-03 can add store + `operator_config_enabled` gate; no HTTP surface yet (Phase 74)

## TDD Gate Compliance

- Task 2: RED `341668c` → GREEN `b6a2cac`
- Task 3: RED `8fc7ce5` → GREEN `fa40484`
- Task 1 scaffold verified via import/grep (no separate test module required by plan)

## Self-Check: PASSED

- All 8 key files FOUND
- Commits 1effc59, 341668c, b6a2cac, 8fc7ce5, fa40484 FOUND
- Schema + secret-ref unittest discovers OK
- `dependencies = []` confirmed; no `qqbot_service` under `packages/operator-config/src`

---
*Phase: 73-operator-config-foundation*
*Completed: 2026-07-10*
