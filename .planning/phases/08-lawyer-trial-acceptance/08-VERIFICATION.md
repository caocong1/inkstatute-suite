---
phase: 08-lawyer-trial-acceptance
status: human_needed
verified_at: 2026-06-28T09:48:00Z
verifier: codex-inline
---

# Phase 08 Verification

## Result

**HUMAN NEEDED** - Phase 8 implementation artifacts are complete and automated checks pass, but V2 lawyer-trial acceptance cannot be marked passed until a real five-workday WeCom lawyer trial supplies sanitized external evidence and human approval.

## Automated Verification

### Focused Trial Checker Tests

```bash
PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py
```

Result: 10 tests passed.

### Local V2 Gate Runner

```bash
python scripts/run_v2_gates.py --json-summary
```

Result: passed.

Gate summary:

- `platform-contract`: 15 tests passed.
- `wecom-service`: 17 tests passed.
- `hermes-contract-layer`: 30 tests passed.
- `conversation-read-view`: 18 tests passed.
- `feedback-service`: 19 tests passed.
- `phase7-privacy-boundary`: 12 tests passed.
- `contract-test-suite`: 85 tests passed.
- `compileall`: passed.

### Schema Drift

```bash
node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" query verify.schema-drift 08
```

Result:

- `drift_detected`: false
- `blocking`: false
- `schema_files`: none
- `orms`: none

### Code Review

`08-REVIEW.md` status: `clean`.

## Requirement Coverage

- `REQ-v2-development-order`: automated Phase 8 work followed the V2 PRD order after Phases 1-7 and did not rebuild Hermes core, router, storage, registry, or model gateway.
- `REQ-lawyer-trial-acceptance`: support artifacts are complete, but final acceptance remains human-needed until live trial evidence proves the PRD thresholds.

## Deliverables Verified

- `trial_acceptance.py` provides minimized evidence rows, fail-closed live evidence semantics, threshold evaluation, `passed_with_repair_plan`, readiness assertion, and sanitized summaries.
- `test_trial_acceptance.py` covers privacy rejection, fixture-not-live behavior, missing readiness gates, threshold pass, feedback repair plan exception, negative feedback response timing, route mismatch candidate evidence, sanitized formatting, and template placeholder blocking.
- `08-LAWYER-TRIAL-RUNBOOK.md` defines trial start gates, evidence kinds, forbidden repo contents, daily checklist, feedback handling, route mismatch review, output-boundary monitoring, final report generation, and stop conditions.
- `08-TRIAL-EVIDENCE-TEMPLATE.json` is valid JSON and contains reference-only minimized task rows.
- `08-TRIAL-ACCEPTANCE.md` has `status: human_needed`, lists live evidence refs and thresholds, and does not claim fixture evidence can pass acceptance.

## Privacy Review

New committed report/template artifacts contain no runtime secrets, callback payloads, media paths, runtime database paths, runtime logs, customer docs, complete identifiers, or raw legal payloads. Privacy grep matches are explanatory forbidden-content references in planning/source text only.

## Human Verification Required

1. Operator must run the trial only after live InkStatute WeCom ownership, Hermes no-channel-IO, and output-boundary gates have external evidence.
2. At least 1 lawyer must use the WeCom bot continuously for 5 workdays.
3. The trial must include at least 15 real tasks, at least 12 clear business outputs, and at least 3 legal task categories.
4. Trial metrics must prove long-task success at least 80%, ordinary-task success at least 85%, feedback capture at least 60%, and positive feedback at least 60% or a categorized repair plan.
5. Negative feedback must have response action evidence within 48 hours.
6. `route_mismatch` count must be no more than 3 and every mismatch must have candidate evidence.
7. Human reviewer must confirm no ordinary lawyer user saw Hermes meta/gateway/update/command/help/debug/runtime notices.
8. Human reviewer must confirm high-risk legal feedback did not trigger automatic legal conclusion changes.

## Blockers To Phase Completion

- No live five-workday lawyer trial evidence was supplied.
- No external InkStatute WeCom receive/send/ACK/send/feedback evidence refs were supplied.
- No human approval has been recorded.

## Next Step

Run the human UAT items in `08-UAT.md`. After all items pass and the acceptance report is updated from sanitized live evidence, rerun verification.

## Verification Complete
