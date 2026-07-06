# Phase 51: RBAC (C1) - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can enforce role-based access control via a new `packages/rbac/` package implementing 4 roles (admin/operator/lawyer/viewer) with a permissions matrix, `RbacGuard` middleware, default-deny with CI scan for unannotated endpoints, and token-based auth with role+tenant claims using short-lived tokens.

**Depends on:** Phase 45
**Requirements:** RBAC-01, RBAC-02

**Success Criteria** (what must be TRUE):
1. `packages/rbac/` implements 4 roles (admin, operator, lawyer, viewer) with a declarative permissions matrix mapping endpoint → required role; `RbacGuard.check(role, endpoint)` middleware wraps admin API handlers.
2. RBAC enforces default-deny: a CI scan fails when any admin API endpoint lacks a role annotation; unannotated endpoints are treated as denied by default.
3. RBAC token-based auth issues short-lived tokens with role+tenant claims; `resolve_identity()` extracts claims from the token, with `check_auth_header` static-token fallback preserved when `rbac_enabled=False`.
4. `rbac_enabled` defaults to `False`; when disabled, the system falls back to v1.6 static-token behavior with no regression.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

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
