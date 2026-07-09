# Phase 62: QQ Egress Sender — Text + Markdown + Keyboard - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

QQ Bot text messages (`msg_type=0`) are delivered with `msg_id`+`msg_seq` dedupe and retry; markdown+keyboard feedback cards (`msg_type=2`) are delivered with callback buttons; markdown replies (`msg_type=2`) are delivered for structured legal answers; passive-reply time window is tracked with window-expiry delivery failure + interim service notice; output boundary is enforced.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints from ROADMAP / ADAPTER-04:
- Reuse Phase 61 `TokenManager` for Authorization bearer tokens
- Keep `dependencies = []` (stdlib urllib + asyncio.to_thread)
- No `wecom_service` imports (`test_no_wecom_import.py` must pass)
- Do not modify frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, or channel-core modules
- QQ-specific behavior via `ChannelDelivery.metadata` / capability metadata only
- Output boundary: filter/rewrite/drop backend gateway/system/meta notices before user delivery
- Passive-reply windows: C2C 60min/4, group 5min/5 per `msg_id`; expiry → delivery failure + InkStatute-owned interim service notice
- Feedback card buttons: up / down / needs_fix / route_wrong
- `adapter.py` `deliver()` wires the new sender

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research. Prior phase: 61 TokenManager (`token_manager.py`).

</code_context>

<specifics>
## Specific Ideas

Requirements: EGRESS-02, EGRESS-03, EGRESS-04, EGRESS-07.
Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped. Rich media (EGRESS-05/06) is Phase 63.

</deferred>
