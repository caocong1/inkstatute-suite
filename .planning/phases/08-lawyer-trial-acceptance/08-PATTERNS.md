# Phase 8: Lawyer Trial Acceptance - Patterns

**Mapped:** 2026-06-28
**Mode:** Inline pattern mapping, no subagent spawn

## Source Inputs

- `.planning/phases/08-lawyer-trial-acceptance/08-CONTEXT.md`
- `.planning/phases/08-lawyer-trial-acceptance/08-RESEARCH.md`

## Files Expected In This Phase

| File | Role | Closest Existing Analog | Pattern To Reuse |
|------|------|-------------------------|------------------|
| `packages/contract-test-suite/src/contract_test_suite/trial_acceptance.py` | Trial metric/checker helper | `packages/contract-test-suite/src/contract_test_suite/coverage_report.py` | Frozen dataclasses, `to_dict()`, dependency-free functions, sanitized summaries, explicit status fields. |
| `packages/contract-test-suite/tests/test_trial_acceptance.py` | Trial checker tests | `packages/contract-test-suite/tests/test_coverage_report.py` | stdlib `unittest`, small in-memory fixtures, threshold failure assertions, privacy-safe summary assertions. |
| `.planning/phases/08-lawyer-trial-acceptance/08-LAWYER-TRIAL-RUNBOOK.md` | Operator runbook | `.planning/phases/05.5-inkstatute-wecom-service-and-hermes-agent-adapter/05.5-WECOM-LIVE-ACCEPTANCE.md` | Explicit `fixture_status`, `live_status`, blocked prerequisites, and external evidence requirements. |
| `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` | Sanitized evidence template | `packages/contract-test-suite/fixtures/phase6_read_feedback_bundle.json` | Reference-first fields, `raw_payload_ref`, no exact `raw_payload`, stable ids and metadata. |
| `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-ACCEPTANCE.md` | Final/pending acceptance report | `.planning/phases/07-ci-composability-and-privacy-gates/07-VERIFICATION.md` | Clear status frontmatter, command evidence, boundary notes, residual human gate. |

## Reusable Data Flow

1. Sanitized contract event streams or read-model outputs provide task and result refs.
2. Feedback queue outputs provide feedback status, classification, human-review, and no-auto-modify data.
3. Operator annotations provide human-only fields such as clear business output, category confirmation, response-action refs, and participant/workday confirmation.
4. Trial checker calculates status and threshold evidence from minimized rows.
5. Acceptance report references external live evidence without storing raw legal payloads.

## Implementation Guardrails

- Keep helper code stdlib-only.
- Keep trial evidence rows minimized and reference-first.
- Fail closed when live/sanitized runtime evidence is missing.
- Treat positive feedback repair-plan exception separately from hard threshold failures.
- Preserve the output-boundary and no-channel-io live gates as blockers.
- Never use fixture rows as live lawyer-trial rows.

## Pattern Mapping Complete
