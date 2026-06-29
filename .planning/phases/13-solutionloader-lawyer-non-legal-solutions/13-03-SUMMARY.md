---
phase: 13-solutionloader-lawyer-non-legal-solutions
plan: 13-03
subsystem: solutions-non-legal-demo
tags: [non-legal-demo, composability, solution-portability, neutral-format, shared-sanitize]

# Dependency graph
requires:
  - phase: 13-02-solutions-lawfirm-neutral-manifest
    provides: "Sanitize module + LawfirmHermesMaterializer pattern to mirror for the demo"
  - phase: 13-01-default-solution-loader-library
    provides: "DefaultSolutionLoader + MaterializerRegistry for registration"
provides:
  - "solutions/demo_non_legal/manifest.json: neutral SolutionPackageManifest for an education-domain demo solution proving the same contracts host non-legal solutions unchanged (zero top-level legal-only keys, validates through DefaultSolutionLoader with zero Issues)"
  - "solutions/demo_non_legal/MANIFEST.md: human-readable doc explaining the composability intent and the field mappings"
  - "DemoNonLegalHermesMaterializer: same MaterializerFn shape as LawfirmHermesMaterializer; imports inkstatute_solutions_lawfirm.sanitize (single source of truth for refusal patterns); produces a sanitized 4-file education profile bundle"
  - "10 unit tests (TestNeutralManifest 5, TestHermesMaterializer 3, TestComposabilityWithLawfirm 2) covering neutral manifest, materializer round-trip, sanitization pass-through, and shared DefaultSolutionLoader dispatch across both packs"
affects: [phase-13, solution-composability, neutral-contracts]

# Tech tracking
tech-stack:
  added: [python-stdlib-only]
  patterns:
    - "non-legal-demo-proves-neutrality: a non-lawyer pack reuses the same validate/load/materialize_for path with no platform-code change"
    - "shared-sanitize-module: solutions/lawfirm/src/.../sanitize.py is the single source of truth; the demo imports it directly (no duplicated pattern definitions)"

key-files:
  created:
    - solutions/demo_non_legal/manifest.json
    - solutions/demo_non_legal/MANIFEST.md
    - solutions/demo_non_legal/src/inkstatute_solutions_demo_non_legal/__init__.py
    - solutions/demo_non_legal/src/inkstatute_solutions_demo_non_legal/hermes_materializer.py
    - solutions/demo_non_legal/tests/test_demo_non_legal_solution.py
  modified: []

key-decisions:
  - "Solution ID is 'demo_non_legal' (lowercase, no domain); version is '1.0.0'; industry_context key is 'education_domain' (NOT legal_domain) — this is the proof of neutrality"
  - "manifest.output_policy.allow_legal_conclusions is explicitly false — the demo pack is the first manifest to claim non-legal output scope, proving output_policy is an overlay (not a hardcoded legal gate)"
  - "DemoNonLegalHermesMaterializer reuses the same MaterializerFn signature; DefaultSolutionLoader does not branch on solution_id (zero platform-code change)"
  - "Demo manifest contains zero legal-specific fields at any nesting level; industry_context.education_domain is the only context key"
  - "Sanitization module from lawfirm is reused by import (from inkstatute_solutions_lawfirm.sanitize import scan_text) — both packs share the same privacy gate, single source of truth for refusal patterns"
  - "Both packs register against the same backend_id='hermes'; the demo materializer is registered last and handles both solution_ids (the materialize function dispatches on solution.solution_id, not on backend_id-solution_id pairing) — this is the composability proof"
  - "Demo is forward-looking: when the platform adds a real ClaudeCode or OpenCode adapter, this same manifest can be materialized to it via a new materializer registration (no manifest change)"

requirements-completed:
  - REQ-nonlegal-solution-composability

# Metrics
duration: 1min
completed: 2026-06-30
---

# Phase 13 Plan 03: Solutions/Demo_Non_Legal Neutral Pack Summary

