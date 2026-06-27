---
phase: 03-hermes-integration-spike-and-risk-closure
plan: 01
subsystem: planning
tags: [hermes, integration-risk, evidence-led-docs, privacy]

requires:
  - phase: 02-contract-test-suite-foundation
    provides: dependency-free contract validation and fixture replay harness
provides:
  - repo-local Hermes source/runtime evidence inventory
  - PRD section 13 integration risk matrix with status tags and Phase 4 impact
affects: [03-02, 03-03, 03-04, 04-hermes-shadow-event-layer]

tech-stack:
  added: []
  patterns: [evidence-led inventory before Hermes production hook work]

key-files:
  created:
    - .planning/phases/03-hermes-integration-spike-and-risk-closure/03-HERMES-SOURCE-INVENTORY.md
    - .planning/phases/03-hermes-integration-spike-and-risk-closure/03-INTEGRATION-RISK-MATRIX.md
  modified: []

key-decisions:
  - "Treat PRD descriptions of Hermes hooks and feedback flow as specification evidence, not source-confirmed Hermes API evidence."
  - "Block separate Phase 4 contract_result_recorder hook work until Hermes hook ordering after response_filter is source/runtime-confirmed or a fallback is selected."
  - "Carry message_id, callback payload, long-task state, and raw payload storage details into downstream plans as requires Hermes source/runtime."

patterns-established:
  - "Use status tags confirmed, assumed, requires Hermes source/runtime, deferred, and blocked for Phase 3 risk decisions."
  - "Store only paths, command summaries, status, and references in Phase 3 evidence docs; do not embed runtime payloads or legal/customer data."

requirements-completed:
  - REQ-implementation-risk-resolution

duration: 3m53s
completed: 2026-06-27
---

# Phase 03 Plan 01: Source Inventory and Integration Risk Matrix Summary

**Repo-local Hermes evidence was inventoried and every PRD section 13 integration risk was mapped to a status, fallback, and Phase 4 impact.**

## Performance

- **Duration:** 3m53s
- **Started:** 2026-06-27T18:24:49Z
- **Completed:** 2026-06-27T18:28:42Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `03-HERMES-SOURCE-INVENTORY.md` with the exact repo scan commands and source/runtime evidence status for hook files, feedback JSONL, previews, sessions, callbacks, gateway events, and long-task state sources.
- Created `03-INTEGRATION-RISK-MATRIX.md` with one row for each V2 PRD section 13 risk, D-01 through D-09 coverage, accepted status tags, fallbacks, and Phase 4 go/no-go effects.
- Confirmed no production Hermes hook, mapper, writer, WeCom gateway, feedback-service, read API, database, queue, `.github` workflow, or legal skill modification code was introduced.

## Task Commits

1. **Task 1: Create Hermes source inventory evidence ledger** - `76239de` (docs)
2. **Task 2: Create integration risk matrix for PRD section 13** - `0cb8f15` (docs)

## Files Created/Modified

- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HERMES-SOURCE-INVENTORY.md` - repo-local command ledger and artifact inventory for Hermes source/runtime evidence.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-INTEGRATION-RISK-MATRIX.md` - PRD section 13 risk matrix with status, evidence, decision, fallback, and Phase 4 impact.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-01-SUMMARY.md` - this execution summary.

## Decisions Made

- PRD prose is product/specification evidence only; source-dependent Hermes claims remain `requires Hermes source/runtime` until source/runtime artifacts or sanitized probes are available.
- Separate `contract_result_recorder` deployment remains `blocked` until hook ordering after `response_filter` is confirmed, or recording is moved inside/adjacent to `response_filter`.
- Contract-side `feedback_target` and async state vocabulary are present, but real `message_id`, callback, idempotency, and long-task source mappings are not source-confirmed in this repo.

## Verification

| Command | Result |
|---------|--------|
| `python -c "from pathlib import Path; p=Path('.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HERMES-SOURCE-INVENTORY.md'); text=p.read_text(); required=['HOOK.yaml','handler.py','response_filter','template_card_dispatcher','wecom_template_card_shim','feedback.jsonl','pending_previews.jsonl','agent:end','gateway:startup','requires Hermes source/runtime']; assert all(item in text for item in required); assert 'raw_payload' not in text.lower() or 'raw_payload_ref' in text"` | Passed |
| `python -c "from pathlib import Path; p=Path('.planning/phases/03-hermes-integration-spike-and-risk-closure/03-INTEGRATION-RISK-MATRIX.md'); text=p.read_text(); required=['hook event ordering','inbound event absence','message_id stability','long-task state source','feedback idempotency','raw payload storage','redaction','simple QA route logs','fixture representativeness','skill candidate safety','multi-hook same-event order']; assert all(item in text for item in required); assert all(tag in text for tag in ['confirmed','assumed','requires Hermes source/runtime','deferred','blocked']); assert all(f'D-0{i}' in text for i in range(1,10))"` | Passed |
| `python -m compileall packages/platform-contract/src packages/platform-contract/tests packages/contract-test-suite/src packages/contract-test-suite/tests packages/contract-test-suite/scripts && cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` | Passed, 21 tests |
| `rg -n "response_filter|template_card|wecom_template_card_shim|message_id|feedback|long_task|agent:end" -S .` | Passed as evidence scan; matches are docs, schemas, tests, and synthetic fixtures, not Hermes runtime source. |
| `git diff --name-only 7b8e509..HEAD && git status --short` | Passed; only the two Phase 03-01 artifact docs were changed before summary creation. |

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** None.

## Issues Encountered

None. The Hermes source/runtime absence was expected by the plan and documented as evidence, not treated as a failure.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Evidence Gaps for Plan 03-02

- Hermes hook loader and same-event execution order for `agent:end`, `admin_notice`, `response_filter`, and `contract_result_recorder`.
- Hidden inbound hook availability or complete session context for AgentTurn content and attachments.
- Stable `message_id` propagation across `response_filter`, `pending_previews.jsonl`, template card dispatch, callback payloads, and `feedback.jsonl`.
- Sanitized template-card callback payload fields and native callback id, if one exists.
- Hermes long-task lifecycle signals for `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`.
- Raw payload reference namespace, retention owner, storage location, and redaction/minimization implementation.

## Next Phase Readiness

Plan 03-02 can cite the inventory and risk matrix as its dependency source. Production Hermes hook decisions remain blocked on Hermes source/runtime evidence or an explicitly documented fallback.

## Self-Check: PASSED

- Found `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HERMES-SOURCE-INVENTORY.md`.
- Found `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-INTEGRATION-RISK-MATRIX.md`.
- Found `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-01-SUMMARY.md`.
- Found task commit `76239de`.
- Found task commit `0cb8f15`.

---
*Phase: 03-hermes-integration-spike-and-risk-closure*
*Completed: 2026-06-27*
