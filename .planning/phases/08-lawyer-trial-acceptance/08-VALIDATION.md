---
phase: 08
slug: lawyer-trial-acceptance
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-28
---

# Phase 08 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | stdlib unittest |
| **Config file** | none |
| **Quick run command** | `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py` |
| **Full suite command** | `python scripts/run_v2_gates.py --json-summary` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py` when trial checker code is touched; otherwise run the plan-specific doc/source assertions.
- **After every plan wave:** Run `python scripts/run_v2_gates.py --json-summary`.
- **Before `$gsd-verify-work`:** Full suite must be green and Phase 8 trial acceptance must be either externally passed or explicitly `human_needed`.
- **Max feedback latency:** 48 hours for negative feedback response-action records.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | REQ-lawyer-trial-acceptance | T-08-01-fixture-live | Fixture evidence cannot pass live trial checks | unit | `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py` | W0 | pending |
| 08-01-02 | 01 | 1 | REQ-lawyer-trial-acceptance | T-08-01-threshold | Threshold failures produce failed/blocked reports | unit | `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py` | W0 | pending |
| 08-01-03 | 01 | 1 | REQ-v2-development-order | T-08-01-order | Trial checker requires V2 readiness evidence before final pass | unit | `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_trial_acceptance.py` | W0 | pending |
| 08-02-01 | 02 | 2 | REQ-lawyer-trial-acceptance | T-08-02-leak | Runbook forbids raw payloads/secrets in committed evidence | source | `rg -n "raw_payload\\b|access_token|encodingaeskey|callback body" .planning/phases/08-lawyer-trial-acceptance` | W0 | pending |
| 08-02-02 | 02 | 2 | REQ-v2-development-order | T-08-02-prereq | Runbook requires InkStatute WeCom service and no-channel-io evidence before counting | source | `rg -n "InkStatute WeCom service|no_channel_io|output boundary" .planning/phases/08-lawyer-trial-acceptance/08-LAWYER-TRIAL-RUNBOOK.md` | W0 | pending |
| 08-03-01 | 03 | 3 | REQ-lawyer-trial-acceptance | T-08-03-human | Acceptance report remains human_needed until real evidence is supplied | source | `rg -n "status: human_needed|fixture evidence cannot pass" .planning/phases/08-lawyer-trial-acceptance/08-TRIAL-ACCEPTANCE.md` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:

- `scripts/run_v2_gates.py` already runs repo-wide local gates.
- `packages/contract-test-suite/tests/` already uses stdlib `unittest`.
- `coverage_report.py`, `wecom_validation.py`, read-view, feedback queue, and output policy helpers already exist as inputs.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Five continuous workdays with at least one lawyer | REQ-lawyer-trial-acceptance | Requires real participant usage over calendar time | Operator fills external evidence refs in `08-TRIAL-ACCEPTANCE.md` after the trial window. |
| At least 15 real tasks and 12 clear business outputs | REQ-lawyer-trial-acceptance | Requires legal/business judgment and real task outcomes | Operator records minimized task rows and reviewer confirms `clear_business_output=true` where applicable. |
| Negative feedback response action within 48 hours | REQ-lawyer-trial-acceptance | Requires human response and timestamped external evidence | Reviewer verifies each negative item has `response_action_ref` and `response_action_at`. |
| Route mismatch candidate review | REQ-lawyer-trial-acceptance | Requires human legal/routing judgment | Reviewer verifies each mismatch has `skill_candidate_ref` or `routing_rule_candidate_ref`. |

---

## Validation Sign-Off

- [x] All tasks have automated verify or explicit manual gate references.
- [x] Sampling continuity: no 3 consecutive tasks without automated/source verification.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target is 48 hours.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending Phase 8 execution
