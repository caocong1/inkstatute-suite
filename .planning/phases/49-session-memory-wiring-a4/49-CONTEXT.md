# Phase 49: Session Memory Wiring (A4) - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Operator can enable `session_memory_enabled` and the runtime wires existing `HindsightMemory` + `MemoryOrchestrator` as optional injected dependencies, with adapters declaring `session_memory_support=True` and consuming `ContextBundle` — never calling Hindsight directly.

**Depends on:** Phase 45
**Requirements:** SESSMEM-01, SESSMEM-02

**Success Criteria** (what must be TRUE):
1. `DefaultRunRuntime` accepts optional `memory_orchestrator` and `context_assembler` injected dependencies; when `session_memory_enabled=True`, `MemoryOrchestrator.recall()` queries `HindsightMemory` scoped by `(tenant_id, workspace_id, user_id)` and injects recalled memory refs into `ContextBundle` before `backend.submit_run()`.
2. Adapters declare `session_memory_support=True` in their manifest and consume the `ContextBundle` from `RunRequest.metadata`; no adapter calls `HindsightMemory` or any memory provider directly.
3. When `session_memory_enabled=False` (default), no memory orchestration occurs and the runtime behaves identically to v1.6 — the feature is purely additive and opt-in.

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
