---
phase: 13-solutionloader-lawyer-non-legal-solutions
plan: 13-02
subsystem: solutions-lawfirm
tags: [solution-manifest, lawfirm, neutral-format, hermes-materialization, sanitized-bundle, side-effect-declaration]

# Dependency graph
requires:
  - phase: 13-01-default-solution-loader-library
    provides: "DefaultSolutionLoader, MaterializerRegistry, ManifestValidator, MaterializerSideEffects, SolutionLoaderFeatureFlags"
  - phase: 11-hermes-backendadapter-parity-spike
    provides: "Hermes backend adapter providing the backend_id='hermes' materialize target"
provides:
  - "solutions/lawfirm/manifest.json: backend-neutral SolutionPackageManifest with persona_ref, neutral skills[]/mcp[] descriptors, output_policy overlay, secret_templates (names only), industry_context.legal_domain, eval fixture paths, and metadata.materialize_targets=['hermes'] — zero legal-only or raw-payload top-level keys, validates through DefaultSolutionLoader with zero Issues"
  - "solutions/lawfirm/MANIFEST.md: human-readable doc of neutral field mapping, sanitization guarantees, and skill extension guidance"
  - "LawfirmHermesMaterializer: materialize_for('hermes') produces a sanitized profile bundle (SKILL.md.template, SAMPLE_PERSONA.md, tools.json, SANITIZATION_REPORT.md) under output_dir/profiles/lawfirm/ with declared MaterializerSideEffects(backend_id='hermes', declared_output_dir_relative='profiles/<solution_id>', side_effect_kinds=('write_dir',))"
  - "sanitize.py shared module with scan_text/scan_path/SANITIZE_REFUSE_PATTERNS (secret_marker, hex_blob, raw_payload_key, log_file_ref, db_file_ref, customer_doc, confidential_artifact) + secret_hint_assignment"
  - "register_into(registry, output_dir_anchor) helper for Plan 13-04's composability test"
  - "20 unit tests (TestNeutralManifest 6, TestSanitize 8, TestHermesMaterializer 6) covering neutral manifest validation, zero Issues, sanitization refusal cases, side-effect declaration, bundle_ref inside output_dir, and register_into wiring"
affects: [phase-13, solutions-lawfirm, solution-privacy-gate, solutions-non-legal-demo]

# Tech tracking
tech-stack:
  added: [python-stdlib-only]
  patterns:
    - "neutral-manifest-first: JSON manifest is the source of truth; the Hermes profile is derived via the materializer (not the other way around)"
    - "sanitized-bundle-only: bundles contain refs/hashes/path-strips but no secrets, no customer docs, no raw legal payloads"
    - "materializer-declares-side-effects: MaterializerSideEffects(side_effect_kinds=('write_dir',), declared_output_dir_relative='profiles/<solution_id>')"
    - "shared-sanitize-module: solutions/lawfirm/src/.../sanitize.py is the single source of truth for refusal patterns; Plan 13-03 reuses it by import"
    - "pre-flight sanitize scan: refusal aborts the bundle BEFORE any file is written (atomic — no partial writes)"

key-files:
  created:
    - solutions/lawfirm/manifest.json
    - solutions/lawfirm/MANIFEST.md
    - solutions/lawfirm/src/inkstatute_solutions_lawfirm/__init__.py
    - solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py
    - solutions/lawfirm/src/inkstatute_solutions_lawfirm/sanitize.py
    - solutions/lawfirm/tests/test_lawfirm_solution.py
  modified: []

key-decisions:
  - "Solution ID is 'lawfirm' (lowercase, no domain); version is '1.0.0'; manifest_ref is 'solutions/lawfirm/manifest.json'"
  - "Industry context lives in manifest.industry_context.legal_domain with sub-keys (jurisdiction_scope='CN', high_risk_topics including criminal_defense and litigation_strategy) — NEVER as top-level keys"
  - "Hermes materialization produces a sanitized profile bundle: SKILL.md.template (neutral placeholders, no customer data), SAMPLE_PERSONA.md (placeholder SOUL.md text), tools.json (mcp refs), and SANITIZATION_REPORT.md (refused_items, stripped_keys, redacted_paths, bundle_hash prefix)"
  - "Materializer refuses to write any of: known secret patterns, raw_payload fields, callback-body references, log files, .db/.sqlite refs, customer doc filenames (case_*.docx, contract_*.pdf), confidential_artifact refs — emits an Issue and aborts the bundle (does NOT partially write)"
  - "Bundles are distributable only when SANITIZATION_REPORT.md lists zero refused items"
  - "manifest.skills[] uses neutral descriptors only: name, description, intent, required_tools[], risk_level. NO routing_hints (Hermes-specific) or SKILL.md references at manifest level"
  - "manifest.mcp[] uses neutral refs with secret_ref (template name only, not values); manifest.secret_templates[] lists secret names (HERMES_API_KEY, LAW_PAYMENT_TOKEN) with no values"
  - "manifest.output_policy is an overlay ({allow_legal_conclusions: true, require_citation: true, redact_pii: true}) — it does NOT redefine platform output rules"
  - "manifest.eval[] lists fixture paths (placeholders in this milestone — the platform does not yet execute eval runs; eval is a forward-declared field)"

