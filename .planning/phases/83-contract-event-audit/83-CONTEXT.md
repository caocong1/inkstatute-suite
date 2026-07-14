# Phase 83: Contract Event Audit - Context

**Gathered:** 2026-07-14
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operators can browse AgentTurn and FeedbackEvent contract events in a paginated audit trail and reconstruct full traces by trace_id using existing conversation-read-view primitives.

Success criteria:
1. Operator can browse AgentTurn and FeedbackEvent contract events in a paginated audit trail view with timestamp, event type, session_id, and trace_id columns (reverse-chronological, cursor pagination, event-type filter)
2. Operator can click a trace_id to see the full trace reconstruction (all events sharing that trace_id) using existing conversation-read-view trace reconstruction primitives; a field allowlist displays refs (not resolved secrets) and every value passes through `scrub_contract_payload`/`html.escape`

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
