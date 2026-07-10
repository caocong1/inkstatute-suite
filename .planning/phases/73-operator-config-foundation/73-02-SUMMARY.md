---
phase: 73-operator-config-foundation
plan: 02
subsystem: operator-config
tags: [operator-config, validate, hermes-banlist, refs-only, CFG-01, CFG-03]

requires:
  - phase: 73-01
    provides: frozen OperatorConfigDocument + normalize_config_secret_ref
provides:
  - validate_document + OperatorConfigValidator with Hermes ban-list
  - CFG-01 planted-secret / forbidden-key rejection without echo
  - CFG-03 Hermes path/field authority rejection
affects:
  - 73-03 (store must call validate_document before save)
  - 74 (admin /config HTTP mutate path)

tech-stack:
  added: []
  patterns:
    - ManifestValidator-style issue list (path/code/message/severity)
    - fail-closed validate_document raises OperatorConfigValidationError
    - nested metadata/dict walk for Hermes + raw-secret bans

key-files:
  created:
    - packages/operator-config/src/inkstatute_operator_config/validate.py
    - packages/operator-config/tests/test_hermes_banlist.py
    - packages/operator-config/tests/test_validate_document.py
  modified:
    - packages/operator-config/src/inkstatute_operator_config/__init__.py

key-decisions:
  - "validate_document returns [] on success; raises OperatorConfigValidationError on any error-severity issue"
  - "OperatorConfigValidator.validate collects issues without raising (for tests/callers)"
  - "Hermes authority enforced via path substrings + forbidden field names in nested walks"
  - "Credential *_ref fields always run through normalize_config_secret_ref"

patterns-established:
  - "Operator config mutate candidates: validate_document before any store.save"
  - "Validation errors expose codes@paths only — never planted secret or Hermes path values"

requirements-completed: [CFG-01, CFG-03]

duration: 3min
completed: 2026-07-10
---

# Phase 73 Plan 02: Validate Document + Hermes Ban-list Summary

**Fail-closed `validate_document` rejects Hermes filesystem/profile authority and planted raw secrets without echo, while accepting refs-only OperatorConfigDocument payloads**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-10T07:23:23Z
- **Completed:** 2026-07-10T07:26:11Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented `OperatorConfigValidator` + `validate_document` with Hermes path/field ban-list, raw-secret key bans, secret-marker scan, and `*_ref` normalize integration
- Proved CFG-03 negative matrix (`~/.hermes`, `/.hermes`, `.hermes/`, Windows `\.hermes`, forbidden `hermes_*` / `profile_filesystem_path` fields)
- Proved CFG-01 planted `sk-…` / bearer / forbidden keys rejected without echo; valid `env:` / bare / `secret://` refs pass
- Confirmed package src has no `Path.home()` Hermes writer (ban-list string constants only)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement validate_document with Hermes ban-list and refs-only checks** - `ac4ad24` (test) → `3feea03` (feat)
2. **Task 2: Prove CFG-03 Hermes ban-list and CFG-01 planted-secret document rejection** - `aa104c5` (test)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `packages/operator-config/src/inkstatute_operator_config/validate.py` - Document validator + ban-lists
- `packages/operator-config/src/inkstatute_operator_config/__init__.py` - Export validate_document / OperatorConfigValidator / ValidationIssue
- `packages/operator-config/tests/test_hermes_banlist.py` - CFG-03 negative matrix + no-writer scan
- `packages/operator-config/tests/test_validate_document.py` - CFG-01 planted-secret / refs-only happy path

## Decisions Made

- `validate_document` is fail-closed (raises on errors); `OperatorConfigValidator.validate` returns the full issue list for inspection
- Hermes SoT rejection covers both forbidden field names and path substrings in any nested string (including `api_base_url`)
- Exception summaries use `code@path` only so planted values never appear in operator/logs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 73-03 can wire `validate_document` into `OperatorConfigStore.save` behind `operator_config_enabled`
- Do not add admin HTTP in 73-03 (Phase 74)

## TDD Gate Compliance

- Task 1: RED `ac4ad24` → GREEN `3feea03`
- Task 2: expanded coverage `aa104c5` (implementation already green from Task 1)

## Self-Check: PENDING

---
*Phase: 73-operator-config-foundation*
*Completed: 2026-07-10*
