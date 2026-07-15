# Phase 85: Login Session Auth - Context

**Gathered:** 2026-07-14
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operators can log in via username/password (env-credential MVP) and receive an HMAC-signed session cookie that coexists with existing Bearer token auth through the same RBAC guard pipeline.

Success criteria:
1. Operator can log in to the console via username/password (env-based credentials for MVP) and receive a signed session cookie that authenticates subsequent requests; logout invalidates the session
2. Session cookie auth coexists with existing Bearer token auth — Bearer header takes priority (API path unchanged), cookie auth is fallback for browser sessions; both paths resolve to a single `Identity` and pass through the same `RbacGuard` (no route bypasses the guard)
3. Session cookies are HMAC-signed with `RBAC_TOKEN_SECRET`, have configurable TTL, use `HttpOnly` + `SameSite` attributes, and rotate the session ID on successful login (session fixation prevention); the session store interface is extensible (env-credential MVP, future cred store swappable)
4. Login/logout flows are CSRF-protected (login CSRF prevention — CSRF token issued on GET `/login`, validated on POST, both session cookie and CSRF token rotated after login)

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
