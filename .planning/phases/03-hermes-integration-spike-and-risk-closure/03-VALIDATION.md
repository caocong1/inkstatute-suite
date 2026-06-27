---
phase: 03
slug: hermes-integration-spike-and-risk-closure
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-27
---

# Phase 03 - Validation Strategy

Per-phase validation contract for Hermes integration risk-closure planning and execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` via `packages/contract-test-suite` |
| **Config file** | none - package-local runner uses unittest discovery |
| **Quick run command** | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` |
| **Full suite command** | `python -m compileall packages/platform-contract/src packages/platform-contract/tests packages/contract-test-suite/src packages/contract-test-suite/tests packages/contract-test-suite/scripts && cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` |
| **Estimated runtime** | under 5 seconds in the current repo |

## Sampling Rate

- **After every task commit touching fixtures/tests/contracts:** Run the quick command.
- **After every plan wave:** Run the full suite command and inspect Phase 3 doc artifacts for status-tagged Hermes assumptions.
- **Before verification:** Full suite must be green, and every Hermes-dependent decision must be tagged `confirmed`, `assumed`, `requires Hermes source/runtime`, `deferred`, or `blocked`.
- **Max feedback latency:** 10 seconds for local automated checks.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | REQ-implementation-risk-resolution | T-03-01-I | Hermes source absence and evidence gaps are explicit, not hidden. | doc/probe | `rg -n "response_filter|template_card|wecom_template_card_shim|message_id|feedback|long_task|agent:end" -S .` | pending | pending |
| 03-02-01 | 02 | 2 | REQ-implementation-risk-resolution | T-03-02-I | Hook order and AgentTurn strategy cannot leak admin/unfiltered payload assumptions into Phase 4. | doc review | `test -f .planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-AND-TURN-DECISIONS.md` | pending | pending |
| 03-03-01 | 03 | 3 | REQ-implementation-risk-resolution | T-03-03-T/R | Identifier, idempotency, async state, and raw payload rules are explicit and status-tagged. | doc review | `test -f .planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` | pending | pending |
| 03-04-01 | 04 | 4 | REQ-implementation-risk-resolution | T-03-04-I | Non-happy-path fixtures use references/minimized synthetic data and validate through the harness. | unit/fixture | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` | pending | pending |

## Wave 0 Requirements

- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HERMES-SOURCE-INVENTORY.md` - source/runtime evidence ledger.
- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-INTEGRATION-RISK-MATRIX.md` - PRD section 13 risk status matrix.
- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-AND-TURN-DECISIONS.md` - hook ordering and AgentTurn input strategy.
- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` - identifier, idempotency, async state, raw payload, retention, and redaction rules.
- [ ] Non-happy-path fixtures/tests for route errors, long-task failures, repeated feedback clicks, and one non-legal task.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confirm Hermes hook ordering from real Hermes source/runtime | REQ-implementation-risk-resolution | Hermes runtime source is not present in this repo. | Mount/add Hermes source or a sanitized runtime evidence bundle, then run the Phase 3 hook-order probe documented by this phase. |
| Confirm template card callback payload fields | REQ-implementation-risk-resolution | No callback payload samples or `feedback.jsonl` rows exist in this repo. | Provide one sanitized callback payload and one sanitized feedback row, then map fields to the Phase 3 identifier/idempotency rules. |
| Confirm long-task runtime state source | REQ-implementation-risk-resolution | No Hermes queue/session/long-task source exists in this repo. | Provide Hermes long-task source/log samples for queued, running, waiting, success, failure, and cancellation cases. |

## Validation Sign-Off

- [x] All planned tasks must have automated verify commands or explicit manual-only evidence gates.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 gaps are listed and phase-owned.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 10 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-27 for planning
