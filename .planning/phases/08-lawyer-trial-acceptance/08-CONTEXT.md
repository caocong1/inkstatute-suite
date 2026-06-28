# Phase 8: Lawyer Trial Acceptance - Context

**Gathered:** 2026-06-28T09:19:46Z
**Status:** Ready for planning
**Source:** `$gsd-progress --next --auto` / `$gsd-discuss-phase 8 --auto`

<domain>
## Phase Boundary

Phase 8 validates V2 through real lawyer WeCom usage and metric-backed acceptance evidence. It should turn the existing V2 contract logs, read views, feedback queues, WeCom live evidence, output-boundary checks, and CI gates into a five-workday trial process that can be run, audited, and judged without pretending fixture data is live acceptance.

This phase may add trial runbooks, evidence templates, sanitized metric calculators, acceptance report/checker code, focused tests, and planning artifacts for the human trial. It may consume sanitized runtime references outside the repo. It must not fabricate five-workday usage, commit WeCom secrets/callback bodies/runtime logs/customer documents/raw legal payloads, route ordinary users through Hermes gateway, bypass the assistant output boundary, or auto-modify legal conclusion skills.

</domain>

<decisions>
## Implementation Decisions

### Trial Start Gate And Evidence Authority

- **D-01:** Treat Phase 8 as acceptance orchestration and evidence packaging, not a new feature-building phase. The core V2 surfaces were built in Phases 1-7; Phase 8 proves they work under real lawyer usage.
- **D-02:** The five-workday acceptance clock starts only after live evidence shows InkStatute WeCom service owns ordinary user receive/send, Hermes is used only for agent logic, `agent_backend.mode=hermes` satisfies `no_channel_io`, and the output boundary blocks Hermes meta/gateway/update/command notices.
- **D-03:** Contract logs, read-view outputs, feedback queue outputs, and operator annotations are the evidence authorities. Committed artifacts must be runbooks/templates/sanitized summaries only; raw runtime logs and legal payloads remain outside the repo behind references.
- **D-04:** Fixture and CI evidence may prove readiness but cannot count as lawyer trial tasks or live acceptance. Any checker/report must make `fixture`, `sanitized_runtime`, `operator_annotation`, and `live_external_ref` evidence kinds explicit.

### Metrics And Counting Rules

- **D-05:** Record one minimized trial task row per real task with stable references such as `task_id`, `turn_id`, `conversation_id`, `trace_id`, `result_id`, `feedback_id`, `raw_payload_ref`, and external evidence refs. Do not store user prompts, document text, callback bodies, or full legal conclusions in the repo.
- **D-06:** Each trial task must carry at least: workday, participant alias, legal task category, ordinary vs long-task classification, started/completed timestamps, success status, clear-business-output flag, feedback status/action/category, route_mismatch flag, and negative-feedback response action if applicable.
- **D-07:** Long tasks are tasks with end-to-end duration greater than 60 seconds. Acceptance requires long-task success rate at least 80%, ordinary task success rate at least 85%, feedback capture rate at least 60%, and at least 15 real tasks over five continuous workdays.
- **D-08:** At least 12 of the 15 real tasks must have clear business output, and the trial must cover at least three categories from contract review, legal retrieval Q&A, document drafting, judgment analysis, and case analysis.
- **D-09:** Positive feedback share must be at least 60%. If it is lower, Phase 8 may still produce an acceptance package only when a categorized repair plan is present and linked from the report.

### Feedback, Route Mismatch, And Legal Safety

- **D-10:** Negative feedback requires a response action record within 48 hours. The record can be an external operator reference, but the acceptance report must show status, owner/reviewer alias, action type, and timestamp.
- **D-11:** `route_mismatch` count must be no more than 3. Each mismatch must link to structured `skill_candidate` or `routing_rule_candidate` evidence and stay human-reviewed.
- **D-12:** High-risk legal feedback remains a human gate. Phase 8 must not call `skillopt-runner`, synthesize skills, or auto-modify legal conclusions, statute references, cause-of-action judgments, jurisdiction judgments, liability conclusions, or other high-risk legal outputs.
- **D-13:** Any ordinary WeCom user exposure to Hermes gateway lifecycle, self-update, slash command/help/status/credits/insights, memory/tool progress, delivery debug, stack traces, internal paths, commands, tokens, or runtime details blocks acceptance until repaired and re-tested.

