# Phase 15: Session Resolver and Interrupt Runtime - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Ordinary users can continue, clarify, or start a new task without knowing session commands.

This phase owns backend-neutral session resolution and interrupt/resume runtime behavior for WeCom and platform channels. It must resolve active `conversation_id` and `session_id`/`thread_id` from channel/user/bot signals, active task state, pending interrupts, and idle-window rules; create a new session for clearly new tasks; persist backend clarification state as `waiting_for_user` / `needs_clarification`; and resume the paused run from the user's next WeCom reply without exposing `/new`, `/resume`, backend, or agent terminology.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion - discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 14 context/memory contracts, `.planning/REQUIREMENTS.md`, and existing codebase conventions to guide decisions.

Session decisions and interrupt records must be privacy-safe, reference-first, and backend-neutral. Do not store raw legal/customer text, callback bodies, runtime logs, media, secrets, or full legal payloads in contract logs or memory records.

Hermes remains an agent backend in Hermes mode, not the channel boundary. Ordinary WeCom users must see InkStatute-owned service wording, and Hermes gateway/meta/system/update/command/help/debug notices must not leak.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research. Likely integration areas include platform contract schemas and Python bindings, platform-runtime support types, WeCom service task-flow/active-task routing, Hermes adapter boundaries, and contract-test-suite fixtures.

</code_context>

<specifics>
## Specific Ideas

No additional user-specific requirements - discuss phase skipped. Refer to ROADMAP Phase 15 success criteria, `.planning/REQUIREMENTS.md`, `docs/requirements/V2-PRD.md`, and Phase 14 memory/context artifacts.

</specifics>

<deferred>
## Deferred Ideas

Short-term context assembly belongs to Phase 16. Long-term memory and feedback learning belongs to Phase 17. External memory adapter evaluation belongs to Phase 18. Do not introduce a new service, database, queue, router, skill registry, MCP registry, or model gateway unless the active plan explicitly justifies it inside the V2 scope.

</deferred>
