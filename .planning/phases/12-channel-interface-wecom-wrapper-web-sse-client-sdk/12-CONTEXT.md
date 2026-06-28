# Phase 12: Channel Interface + WeCom Wrapper + Web/SSE + Client SDK - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Make WeCom one implementation under `ChannelAdapter`, add a Web API/SSE channel, and ship the platform API server, TypeScript SDK, and embeddable chat component, all default-OFF.

Success criteria:
- The existing WeCom primitives are wrapped behind `ChannelAdapter` behind a flag, with existing WeCom tests passing and no production regression.
- A non-WeCom channel, Web API plus SSE, passes end-to-end against fakes.
- Channel adapters never call backend adapters directly, enforced by boundary scan; they submit through `RunRuntime`.
- `apps/platform_api` hosts `RunRuntime`; `packages/platform-sdk-ts` is generated deterministically from OpenAPI; `apps/web_chat` renders `RunEvent` streaming.
- Secret refs are isolated per `BotInstance` and `ChannelBinding`; no cross-channel payload sharing.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion because discuss was skipped per project workflow settings. Use the ROADMAP phase goal, success criteria, active V2 PRD, AGENTS.md boundaries, and existing codebase conventions to guide implementation.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

</code_context>

<specifics>
## Specific Ideas

No additional specific requirements were gathered. Refer to the ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
