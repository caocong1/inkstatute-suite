# Phase 74: Admin Config API + RBAC - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Admin/operator roles can read and write config through an explicit `/config/*` API while lawyer/viewer roles cannot mutate and existing operational views stay read-only.

Requirements: ADM-01, ADM-03.

Success criteria:
1. Admin/operator roles can GET and PUT config resources under `/config/*`
2. Lawyer/viewer roles are denied config mutate (and cannot bypass via other admin routes)
3. Existing sessions/tasks/feedback/health/gates views remain read-only; config writes only succeed on the explicit `/config/*` surface
4. When the operator-config flag is OFF, PUT `/config/*` refuses writes even for admin/operator

Depends on Phase 73 (operator-config package + flag + store).

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Locked from prior phases / PROJECT.md:
- Config writes only on explicit `/config/*` (do not break admin read-only contract)
- `operator_config_enabled` default OFF; PUT refuses when OFF
- Secrets as refs only; never echo resolved secrets in GET
- Extend existing admin-console-api; no new SPA/DB/queue
- Phase 73 package `inkstatute_operator_config` is the store authority

</decisions>

<code_context>
## Existing Code Insights

Phase 73 delivered `packages/operator-config/` with schemas, validators, Hermes ban-list, flag-gated atomic store.
Admin console API and RBAC patterns exist from v1.6/v1.7 — research should map `/config/*` onto those.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

Channel apply (75), provider catalog (76), vision runtime (77), SSR forms (78) are out of scope.

</deferred>
