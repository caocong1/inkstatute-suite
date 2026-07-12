---
phase: 76-provider-registry-model-catalog
plan: 01
subsystem: api
tags: [operator-config, provider-registry, model-catalog, validation, frozen-dataclasses, stdlib]

# Dependency graph
requires:
  - phase: 73-operator-config-foundation
    provides: refs-only OperatorConfigDocument schemas, OperatorConfigStore, validate_document, Hermes/secret bans
  - phase: 74-admin-config-api-rbac
    provides: /config/providers and /config/catalog section GET/PUT persistence path
provides:
  - Code-defined BUILTIN_VENDOR_PROFILES (openai, anthropic) and BUILTIN_MODEL_CATALOG (gpt-5, claude-opus-4-8) with required boolean supports_vision
  - ProviderDoc.model_allowlist field and VisionPolicyDoc.vision_provider_id linkage field
  - Store parsing/serialization of model_allowlist and the optional vision provider/model pair
  - Server-side provider invariants (unique ids, supported kinds, canonical built-in URLs, empty built-in allowlists, public-HTTPS custom URLs, non-empty custom allowlists)
  - Cross-document provider/model selection resolution for main catalog and fully-configured vision pairs
  - Public re-exports of catalog symbols from inkstatute_operator_config
affects: [76-02-api-ui-scaffolds, 76-03-probe-and-persistence, 76-04-csrf-ssr, 77-vision-routing-runtime, 78-console-ssr-docs-gate]

# Tech tracking
tech-stack:
  added: []  # stdlib + in-repo only; no new packages
  patterns:
    - "Code-defined frozen catalog tuple as shared authority (no remote /models fetch)"
    - "vendor_id (built-in kind) vs provider_id (operator registry instance) separation"
    - "Shared provider/model resolver reused for main catalog and complete vision pairs"
    - "Structural public-HTTPS validation via stdlib urllib.parse + ipaddress (DNS resolution deferred to API probe)"

key-files:
  created:
    - packages/operator-config/src/inkstatute_operator_config/catalog.py
    - packages/operator-config/tests/test_catalog.py
  modified:
    - packages/operator-config/src/inkstatute_operator_config/schemas.py
    - packages/operator-config/src/inkstatute_operator_config/store.py
    - packages/operator-config/src/inkstatute_operator_config/validate.py
    - packages/operator-config/src/inkstatute_operator_config/__init__.py
    - packages/operator-config/tests/test_schemas.py
    - packages/operator-config/tests/test_validate_document.py
    - packages/operator-config/tests/test_store.py

key-decisions:
  - "Catalog ownership field is vendor_id (built-in kind); provider_id reserved for operator registry instances"
  - "Built-in providers must store the exact canonical VendorProfile api_base_url and an empty model_allowlist, enforced server-side (not only via SSR read-only controls)"
  - "Custom providers require a public-HTTPS api_base_url (no userinfo/query/fragment, no unsafe literal IP) plus a non-empty explicit model_allowlist; DNS-address validation deferred to the API probe plan"
  - "Main catalog selection must be fully absent or fully populated; half-filled selections are rejected"
  - "Vision provider/model pair is validated only when both fields are present; absent or partial pairs remain valid persisted drafts for Phase 77 editing"
  - "Validation failures expose codes@paths only — never URL, secret-ref value, or selected model content"

patterns-established:
  - "Pattern: code-defined frozen catalog/vendor tuples in operator-config/catalog.py as the single authority for API + UI + Phase 77 runtime"
  - "Pattern: shared _resolve_selection_pair resolver with allow_partial flag distinguishing main-catalog (strict) from vision-pair (draft-tolerant) validation"
  - "Pattern: stdlib urllib.parse.urlsplit + ipaddress for structural custom-URL rejection without network access"

requirements-completed:
  - PROV-01
  - PROV-02
  - PROV-03
  - PROV-04

# Metrics
duration: ~12min
completed: 2026-07-11
---

# Phase 76 Plan 01: Provider Registry + Model Catalog Contracts Summary

**Frozen vendor/model catalog, model_allowlist + vision_provider_id linkage, and server-enforced provider/catalog/vision consistency validation in operator-config**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2
- **Files modified:** 8 (plus 1 consistency fix in test_store.py)

## Accomplishments
- Established the code-defined `BUILTIN_VENDOR_PROFILES` (openai, anthropic) and `BUILTIN_MODEL_CATALOG` (gpt-5, claude-opus-4-8, both `supports_vision=True`) as the shared, source-grounded authority — no remote `/models` fetch, no env reads, no Hermes authority.
- Added `ProviderDoc.model_allowlist` and `VisionPolicyDoc.vision_provider_id` with store parsing/serialization that round-trips absent, partial, and complete vision provider/model pairs.
- Enforced provider invariants server-side: unique ids, supported kinds, exact canonical built-in URLs, empty built-in allowlists, public-HTTPS custom URLs, and non-empty custom allowlists.
- Resolved every complete main catalog and vision provider/model selection against the operator registry instance (built-in `vendor_id == kind` or custom allowlist membership) while permitting absent/partial vision drafts for Phase 77.
- Re-exported catalog symbols from `inkstatute_operator_config` for the API/UI plans.

