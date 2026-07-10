# Phase 69: Runtime Registration / Wiring - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Host factory correctly maps dual default-OFF knobs and injects `QQBotChannelAdapter` into `DefaultRunRuntime.channels`, refusing live IO when disabled.

Requirements: REG-01, REG-02, HOST-03

Success criteria:
1. Host factory maps `RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled` and injects token_manager/transport only when `_live_io_ready`.
2. Host constructs `DefaultRunRuntime` with explicit `channels=(QQBotChannelAdapter,)` — no auto-discovery inside `platform-runtime`.
3. When QQBot is disabled (flags/config OFF), the composed path refuses live IO with explicit non-success behavior (e.g. 503/refuse) and does not call OpenAPI transports.
4. FakeBackend unit tests cover enabled vs disabled wiring without network.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 68 host skeleton patterns, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research. Phase 68 delivered `services/qqbot-service/` skeleton with secret-ref config and ADAPTER-04 isolation tests.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped. Webhook composition deferred to Phase 70.

</deferred>
