# Phase 68: Host Skeleton + Safety Baseline - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operators and CI can verify a deployable `services/qqbot-service/` skeleton exists with ADAPTER-04 isolation and secret-ref discipline before any webhook composition ships.

Requirements: SAFE-01, SAFE-02

Success criteria:
1. `services/qqbot-service/` exists with `pyproject.toml` `dependencies=[]` and a V2 gate PYTHONPATH entry covering the new service.
2. ChannelAdapter remains frozen at 6 methods; BackendAdapter remains frozen at 9 methods; no `wecom_service` import appears in the qqbot host/package path.
3. Feature flags that gate QQBot live IO default to OFF (including `qqbot_channel_enabled`).
4. Host config stores secrets as refs only; tests prove values are not committed and resolve only at process edge.
5. `.planning/phases/08-lawyer-trial-acceptance/` remains present (carried human-gate artifacts preserved).

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