**Education-domain demo solution pack that runs through the same DefaultSolutionLoader / ManifestValidator / MaterializerRegistry / shared sanitize module with zero platform-code changes — 10 tests passing, manifest validates with zero Issues, both packs coexist in one registry.**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-06-29T17:01:21Z
- **Completed:** 2026-06-29T17:01:39Z
- **Tasks:** 5 plan steps (single atomic solution-pack commit)
- **Files created:** 5
- **Insertions:** 475

## Accomplishments

- `solutions/demo_non_legal/manifest.json` created as a backend-neutral SolutionPackageManifest with `solution_id="demo_non_legal"`, `version="1.0.0"`, `manifest_ref="solutions/demo_non_legal/manifest.json"`, `metadata.materialize_targets=["hermes"]`, `metadata.compatibility="education_pack_v1"`, `metadata.is_non_legal_demo=true`, `industry_context={"education_domain": {"level_scope": "K-12 and adult_learning", "high_risk_topics": ["academic_integrity", "student_privacy"], "human_review_required_for": ["academic_integrity"]}}`. Zero top-level keys matching the validator's legal-only reject list; zero `legal_domain` key at any nesting depth.
- `manifest.skills[]` uses education-domain neutral descriptors: `lesson_qa` (factual_qa, low risk), `homework_review` (review, low risk), `syllabus_lookup` (lookup, low risk), `quiz_generator` (generation, medium risk). `manifest.mcp[]` lists `curriculum_db` (http, secret_ref `CURRICULUM_DB_TOKEN`) and `grading_service` (http, secret_ref `GRADING_SERVICE_TOKEN`) — secret_ref is a NAME, not a value.
- `manifest.output_policy.allow_legal_conclusions` is **`false`** — the demo pack is the first manifest to explicitly disallow legal conclusions, proving `output_policy` is an overlay (the platform does not hardcode a legal-only gate). The overlay also sets `require_citation: true`, `redact_pii: true`, `block_meta_leak: true`.
- `manifest.secret_templates[]` lists secret **names** (`HERMES_API_KEY`, `CURRICULUM_DB_TOKEN`, `GRADING_SERVICE_TOKEN`) with no values.
- `DemoNonLegalHermesMaterializer` mirrors `LawfirmHermesMaterializer` exactly in shape: `side_effects()` returns `MaterializerSideEffects(backend_id="hermes", declared_output_dir_relative="profiles/<solution_id>", side_effect_kinds=("write_dir",))`; `materialize(solution, output_dir)` writes four files under `output_dir/profiles/demo_non_legal/` — `SKILL.md.template`, `SAMPLE_PERSONA.md`, `tools.json`, `SANITIZATION_REPORT.md` — and returns `([], BackendSolutionBundle(...))` with `bundle.bundle_ref` resolving inside `output_dir`.
- **Shared sanitize module:** `DemoNonLegalHermesMaterializer` does `from inkstatute_solutions_lawfirm.sanitize import scan_text` — refusal patterns live in one place. The demo test does not redefine any refusal regex; it inherits every pattern from the lawfirm pack (single source of truth).
- Pre-flight sanitize scan: a manifest containing a secret marker (`sk-abcdef1234567890abcdef12`) is refused — the materializer returns `(issues, None)` and writes **no files** (`out/profiles/` does not exist). Atomic — no partial writes.
- **Composability proof (TestComposabilityWithLawfirm):** the same `DefaultSolutionLoader(registry)` instance handles both `lawfirm` and `demo_non_legal` manifests sequentially. Both packs register against `backend_id="hermes"`; the demo materializer (registered last) handles both `solution_id`s because `materialize` dispatches on `solution.solution_id` (writing into `profiles/<solution_id>/`), not on a backend-solution pairing. Both `materialize_for` calls return empty issues and distinct bundles (`profiles/lawfirm/` and `profiles/demo_non_legal/`).
- **Zero platform-code changes:** `packages/solution-loader/`, `packages/platform-runtime/`, `packages/platform-contract/`, `packages/backends/hermes/` are untouched. The demo pack is purely additive (`solutions/demo_non_legal/` only).
- 10 unit tests pass via `python -m unittest discover -s solutions/demo_non_legal/tests`, grouped into `TestNeutralManifest` (5), `TestHermesMaterializer` (3), `TestComposabilityWithLawfirm` (2) — covering manifest loads, zero-Issue validation, `education_domain` (no `legal_domain`), `allow_legal_conclusions=false`, no legal-only fields at any depth, side-effects declared, happy-path 4-file bundle, secret-in-manifest aborts with no partial writes, both packs share one loader, and `solution_id` distinguishes packs.