## Task Commits

Each task was committed atomically:

1. **Task 1: Define the canonical provider and model catalog contracts** — `a44f663b` (feat)
2. **Task 2: Enforce provider invariants and catalog-to-registry consistency** — `bd02127c` (feat)

## Files Created/Modified
- `packages/operator-config/src/inkstatute_operator_config/catalog.py` — NEW: `VendorProfile`, `BuiltInCatalogEntry`, `BUILTIN_VENDOR_PROFILES`, `BUILTIN_MODEL_CATALOG`, and lookup helpers.
- `packages/operator-config/src/inkstatute_operator_config/schemas.py` — added `ProviderDoc.model_allowlist` and `VisionPolicyDoc.vision_provider_id`.
- `packages/operator-config/src/inkstatute_operator_config/store.py` — parses `model_allowlist` (list/tuple only) and `vision_provider_id`; malformed allowlists raise `OperatorConfigStoreError`.
- `packages/operator-config/src/inkstatute_operator_config/validate.py` — provider registry, catalog selection, and vision pair validators plus `_is_valid_custom_base_url`.
- `packages/operator-config/src/inkstatute_operator_config/__init__.py` — public re-exports of catalog symbols.
- `packages/operator-config/tests/test_catalog.py` — NEW: canonical vendor/model catalog integrity proofs.
- `packages/operator-config/tests/test_schemas.py` — model_allowlist/vision_provider_id field and default proofs.
- `packages/operator-config/tests/test_validate_document.py` — positive/negative provider, catalog, and vision consistency proofs with no-echo assertions.
- `packages/operator-config/tests/test_store.py` — consistency fix: canonical `gpt-5` catalog model (was `gpt-4o`).

## Decisions Made
- Reused a single `_resolve_selection_pair` helper for both main catalog and vision selection, differing only by `allow_partial` (strict for main, draft-tolerant for vision) so Phase 77 can own complete vision editing without weakening the main-catalog rule.
- Used stdlib `urllib.parse.urlsplit` + `ipaddress` for custom-URL structural validation; DNS-name resolution is intentionally deferred to the API probe plan (76-03) to keep operator-config network-free.
- Collapsed built-in "unknown model" and "vendor mismatch" into a single `builtin_model_vendor_mismatch` code because both reduce to the catalog entry not being found for `provider.kind`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Scope consistency] Updated test_store.py fixture to the canonical catalog model**
- **Found during:** Task 2 (validation enforcement)
- **Issue:** `test_store.py::_refs_only_doc()` persisted `CatalogSelectionDoc(provider_id="openai", model_id="gpt-4o")`. The new catalog-to-registry validation rejects `gpt-4o` because the source-grounded built-in catalog contains only `gpt-5` and `claude-opus-4-8`, so `test_atomic_round_trip_when_flag_on` and `test_save_uses_os_replace_sibling_tmp` failed.
- **Fix:** Changed the fixture and its assertion to the canonical `gpt-5` model. `test_store.py` is outside the plan's `files_modified` list but is not owned by any parallel plan (76-02 owns only API/UI scaffold tests) and the fix is required to keep the operator-config package gate green.
- **Files modified:** packages/operator-config/tests/test_store.py
- **Verification:** `python -m pytest packages/operator-config/tests/ -q` → 93 passed, 51 subtests passed.
- **Committed in:** `bd02127c` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (scope consistency)
**Impact on plan:** Minimal — a one-value fixture alignment to the new canonical catalog. No scope creep; no contract or behavior beyond the plan's must-haves.

## Issues Encountered
- The 76-02 scaffold tests (`test_config_providers.py`, `test_config_catalog.py`, `test_config_probe.py`, and one scaffold case in `test_config_channels_effective.py`) remain RED. This is by design: VALIDATION.md states scaffolds intentionally fail until plans 76-03/76-04 implement production code. Task 2's plan-mandated built-in URL enforcement changed the failure mode of the `test_config_channels_effective.py` scaffold from accidentally-green (lax validation) to correctly-red (the API layer must fill the canonical built-in URL before validation — a 76-03 responsibility). No previously-green production test was broken; all 93 operator-config tests pass.

## User Setup Required
None — no external service configuration required. No new packages, env vars, or runtime dependencies.

## Next Phase Readiness
- operator-config is now a complete provider/catalog authority: canonical built-ins cannot be forged, custom providers are explicit, and every complete persisted main or vision selection belongs to the resolved provider instance.
- Plans 76-03 (API probe + canonical-URL filling on PUT) and 76-04 (CSRF-protected SSR forms) can consume the public catalog symbols and the `model_allowlist` / `vision_provider_id` contracts directly.
- Phase 77 can read `supports_vision` and the `vision_provider_id`/`vision_model_id` pair to drive the vision router; Phase 76 deliberately leaves routing modes and the complete vision editor to Phase 77.

---
*Phase: 76-provider-registry-model-catalog*
*Plan: 01*
*Completed: 2026-07-11*
