# Phase 8: Lawyer Trial Acceptance - Research

**Researched:** 2026-06-28
**Status:** Complete
**Mode:** Inline GSD research, no subagent spawn

## Research Question

What does Phase 8 need to know before planning a five-workday lawyer trial that is honest about live evidence, privacy, metrics, and human legal review?

## Findings

### Existing Evidence Surface

- `scripts/run_v2_gates.py` is the repo-root V2 readiness command. It runs platform, service, contract-suite, privacy, boundary, coverage, and compile gates.
- `contract_test_suite.coverage_report` already distinguishes fixture coverage from sanitized runtime input and can fail when runtime input is required but missing.
- `hermes_contract_layer.wecom_validation.validate_wecom_shadow_evidence` validates sanitized WeCom evidence for channel, ACK timing, feedback target, and secret/raw-payload leakage.
- `conversation_read_view.read_model.ContractLogReadModel` can build conversation/task/trace views from contract event records without a new authoritative database.
- `feedback_service.queue.build_pending_feedback_queue` can derive pending feedback items with idempotency keys, duplicate counts, human-review flags, and no-auto-modify evidence.
- `wecom_service.output_policy.apply_output_policy` classifies outbound text as allow/rewrite/block and stores only sanitized audit metadata.

### Missing Phase 8 Capabilities

- There is no trial evidence row model that counts the 5-workday / 15-task acceptance threshold.
- There is no local checker that returns `pending`, `blocked`, `failed`, or `passed` for trial evidence.
- There is no runbook telling an operator what live WeCom, Hermes adapter, output-boundary, feedback, and privacy evidence to collect without committing secrets or legal payloads.
- There is no Phase 8 acceptance report template that clearly separates readiness, live trial evidence, metric thresholds, negative feedback response actions, route mismatch review, and final human approval.

### Implementation Constraints

- Do not add a new service, database, durable queue, web UI, or runtime dependency. Phase 8 can add dependency-free helpers, tests, templates, and planning/report artifacts.
- Do not commit WeCom keys, callback tokens, AES keys, access tokens, callback bodies, runtime logs, media, customer documents, raw legal payloads, runtime DBs, or generated confidential documents.
- Do not count fixture tasks as lawyer trial tasks. Fixtures can prove the checker and templates only.
- Do not auto-modify legal conclusion skills. Negative feedback and route mismatch remain human-reviewed.
- Do not mark Phase 8 complete unless live external evidence proves the PRD thresholds.

## Trial Evidence Architecture

### Evidence Row

Use one minimized row per real task. Required fields should include:

- `task_ref`, `turn_id`, `conversation_id`, `trace_id`, `result_id`, `feedback_id`
- `evidence_kind` with values such as `sanitized_runtime`, `operator_annotation`, or `live_external_ref`
- `workday`, `participant_alias`, `category`
- `started_at`, `completed_at`, `duration_seconds`, `is_long_task`
- `success`, `clear_business_output`
- `feedback_captured`, `feedback_action`, `feedback_category`, `positive_feedback`
- `negative_feedback`, `response_action_ref`, `response_action_at`
- `route_mismatch`, `skill_candidate_ref`, `routing_rule_candidate_ref`
- `output_boundary_checked`, `hermes_meta_leak_detected`
- `raw_payload_ref` or other external evidence refs

### Acceptance Report

The report should calculate:

- continuous workday count and participant count;
- real task count and clear-business-output count;
- category coverage;
- long-task success rate and ordinary-task success rate;
- feedback capture rate and positive feedback share;
- negative feedback response action within 48 hours;
- route mismatch count and required candidate evidence;
- output-boundary live result;
- baseline readiness from the V2 local gate runner.

### Status Semantics

- `pending`: report/template exists but trial has not started.
- `blocked`: live/sanitized runtime evidence is missing or prerequisite live WeCom gate is not met.
- `failed`: live evidence exists but one or more thresholds fail without an allowed repair plan.
- `passed_with_repair_plan`: positive feedback share is below 60%, but a categorized repair plan exists and all hard thresholds pass.
- `passed`: all hard thresholds and human gates pass.

## Validation Architecture

| Gate | Primary Proof | Command |
|------|---------------|---------|
| Trial checker unit tests | Metrics, thresholds, blocked status, privacy shape, and fixture-not-live behavior | `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py` |
| Readiness baseline | Existing local V2 gate runner remains green before trial/final report | `python scripts/run_v2_gates.py --json-summary` |
| Privacy scan | Trial templates/reports contain refs and no raw payloads/secrets | `python scripts/run_v2_gates.py` |
| Human gate | Live trial evidence remains `human_needed` until operator supplies external refs and approval | Review `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-ACCEPTANCE.md` |

## Risks

- A checker could pass fixture data as live trial evidence. Require runtime/live evidence kinds for a pass.
- A report could leak customer facts in a convenience field. Use references and sanitized counts only.
- Phase 8 could be mistaken for a normal code phase. Keep the final live trial as an explicit human gate.
- Positive feedback may fall below 60%. Allow `passed_with_repair_plan` only when a categorized repair plan exists.

## Research Complete

Phase 8 can be planned as three sequential slices:

1. Trial metrics model and acceptance checker.
2. Trial runbook and evidence templates.
3. Pending acceptance report and human gate.
