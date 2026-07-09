# Phase 66: Feedback Loop Parity + Interaction Recall - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

QQ Bot feedback loop is wired end-to-end (keyboard card dispatch → user button click → INTERACTION_CREATE → FeedbackEvent normalization → feedback-service dedupe/classify/queue); interaction ACK after feedback normalization; feedback dedupe via msg_id + button identity; is_wakeup interaction recall for over-window long-task completion (windowed 30-day periods, 1 per period); parity with WeCom feedback pipeline.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

Key constraints:
- End-to-end feedback: keyboard → INTERACTION_CREATE → FeedbackEvent → feedback-service
- Interaction ACK (PUT /interactions/{id}) after feedback normalization
- Dedupe: msg_id + button identity
- is_wakeup recall: 30-day windows, 1 per period
- Parity with WeCom feedback pipeline (compose patterns, no wecom_service import)
- dependencies=[]; no frozen Protocol/platform-contract/channel-core edits
- Reuse Phase 60 normalization FeedbackEvent + Phase 65 ack_interaction

</decisions>

<code_context>
## Existing Code Insights

Prior: Phase 60 INTERACTION_CREATE → FeedbackEvent; Phase 62 keyboard cards; Phase 65 two-tier ACK / ack_interaction. Feedback-service exists for WeCom path.

</code_context>

<specifics>
## Specific Ideas

Requirements: FEEDBACK-01, FEEDBACK-02, FEEDBACK-03, RECALL-01.

</specifics>

<deferred>
## Deferred Ideas

Smoke toolkit is Phase 67. Live promotion remains human gate.

</deferred>
