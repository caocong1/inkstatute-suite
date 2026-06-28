# Phase 10: Embeddable RunRuntime + Fake Backend - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Implement `RunRuntime` as a dependency-injected, embeddable library and prove the full run lifecycle against fakes with no live system.

Success criteria:
- `RunRuntime` implements create/poll/stream/cancel/approve against a `FakeBackendAdapter` and `FakeChannelAdapter`.
- `RunRuntime` constructs with zero channels and with no network server, preserving embeddability invariants N1/N4.
- Every run event/delta passes through the assistant output boundary; leak fixtures prove meta/tool/approval/gateway events never surface to ordinary users.
- Contract-log store is append-only and `raw_payload_ref`-first; run logs store refs/hashes only, never secrets or raw payloads.
- All new lanes are gated behind default-OFF feature flags.

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
