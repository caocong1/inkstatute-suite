# Phase 11: Hermes BackendAdapter + Parity Spike - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Implement the Hermes backend adapter, subprocess one-shot first, a non-mutating capability probe, and a fixture-based `/v1/runs` lawfirm-equivalence parity spike.

Success criteria:
- The Hermes adapter passes `BackendAdapter` Protocol conformance tests via subprocess one-shot.
- The capability probe is non-mutating and uses `/health`, `/v1/capabilities`, and `/v1/models`, never `GET /v1/runs/{id}`; probe failure falls back to one-shot with a sanitized audit reason.
- The `/v1/runs` lane exists behind `INKSTATUTE_HERMES_API_RUNS_ENABLED` and is not default.
- The parity spike compares `/v1/runs` vs one-shot on fixtures: legal Q&A, drafting plus artifact, follow-up, route-mismatch, MCP/tool task, and non-legal; one-shot stays default if the spike fails.
- `Approval` cannot auto-approve high-risk legal conclusions; no transcripts or secrets are committed.

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
