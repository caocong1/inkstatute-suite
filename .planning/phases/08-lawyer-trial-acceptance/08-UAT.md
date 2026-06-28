---
status: testing
phase: 08-lawyer-trial-acceptance
source: [08-VERIFICATION.md]
started: 2026-06-28T09:48:00Z
updated: 2026-06-28T23:53:52+08:00
---

## Current Test

number: 1
name: Run live task-flow UAT before starting the trial clock
expected: |
  InkStatute WeCom service handles long document tasks as background task flows: one quick ACK, recurring service-owned progress, explicit final/timeout/failure state, no empty-message answer for file+text turns, and a fast service response when the user sends a second message while the first task is still running.
awaiting: fresh live WeCom document+instruction UAT after 2026-06-28T23:53:44+08:00 bridge restart, plus a follow-up message while the task is still running

## Tests

### 1. Repair live long-task task flow before starting the trial clock

expected: Long-running file/document tasks use task-flow runtime, and follow-up user input is handled through a fast control-plane route instead of waiting behind the active task.
result: [pending] Local task-flow/router implementation is complete and was rechecked. Live UAT at 2026-06-28T23:13-23:17+08:00 exposed a `completed` false positive: Hermes one-shot returned the 46-character intermediate progress sentence "合同全文已解析完毕...生成带修订痕迹的 DOCX", but no final DOCX was generated or sent (`file_count=0`). The bridge now has a delivery-completion guard that records this as `agent_backend_incomplete_output` instead of `completed`, plus private runtime audit JSONL for bot boundary messages, Hermes prompt/stdout/stderr, and newly written Hermes `state.db` transcript messages. Full V2 gates passed, and `inkstatute-wecom-live-bridge.service` was restarted successfully for chat `155` at 2026-06-28T23:53:44+08:00. Fresh live WeCom document+instruction UAT is still required before this item can pass.

### 2. Run live readiness gates before starting the trial clock

expected: Operator supplies external live readiness refs before counting any trial workday.
result: [pending]

### 3. Complete five-workday lawyer trial

expected: At least 1 lawyer uses the WeCom bot continuously for 5 workdays.
result: [pending]

### 4. Supply minimized task evidence

expected: Evidence covers at least 15 real tasks, at least 12 clear business outputs, and at least 3 legal task categories.
result: [pending]

### 5. Prove acceptance metrics

expected: Checker report proves long-task success at least 80%, ordinary-task success at least 85%, feedback capture at least 60%, and positive feedback at least 60% or a categorized repair plan.
result: [pending]

### 6. Review feedback and route mismatch safety

expected: Negative feedback has response action evidence within 48 hours; route_mismatch count is no more than 3 and every mismatch has candidate evidence.
result: [pending]

### 7. Confirm output boundary and legal safety

expected: Human reviewer confirms no Hermes meta notices reached ordinary users and no high-risk legal feedback triggered automatic legal conclusion changes.
result: [pending]

## Summary

total: 7
passed: 0
issues: 1
pending: 7
skipped: 0
blocked: 1

## Gaps

- Live UAT exposed that the temporary one-shot Hermes bridge can time out long document work and cannot provide meaningful backend-neutral progress or fast mid-task follow-up handling.
- 08-04 local repair is implemented and the live bridge has been restarted with task-flow code loaded, but the 2026-06-28T23:13+08:00 live UAT found a completed false positive when Hermes returned an intermediate "now generating DOCX" message without an artifact.
- 2026-06-28T23:53+08:00 repair adds delivery-completion guardrails and private runtime audit JSONL, including Hermes boundary request/response and `state.db` transcript capture. The five-workday trial clock remains blocked until a fresh live WeCom file+instruction task proves quick ACK, recurring progress, explicit final/timeout/failure state, no empty-message answer, no Hermes meta leak, final artifact delivery or honest incomplete/failure classification, and fast follow-up response during an active task.
