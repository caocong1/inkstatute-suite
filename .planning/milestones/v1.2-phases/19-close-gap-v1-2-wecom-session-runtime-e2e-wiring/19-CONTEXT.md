# Phase 19: Close gap: v1.2 WeCom session runtime E2E wiring - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning
**Mode:** Auto-generated from v1.2 milestone audit gaps (`workflow.skip_discuss=true`)

<domain>
## Phase Boundary

Close the v1.2 milestone audit's critical E2E wiring gaps: ordinary WeCom continue/start-new turns must reach the platform runtime by calling `RunRuntime.create_run()`, while pending clarification answers keep using `RunRuntime.resume_interrupt()`. This phase must stay inside the existing backend-neutral WeCom service/runtime library boundary and must not add a live WeCom server, database, queue, raw payload store, or Hermes core behavior.

</domain>

<decisions>
## Implementation Decisions

### Runtime handoff
- **D-01:** `WeComSessionRuntime.handle_turn()` must call `runtime.create_run()` for `CONTINUE_SESSION` and `START_NEW_SESSION` decisions.
- **D-02:** `RESUME_INTERRUPT` must continue to call `runtime.resume_interrupt()` and preserve duplicate-answer idempotency.
- **D-03:** Active-task follow-up turns remain fast control-plane outcomes and must not submit a backend run unless a future adapter capability explicitly supports it.

### Ingress boundary
- **D-04:** Add a pure service-level ingress orchestration helper that normalizes a sanitized callback, builds `SessionScope` and `RunRequest`, and invokes `WeComSessionRuntime.handle_turn()`.
- **D-05:** The helper is the production host integration boundary for this repo; it must be callable by callback/app orchestration but must not create a server or perform network IO in tests.

### Context and privacy
- **D-06:** Create-run requests must carry bounded-context metadata references through `RunRequest.metadata`, including current turn/raw payload refs plus caller-supplied recent turn, memory, feedback correction, artifact, output policy, and output constraint refs.
- **D-07:** Evidence and metadata must remain reference-first. Do not store raw legal/customer payloads, full-text documents, or secrets.

### the agent's Discretion
- Exact helper name and dataclass shape are at the agent's discretion.
- Tests may use in-memory fake runtimes and sanitized fixtures only.

</decisions>

<specifics>
## Specific Ideas

- Audit gap `INTG-v1.2-01`: `services/wecom-service/src/wecom_service/session_runtime.py` returns continue/start outcomes without submitting `runtime.create_run()`.
- Audit gap `INTG-v1.2-02`: no production caller was found for `WeComSessionRuntime.handle_turn()`.
- Required flows: continue existing conversation, start clearly new task, answer clarification, and receive bounded context.

</specifics>

<canonical_refs>
## Canonical References

### Audit and milestone contract
- `.planning/v1.2-MILESTONE-AUDIT.md` — Critical gaps, affected requirements, and recommended closure scope.
- `.planning/REQUIREMENTS.md` — CTX, INT, and STM requirement traceability.
- `docs/requirements/V2-PRD.md` — Active product source of truth for V2 privacy, WeCom, and backend-neutral boundaries.

### Existing runtime and WeCom code
- `services/wecom-service/src/wecom_service/session_runtime.py` — Current session resolution, interrupt resume, active-task routing, and evidence emission.
- `services/wecom-service/src/wecom_service/normalization.py` — Sanitized WeCom callback to `AgentTurn` normalization.
- `packages/platform-runtime/src/platform_runtime/runtime.py` — `DefaultRunRuntime.create_run()` context assembly and contract logging behavior.
- `packages/platform-runtime/src/platform_runtime/session_resolver.py` — Session decision semantics and privacy-safe decision records.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WeComSessionRuntime` already composes session resolution, interrupt store lookup, active-task routing, and scope validation.
- `normalize_wecom_turn()` already validates sanitized callback envelopes and returns an `AgentTurn`-shaped event with idempotency and raw payload refs.
- `DefaultRunRuntime._attach_context_bundle()` already consumes metadata refs from `RunRequest.metadata` when context assembly is enabled.

### Established Patterns
- Service package tests use dependency-light fake runtimes and fixtures; keep the new wiring in the same style.
- Privacy guards reject `raw_payload` and full-text payload keys in session/runtime evidence.
- Runtime lanes stay default-off and dependency-injected.

### Integration Points
- Add create-run handoff in `WeComSessionRuntime.handle_turn()` after `CONTINUE_SESSION` or `START_NEW_SESSION` resolution.
- Add a service-level callback orchestration helper exported from `wecom_service.__init__`.
- Extend `services/wecom-service/tests/test_session_interrupt_runtime.py` and add ingress-level tests.

</code_context>

<deferred>
## Deferred Ideas

- Feedback-to-memory-to-next-context service pipeline remains a follow-up unless it is needed for this critical E2E closure.
- Live WeCom deployment/UAT remains a human gate and must not be claimed by fixture tests.

</deferred>

---

*Phase: 19-close-gap-v1-2-wecom-session-runtime-e2e-wiring*
*Context gathered: 2026-07-02*