### Reports, Gates, And Automation Boundary

- **D-14:** Add a trial acceptance checker/report that can return `pending`, `blocked`, `failed`, or `passed` with concrete threshold evidence. It must fail closed when live/sanitized runtime input is absent.
- **D-15:** Run `python scripts/run_v2_gates.py --json-summary` before the trial and before final acceptance report generation. Local gates are baseline readiness, not live acceptance.
- **D-16:** Prefer dependency-free Python helpers and stdlib `unittest`, consistent with prior phases. If the planner adds code, put reusable metric/report logic where it can be tested locally without a live WeCom server.
- **D-17:** Trial reports should be human-readable and machine-checkable enough for CI/local verification, but generated reports committed to the repo must be sanitized and must not include runtime callback bodies, media paths, customer document names, complete personal identifiers, phone numbers, bank accounts, addresses, secrets, tokens, or raw legal payloads.

### the agent's Discretion

- The planner may choose whether trial metric logic lives under `packages/contract-test-suite`, a small `scripts/` helper, or a Phase 8 planning artifact, as long as it stays dependency-free and does not become a new production service.
- The planner may choose exact artifact names. Prefer names like `08-LAWYER-TRIAL-RUNBOOK.md`, `08-TRIAL-EVIDENCE-TEMPLATE.json`, `08-TRIAL-ACCEPTANCE.md`, or `trial_acceptance.py` if they make the live-vs-fixture boundary obvious.
- The planner may split Phase 8 into plans for readiness/runbook, metric/report tooling, live trial evidence collection, and final acceptance audit.
- If live credentials or participants are unavailable, the implementation should complete runbooks/templates/checkers and stop at a `human_needed` gate rather than fabricating evidence.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product And Acceptance Scope

- `AGENTS.md` - V2 source-of-truth rules, continuation protocol, InkStatute-owned WeCom boundary, privacy/no-secrets rules, and lawyer trial human gate.
- `docs/requirements/V2-PRD.md` - Active V2 PRD, especially sections 10.4, 12.1 step 9, and the WeCom/output-boundary requirements that must be proven live before acceptance.
- `.planning/PROJECT.md` - Current product definition, constraints, out-of-scope list, and key decisions.
- `.planning/REQUIREMENTS.md` - `REQ-lawyer-trial-acceptance`, `REQ-v2-development-order`, `REQ-wecom-daily-test-loop`, `REQ-assistant-output-boundary`, `REQ-feedback-service`, and privacy baseline.
- `.planning/ROADMAP.md` - Phase 8 goal, dependencies, success criteria, and milestone completion boundary.
- `.planning/STATE.md` - Current accumulated concerns, including legal/safety human review and the live WeCom evidence gate.

### Upstream Phase Evidence

- `.planning/phases/05.5-inkstatute-wecom-service-and-hermes-agent-adapter/05.5-CONTEXT.md` - WeCom service, Hermes adapter, output boundary, no-channel-io, and live acceptance gate decisions.
- `.planning/phases/05.5-inkstatute-wecom-service-and-hermes-agent-adapter/05.5-WECOM-LIVE-ACCEPTANCE.md` - Fixture-passed/live-blocked evidence split and required live WeCom evidence.
- `.planning/phases/06-read-and-feedback-service-apis/06-CONTEXT.md` - Contract-log read model, pending feedback queue, route-mismatch human-review, and privacy decisions.
- `.planning/phases/06-read-and-feedback-service-apis/06-VERIFICATION.md` - Verified read API and feedback queue behavior that Phase 8 can use for metrics.
- `.planning/phases/07-ci-composability-and-privacy-gates/07-CONTEXT.md` - CI/privacy/composability gates and the explicit Phase 8 live acceptance boundary.
- `.planning/phases/07-ci-composability-and-privacy-gates/07-VERIFICATION.md` - Local gate runner evidence and Phase 8 ownership of live trial metrics.

### Existing Code And Test Surface

