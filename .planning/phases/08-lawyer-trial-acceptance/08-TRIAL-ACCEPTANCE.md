---
phase: 08-lawyer-trial-acceptance
status: human_needed
live_trial_status: pending
fixture_status: readiness_only
updated: 2026-06-28
---

# Phase 8 Trial Acceptance Report

## Verdict

Current verdict: `human_needed`.

Automation artifacts are ready, local V2 gates pass, and the checker can evaluate minimized evidence rows. The five-workday lawyer trial has not been supplied as live external evidence in this repo, so V2 live acceptance is still pending.

fixture evidence cannot pass Phase 8 acceptance. Fixture and CI evidence only prove readiness tooling.

## Readiness Gates

| Gate | Current Status | Evidence |
|---|---|---|
| Local V2 gates | passed | `python scripts/run_v2_gates.py --json-summary` passed on 2026-06-28 during Plan 08-02 execution |
| InkStatute WeCom owns ordinary-user receive/send | pending | external live evidence ref required |
| Hermes adapter runs as agent backend only | pending | external `no_channel_io` evidence ref required |
| Output boundary protects ordinary-user sends | pending | external live output-boundary evidence ref required |
| No Hermes meta exposure to ordinary users | pending | external operator confirmation ref required |

The trial clock must not start until the pending live gates above are satisfied.

## Metric Thresholds

Phase 8 can pass only when live evidence proves:

- at least 1 lawyer over 5 continuous workdays;
- at least 15 real WeCom tasks;
- at least 12 clear business outputs;
- at least 3 task categories;
- long-task success rate at least 80%;
- ordinary-task success rate at least 85%;
- feedback capture rate at least 60%;
- positive feedback share at least 60%, or a categorized repair plan ref;
- every negative feedback item has response action evidence within 48 hours;
- `route_mismatch` count is no more than 3;
- every `route_mismatch` has `skill_candidate_ref` or `routing_rule_candidate_ref`;
- no Hermes meta, gateway, update, command, help, debug, lifecycle, memory/tool-progress, stack-trace, internal path, token, or runtime-detail notice reached ordinary lawyer users.

## Current Evidence Status

| Metric | Current Count/Status | Required |
|---|---:|---:|
| Live trial tasks | 0 | 15 |
| Continuous workdays | 0 | 5 |
| Lawyer participants | 0 | 1+ |
| Clear business outputs | 0 | 12 |
| Categories | 0 | 3 |
| Long-task success rate | pending | 80% |
| Ordinary-task success rate | pending | 85% |
| Feedback capture rate | pending | 60% |
| Positive feedback share | pending | 60% or repair plan |
| Negative feedback response actions | pending | within 48 hours |
| route_mismatch count | pending | no more than 3 |
| Output-boundary live evidence | pending | required |

Current checker status with no supplied live rows would be `pending` or `blocked`, not `passed`.

## Required External Evidence Refs

Before this report can move out of `human_needed`, attach sanitized external refs for:

- live InkStatute WeCom receive/ACK evidence;
- live InkStatute WeCom text/file/card send evidence;
- Hermes adapter invocation evidence showing agent logic only and no direct channel I/O;
- contract log or read-view refs for each live task;
- feedback callback or operator annotation refs;
- negative-feedback response action refs;
- route mismatch candidate refs;
- output-boundary monitoring refs;
- operator confirmation that ordinary users did not see Hermes meta notices.

## Negative Feedback Response Actions

No negative live feedback evidence has been supplied yet.

When supplied, each negative feedback item must include:

- reviewer/operator alias;
- action type;
- external response action ref;
- response action timestamp within 48 hours of task completion;
- human-review status for any high-risk legal feedback.

No automated legal conclusion changes are authorized by this phase.

## Route Mismatch Candidate Review

No live route mismatch evidence has been supplied yet.

Every future `route_mismatch` row must keep human review and link one of:

- `skill_candidate_ref`;
- `routing_rule_candidate_ref`.

The total count must remain no more than 3.

## Output-Boundary Evidence

No live output-boundary evidence has been supplied yet.

The final acceptance package must prove ordinary WeCom output was sent by InkStatute WeCom service after output-policy handling. Any ordinary-user exposure to Hermes meta, gateway, update, command, help, debug, lifecycle, memory/tool-progress, internal path, token, or runtime-detail text blocks acceptance until repaired and re-tested.

## Privacy Review

This committed report contains only status, thresholds, counts, and references. It must not include runtime callback payloads, media paths, runtime database paths, runtime logs, customer docs, complete identifiers, phone numbers, bank accounts, addresses, secrets, tokens, raw legal payloads, or confidential generated documents.

Use `raw_payload_ref`-style references for sensitive source material retained outside the repo.

## Human Approval Checklist

- [ ] Operator confirms the five-workday trial clock started only after live readiness gates passed.
- [ ] Operator supplies minimized evidence for at least 15 real WeCom tasks.
- [ ] Operator confirms at least 12 tasks have clear business output.
- [ ] Operator confirms at least 3 task categories are represented.
- [ ] Operator confirms long-task and ordinary-task success rates meet 80% and 85%.
- [ ] Operator confirms feedback capture and positive feedback requirements meet 60%, or links a categorized repair plan.
- [ ] Operator confirms every negative feedback item has response action evidence within 48 hours.
- [ ] Operator confirms every route mismatch has candidate evidence and human review.
- [ ] Operator confirms no high-risk legal feedback caused automated legal conclusion modification.
- [ ] Operator confirms no ordinary lawyer user saw Hermes meta notices.
- [ ] Operator approves final report status change from `human_needed` to passed or passed_with_repair_plan.

## Final Verdict

Status remains `human_needed`.

The automation and documentation needed to run Phase 8 are complete. Live acceptance still requires external five-workday lawyer trial evidence and human approval.
