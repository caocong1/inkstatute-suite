# Phase 111: v3.1 Closure — Desktop Arena Integration + Export + Wiring + Test Fix - Context

**Gathered:** 2026-08-09
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Wire arena UI components into the desktop app so lawyers can actually use the arena workflow end-to-end (create → stream → score → review → synthesis → export), add the missing Word export endpoint to arena-service, wire Phase 106 FS handler into arena-engine for reference_dir reading, and fix the BackendAdapter method count test regression introduced by SAFE-06's `backend_family()` addition.

This phase closes the v3.1 audit tech_debt (8/45 requirements partial). It is the final phase of milestone v3.1 Legal AI Arena and depends on Phase 110 (Arena UI + Integration).

**Requirements:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, GATE-01 (closure of partial items from v3.1 audit)

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Binding constraints from AGENTS.md / PROJECT.md that MUST be honored:
- Chat UI must have exactly one implementation (in `@inkstatute/ui-core`); desktop app imports, does not re-implement.
- Word-native track-changes docx generation lives in agent-core (the 41,185-byte Python module `contract_review_trackchanges.py`); the new export endpoint calls into it, never re-implements it.
- ACP fs/* handler from Phase 106 (`FSSandbox.read_text_file`) is the only sanctioned path for reference_dir reading; path sandboxing must not be bypassed.
- Output boundary enforced twice (ACP event bridge + Gateway); backend/system notices must not reach ordinary lawyer users.
- Permission requests must never be auto-approved server-side.
- Legal guardrails (research-gate / citation audit / ask-user / de-AI polish) are non-bypassable in the arena workflow.
- Every new `packages/*/src` and `services/*/src` directory must be covered by a gate.
- Run `python scripts/run_v2_gates.py` before claiming phase complete; all 41 gates must stay green (qqbot-channel recall test pre-existing failure accepted as carry).

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

Key entry points to investigate during planning:
- `apps/desktop/src/` — desktop app shell; needs arena page/route
- `packages/ui-core/` — arena UI components (ArenaWorkflowCreator, ParallelStreamPanel, ScoreCard, ReviewSummary, SynthesisViewer, arenaStream store, ArenaEventReducer, desktopFileAdapter)
- `services/arena-service/` — local HTTP+SSE service; needs `POST /v1/arena/{arena_id}/export`
- `packages/arena-engine/` — workflow orchestrator; needs FS handler wiring for `reference_dir`
- `packages/acp-client/` — ACP session management (reused)
- `packages/agent-core/` — track-changes docx generation + legal guardrails (reused)
- Phase 106 FS handler (`FSSandbox.read_text_file`) — to be wired into arena-engine
- `test_backend_adapter_has_exactly_9_methods` — qqbot-channel gate test to update to 10 methods (SAFE-06 `backend_family()`)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
