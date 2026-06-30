---
phase: 13-solutionloader-lawyer-non-legal-solutions
plan: 13-04
subsystem: testing
tags: [solution-privacy-gate, composability-gate, contract-evidence, boundary-scan, v2-gates]

# Dependency graph
requires:
  - phase: 13-01-default-solution-loader-library
    provides: "SolutionLoader, registry, side-effects"
  - phase: 13-02-solutions-lawfirm-neutral-manifest
    provides: "lawfirm manifest + sanitize module + materializer"
  - phase: 13-03-solutions-non-legal-demo
    provides: "demo_non_legal manifest + materializer"
  - phase: 09-architecture-contracts-schema-foundation
    provides: "BoundaryAllowlistPolicy and assert_neutral_boundary_allowlist"
provides:
  - "Solution privacy scanner: inkstatute_solution_loader.privacy_scan.scan_bundle_dir(path) returns refusal Issues for any of secrets/logs/DBs/media/raw_payloads/customer_docs/confidential_artifacts detected in a bundle"
  - "Phase 13 contract-test-suite evidence: 24 aggregate tests proving SolutionLoader, lawfirm manifest, demo_non_legal manifest, and privacy scanner agree on default-off, sanitized, and neutral claims"
  - "V2 gate wiring: scripts/run_v2_gates.py contract-test-suite gate extends PYTHONPATH with packages/solution-loader/src, solutions/lawfirm/src, solutions/demo_non_legal/src; run_contract_tests.py SOURCE_PATHS discovers the new modules"
  - "Boundary allowlist update: packages/solution-loader/ and solutions/ added to BoundaryAllowlistPolicy.concrete_package_roots; test_allows_phase13_solution_and_loader_package_paths covers the new allowed paths"
  - "solutions_meta.py registration glue: register_lawfirm_materializer / register_demo_non_legal_materializer helpers for the aggregate evidence test"
affects: [phase-13, contract-test-suite, scripts-run-v2-gates, boundary-scan]

# Tech tracking
tech-stack:
  added: [python-stdlib-only]
  patterns:
    - "privacy-scanner-on-bundle-dir: scan_bundle_dir(path) walks all files; for text files it reads + scans; for binary files it scans file path only (extension + name). Returns list[Issue] sorted by (path, rule_id)"
    - "aggregate-evidence-test: one Phase13SolutionEvidenceTests class wires every Phase 13 artifact into a single default-off, sanitized, neutral view"
    - "lazy-import-with-fallback: privacy_scan lazy-imports inkstatute_solutions_lawfirm.sanitize; if unavailable, falls back to name-only scan"
    - "fixture-driven-contract-evidence (extends Phase 11/12 pattern)"

key-files:
  created:
    - packages/solution-loader/src/inkstatute_solution_loader/privacy_scan.py
    - packages/solution-loader/src/inkstatute_solution_loader/solutions_meta.py
    - packages/contract-test-suite/tests/test_phase13_solution_evidence.py
    - packages/contract-test-suite/fixtures/phase13_solution_bundles.json
  modified:
    - packages/solution-loader/src/inkstatute_solution_loader/__init__.py
    - packages/contract-test-suite/scripts/run_contract_tests.py
    - packages/contract-test-suite/src/contract_test_suite/boundary_checks.py
    - packages/contract-test-suite/tests/test_boundary_allowlist.py
    - scripts/run_v2_gates.py

key-decisions:
  - "Solution privacy scanner is stdlib-only and reuses inkstatute_solutions_lawfirm.sanitize.scan_text to avoid duplicating refusal patterns (single source of truth)"
  - "scan_bundle_dir walks all files; text files (.md/.txt/.json/.template/.jsonl) get content-scanned, binary files (.log/.db/.sqlite/.png/.jpg/.jpeg/.gif/.mp3/.mp4/.wav/.pdf/.docx/.doc) are refused by extension"
  - "Lazy-import with fallback: privacy_scan lazy-imports inkstatute_solutions_lawfirm.sanitize; if unavailable, falls back to name-only scan (still flags refused extensions and obvious file-name patterns)"
  - "Aggregate evidence test asserts: lawfirm + demo_non_legal manifests both validate with zero Issues; both materialize_for produce sanitized bundles; both bundles pass scan_bundle_dir; side_effects declarations match; platform code change diff is empty for non-solution files"
  - "Boundary allowlist update: packages/solution-loader/ and solutions/ added to BoundaryAllowlistPolicy.concrete_package_roots (these are NOT neutral platform code, so they get explicit allowlist entries)"
  - "scripts/run_v2_gates.py contract-test-suite gate adds packages/solution-loader/src, solutions/lawfirm/src, and solutions/demo_non_legal/src to PYTHONPATH"
  - "solutions_meta.py registration glue: register_lawfirm_materializer / register_demo_non_legal_materializer helpers so the aggregate test does not need to know each pack's registration helper"

patterns-established:
  - "privacy-scanner-on-bundle-dir: downstream caller assertion, not a loader invariant — scan_bundle_dir is run on materialized bundles to assert privacy compliance"
  - "aggregate-evidence-test: one test class wires every phase artifact into a single view (extends Phase 11/12 pattern)"
  - "lazy-import-with-fallback: cross-package imports use lazy loading with graceful degradation to keep the privacy scanner usable even if the source pack is not on PYTHONPATH"

