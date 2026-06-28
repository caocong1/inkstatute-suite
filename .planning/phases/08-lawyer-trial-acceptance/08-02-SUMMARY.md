---
phase: 08-lawyer-trial-acceptance
plan: 08-02
subsystem: documentation
tags: [trial-runbook, evidence-template, privacy, wecom]
requires:
  - phase: 08-lawyer-trial-acceptance
    provides: Plan 08-01 trial acceptance checker and tests
provides:
  - Phase 8 lawyer trial runbook
  - minimized JSON evidence template
  - template compatibility test through the trial checker
affects: [lawyer-trial-acceptance, contract-test-suite, operator-runbook]
tech-stack:
  added: []
  patterns: [reference-only trial evidence templates, operator runbook gates, template compatibility unittest]
key-files:
  created:
    - .planning/phases/08-lawyer-trial-acceptance/08-LAWYER-TRIAL-RUNBOOK.md
    - .planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json
  modified:
    - packages/contract-test-suite/tests/test_trial_acceptance.py
key-decisions:
  - "The trial clock starts only after live InkStatute WeCom ownership, Hermes no_channel_io, and output-boundary evidence exist."
  - "The evidence template is blocked by default and cannot pass acceptance as placeholder data."
  - "Operator artifacts must use references, aliases, and counts instead of runtime payloads or legal source text."
patterns-established:
  - "Runbooks distinguish readiness fixtures from live acceptance evidence."
  - "Evidence templates can be parsed by stdlib JSON tooling and checked by local unittest."
requirements-completed:
  - REQ-lawyer-trial-acceptance
  - REQ-v2-development-order
duration: 4 min
completed: 2026-06-28
---

# Phase 08 Plan 08-02: Trial Runbook And Evidence Templates Summary

**Operator trial runbook and minimized JSON evidence template wired to the Phase 8 checker without storing runtime-sensitive material**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-28T09:38:30Z
- **Completed:** 2026-06-28T09:42:16Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added the Phase 8 lawyer trial runbook with pre-trial readiness gates, allowed evidence kinds, forbidden repo contents, daily operator checklist, feedback handling, route mismatch review, output-boundary monitoring, final report generation, and stop conditions.
- Added a minimized JSON evidence template with readiness gates, one placeholder task row, repair-plan ref, and external evidence refs.
- Added a unittest that loads the template from disk and proves placeholder rows remain `blocked` until real readiness gates and evidence are supplied.

## Task Commits

Each task was committed atomically:

1. **Task 08-02-01: Lawyer trial runbook** - `86877f2` (docs)
2. **Task 08-02-02: Evidence template** - `a658e23` (docs)
3. **Task 08-02-03: Template compatibility verification** - `9857524` (test)

## Files Created/Modified

- `.planning/phases/08-lawyer-trial-acceptance/08-LAWYER-TRIAL-RUNBOOK.md` - operator instructions and stop conditions for live lawyer trial evidence collection.
- `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` - parseable reference-only evidence template for minimized Phase 8 rows.
- `packages/contract-test-suite/tests/test_trial_acceptance.py` - template compatibility test proving placeholder rows cannot pass live acceptance.

## Verification

- `python -m json.tool .planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` - passed.
- `rg -n '"raw_payload"|access_token|encodingaeskey|callback body|customer document' .planning/phases/08-lawyer-trial-acceptance/08-LAWYER-TRIAL-RUNBOOK.md .planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json` - no matches.
- `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py` - 10 tests passed.
- `python scripts/run_v2_gates.py --json-summary` - passed all gates:
  - platform-contract: 15 tests
  - wecom-service: 17 tests
  - hermes-contract-layer: 30 tests
  - conversation-read-view: 18 tests
  - feedback-service: 19 tests
  - phase7-privacy-boundary: 12 tests
  - contract-test-suite: 85 tests
  - compileall: passed

## Decisions Made

- The runbook repeats the local V2 gate command before both trial start and final reporting.
- The evidence template carries `live_external_ref` as an example evidence kind but remains blocked because readiness gates are false and only one placeholder row exists.
- The runbook avoids exact secret names and raw runtime material while still naming the sensitive categories operators must not commit.

## Deviations from Plan

None - plan executed exactly as written.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required in the repo. Live trial operation still requires external WeCom/Hermes runtime evidence that is intentionally not stored here.

## Next Phase Readiness

Ready for Plan 08-03 to create the pending acceptance report and human approval gate.

## Self-Check: PASSED

- Key files exist on disk.
- Commits for `08-02` are present in git history.
- Verification commands passed, including the full V2 gate runner.
- Template placeholder evidence remains blocked by design.

---
*Phase: 08-lawyer-trial-acceptance*
*Completed: 2026-06-28*
