---
phase: 03-hermes-integration-spike-and-risk-closure
plan: 02
subsystem: integration
tags: [hermes, hooks, agent-turn, source-evidence, privacy]

requires:
  - phase: 03-01
    provides: Hermes source inventory and integration risk matrix
provides:
  - Source-confirmed Hermes hook ordering decision for response_filter and contract_result_recorder
  - AgentTurn input strategy with field-level source status
  - Phase 4 gate constraints for after-filter recorder registration
affects: [phase-04-hermes-shadow-event-layer, phase-05-wecom-shadow-loop-validation, phase-06-feedback-service]

tech-stack:
  added: []
  patterns:
    - Source evidence must distinguish directory ordering from manifest hook names
    - AgentTurn content coverage must label truncated or unavailable source fields

key-files:
  created:
    - .planning/phases/03-hermes-integration-spike-and-risk-closure/03-02-SUMMARY.md
  modified:
    - .planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-ORDER-EVIDENCE.md
    - .planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-AND-TURN-DECISIONS.md

key-decisions:
  - "A separate recorder can run after response_filter only when its hook directory sorts after response_filter; the manifest name is not the ordering key."
  - "A canonical contract_result_recorder/ directory would run before response_filter and is not valid for after-filter recording."
  - "AgentTurn should prefer the source-confirmed agent:start hook for available inbound metadata; full input content, attachments, message type, and received_at remain source-dependent."

patterns-established:
  - "Hook-order evidence cites Hermes core/profile source paths and includes a sanitized order probe without raw payloads."
  - "Phase 4 gates must preserve privacy and avoid claiming full outbound capture from the capped agent:end hook context."

requirements-completed:
  - REQ-implementation-risk-resolution

duration: 10min
completed: 2026-06-28
---

# Phase 03 Plan 02: Hook Ordering and AgentTurn Decision Summary

**Hermes hook order is source-confirmed, with an after-filter recorder allowed only through directory ordering after `response_filter`.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-28T01:15:50Z
- **Completed:** 2026-06-28T01:25:10Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Replaced the previous evidence gap with source-confirmed Hermes hook ordering from `gateway/hooks.py`, `gateway/run.py`, and the lawfirm profile hook files.
- Documented the exact Phase 4 constraint: a separate recorder must live in a hook directory that sorts after `response_filter`; a plain `contract_result_recorder/` directory would run too early.
- Updated AgentTurn strategy to use the source-confirmed `agent:start` hook for available inbound metadata while keeping full content, attachments, message type, timestamps, and raw payload references explicitly source-dependent.

## Task Commits

1. **Task 1: Create blocking hook-order evidence gate and decision section** - `aaab84a` (docs)
2. **Task 2: Document AgentTurn input strategy and reverse-inference limits** - `aaab84a` (docs)

**Plan metadata:** `644ac87` (docs: complete plan)

## Files Created/Modified

- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-ORDER-EVIDENCE.md` - Source-confirmed hook ordering evidence, sanitized probe result, and Phase 4 impact.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-AND-TURN-DECISIONS.md` - D-03 hook-order decision and D-04 AgentTurn field strategy.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-02-SUMMARY.md` - Completion record for this plan.

## Decisions Made

- A separate recorder can run after `response_filter` only if its hook directory sorts after `response_filter`; the manifest name does not determine same-event order.
- A canonical `contract_result_recorder/` directory is rejected for after-filter recording because it sorts before `response_filter`.
- `agent:start` is the preferred AgentTurn source for available inbound metadata; `agent:end` reverse inference is only a limited fallback.
- Phase 4 must not claim full outbound response capture from the current `agent:end` hook context because gateway source passes a capped response preview into hook context.

## Deviations from Plan

None - plan executed exactly as written after the missing Hermes source evidence was found in the local Hermes profile/core paths.

## Issues Encountered

- The earlier session correctly blocked because the InkStatute repo itself lacked Hermes source/runtime evidence. During resume, Hermes source was found in adjacent local paths:
  - `/home/sorawatcher/.hermes/hermes-agent/gateway/hooks.py`
  - `/home/sorawatcher/.hermes/hermes-agent/gateway/run.py`
  - `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/...`
- The source evidence narrowed, rather than broadened, the allowed implementation: Phase 4 must encode directory-order constraints and response truncation limits.

## User Setup Required

None - no external service configuration required.

## Verification

- PASS: Plan Task 1 Python assertion verified `EVIDENCE_OUTCOME: source_confirmed`, a concrete `HOOK_ORDER_DECISION`, no old gap marker in evidence, and required hook-order decision text.
- PASS: Plan Task 2 Python assertion verified AgentTurn strategy content for `gateway:startup`, `agent:end`, `turn_id`, `conversation_id`, `message_type`, `attachments`, `output_constraints`, `raw_payload_ref`, and Phase 4 gate.
- PASS: Additional assertion verified exactly one `EVIDENCE_OUTCOME:` and one `HOOK_ORDER_DECISION:` marker in the evidence file.

## Self-Check: PASSED

- Key files exist on disk.
- Plan acceptance checks pass.
- No production Hermes hook, mapper, writer, service, database, queue, gateway, or legal skill modification code was written.

## Next Phase Readiness

Ready for `03-04-PLAN.md`. Non-happy-path fixtures can now cite the source-confirmed hook-order decision and should preserve the Phase 4 constraints around after-filter directory ordering, capped hook response context, and reference-first raw payload handling.

---
*Phase: 03-hermes-integration-spike-and-risk-closure*
*Completed: 2026-06-28*
