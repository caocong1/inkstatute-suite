# Phase 64: QQBotSessionRuntime + QQBotIngressRuntime - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

QQBotSessionRuntime orchestrates continuous conversation for QQ users via `RunRuntime` + `SessionResolutionPolicy` + `InterruptStore` + `MemoryOrchestrator` (composing `platform_runtime` primitives directly, no `wecom_service` import); QQBotIngressRuntime wires callback → turn → session runtime; scene-aware conversation identity; interrupt resume; memory recall with fail-open degradation.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

Key constraints:
- Compose `platform_runtime` primitives directly — NO `wecom_service` import
- Scene-aware conversation identity: `qqbot:{scene}:{scene_id}:{user_openid}`
- Interrupt resume across user replies via InterruptStore
- Memory: pre-turn recall + post-turn retention via MemoryOrchestrator; fail-open on memory errors
- `dependencies = []` for qqbot package; no frozen protocol/platform-contract/channel-core edits
- Reuse existing normalization (Phase 60) and sender (Phase 62/63) where needed

</decisions>

<code_context>
## Existing Code Insights

Codebase context gathered during research. Prior phases: 60 normalization, 61 token, 62/63 sender.

</code_context>

<specifics>
## Specific Ideas

Requirements: SESS-01, SESS-02, SESS-03.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped. Full adapter Protocol IO promotion is Phase 65.

</deferred>
