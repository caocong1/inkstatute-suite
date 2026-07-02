# Phase 14: Memory Research and Contract Spec - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Phase 14 defines the backend-neutral context and memory vocabulary, JSON schemas, Python bindings, privacy policy, and external-memory evaluation criteria needed before runtime session resolution or memory writes are implemented. It must not make an external memory system mandatory for production legal use.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
- Keep the contract package dependency-free and aligned with the existing JSON Schema plus Python dataclass parity checks.
- Represent raw conversation/legal/customer material by references such as `source_refs`, `raw_payload_ref`, `summary_ref`, and `resume_state_ref`; do not introduce raw full-text memory storage.
- Treat external systems such as Mem0/Zep as optional future adapters behind a capability/evaluation contract, not as the default legal path.
- Keep legal-specific memory details inside `industry_context` or `metadata`, never as top-level required platform fields.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/platform-contract/src/platform_contract/schemas/*.schema.json` for contract schema shape.
- `packages/platform-contract/src/platform_contract/events.py` and `enums.py` for Python bindings.
- `packages/platform-contract/scripts/self_check.py` for schema/binding parity and fixture validation.
- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` for cross-package fixture validation.

### Established Patterns
- Schemas use draft 2020-12, `additionalProperties: false`, shared definitions in `common.schema.json`, and reference-first privacy fields.
- Python bindings are frozen dataclasses with default empty `metadata` and `industry_context` containers where applicable.
- Contract-test fixtures remain synthetic and use `fixture://` refs for source material.

### Integration Points
- New memory/context artifacts belong in `packages/platform-contract` first, then contract-test-suite fixture validation.
- Phase 15-18 runtime work should consume these contracts instead of inventing service-local shapes.

</code_context>

<specifics>
## Specific Ideas

No additional user-specific requirements; use ROADMAP, REQUIREMENTS, AGENTS, and existing contract package conventions.

</specifics>

<deferred>
## Deferred Ideas

- Runtime session resolver, interrupt persistence, context assembly, memory store behavior, and external adapter implementation are deferred to Phases 15-18.
- User-facing memory management UI is explicitly out of scope for this milestone.

</deferred>
