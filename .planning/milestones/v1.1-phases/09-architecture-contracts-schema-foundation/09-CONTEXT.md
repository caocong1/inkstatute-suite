# Phase 09: Architecture Contracts & Schema Foundation - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Lock the four North Star interface contracts and extend the platform-contract package with the new neutral schemas, with zero runtime behavior change.

Success criteria:
- The North Star doc is promoted to `docs/architecture/` and the four Protocols (`ChannelAdapter`, `BackendAdapter`, `SolutionLoader`, `RunRuntime`) exist as signature-only stubs in `packages/platform-runtime`.
- New JSON Schemas and Python bindings exist in `platform-contract`: `ChannelMessage`, `ChannelDelivery`, `Run`, `RunEvent`, `RunStep`, `ToolCall`, `Approval`, `ArtifactRecord`, `Session`, `Tenant`, `Workspace`, `SolutionPackageManifest` plus neutral skill/MCP descriptors, `BotInstance`, and `ChannelBinding`.
- `Run.status` uses the existing `AsyncTaskState`; `AdapterCapabilitySet` is extended backward-compatibly; `ArtifactRecord` does not replace nested `AgentResult.artifacts`.
- ADR-0001 through ADR-0007 drafts exist under `docs/architecture/adr/`.
- The boundary-scan allowlist tool passes on neutral packages; a non-legal fixture validates with no platform-code change; existing V2 contracts still validate.

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
