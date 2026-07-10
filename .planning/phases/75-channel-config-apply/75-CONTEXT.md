# Phase 75: Channel Config Apply - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operators can configure QQ and WeCom channel enablement and credential refs with dual-knob effective state visible, without collapsing safety knobs or echoing resolved secrets.

Requirements: CHAN-01, CHAN-02, CHAN-03, CHAN-04.

Success criteria:
1. Configure QQBot channel settings via admin config API (and channel SSR form when present)
2. Configure WeCom channel settings via admin config API (and channel SSR form when present)
3. Dual-knob effective enablement visible (platform flag AND host enabled) — no single bypass toggle
4. Credential fields accept secret refs only; GET never echoes resolved secrets

Depends on Phase 74 (`/config/*` API + RBAC). Incremental SSR forms allowed; Phase 78 owns complete CSRF-protected SSR surface verification.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss skipped. Use ROADMAP, success criteria, and codebase conventions.

Locked:
- Dual-knob channel enablement preserved (never collapse)
- Secrets as refs only; no echo of resolved values
- Extend admin-console-api + admin-web-ui stdlib SSR
- Hot-reload vs restart: MVP documents restart unless plan proves safe reload
- Carried human gates must not be auto-closed

</decisions>

<code_context>
## Existing Code Insights

Phase 73–74: OperatorConfigStore + `/config/{channels,providers,catalog,vision}` GET/PUT with RBAC.
Existing QQ/WeCom channel packages and host enable flags from prior milestones.
Admin-web-ui stdlib SSR patterns from v1.7+.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss skipped.

</specifics>

<deferred>
## Deferred Ideas

Provider catalog (76), vision runtime (77), complete SSR/docs/gate honesty (78).

</deferred>