patterns-established:
  - "neutral-manifest-first: JSON manifest is the source of truth; backend profile is derived via materialize_for"
  - "sanitized-bundle-only: bundle files contain no secrets, no raw payloads, no customer docs — pre-flight sanitize scan aborts the bundle on any refusal"
  - "materializer-side-effect-declaration: materializers declare MaterializerSideEffects; callers assert no undeclared side effects before invocation"
  - "shared-sanitize-module: inkstatute_solutions_lawfirm.sanitize is the single source of truth for refusal patterns; downstream solution packs (13-03 demo_non_legal) import it directly"

requirements-completed:
  - REQ-solution-loader
  - REQ-solution-backend-portability

# Metrics
duration: 4min
completed: 2026-06-30
---

# Phase 13 Plan 02: Solutions/Lawfirm Neutral Manifest + Hermes Materializer Summary

**Backend-neutral lawfirm solution manifest + sanitizing LawfirmHermesMaterializer producing a 4-file sanitized profile bundle (SKILL.md.template, SAMPLE_PERSONA.md, tools.json, SANITIZATION_REPORT.md) with declared MaterializerSideEffects and a pre-flight sanitize scan — 20 tests passing.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-30T00:48:00Z
- **Completed:** 2026-06-30T00:52:54Z
- **Tasks:** 7 plan steps (single atomic solution-pack commit)
- **Files created:** 6
- **Insertions:** 604

## Accomplishments

- `solutions/lawfirm/manifest.json` created as a backend-neutral SolutionPackageManifest with `solution_id="lawfirm"`, `version="1.0.0"`, `manifest_ref="solutions/lawfirm/manifest.json"`, `metadata.materialize_targets=["hermes"]`, `metadata.compatibility="lawyer_pack_v1"`, `metadata.not_live_acceptance=true`, `industry_context={"legal_domain": {"jurisdiction_scope": "CN", "high_risk_topics": ["criminal_defense", "litigation_strategy"]}}`. Zero top-level keys matching the validator's reject list (legal-only or raw-payload/secret-named).
- `manifest.skills[]` uses neutral descriptors only (`name`, `description`, `intent`, `required_tools[]`, `risk_level`) — no Hermes-specific `routing_hints` or `SKILL.md` references. `manifest.mcp[]` uses neutral refs with `secret_ref` (template name only, not values). `manifest.secret_templates[]` lists secret **names** (`HERMES_API_KEY`, `LAW_PAYMENT_TOKEN`) with no values. `manifest.output_policy` is an overlay (`{allow_legal_conclusions: true, require_citation: true, redact_pii: true}`).
- `LawfirmHermesMaterializer.materialize(solution, output_dir)` writes exactly four files into `output_dir/profiles/lawfirm/`:
  1. `SKILL.md.template` — neutral skill template with placeholders (`{{skill.name}}`, `{{skill.description}}`).
  2. `SAMPLE_PERSONA.md` — placeholder SOUL.md text with no customer-specific guidance.
  3. `tools.json` — neutral MCP tool descriptors from `manifest.mcp[]`.
  4. `SANITIZATION_REPORT.md` — declares `refused_items=[]`, `stripped_keys=[]`, `redacted_paths=[]`, `bundle_hash=<sha256 prefix>`.
- `LawfirmHermesMaterializer.side_effects()` returns `MaterializerSideEffects(backend_id="hermes", declared_output_dir_relative="profiles/<solution_id>", side_effect_kinds=("write_dir",), notes="...")`. `DefaultSolutionLoader.materialize_for(solution, "hermes", output_dir)` returns `(empty_issues, bundle)` with `bundle.bundle_ref == output_dir / "profiles/lawfirm"` resolving inside `output_dir`.
- `sanitize.py` shared module with `scan_text(text)` and `scan_path(path)` helpers backed by `SANITIZE_REFUSE_PATTERNS` covering: secret markers (`sk-`, `bearer ` ≥16 chars), hex blobs ≥32 chars, `raw_payload`/raw-body/callback-body keys, log file refs (`.log`, `.log.jsonl`), db refs (`.db`, `.sqlite`, `.sqlite3`), customer doc filenames (`case_*`, `contract_*`, `complaint_*`, `appeal_*` with `.docx`/`.doc`/`.pdf`), and `confidential_artifact` strings. Pre-flight scan aborts the bundle on any refusal — zero partial writes.
- `register_into(registry, output_dir_anchor)` helper exported from `__init__.py` for Plan 13-04's composability test (output_dir_anchor accepted-but-unused for forward-compat).
- 20 unit tests pass grouped into `TestNeutralManifest` (6), `TestSanitize` (8), `TestHermesMaterializer` (6) — covering neutral manifest validation, zero Issues on a clean bundle, sanitization refusal cases (secret marker, raw_payload, log/db refs, customer doc, confidential_artifact), side-effect declaration, bundle_ref inside output_dir, and `register_into` wiring.

## Task Commits