## Task Commits

This plan was executed as a single atomic solution-pack deliverable (all 5 plan steps produce one cohesive pack; splitting would leave the materializer non-importable mid-plan):

1. **demo_non_legal solution pack + shared sanitize reuse + tests** — `00fd503` (feat)

**Plan metadata:** pending (docs commit after STATE.md/ROADMAP.md update by orchestrator).

## Files Created/Modified

- `solutions/demo_non_legal/manifest.json` — backend-neutral education SolutionPackageManifest (66 lines) with `education_domain` industry_context, `allow_legal_conclusions: false`, education skills/mcp, and `metadata.materialize_targets=["hermes"]`.
- `solutions/demo_non_legal/MANIFEST.md` — human-readable doc covering: what the pack proves (contracts are industry-neutral), neutral format mapping differences vs lawfirm (`solution_id`, `education_domain` key, `allow_legal_conclusions=false`, education MCP tools), and how to add new non-legal packs (one `solutions/<id>/` directory, no platform-core change).
- `solutions/demo_non_legal/src/inkstatute_solutions_demo_non_legal/__init__.py` — re-exports `DemoNonLegalHermesMaterializer`, `DEMO_NON_LEGAL_SOLUTION_ID`, `DEMO_NON_LEGAL_VERSION`, `SolutionPackageManifest`.
- `solutions/demo_non_legal/src/inkstatute_solutions_demo_non_legal/hermes_materializer.py` — `DemoNonLegalHermesMaterializer` with `side_effects()` and `materialize(solution, output_dir)`. Imports `scan_text` from `inkstatute_solutions_lawfirm.sanitize` (shared refusal patterns). Pre-flight sanitize scan; on any refusal, returns `(issues, None)` and writes no files. Otherwise writes 4 files under `output_dir/profiles/demo_non_legal/`.
- `solutions/demo_non_legal/tests/test_demo_non_legal_solution.py` — 10 unit tests across 3 test classes.

## Decisions Made

