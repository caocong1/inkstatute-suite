# Phase 33: V2 Requirement Audit & Traceability Infrastructure - Context

**Gathered:** 2026-07-03
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can run a deterministic audit that maps every unchecked V2 Active requirement to concrete code evidence and classifies each as satisfied, partial, gap, or human_gate using three-level verification (schema → library surface → production wiring). The audit produces a traceability matrix, per-requirement evidence bundles, a machine-readable JSON sidecar, a PRD §10 criterion-to-test mapping, and a 9th V2 gate that fails on gaps.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key research findings to inform decisions:
- No new runtime dependencies — stdlib-only tooling (Python 3.11+ `pathlib`, `re`, `json`, `tomllib`, `argparse`, `dataclasses`, `subprocess`, `ast`)
- Follow the proven `scripts/check_v1_3_verification_artifacts.py` pattern for the audit script
- Invoke existing contract-test-suite evidence producers (`boundary_checks`, `privacy_scan`, `coverage_report`, `schema_validation`) rather than re-implementing checks
- JSON (not YAML) for traceability manifest — `json` is stdlib, PyYAML is not installed
- Extend `scripts/run_v2_gates.py` with one new `Gate(...)` entry for the 9th gate
- Three-level verification prevents the v1.4 MEM-07/MEM-16 false-positive pattern (infrastructure present but wiring missing)
- The 10 unchecked V2 Active requirements in PROJECT.md are the audit targets
- V2-PRD §10.1–10.4 acceptance criteria are the criterion-to-test mapping source

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

Key existing artifacts:
- `scripts/run_v2_gates.py` — V2 gate runner (424 tests, 7 suites, `--json-summary` output)
- `scripts/check_v1_3_verification_artifacts.py` — proven audit script pattern (regex, pathlib, argparse, dataclass)
- `packages/contract-test-suite/src/contract_test_suite/` — evidence producers (boundary_checks, privacy_scan, coverage_report, schema_validation, event_stream_replay, trial_acceptance)
- `packages/platform-contract/src/platform_contract/schemas/*.schema.json` — 17 schema files
- `.planning/PROJECT.md` — 10 unchecked Active requirements (lines 43-52)
- `docs/requirements/V2-PRD.md` — §10 acceptance criteria, §13 residual risks

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

Requirements for this phase: AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05, AUDIT-06, AUDIT-07

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