- `scripts/run_v2_gates.py` - Local V2 readiness gate runner that Phase 8 should run before trial/final reporting.
- `packages/contract-test-suite/src/contract_test_suite/coverage_report.py` - Paired AgentTurn/AgentResult coverage and relationship breakage summary helpers, including runtime-input status handling.
- `services/hermes-contract-layer/src/hermes_contract_layer/wecom_validation.py` - WeCom evidence validator for channel, ACK timing, feedback target, and privacy/secret leakage.
- `services/conversation-read-view/src/conversation_read_view/read_model.py` - Contract-log-derived conversation/task/trace read model.
- `services/conversation-read-view/src/conversation_read_view/api.py` - Pure GET handlers for conversations, tasks, and pending feedback.
- `services/feedback-service/src/feedback_service/queue.py` - Feedback normalization, dedupe, pending queue derivation, and human-review evidence fields.
- `services/feedback-service/src/feedback_service/classification.py` - Rule-based feedback classification categories and no-auto-modify behavior.
- `services/wecom-service/src/wecom_service/output_policy.py` - Assistant output boundary allow/rewrite/block decisions and sanitized audit metadata.
- `packages/contract-test-suite/tests/test_coverage_report.py` - Tests proving fixture coverage is not reported as live acceptance and sanitized runtime input can be required.
- `packages/contract-test-suite/tests/test_ci_workflow_contract.py` - Tests that CI remains a thin wrapper around local V2 gates and documents Phase 8 ownership.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `coverage_report.assert_coverage_thresholds(..., require_runtime_input=True)` can fail closed when sanitized runtime coverage input is absent.
- `wecom_validation.validate_wecom_shadow_evidence` already checks ACK timing, WeCom channel evidence, feedback target presence, and secret/raw-payload leakage for sanitized streams.
- `ContractLogReadModel` can derive conversation/task/trace views from contract event records without a new authoritative database.
- `feedback_service.queue.build_pending_feedback_queue` can derive pending human-review feedback items with duplicate counts, idempotency keys, `requires_human_review`, and `no_auto_modify`.
- `output_policy.apply_output_policy` already returns sanitized audit metadata and blocks/rewrite backend-originated notices before ordinary WeCom delivery.
- `scripts/run_v2_gates.py` provides the repo-wide readiness command that Phase 8 can cite in runbooks and final reports.

### Established Patterns

- Phase artifacts separate fixture readiness from live acceptance. Phase 8 must preserve this split more strictly than earlier phases.
- Python packages/services are dependency-free and tested through stdlib `unittest` with explicit `PYTHONPATH`.
- Fixtures and reports use `fixture://`, `raw_payload_ref`, and external references instead of raw customer/legal payloads.
- Route-mismatch and skill-candidate evidence stays human-reviewed and must never imply automatic legal skill changes.
- Planning and verification artifacts can record blocked/human-needed status honestly when runtime evidence is not available.

### Integration Points

- Trial metric tooling can consume sanitized contract event streams, read-model outputs, pending feedback queues, and operator annotation rows.
- Trial reports can link to external evidence refs for live WeCom callback/send logs, contract logs, file/card delivery evidence, feedback callbacks, and response actions.
- Pre-trial and final checks should call the local V2 gate runner and keep GitHub Actions as a wrapper only.
- Any Phase 8 code should live in a testable local module or script; no new service, database, queue, or runtime dependency is required for acceptance reporting.

</code_context>

<specifics>
## Specific Ideas

- Prefer a trial evidence template with sections for participant/day, task refs, category, timing, success/business-output status, feedback, route mismatch, response action, and output-boundary evidence.
- Prefer final report statuses: `pending_live_trial`, `blocked_missing_live_evidence`, `failed_thresholds`, `passed_with_repair_plan`, and `passed`.
- Prefer explicit labels on every evidence row: `fixture`, `sanitized_runtime`, `operator_annotation`, or `live_external_ref`.
- Prefer one command that prints sanitized threshold summaries and never dumps task text or callback payloads.
- Prefer a manual trial runbook that tells the operator exactly what to collect without placing secrets, raw callback bodies, documents, media, or customer facts in the repo.

</specifics>

<deferred>
## Deferred Ideas

- Long-term legal quality evaluation beyond 5 workdays and 15 tasks belongs after V2.
- Production dashboards, admin console UI, durable trial databases, WORM audit logs, RBAC, retention/destruction workflows, and ongoing analytics belong to later milestones.
- Codex/provider-model production adapters, QQBot/WeChat V2 live loops, and multi-channel acceptance remain beyond V2.
- Automatic skill synthesis or automatic legal conclusion modification remains out of scope.

</deferred>

---

*Phase: 8-Lawyer Trial Acceptance*
*Context gathered: 2026-06-28T09:19:46Z*