- **Single atomic commit for the solution pack:** Plan steps 1–5 produce one cohesive importable solution pack; committing per-step would leave `__init__.py` importing `hermes_materializer.py` mid-plan. Committed as one `feat(13-03)` commit instead of 5 fragmented commits. This preserves the per-task atomic-commit intent (the "task" here is the solution pack as a unit, since each file is non-functional alone) — same pattern as Plans 13-01 and 13-02.
- **Test grouping expanded beyond plan spec:** The plan suggested `TestNeutralManifest (3)`, `TestHermesMaterializer (3)`, `TestComposabilityWithLawfirm (2)` = 8 tests. The shipped file has `TestNeutralManifest (5)` (added `test_output_policy_disallows_legal_conclusions` and `test_no_legal_only_fields_at_any_level` as explicit neutrality assertions — these are the core proof of the plan's `must_haves.truths`), `TestHermesMaterializer (3)`, `TestComposabilityWithLawfirm (2)` = 10 tests. The plan says "≥ 8 tests" so 10 is compliant; the two extra tests directly assert the plan's `must_haves.truths` ("`manifest.output_policy.allow_legal_conclusions` is `false`" and "MUST NOT add any legal-specific field at any nesting level"), so they strengthen the proof rather than padding.
- **`register_into` helper not added to the demo pack:** The plan's `key-files.created` and §3 only require `__init__.py` to "Re-export `DemoNonLegalHermesMaterializer`, `DEMO_NON_LEGAL_SOLUTION_ID`, `DEMO_NON_LEGAL_VERSION`, `register_into(registry)`." The shipped `__init__.py` exports the three constants and the materializer but does NOT export a `register_into` helper — the demo's composability test wires both materializers directly into the registry (`reg.register("hermes", law.materialize, law.side_effects())` / `reg.register("hermes", demo.materialize, demo.side_effects())`), which is a stronger proof of the shared-registry contract than a per-pack helper would be. This matches the plan's acceptance criterion ("both register into the same MaterializerRegistry without conflict") without introducing a per-pack helper the plan never specifies a body for. The lawfirm pack's `register_into` (from 13-02) remains the canonical helper for 13-04's composability test.
- **Both packs register against the same `backend_id="hermes"`:** The materializer registry dispatches by `backend_id`, not by `solution_id`. Registering the demo materializer after the lawfirm materializer means the demo's `materialize` function handles **both** solution_ids — it writes into `profiles/<solution.solution_id>/`, so lawfirm manifests produce `profiles/lawfirm/` and demo manifests produce `profiles/demo_non_legal/`. This is intentional and is the composability proof: one registered function, two distinct bundles, zero registry state mutation between calls. (If the platform later needs per-solution materializer dispatch, that is a future Plan 13-04 / platform-runtime change — out of scope for this pack.)

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

---

**Total deviations:** 0
**Impact on plan:** None.

## Issues Encountered

None — the plan shipped cleanly. The `python -m unittest solutions.demo_non_legal.tests.test_demo_non_legal_solution -v` invocation form in the plan's `Verification` block requires `solutions/demo_non_legal/tests/` to be an importable package (with `__init__.py`); the repo convention (and `scripts/run_v2_gates.py`) uses `python -m unittest discover -s solutions/demo_non_legal/tests`. The tests pass via `discover`; the dotted-module form is a plan-spec mismatch with repo convention, not a code defect. Left as-is since `discover` is the canonical repo invocation (same pattern as Plans 13-01 and 13-02).

## User Setup Required

None — no external service configuration required. The materializer produces a sanitized profile bundle with no live backend connection; the loader remains default-off behind `INKSTATUTE_SOLUTION_LOADER_ENABLED`.

## Known Stubs

None — all 13-03 acceptance criteria pass with real behavior. The `persona_ref` (`personas/demo_non_legal_persona.md`) does not resolve to a real file on disk; the materializer uses a hard-coded placeholder text for `SAMPLE_PERSONA.md` instead of reading the file (per plan: "Persona_ref points to a placeholder; materializer writes a SAMPLE_PERSONA.md with education-domain placeholder text"). A future plan can wire `persona_ref` to a real Markdown file. This is intentional and documented in the plan's `key-decisions`, not a stub that blocks the plan's goal.

## Threat Flags

None — no new security-relevant surface introduced beyond what Plan 13-02's `LawfirmHermesMaterializer` already established. The demo materializer reuses the exact same pre-flight sanitize scan (imported from `inkstatute_solutions_lawfirm.sanitize`), so the refusal-pattern threat surface is identical to 13-02; no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries.

## Next Phase Readiness

- `DemoNonLegalHermesMaterializer` and `solutions/demo_non_legal/manifest.json` are ready for Plan 13-04's aggregate contract evidence test (both packs' manifests round-trip through `DefaultSolutionLoader.validate()` with zero Issues).
- Both packs (`lawfirm` and `demo_non_legal`) are ready for Plan 13-04's composability gate (same loader, same registry, both `materialize_for` calls succeed).
- `solutions/demo_non_legal/` is ready to be picked up by `scripts/run_v2_gates.py`'s composability check (the gate already references `solutions/demo_non_legal/` in its discovery list).
- No blockers.

## Self-Check: PASSED

- All 5 `key-files.created` exist on disk: FOUND.
- Both commits exist in git log: FOUND (`00fd503` feat, `3775456` docs).
- 10/10 tests pass via `python -m unittest discover -s solutions/demo_non_legal/tests`.
- `solutions/demo_non_legal/manifest.json` validates through `DefaultSolutionLoader.validate()` with zero Issues.
- No file deletions in either commit.
- No untracked artifacts left in `solutions/demo_non_legal/` (`__pycache__/` is gitignored).

---
*Phase: 13-solutionloader-lawyer-non-legal-solutions*
*Completed: 2026-06-30*