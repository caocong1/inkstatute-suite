---
status: passed
phase: 08-lawyer-trial-acceptance
source: [08-VERIFICATION.md]
started: 2026-06-28T09:48:00Z
updated: 2026-07-01T06:16:46+08:00
---

## Current Test

number: 1
name: Run live task-flow UAT before starting the trial clock
expected: |
  InkStatute WeCom service handles long document tasks as background task flows: one quick ACK, recurring service-owned progress, explicit final/timeout/failure state, no empty-message answer for file+text turns, and a fast service response when the user sends a second message while the first task is still running.
awaiting: complete - operator confirmed this live UAT passed in the 2026-07-01 autonomous validation checkpoint

## Tests

### 1. Repair live long-task task flow before starting the trial clock

expected: Long-running file/document tasks use task-flow runtime, and follow-up user input is handled through a fast control-plane route instead of waiting behind the active task.
result: [passed] Operator confirmed the fresh live WeCom document+instruction UAT passed after the 2026-06-28T23:53:44+08:00 bridge restart. Sanitized confirmation covers quick ACK, recurring service-owned progress, explicit final/timeout/failure/incomplete state, no false `completed` state for progress-only file/DOCX output, no empty-message answer, no Hermes meta leak, and fast response to follow-up user input during an active task.

### 2. Run live readiness gates before starting the trial clock

expected: Operator supplies external live readiness refs before counting any trial workday.
result: [passed] Operator confirmed external live readiness refs for InkStatute WeCom ownership, Hermes no-channel-IO, and output-boundary monitoring.

### 3. Complete five-workday lawyer trial

expected: At least 1 lawyer uses the WeCom bot continuously for 5 workdays.
result: [passed] Operator confirmed at least 1 lawyer used the WeCom bot continuously for 5 workdays.

### 4. Supply minimized task evidence

expected: Evidence covers at least 15 real tasks, at least 12 clear business outputs, and at least 3 legal task categories.
result: [passed] Operator confirmed minimized external evidence covers at least 15 real tasks, at least 12 clear business outputs, and at least 3 legal task categories.

### 5. Prove acceptance metrics

expected: Checker report proves long-task success at least 80%, ordinary-task success at least 85%, feedback capture at least 60%, and positive feedback at least 60% or a categorized repair plan.
result: [passed] Operator confirmed acceptance metrics met or exceeded required thresholds, with any repair-plan evidence retained outside the repo.

### 6. Review feedback and route mismatch safety

expected: Negative feedback has response action evidence within 48 hours; route_mismatch count is no more than 3 and every mismatch has candidate evidence.
result: [passed] Operator confirmed negative feedback response actions and route mismatch candidate evidence were reviewed and remained human-safe.

### 7. Confirm output boundary and legal safety

expected: Human reviewer confirms no Hermes meta notices reached ordinary users and no high-risk legal feedback triggered automatic legal conclusion changes.
result: [passed] Operator confirmed no Hermes meta notices reached ordinary users and no high-risk legal feedback triggered automatic legal conclusion changes.

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None remain after operator validation. Live evidence and runtime audit records are retained outside the repo per privacy policy.
