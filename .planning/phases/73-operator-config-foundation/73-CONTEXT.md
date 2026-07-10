# Phase 73: Operator Config Foundation - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operators have an InkStatute-owned, refs-only config authority that is off by default and never treats Hermes filesystem paths as config source of truth.

Requirements: CFG-01, CFG-02, CFG-03.

Success criteria:
1. Operator can persist channel/provider/catalog/vision config documents in an InkStatute store that accepts secret refs only and never stores raw secret values
2. When `operator_config_enabled` is OFF (default), config mutate paths refuse writes
3. Config schemas/validators reject Hermes `~/.hermes` / profile filesystem paths as config authority

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Locked from milestone init / PROJECT.md:
- Config secrets stay as refs; values resolve at process edge only
- Extend existing admin-console-api + admin-web-ui (stdlib SSR); no new SPA/DB/queue for MVP
- `operator_config_enabled` default OFF; dual-knob channel enablement preserved
- Never treat Hermes `~/.hermes` / profile filesystem as config authority

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

Prior research: `.planning/research/SUMMARY.md` (v1.10 stack/architecture for operator config).
Existing surfaces: admin-console-api, admin-web-ui, channel/provider packages from prior milestones.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped. CFG-F01..F03 and related future items remain beyond v1.10 per STATE.md.

</deferred>
