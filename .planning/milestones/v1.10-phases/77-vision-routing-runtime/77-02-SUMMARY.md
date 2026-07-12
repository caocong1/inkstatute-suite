---
phase: 77-vision-routing-runtime
plan: 02
subsystem: api
tags: [admin-console-api, vision-routing, operator-config, config-api, refs-only, probe, ssr-metadata]

# Dependency graph
requires:
  - phase: 77-vision-routing-runtime
    provides: routing_mode enum validation and vision completeness enforcement (Plan 77-01 validate.py)
  - phase: 76-provider-registry-model-catalog
    provides: VisionPolicyDoc stub, vision section in CONFIG_SECTIONS, _SECTION_ALLOWED_KEYS for vision, target=vision probe handler
provides:
  - Vision section GET/PUT metadata (routing_modes list, vision_configured boolean, vision_status field, apply_semantics=restart_required)
  - Empty-string-to-None normalization for vision PUT bodies (routing_mode, main_model_id, vision_model_id, vision_provider_id)
  - test_config_vision.py RED+green contract for routing_mode, completeness, metadata, and refs-only safety
  - Vision probe integration proof after a Phase 77 routing_mode save (test_config_probe.py)
affects: [77-03-web-ui-vision-form, 77-04-vision-router-runtime]

# Tech tracking
tech-stack:
  added: []  # stdlib + in-repo only; no new packages
  patterns:
    - "Section-specific metadata extension via _vision_status_metadata helper computed from the stored document"
    - "Empty-string-to-None normalization layer for SSR blank-select persistence (draft-tolerant None)"
    - "Validation-gates-probe-availability proof: a partial vision pair under auto is rejected at PUT time so the probe is never reached"

key-files:
  created:
    - services/admin-console-api/tests/test_config_vision.py
  modified:
    - services/admin-console-api/src/admin_console_api/config_api.py
    - services/admin-console-api/tests/test_config_probe.py

key-decisions:
  - "Extended _config_metadata to include apply_semantics=restart_required for the vision section (runtime reads config at startup), matching channels/providers/catalog"
  - "Added routing_modes static list (auto, always_preprocess, main_only) to vision metadata for the SSR form consumer"
  - "Computed vision_configured (bool) and vision_status (configured/not_configured) from the stored VisionPolicyDoc pair completeness via a _vision_status_metadata helper, applied in both GET and PUT handlers"
  - "Normalized empty-string vision fields to None before document_from_payload so SSR blank selects persist as draft-tolerant None rather than empty strings"
  - "Did not modify probe.py — the Phase 76 probe handler already resolves vision_provider_id/vision_model_id from the stored document; Plan 77-02 adds test coverage only"
  - "Did not introduce a new probe route, new network behavior, or runtime routing logic"

patterns-established:
  - "Pattern: section-specific status metadata computed from the stored document and merged into the base _config_metadata dict (vision_configured/vision_status)"
  - "Pattern: empty-string-to-None normalization for optional string fields before persistence, keeping the operator config schema canonical"
  - "Pattern: validation-gates-probe-availability integration test — a rejected PUT means the probe sees the prior (unconfigured) state"

requirements-completed:
  - VIS-01

# Metrics
duration: ~12min
completed: 2026-07-11
---

# Phase 77 Plan 02: Vision Config Endpoint Metadata and Probe Integration Summary

**Admin-console-api vision GET/PUT metadata (routing_modes, vision_configured, vision_status), empty-string normalization, and vision probe integration proof after a Phase 77 routing_mode save**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2 (TDD: RED → GREEN)
- **Files modified:** 3

## Accomplishments
- Added vision section GET/PUT metadata: `routing_modes` list (`auto`/`always_preprocess`/`main_only`), `vision_configured` boolean, and `vision_status` (`configured`/`not_configured`) computed from the stored `VisionPolicyDoc` pair completeness.
- Extended `apply_semantics=restart_required` to the vision section (runtime reads config at startup; never claims live/hot-reload apply).
- Normalized empty-string vision fields (`routing_mode`, `main_model_id`, `vision_model_id`, `vision_provider_id`) to `None` before persistence so the SSR form's blank selects persist as draft-tolerant `None`.
- Added `test_config_vision.py` with 27 RED+green proofs covering GET metadata, PUT `main_only`/`auto`/`always_preprocess` acceptance, invalid `routing_mode` no-echo, unexpected-key (planted secret) rejection, empty-string normalization, `vision_configured`/`vision_status`, refs-only safety, `apply_semantics`, flag-off refusal, and RBAC denial.
- Added `ConfigProbeVisionRoutingModeTests` to `test_config_probe.py` proving the existing Phase 76 vision probe resolves the stored vision pair after a `routing_mode=auto` save, returns `not_configured` after `main_only` with no pair, and that a partial pair under `auto` is rejected at PUT time so the probe is never reached.

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Vision section GET metadata, PUT normalization, and probe integration proof** — `21663d9` (feat)

## Files Created/Modified
- `services/admin-console-api/src/admin_console_api/config_api.py` — extended `_config_metadata` with `apply_semantics` and `routing_modes` for the vision section; added `_vision_status_metadata` helper computing `vision_configured`/`vision_status` from the stored document; added `_normalize_vision_empty_strings` helper and applied it in `handle_config_put` for the vision section; merged vision status metadata into both GET and PUT response bodies.
- `services/admin-console-api/tests/test_config_vision.py` — new test file with 27 proofs for vision config API (GET metadata, PUT acceptance/rejection, normalization, refs-only safety, flag/RBAC gates).
- `services/admin-console-api/tests/test_config_probe.py` — added `ConfigProbeVisionRoutingModeTests` with 6 vision probe integration proofs after a Phase 77 routing_mode save.

## Decisions Made
- Reused the existing `_config_metadata` base dict and merged vision-specific status fields (`vision_configured`/`vision_status`) via a dedicated `_vision_status_metadata` helper, keeping the metadata assembly pattern consistent with channels/providers/catalog.
- Computed `vision_configured` as `bool(vision_provider_id) and bool(vision_model_id)` and `vision_status` as `"configured"` when both present, `"not_configured"` otherwise — matching the probe's `not_configured` semantics for absent/partial pairs.
- Applied empty-string normalization in `handle_config_put` after `_normalize_section_body` and before `document_from_payload`, so the canonical `None` unset value reaches the Plan 77-01 validator and the stored document.
- Did not modify `probe.py` — the Phase 76 probe handler already resolves `vision_provider_id`/`vision_model_id` from the stored document; Plan 77-02 adds test coverage only, per the plan's "no new probe route" constraint.
- Did not echo rejected values, resolved secrets, `api_key_ref` values, base URLs, or endpoint contents in any vision GET or PUT response.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Vision config API surface is complete: GET/PUT `/config/vision` emits `routing_modes`, `vision_configured`, `vision_status`, and `apply_semantics` metadata for the SSR consumer (Plan 77-03).
- Empty-string normalization ensures SSR blank selects persist as `None`, so the Plan 77-03 vision form can submit blank selects without breaking validation.
- The vision probe integration proof confirms the existing Phase 76 `target=vision` probe works after a Phase 77 `routing_mode` save, so Plan 77-03 can wire the vision probe button.
- Plan 77-04 (vision router runtime) can consume the stored validated `VisionPolicyDoc` (routing_mode + vision pair) for routing decisions.

---
*Phase: 77-vision-routing-runtime*
*Completed: 2026-07-11*
