---
phase: 77-vision-routing-runtime
plan: 01
subsystem: operator-config
tags: [operator-config, vision-routing, validation, routing-mode, frozen-dataclasses, stdlib]

# Dependency graph
requires:
  - phase: 76-provider-registry-model-catalog
    provides: VisionPolicyDoc stub, _resolve_selection_pair with allow_partial, built-in vendor/model catalog with supports_vision
provides:
  - _SUPPORTED_ROUTING_MODES frozenset (auto/always_preprocess/main_only) in validate.py
  - routing_mode enum validation emitting unsupported_routing_mode at vision.routing_mode (no value echo)
  - Vision pair completeness enforcement gated by routing mode (incomplete_vision_selection at the missing field path)
  - Preserved Phase 76 draft-tolerant behavior for main_only and unset (None) routing_mode
  - VisionPolicyDoc docstring documenting the three routing modes and the completeness rule
affects: [77-02-api-vision-config, 77-03-web-ui-vision-form, 77-04-vision-router-runtime]

# Tech tracking
tech-stack:
  added: []  # stdlib + in-repo only; no new packages
  patterns:
    - "Module-level frozenset enum validation (_SUPPORTED_ROUTING_MODES) mirroring _SUPPORTED_PROVIDER_KINDS"
    - "Routing-mode-gated completeness: auto/always_preprocess require a complete vision pair; main_only/None remain draft-tolerant"
    - "Shared _resolve_selection_pair resolver still resolves complete vision pairs (any mode) against the registry"

key-files:
  created: []
  modified:
    - packages/operator-config/src/inkstatute_operator_config/validate.py
    - packages/operator-config/src/inkstatute_operator_config/schemas.py
    - packages/operator-config/tests/test_validate_document.py
    - packages/operator-config/tests/test_schemas.py
    - packages/operator-config/tests/test_store.py

key-decisions:
  - "routing_mode is validated as an enum (auto/always_preprocess/main_only) plus None (unset); any other value emits unsupported_routing_mode at vision.routing_mode without echoing the rejected value"
  - "auto and always_preprocess require a complete vision_provider_id + vision_model_id pair; an absent or partial pair emits incomplete_vision_selection at the missing field path (vision.vision_model_id when the provider is present or both absent; vision.vision_provider_id when only the model is present)"
  - "main_only and an unset (None) routing_mode preserve the Phase 76 draft-tolerant behavior: absent/partial/complete vision pairs are all valid persisted drafts because the runtime ignores vision fields under main_only"
  - "A complete vision pair (any routing_mode) is still resolved against the operator registry by the same built-in-vendor or custom-allowlist rules as the main catalog selection"
  - "An unsupported routing_mode is fail-closed for completeness (no completeness issue emitted under an unknown mode) but a complete pair is still resolved so registry errors are surfaced"
  - "No new public symbols are re-exported from __init__.py; _SUPPORTED_ROUTING_MODES and _check_vision_completeness are private/internal, and validate_document/OperatorConfigValidator/ValidationIssue are already exported"

patterns-established:
  - "Pattern: routing-mode-gated completeness enforcement layered on top of the shared _resolve_selection_pair resolver"
  - "Pattern: enum validation via a module-level frozenset + code@path issue with no value echo (mirrors unsupported_provider_kind)"

requirements-completed:
  - VIS-01

# Metrics
duration: ~10min
completed: 2026-07-11
---

# Phase 77 Plan 01: Vision Routing Mode Validation and Policy Schema Summary

**Operator-config `routing_mode` enum validation and vision pair completeness enforcement gated by routing mode**

## Performance

- **Duration:** ~10 min
- **Tasks:** 1 (TDD: RED → GREEN)
- **Files modified:** 5

## Accomplishments
- Added `_SUPPORTED_ROUTING_MODES` frozenset (`auto`/`always_preprocess`/`main_only`) mirroring the existing `_SUPPORTED_PROVIDER_KINDS` pattern.
- Rewrote `_check_vision_selection` to validate `routing_mode` first: an unsupported (non-None, non-enum) value emits `unsupported_routing_mode` at `vision.routing_mode` with a message that names the allowed values but never echoes the rejected value.
- Enforced vision pair completeness when `routing_mode` is `auto` or `always_preprocess`: an absent or partial `vision_provider_id`/`vision_model_id` pair emits `incomplete_vision_selection` at the missing field path.
- Preserved the Phase 76 draft-tolerant behavior for `main_only` and an unset (`None`) `routing_mode`: absent/partial/complete vision pairs remain valid persisted drafts.
- Kept a complete vision pair (any routing_mode) resolved against the operator registry by the existing `_resolve_selection_pair` logic, so built-in vendor mismatch, unknown provider, and custom model-not-allowed are still caught.
- Updated the `VisionPolicyDoc` docstring to document the three routing modes, the completeness rule, and the `main_model_id` echo semantics, while remaining a frozen slotted dataclass with no new fields.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add routing_mode enum validation and vision completeness enforcement** — `662d82f` (feat)

