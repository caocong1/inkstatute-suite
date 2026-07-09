# Phase 60: QQ Event Normalization - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

QQ Bot gateway envelope `{op, t, d}` is parsed into typed event categories (C2C message, GROUP_AT_MESSAGE_CREATE, INTERACTION_CREATE, validation challenge) with correct dispatch; C2C/group @-bot messages normalize into `AgentTurn` with @-bot prefix stripped and scene-aware `conversation_id`; INTERACTION_CREATE normalizes into `FeedbackEvent` with `source="card_button"` frozen enum.

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
