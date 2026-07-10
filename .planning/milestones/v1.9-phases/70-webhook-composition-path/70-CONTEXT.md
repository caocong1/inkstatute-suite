# Phase 70: Webhook Composition Path - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operators can deploy a thin InkStatute-owned QQBot webhook that composes package Protocol methods end-to-end with prompt verify-and-ACK before heavy agent work.

Requirements: HOST-01, HOST-02

Success criteria:
1. Operator can run a thin webhook host that composes `verify_and_ack` → ingress/session/feedback → `deliver` without reimplementing package crypto/normalize/send logic.
2. Webhook returns verify-and-ACK promptly for op=13 validation challenge and op=12 body ACK before heavy agent work.
3. Pure request handler + stdlib `http.server` wrapper capture raw body once, preserve signature verification, and apply output boundary on egress.
4. Unit tests with Fake transports prove the composition path without live QQ network.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 68–69 host patterns (`wiring.py`, secret refs, refuse-when-disabled), and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Phase 68: `services/qqbot-service/` skeleton, secret-ref config, ADAPTER-04 isolation.
Phase 69: `wiring.py` factory maps dual default-OFF knobs, injects QQBotChannelAdapter into DefaultRunRuntime.channels, refuses live IO when disabled.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped. Smoke Protocol-path hardening deferred to Phase 71; live path to Phase 72.

</deferred>
