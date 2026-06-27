---
phase: 03-hermes-integration-spike-and-risk-closure
plan: 03
subsystem: planning
tags: [hermes, feedback, async-state, privacy, idempotency, legal-safety]

requires:
  - phase: 03-hermes-integration-spike-and-risk-closure
    provides: source inventory and integration risk matrix from Plan 03-01
provides:
  - identifier and feedback association rules for Phase 4/6 implementation
  - exact AsyncTaskState mapping target table for Hermes long-task signals
  - raw_payload_ref namespace, retention owner assumptions, redaction minimums, and skill candidate safety rules
affects: [03-02, 03-04, 04-hermes-shadow-event-layer, 06-read-and-feedback-service-apis, 07-ci-composability-and-privacy-gates]

tech-stack:
  added: []
  patterns: [documentation-only evidence rules, reference-first privacy policy, human-review-only skill candidates]

key-files:
  created:
    - .planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md
    - .planning/phases/03-hermes-integration-spike-and-risk-closure/03-03-SUMMARY.md
  modified: []

key-decisions:
  - "Use feedback_target = message_id only after Hermes source/runtime proves message_id survives response filtering, preview storage, card dispatch, callbacks, and feedback rows."
  - "Map async task states only to exact platform AsyncTaskState values and mark missing Hermes signals unavailable rather than approximating them."
  - "Keep raw payloads reference-first with raw_payload_ref namespaces; storage location, retention owner, and redaction enforcement remain requires Hermes source/runtime."
  - "Route mismatch and skill_candidate feedback require human review and must not auto-modify legal skills."

patterns-established:
  - "One canonical feedback_target per user-visible response, with duplicate cards/callbacks normalized back to that target."
  - "Idempotency ladder: native callback id, then feedback_target/action/user_id/created_at_bucket, then raw_payload_hash metadata with payload by reference."
  - "Contract logs must not become raw payload storage to satisfy coverage targets."

requirements-completed:
  - REQ-implementation-risk-resolution

duration: 3m07s
completed: 2026-06-27
---

# Phase 03 Plan 03: Identifier, State, Privacy, and Safety Rules Summary

**Identifier, feedback, async-state, payload-reference, retention, redaction, and legal-safety rules are now documented as Phase 4/6 inputs without adding runtime code.**

## Performance

- **Duration:** 3m07s
- **Started:** 2026-06-27T18:33:17Z
- **Completed:** 2026-06-27T18:36:24Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `03-IDENTIFIER-STATE-PRIVACY-RULES.md` with the D-05 association graph across `turn_id`, `result_id`, `feedback_target`, `message_id`, `template_card_id`, `callback_event_id`, `pending_previews.jsonl`, and `feedback.jsonl`.
- Defined the repeated-callback idempotency ladder and the one-canonical-`feedback_target` rule for multi-card and duplicate callback handling.
- Added D-06 async state mapping rules using exact `AsyncTaskState` values: `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`.
- Added D-07 `raw_payload_ref` namespace, retention owner assumptions, storage-location evidence gaps, and minimum redaction rules.
- Locked D-09 legal safety behavior: `requires_human_review` for route mismatch/skill candidates and no automatic legal skill modification.

## Task Commits

1. **Task 1: Define identifier, feedback target, and idempotency rules** - `b484634` (docs)
2. **Task 2: Define async state, raw payload, retention, and redaction rules** - `bf18560` (docs)

## Files Created/Modified

- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` - identifier, feedback association, idempotency, async state, raw payload, retention, redaction, and safety rules.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-03-SUMMARY.md` - this execution summary.

## Decisions Made

- `feedback_target = message_id` is allowed only after Hermes source/runtime confirms stable propagation across `response_filter`, preview storage, card dispatch, callback payload, and `feedback.jsonl`.
- If `message_id` is not proven stable, Phase 4/6 must use only confirmed runtime fields for a derived key and keep unknown fields marked `requires Hermes source/runtime`.
- Async state mapping must use only the platform enum values and keep unsupported Hermes signals visible as unavailable.
- Contract logs and fixtures must prefer `raw_payload_ref`; full callback payloads, sensitive legal text, plaintext secrets, complete ID numbers, phone numbers, bank accounts, and addresses are forbidden inline by default.
- Skill candidate and route mismatch feedback are documentation/queue evidence only unless a human review step approves downstream legal-skill changes.

## Verification

| Command | Result |
|---------|--------|
| `python -c "from pathlib import Path; text=Path('.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md').read_text(); required=['message_id','feedback_target','template_card_id','callback_event_id','pending_previews.jsonl','feedback.jsonl','idempotency_key','created_at_bucket','raw_payload_hash','requires_human_review','must not auto-modify']; assert all(item in text for item in required)"` | Passed |
| `PYTHONPATH=packages/platform-contract/src python -c "from pathlib import Path; from platform_contract.enums import AsyncTaskState; text=Path('.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md').read_text(); assert [s.value for s in AsyncTaskState] == ['queued','running','waiting_for_user','succeeded','failed','cancelled']; assert all(s.value in text for s in AsyncTaskState); assert all(item in text for item in ['raw_payload_ref','retention','redaction','complete ID numbers','phone numbers','bank accounts','addresses','requires Hermes source/runtime'])"` | Passed |
| `rg -n "TODO|FIXME|placeholder|coming soon|not available|=\\[\\]|=\\{\\}|=null|=\\"\\"" .planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md || true` | Passed; only matched the intentional phrase "Synthetic test fixture payload placeholders" in the `fixture://raw/...` namespace row. |
| `git log --oneline --all \| rg 'b484634\|bf18560'` | Passed |

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** None.

## Issues Encountered

None. The remaining Hermes source/runtime gaps were expected by the plan and are documented as evidence gaps, not treated as implementation failures.

## Known Stubs

None. The `fixture://raw/...` namespace row describes synthetic reference placeholders and does not leave runtime behavior stubbed.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Evidence Gaps for Plan 03-02

- Hermes hook loader and same-event ordering for `agent:end`, `admin_notice`, `response_filter`, and a separate `contract_result_recorder`.
- Hidden inbound hook availability or complete session context for AgentTurn content and attachments.
- Stable `message_id` propagation across `response_filter`, `pending_previews.jsonl`, template card dispatch, callback payload, and `feedback.jsonl`.

## Evidence Gaps for Plan 03-04

- Plan 03-04 still owns non-happy-path fixtures and contract-test-suite coverage for route errors, long-task failures, repeated feedback clicks, and non-legal tasks.
- Fixture examples must apply the rules from this plan but still need Hermes-source/runtime-dependent fields marked as assumptions or references.
- Long-task lifecycle signals and callback idempotency fields remain `requires Hermes source/runtime`; fixtures should not claim them as source-confirmed.

## Next Phase Readiness

Plan 03-03 is complete as a documentation/rules plan. Phase 4/6 implementation can use the contract-side rules, but production Hermes hook and feedback normalization work remains blocked on Hermes source/runtime evidence or explicit fallback choices from the surrounding Phase 03 plans.

## Self-Check: PASSED

- Found `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md`.
- Found `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-03-SUMMARY.md`.
- Found task commit `b484634`.
- Found task commit `bf18560`.

---
*Phase: 03-hermes-integration-spike-and-risk-closure*
*Completed: 2026-06-27*
