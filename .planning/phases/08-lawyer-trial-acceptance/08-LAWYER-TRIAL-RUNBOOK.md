---
phase: 08-lawyer-trial-acceptance
status: ready_for_operator
updated: 2026-06-28
---

# Phase 8 Lawyer Trial Runbook

## Pre-Trial Readiness Gates

Run the local readiness gate before starting the clock:

```bash
python scripts/run_v2_gates.py --json-summary
```

The five-workday clock starts only after all of these live gates have evidence:

- InkStatute WeCom service owns ordinary lawyer-user receive/send, ACK, text/file/card delivery, and feedback callbacks.
- Hermes is used only as the agent backend in Hermes mode.
- The Hermes adapter evidence shows `no_channel_io=true`.
- The assistant output boundary is active before every ordinary-user WeCom send.
- Ordinary users have not seen Hermes meta, gateway, update, command, help, debug, lifecycle, memory, tool-progress, stack-trace, internal path, or runtime-detail notices.

Fixture data cannot count as live trial evidence. Fixtures and CI prove readiness only.

## Allowed Evidence Kinds

- `sanitized_runtime`: minimized rows derived from live contract logs or read-view outputs.
- `operator_annotation`: operator-entered metric fields that do not include sensitive source content.
- `live_external_ref`: stable references to external live evidence retained outside the repo.
- `fixture`: allowed only for checker/template tests and never counted as trial acceptance.

## Forbidden Repository Contents

Do not commit runtime callback payloads, media files, runtime database paths, runtime logs, WeCom keys, callback tokens, AES keys, model keys, complete identifiers, phone numbers, bank accounts, addresses, raw legal payload text, or confidential generated documents.

Committed artifacts must use minimized counts, aliases, and references such as `raw_payload_ref`, `task_ref`, `turn_id`, `conversation_id`, `trace_id`, `result_id`, and `feedback_id`.

## Day-By-Day Operator Checklist

For each of the 5 continuous workdays:

1. Confirm the local readiness command remains green before collection starts.
2. Confirm InkStatute WeCom service, not Hermes gateway, is receiving ordinary-user input and sending ordinary-user output.
3. Record one minimized task row per real lawyer task in the evidence template.
4. Capture at least one stable external evidence ref for ACK/send/feedback or contract-log evidence.
5. Mark whether the task was ordinary or long by duration. Long means end-to-end duration greater than 60 seconds.
6. Record whether output-boundary monitoring saw any Hermes meta exposure.
7. Stop counting new tasks immediately if a stop condition below is met.

## Task Category Guidance

The 15 real tasks must cover at least 3 of these categories:

- `contract_review`
- `legal_retrieval_qa`
- `document_drafting`
- `judgment_analysis`
- `case_analysis`

At least 12 of the 15 tasks must have clear business output.

## Feedback Capture Process

For every task, record:

- whether template-card feedback or operator annotation was captured;
- whether the feedback is positive, neutral, or negative;
- `feedback_id` or external feedback ref when available;
- whether the feedback implies route mismatch or a skill/routing candidate.

Feedback capture must reach at least 60% of live tasks. Positive feedback share must reach at least 60%, unless a categorized repair plan is linked from the final report.

## Negative Feedback 48 Hours Response Process

Every negative feedback item needs a response action within 48 hours of task completion.

Record only:

- reviewer/operator alias;
- action type;
- external response action ref;
- response action timestamp;
- whether high-risk legal conclusions require human review.

Do not auto-modify legal conclusion skills, statute references, cause-of-action judgments, jurisdiction judgments, liability conclusions, or other high-risk legal outputs.

## Route Mismatch Candidate Review

`route_mismatch` count must be no more than 3.

Every route mismatch row must link one of:

- `skill_candidate_ref`
- `routing_rule_candidate_ref`

Candidate review is human-reviewed and must preserve `no_auto_modify` semantics.

## Output-Boundary Monitoring

For each live task row, set `output_boundary_checked=true` only when external evidence shows ordinary WeCom output was sent by InkStatute WeCom service after output-policy handling.

If any ordinary lawyer user sees Hermes meta, gateway, update, command, help, status, credits, insights, memory/tool-progress, debug, stack trace, internal path, command, token, or runtime detail text, stop the trial count. Repair the boundary, rerun readiness gates, and restart counting after retest.

## Final Report Generation

Before final report generation, rerun:

```bash
python scripts/run_v2_gates.py --json-summary
```

Then evaluate the minimized evidence rows with `contract_test_suite.trial_acceptance.evaluate_trial_acceptance`.

The report can only pass when live evidence reaches:

- at least 5 workdays;
- at least 15 real tasks;
- at least 12 clear business outputs;
- at least 3 categories;
- long-task success rate at least 80%;
- ordinary-task success rate at least 85%;
- feedback capture rate at least 60%;
- positive feedback share at least 60%, or a categorized repair plan ref;
- negative feedback response actions within 48 hours;
- route mismatch count no more than 3, with candidate evidence for each mismatch;
- no Hermes meta exposure.

## Stop Conditions

Stop counting and mark the report blocked if any condition occurs:

- Live InkStatute WeCom ownership is not proven.
- Hermes gateway becomes the ordinary-user channel boundary.
- Hermes adapter no-channel-IO evidence is missing or false.
- Output boundary evidence is missing for ordinary-user sends.
- A Hermes meta notice reaches an ordinary lawyer user.
- Sensitive runtime material is accidentally placed in repo artifacts.
- High-risk legal feedback would require automated legal conclusion changes.