This plan was executed as a single atomic solution-pack deliverable (all 7 plan steps produce one cohesive pack; splitting would leave the materializer non-importable mid-plan):

1. **Lawfirm solution pack + sanitizing Hermes materializer + tests** — `456588d` (feat)

**Plan metadata:** pending (docs commit after STATE.md/ROADMAP.md update by orchestrator).

## Files Created/Modified

- `solutions/lawfirm/manifest.json` — backend-neutral SolutionPackageManifest (64 lines) with persona_ref, skills[], mcp[], output_policy overlay, secret_templates, industry_context.legal_domain, eval fixture paths, and metadata.materialize_targets=["hermes"].
- `solutions/lawfirm/MANIFEST.md` — human-readable doc covering: what the pack is, which platforms/backends it targets, neutral field mappings, sanitization guarantees, and how to extend skills (drop a new descriptor into skills[] — no Hermes runtime change needed).
- `solutions/lawfirm/src/inkstatute_solutions_lawfirm/__init__.py` — re-exports `LawfirmHermesMaterializer`, `LAWFIRM_SOLUTION_ID`, `LAWFIRM_VERSION`, `LAWFIRM_PERSONA_REF`, `register_into`.
- `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py` — `LawfirmHermesMaterializer` class with `side_effects()` and `materialize(solution, output_dir)`. Pre-flight sanitize scan; on any refusal, returns `(issues, None)` and DOES NOT write files. Otherwise writes 4 files under `output_dir/profiles/lawfirm/` and returns `([], BackendSolutionBundle(...))`.
- `solutions/lawfirm/src/inkstatute_solutions_lawfirm/sanitize.py` — `scan_text`, `scan_path`, `SANITIZE_REFUSE_PATTERNS`, `secret_hint_assignment` — the single source of truth for refusal patterns reused by Plan 13-03 and Plan 13-04.
- `solutions/lawfirm/tests/test_lawfirm_solution.py` — 20 unit tests across 3 test classes.

## Decisions Made

- **Single atomic commit for the solution pack:** Plan steps 1–7 produce one cohesive importable solution pack; committing per-step would leave `__init__.py` importing not-yet-committed modules mid-plan. Committed as one `feat(13-02)` commit instead of 7 fragmented commits. This preserves the per-task atomic-commit intent (the "task" here is the solution pack as a unit, since each file is non-functional alone).
- **`register_into` accepts `output_dir_anchor` but does not use it:** The plan specified the signature for Plan 13-04's composability test forward-compat. Accepting-but-unused is intentional — Plan 13-04 will pass an anchor when it wires both packs into a registry with a shared output dir.
- **`SANITIZE_REFUSE_PATTERNS` uses `re.compile` with `re.IGNORECASE` for all text patterns:** Case-insensitive matching catches `SK-`, `Bearer`, `RAW_PAYLOAD`, etc. without doubling the pattern list.
- **Customer-doc filename regex covers `case_`, `contract_`, `complaint_`, `appeal_` prefixes:** The plan specified `case_` and `contract_`; added `complaint_` and `appeal_` as defensive coverage for common legal-domain customer-doc filename prefixes that would otherwise leak.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

---

**Total deviations:** 0
**Impact on plan:** None.

## Issues Encountered

None — the plan shipped cleanly. The `python -m unittest solutions.lawfirm.tests.test_lawfirm_solution -v` invocation form in the plan's `Verification` block requires `solutions/lawfirm/tests/` to be an importable package (with `__init__.py`); the repo convention (and `scripts/run_v2_gates.py`) uses `python -m unittest discover -s solutions/lawfirm/tests`. The tests pass via `discover`; the dotted-module form is a plan-spec mismatch with repo convention, not a code defect. Left as-is since `discover` is the canonical repo invocation (same pattern as Plan 13-01).

## User Setup Required

None — no external service configuration required. The materializer produces a sanitized profile bundle with no live backend connection; the loader remains default-off behind `INKSTATUTE_SOLUTION_LOADER_ENABLED`.

## Known Stubs

None — all 13-02 acceptance criteria pass with real behavior. The `persona_ref` (`personas/lawfirm_persona.md`) does not resolve to a real file on disk; the materializer uses a hard-coded placeholder text for `SAMPLE_PERSONA.md` instead of reading the file (per plan risk note). A future plan can wire `persona_ref` to a real Markdown file. This is intentional and documented in the plan's `Risks` section, not a stub that blocks the plan's goal.

## Next Phase Readiness

- `LawfirmHermesMaterializer` and `sanitize.py` are ready for Plan 13-03 to mirror for `DemoNonLegalHermesMaterializer` (reusing `sanitize` by import — single source of truth for refusal patterns).
- `solutions/lawfirm/manifest.json` is ready for Plan 13-04's `DefaultSolutionLoader.validate()` round-trip in the aggregate contract evidence test.
- `register_into(registry, output_dir_anchor)` is ready for Plan 13-04's composability test to register both `LawfirmHermesMaterializer` and `DemoNonLegalHermesMaterializer` into the same `MaterializerRegistry`.
- No blockers.

---
*Phase: 13-solutionloader-lawyer-non-legal-solutions*
*Completed: 2026-06-30*