requirements-completed:
  - REQ-solution-loader
  - REQ-solution-backend-portability
  - REQ-solution-privacy-gate
  - REQ-nonlegal-solution-composability

# Metrics
duration: 3min
completed: 2026-06-30
---

# Phase 13 Plan 04: Solution Privacy Scan + Phase 13 Contract Evidence Summary

**Stdlib-only `scan_bundle_dir` privacy scanner + 24 aggregate contract evidence tests + V2 gate wiring + boundary allowlist update — proving all Phase 13 artifacts agree on default-off, sanitized, and industry-neutral claims.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-30T01:02:00Z
- **Completed:** 2026-06-30T01:05:27Z
- **Tasks:** 7 plan steps (single atomic testing-infrastructure commit)
- **Files created:** 4
- **Files modified:** 5
- **Insertions:** 527

## Accomplishments

- `packages/solution-loader/src/inkstatute_solution_loader/privacy_scan.py` exposes `scan_bundle_dir(path: Path) -> list[Issue]` — stdlib-only, reuses `inkstatute_solutions_lawfirm.sanitize.scan_text` via lazy import with a graceful fallback to name-only scan. Returns empty list for a clean bundle; returns ≥1 Issue for each refusal class: secret marker in a `.md` file, raw_payload key in `tools.json`, log file (`app.log`) presence, db file (`profile.db`) presence, media file (`cover.png`) presence, customer doc filename (`case_123.docx`) presence, confidential_artifact string in any text file. Each Issue has `path=<relative path under bundle>`, `rule=<refusal class>`, `severity="error"`, `message=<human-readable>`.
- `packages/contract-test-suite/tests/test_phase13_solution_evidence.py` ships 24 aggregate evidence tests grouped into `TestManifestNeutrality` (5), `TestMaterializerRoundTrip` (6), `TestSolutionPrivacyGate` (9), `TestComposability` (4) — proving: lawfirm + demo_non_legal manifests both pass `validate()`; both materialize_for produce sanitized bundles inside caller-provided output_dir; both bundles pass `scan_bundle_dir`; both declare `side_effect_kinds=("write_dir",)`; bundle_ref resolves inside output_dir; each privacy refusal class triggers a scanner Issue; clean bundle yields zero Issues; binary files scan by name only (extension); a single `DefaultSolutionLoader` handles both solutions sequentially without reconfiguration.
- `packages/contract-test-suite/fixtures/phase13_solution_bundles.json` — sanitized evidence fixture with `not_live_acceptance=true`, `evidence_scope="sanitized_fixture_only"`, `raw_payload_policy="raw_payload_ref_and_hashes_only"`, expected lawfirm/demo_non_legal bundle metadata, and one example per refusal class.
- `packages/solution-loader/src/inkstatute_solution_loader/solutions_meta.py` — `register_lawfirm_materializer` / `register_demo_non_legal_materializer` glue so the aggregate evidence test does not need to know each pack's registration helper.
- `packages/contract-test-suite/scripts/run_contract_tests.py` `SOURCE_PATHS` updated with `packages/solution-loader/src`, `solutions/lawfirm/src`, `solutions/demo_non_legal/src` so the test runner discovers the new modules.
- `scripts/run_v2_gates.py` contract-test-suite gate `PYTHONPATH` extended with `packages/solution-loader/src`, `solutions/lawfirm/src`, `solutions/demo_non_legal/src`.
- `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py` `BoundaryAllowlistPolicy.concrete_package_roots` extended with `packages/solution-loader/` and `solutions/` so the new concrete dirs are accepted by the neutral boundary scan.
- `packages/contract-test-suite/tests/test_boundary_allowlist.py` gains `test_allows_phase13_solution_and_loader_package_paths` covering the new allowed paths and the repo-wide neutral boundary scan.
- `packages/solution-loader/src/inkstatute_solution_loader/__init__.py` re-exports `scan_bundle_dir`, `TEXT_EXTENSIONS`, `BINARY_REFUSE_EXTENSIONS` from `privacy_scan` (closes the 13-01-deferred re-export).

## Task Commits

This plan was executed as a single atomic testing-infrastructure deliverable (all 7 plan steps produce one cohesive contract-evidence layer; splitting would leave the gate wiring non-functional mid-plan):

1. **Solution privacy scanner + Phase 13 aggregate contract evidence + V2 gate wiring** — `583881f` (feat)

**Plan metadata:** this SUMMARY (docs commit pending after this write).

## Files Created/Modified

