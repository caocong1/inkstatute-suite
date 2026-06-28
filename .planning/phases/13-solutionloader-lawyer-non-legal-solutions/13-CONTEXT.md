# Phase 13: SolutionLoader + Lawyer & Non-Legal Solutions - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Prove the lawyer pack is a backend-portable solution, not platform core, and that a non-legal pack runs through the same contracts unchanged.

Success criteria:
- `SolutionLoader` validates and loads manifests, and `materialize_for("hermes")` produces or refreshes a sanitized lawfirm profile bundle with no undeclared side effects.
- The lawyer solution runs through platform contracts with zero new legal top-level fields in platform core.
- A `demo_non_legal` solution runs through the same contracts with no platform-code change.
- The solution privacy scan rejects secrets, logs, databases, media, raw payloads, customer documents, and confidential artifacts.
- Composability gates prove the platform core stays industry-neutral.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion because discuss was skipped per project workflow settings. Use the ROADMAP phase goal, success criteria, active V2 PRD, AGENTS.md boundaries, and existing codebase conventions to guide implementation.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

</code_context>

<specifics>
## Specific Ideas

No additional specific requirements were gathered. Refer to the ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
