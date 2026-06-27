# Phase 2: Contract Test Suite Foundation - Context

**Gathered:** 2026-06-27
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

This phase delivers the initial `packages/contract-test-suite/` harness that validates the Phase 1 platform contract artifacts before Hermes hook implementation begins. It should test JSON Schema shape, fixture replay basics, relationship integrity, and non-legal composability using local synthetic data. It must not implement Hermes hooks, real Hermes replay adapters, WeCom integration, feedback service, read-view APIs, or CI workflow files beyond package-local commands unless a plan explicitly scopes a minimal local runner.

</domain>

<decisions>
## Implementation Decisions

### Scope
- Build a package-local contract test suite that consumes `packages/platform-contract/`.
- Validate all five V2 event schemas and Phase 1 fixtures.
- Include relationship checks for `turn_id`, `conversation_id`, `result_id`, `feedback_target`, route decision, execution trace, and artifact identifiers.
- Include synthetic non-legal fixtures or checks proving finance/tax, engineering, and education examples do not require legal-only top-level fields.
- Keep CI wiring for Phase 7; this phase may provide commands that CI can later call, but should not add `.github/` workflows.

### Tooling
- Prefer Python stdlib `unittest` and local helper scripts unless an external dependency is clearly necessary.
- Treat `jsonschema` as optional only if already available; do not require it as a runtime dependency unless the plan explicitly updates package metadata and verification.
- Reuse Phase 1 `platform-contract` self-checks where useful, but keep this package as a separate harness under `packages/contract-test-suite/`.

### Autonomy
- The agent may choose the internal test layout and helper names.
- Plans must preserve the V2 thin-layer boundary: contract tests validate contract artifacts and synthetic events; they do not inspect or modify Hermes runtime.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/platform-contract/src/platform_contract/schemas/*.schema.json`
- `packages/platform-contract/fixtures/legal_wecom_contract_review.json`
- `packages/platform-contract/fixtures/non_legal_engineering_task.json`
- `packages/platform-contract/scripts/self_check.py`
- `packages/platform-contract/tests/test_self_check.py`

### Established Patterns
- Phase 1 uses Python stdlib-only self-checks and `unittest`.
- Schema/binding parity and privacy-boundary checks are already package-local quality gates.
- GSD Phase 1 produced `01-VERIFICATION.md` status `passed` and `01-REVIEW.md` status `clean`.

### Integration Points
- Phase 2 should depend on Phase 1 artifacts, not duplicate contract definitions.
- Phase 3 and Phase 4 will later add real Hermes hook output fixtures/adapters.
- Phase 7 will later wire the test suite into CI and coverage gates.

</code_context>

<specifics>
## Specific Ideas

- Provide a single local command for the suite, for example `PYTHONPATH=../platform-contract/src python -m unittest discover -s tests`, if the package layout supports it.
- Add test fixtures for non-legal finance/tax and education examples if Phase 1 only covers engineering.
- Make error messages useful for future Hermes mapper debugging.

</specifics>

<deferred>
## Deferred Ideas

- Real Hermes hook output replay and Hermes-specific adapters belong to Phase 3 and Phase 4.
- CI job wiring belongs to Phase 7.
- Contract log coverage metrics against real tasks belongs to later phases once real contract logs exist.
- WeCom end-to-end feedback validation belongs to Phase 5.

</deferred>
