# Phase 1: Platform Contract Foundation - Context

**Gathered:** 2026-06-27
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

This phase delivers the pure `packages/platform-contract/` definition package for InkStatute V2. It defines the five platform event contracts, async task states, error categories, Python bindings, JSON Schema files, and fixtures needed by later phases. It must not implement Hermes hooks, runtime services, feedback normalization, read APIs, or CI orchestration beyond basic package self-checks.

</domain>

<decisions>
## Implementation Decisions

### Scope
- Implement `AgentTurn`, `AgentResult`, `FeedbackEvent`, `ExecutionTrace`, and `RouteDecision` as event contracts, not database tables.
- Keep the package pure-definition: no Hermes runtime import, no service process, no persistence layer, and no network access.
- Treat JSON Schema as the cross-language source format and Python bindings as the first runtime binding.
- Include sample fixtures that demonstrate object relationships through `turn_id`, `conversation_id`, `result_id`, `feedback_target`, and artifact identifiers.

### Schema Boundaries
- Legal-only fields must not become top-level required schema fields.
- Use `industry_context` and extension-style `metadata` objects for profile-specific or implementation-specific data.
- Async task states are `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`.
- Error categories are `contract_error`, `runtime_error`, and `channel_error`.

### Autonomy
- The agent may choose package internals conservatively as long as the public artifacts remain stable, simple, and testable.
- Prefer standard-library Python and JSON files unless a dependency is clearly necessary.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docs/requirements/V2-PRD.md` contains the authoritative schema field lists and acceptance criteria.
- `.planning/REQUIREMENTS.md` maps Phase 1 to `REQ-platform-contract-package` and `REQ-contract-event-schemas`.

### Established Patterns
- The repository is currently documentation-first with no existing package tooling.
- GSD state is committed under `.planning/` and should be updated as Phase 1 progresses.

### Integration Points
- Later phases will consume `packages/platform-contract/` from `packages/contract-test-suite/`, `services/hermes-contract-layer/`, `services/conversation-read-view/`, and `services/feedback-service/`.

</code_context>

<specifics>
## Specific Ideas

- Start with JSON Schema and Python bindings first; TypeScript is deferred until V2 priority work needs it.
- Keep examples non-sensitive and synthetic.
- Include at least one lawfirm-oriented fixture and one non-legal fixture to preserve industry-neutral shape.

</specifics>

<deferred>
## Deferred Ideas

- Full contract-test-suite, fixture replay runner, relationship coverage metrics, and CI gates belong to Phase 2.
- Hermes hook mapping and real hook output replay belong to Phase 3 and Phase 4.
- TypeScript bindings can follow after V2 priority work.

</deferred>