- `packages/solution-loader/src/inkstatute_solution_loader/privacy_scan.py` — `scan_bundle_dir(path)`, `TEXT_EXTENSIONS`, `BINARY_REFUSE_EXTENSIONS`, lazy-import of `inkstatute_solutions_lawfirm.sanitize` with fallback.
- `packages/solution-loader/src/inkstatute_solution_loader/solutions_meta.py` — `register_lawfirm_materializer` / `register_demo_non_legal_materializer` registration glue.
- `packages/contract-test-suite/tests/test_phase13_solution_evidence.py` — 24 aggregate evidence tests across 4 test classes.
- `packages/contract-test-suite/fixtures/phase13_solution_bundles.json` — sanitized evidence fixture.
- `packages/solution-loader/src/inkstatute_solution_loader/__init__.py` — re-exports `scan_bundle_dir`, `TEXT_EXTENSIONS`, `BINARY_REFUSE_EXTENSIONS` (modified).
- `packages/contract-test-suite/scripts/run_contract_tests.py` — `SOURCE_PATHS` extended with 3 new package roots (modified).
- `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py` — `BoundaryAllowlistPolicy.concrete_package_roots` extended with `packages/solution-loader/` and `solutions/` (modified).
- `packages/contract-test-suite/tests/test_boundary_allowlist.py` — `test_allows_phase13_solution_and_loader_package_paths` added (modified).
- `scripts/run_v2_gates.py` — contract-test-suite gate `PYTHONPATH` extended with 3 new package source roots (modified).

## Decisions Made

- **Single atomic commit for the testing infrastructure:** Plan steps 1–7 produce one cohesive contract-evidence layer; committing per-step would leave the gate wiring non-functional mid-plan (e.g., `run_contract_tests.py` SOURCE_PATHS without the boundary allowlist update would surface as test-discovery failures). Committed as one `feat(13-04)` commit.
- **`solutions_meta.py` registration glue (Rule 2 — missing critical functionality):** The aggregate test imports `register_lawfirm_materializer` / `register_demo_non_legal_materializer` from `solutions_meta.py` so it does not need to know each pack's internal `register_into` helper. Without this glue, the aggregate test would need to import each pack's `__init__.py` and call pack-specific helpers — brittle and not composability-proving.
- **Lazy-import with fallback:** `privacy_scan.py` lazy-imports `inkstatute_solutions_lawfirm.sanitize` so the privacy scanner is usable even if the lawfirm pack is not on PYTHONPATH (test-time fallback to name-only scan). This avoids a hard cross-package dependency at import time.
- **BoundaryAllowlistPolicy `concrete_package_roots` extension:** Added `packages/solution-loader/` and `solutions/` (not just `solutions/lawfirm/` and `solutions/demo_non_legal/`) so future solution packs and the loader package itself are accepted by the neutral boundary scan without per-pack allowlist edits.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing Critical] Added `solutions_meta.py` registration glue**
- **Found during:** Task 3 (aggregate evidence test)
- **Issue:** The aggregate test needs to register both `LawfirmHermesMaterializer` and `DemoNonLegalHermesMaterializer` into the same `MaterializerRegistry`. Without glue helpers, the test would need to import each pack's `__init__.py` and call pack-specific `register_into` helpers — brittle and not composability-proving.
- **Fix:** Added `packages/solution-loader/src/inkstatute_solution_loader/solutions_meta.py` with `register_lawfirm_materializer` / `register_demo_non_legal_materializer` helpers that wrap each pack's `register_into` call. The aggregate test imports these helpers and proves composability through a single registration surface.
- **Files modified:** `packages/solution-loader/src/inkstatute_solution_loader/solutions_meta.py` (created)
- **Verification:** 24 aggregate evidence tests pass; the `TestComposability` class uses `register_lawfirm_materializer` and `register_demo_non_legal_materializer` to register both packs into the same registry without conflict.
- **Committed in:** `583881f` (part of the testing-infrastructure commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical — registration glue)
**Impact on plan:** The glue is a minimal, composability-proving addition; it does not change the plan's specified public surface or scope. No scope creep — the aggregate test's composability guarantee depends on this glue.

## Issues Encountered

None — the plan shipped cleanly. The `scripts/run_v2_gates.py` exit-0 verification was confirmed by the executor before commit.

## User Setup Required

None — no external service configuration required. The privacy scanner and aggregate evidence tests are library-only; the V2 gate wiring is repo-local.

## Known Stubs

None — all 13-04 acceptance criteria pass with real behavior. The `scan_bundle_dir` lazy-import fallback to name-only scan is a graceful-degradation path, not a stub — the scanner still flags refused extensions and obvious file-name patterns when the lawfirm sanitize module is unavailable.

## Next Phase Readiness

- Phase 13 is complete: all 4 plans shipped, 24 aggregate evidence tests pass, `scripts/run_v2_gates.py` exits 0, boundary allowlist accepts the new paths.
- `scan_bundle_dir` is ready for downstream callers (operators, CI gates) to assert privacy compliance on any materialized bundle.
- The aggregate evidence test pattern is ready for Phase 14+ to extend with new solution packs (IT-ops, finance, etc.) — each new pack adds a manifest + materializer + `register_into` helper + `solutions_meta.py` glue entry, and the aggregate test extends with the new pack's assertions.
- No blockers. Ready for phase verification (`gsd-verifier`) and milestone audit (`gsd-audit-milestone`).

---
*Phase: 13-solutionloader-lawyer-non-legal-solutions*
*Completed: 2026-06-30*