## Files Created/Modified
- `packages/operator-config/src/inkstatute_operator_config/validate.py` — added `_SUPPORTED_ROUTING_MODES`; rewrote `_check_vision_selection` with routing_mode enum validation, completeness gating, and a new `_check_vision_completeness` helper.
- `packages/operator-config/src/inkstatute_operator_config/schemas.py` — updated `VisionPolicyDoc` docstring to document the three routing modes and the completeness rule (no field changes).
- `packages/operator-config/tests/test_validate_document.py` — added `TestVisionRoutingModeValidation` covering supported modes, invalid-mode no-echo, auto/always_preprocess completeness (absent/partial path assertions), main_only draft tolerance, None draft tolerance, complete-pair registry resolution under auto and main_only, and no-echo of present field values.
- `packages/operator-config/tests/test_schemas.py` — added `routing_mode` round-trip proofs for each supported mode and the `None` default.
- `packages/operator-config/tests/test_store.py` — updated the `_refs_only_doc()` fixture from `routing_mode="off"` (now invalid) to `routing_mode="main_only"` (valid with an absent vision pair).

## Decisions Made
- Reused the existing `_resolve_selection_pair` resolver for complete vision pairs (any mode) so registry consistency rules stay shared with the main catalog selection; only the completeness gate is new and routing-mode-aware.
- Chose `incomplete_vision_selection` path as the missing field: `vision.vision_provider_id` when only the model is present, `vision.vision_model_id` when the provider is present or both are absent — surfacing the field the operator still needs to fill.
- Treated an unsupported `routing_mode` as fail-closed for completeness (no completeness issue under an unknown mode) while still resolving a complete pair, so the single `unsupported_routing_mode` issue is the authoritative signal and registry errors are not silently swallowed.
- Did not add new public re-exports: `_SUPPORTED_ROUTING_MODES` and `_check_vision_completeness` are private/internal; `validate_document`, `OperatorConfigValidator`, and `ValidationIssue` are already exported.

## Deviations from Plan

### Auto-fixed Issues

**1. [Scope consistency] Updated test_store.py fixture to a valid routing_mode**
- **Found during:** Task 1 (GREEN run)
- **Issue:** `test_store.py::_refs_only_doc()` persisted `VisionPolicyDoc(routing_mode="off")`. The new `routing_mode` enum validation rejects `"off"` with `unsupported_routing_mode`, so `test_atomic_round_trip_when_flag_on` and `test_save_uses_os_replace_sibling_tmp` failed.
- **Fix:** Changed the fixture and its assertion to `routing_mode="main_only"` (valid with an absent vision pair). `test_store.py` is outside the plan's `files_modified` list but is not owned by any parallel plan and the fix is required to keep the operator-config package gate green.
- **Files modified:** packages/operator-config/tests/test_store.py
- **Verification:** `PYTHONPATH=src python -m pytest tests/ -q` → 110 passed, 71 subtests passed.
- **Committed in:** `662d82f` (Task 1 commit)

**2. [Test design] Refined invalid routing_mode no-echo subtest values**
- **Found during:** Task 1 (RED → GREEN)
- **Issue:** The initial no-echo subtest included `""` (empty string is a substring of every message, including the code@path summary) and `"vision"` (collides with the path prefix `vision.routing_mode`), both of which made `assertNotIn(bad, message)` unsatisfiable.
- **Fix:** Replaced those two values with `"hybrid"` so every subtest value is a genuine rejected token that must not appear in the failure message.
- **Files modified:** packages/operator-config/tests/test_validate_document.py
- **Verification:** All `TestVisionRoutingModeValidation` subtests pass.
- **Committed in:** `662d82f` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 scope consistency, 1 test design)
**Impact on plan:** Minimal — a one-value fixture alignment to the new enum and a no-echo subtest value refinement. No scope creep; no contract or behavior beyond the plan's must-haves.

## Issues Encountered
- The admin-console-api downstream tests could not be run standalone because they have transitive runtime dependencies (e.g. `rbac`) not installed in this isolated execution. A grep audit confirmed every downstream `routing_mode` usage in `services/admin-console-api` and `services/admin-web-ui` is `None` (valid), so the new enum validation introduces no downstream breakage. The operator-config package gate is self-contained and green.

## Verification
- `cd packages/operator-config && PYTHONPATH=src python -m pytest tests/ -q` → **110 passed, 71 subtests passed** (was 93 passed, 51 subtests passed before this plan; +17 tests, +20 subtests).
- RED confirmation before implementation: 14 failures (8 test methods + 6 subtests) across the new `TestVisionRoutingModeValidation` class, all resolved by the GREEN implementation.
