# Phase 57: Admin Web UI + Lawyer Web Chat (C3 + C4) - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can use an Admin Web UI (`services/admin-web-ui/`) rendering an operator dashboard with session/task inspection, feedback review queue, gate status, and health monitoring, and lawyers can use a Web chat interface with real SSE, session auth, message history, file upload, feedback submission, and multi-device sync — both enforcing the output boundary.

**Depends on:** ?

**Success Criteria** (what must be TRUE):
1. Admin Web UI (`services/admin-web-ui/`) renders an operator dashboard with session/task inspection, feedback review queue, gate status visualization, and health monitoring; built with Preact + Tailwind (static bundle, no Node.js server required).
2. Admin Web UI consumes existing `admin-console-api` read endpoints plus new read route branches (`/mcp-servers`, `/model-gateway/health`, `/skills`, `/tenants`); RBAC middleware enforces role-based access between flag gate and route dispatch.
3. Admin Web UI enforces the output boundary: all backend content is rendered as escaped plaintext or DOMPurify-sanitized content — never `innerHTML`; CSP headers and httpOnly cookies prevent XSS; no secrets or raw legal payloads in browser storage.
4. Lawyer-facing Web chat promotes existing `web_sse` ChannelAdapter from fixture-grade to production with real SSE transport and RBAC session auth (lawyer role); provides session list, message history, file upload, feedback submission, and multi-device sync via server-side sessions.
5. Lawyer Web chat enforces the same output boundary as WeCom — no backend notices (gateway/meta/system/update/command) reach the lawyer; `web_sse_channel_enabled` defaults to `False`.

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
