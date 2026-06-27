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
- **Blocking hook-order gate:** Phase 3 verification fails unless `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-ORDER-EVIDENCE.md` contains Hermes source/runtime evidence or a sanitized tested probe confirming whether `contract_result_recorder` can run after `response_filter`. `requires Hermes source/runtime` alone is a Phase 3 verification gap, not a passing status.
- **Max feedback latency:** 10 seconds for local automated checks.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | REQ-implementation-risk-resolution | T-03-01-I | Hermes source absence and evidence gaps are explicit, not hidden. | doc/probe | `rg -n "response_filter|template_card|wecom_template_card_shim|message_id|feedback|long_task|agent:end" -S .` | pending | pending |
| 03-02-01 | 02 | 2 | REQ-implementation-risk-resolution | T-03-02-I | Hook order and AgentTurn strategy cannot leak admin/unfiltered payload assumptions into Phase 4. | blocking doc/probe gate | `python -c "from pathlib import Path; base=Path('.planning/phases/03-hermes-integration-spike-and-risk-closure'); evidence=(base/'03-HOOK-ORDER-EVIDENCE.md').read_text(); decisions=(base/'03-HOOK-AND-TURN-DECISIONS.md').read_text(); assert 'EVIDENCE_OUTCOME: source_confirmed' in evidence or 'EVIDENCE_OUTCOME: sanitized_probe_tested' in evidence; assert 'HOOK_ORDER_DECISION: can_run_after_response_filter' in evidence or 'HOOK_ORDER_DECISION: cannot_run_after_response_filter' in evidence; assert 'BLOCKING_VERIFICATION_GAP' not in evidence; assert '03-HOOK-ORDER-EVIDENCE.md' in decisions"` | pending | pending |
| 03-03-01 | 03 | 3 | REQ-implementation-risk-resolution | T-03-03-T/R | Identifier, idempotency, async state, and raw payload rules are explicit and status-tagged. | doc review | `test -f .planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` | pending | pending |
| 03-04-01 | 04 | 4 | REQ-implementation-risk-resolution | T-03-04-I | Non-happy-path fixtures use references/minimized synthetic data and validate through the harness. | unit/fixture | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` | pending | pending |

## Wave 0 Requirements

- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HERMES-SOURCE-INVENTORY.md` - source/runtime evidence ledger.
- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-INTEGRATION-RISK-MATRIX.md` - PRD section 13 risk status matrix.
- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-ORDER-EVIDENCE.md` - blocking source/runtime or sanitized probe evidence for whether `contract_result_recorder` can run after `response_filter`.
- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-AND-TURN-DECISIONS.md` - hook ordering and AgentTurn input strategy.
- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` - identifier, idempotency, async state, raw payload, retention, and redaction rules.
- [ ] Non-happy-path fixtures/tests for route errors, long-task failures, repeated feedback clicks, and one non-legal task.

## Manual-Only Verifications

Hook ordering is a blocking manual/external-evidence gate. If the executor cannot mount Hermes source/runtime evidence or produce a sanitized tested hook-order probe, Plan 03-02 must report `BLOCKING_VERIFICATION_GAP` and Phase 3 verification must not pass.

| Behavior | Requirement | Gate | Why Manual | Test Instructions |
|----------|-------------|------|------------|-------------------|
| Confirm Hermes hook ordering from real Hermes source/runtime | REQ-implementation-risk-resolution | blocking | Hermes runtime source is not present in this repo. | Mount/add Hermes source or a sanitized runtime evidence bundle, then run the Phase 3 hook-order probe documented by this phase. Passing evidence must update `03-HOOK-ORDER-EVIDENCE.md` with `EVIDENCE_OUTCOME: source_confirmed` or `EVIDENCE_OUTCOME: sanitized_probe_tested`, plus `HOOK_ORDER_DECISION: can_run_after_response_filter` or `HOOK_ORDER_DECISION: cannot_run_after_response_filter`. |
| Confirm template card callback payload fields | REQ-implementation-risk-resolution | blocking for Phase 4, informational for Phase 3 fixture execution | No callback payload samples or `feedback.jsonl` rows exist in this repo. | Provide one sanitized callback payload and one sanitized feedback row, then map fields to the Phase 3 identifier/idempotency rules. |
| Confirm long-task runtime state source | REQ-implementation-risk-resolution | blocking for Phase 4, informational for Phase 3 fixture execution | No Hermes queue/session/long-task source exists in this repo. | Provide Hermes long-task source/log samples for queued, running, waiting, success, failure, and cancellation cases. |

## Validation Sign-Off

- [x] All planned tasks must have automated verify commands or explicit manual-only evidence gates.
- [x] Hook ordering manual/external evidence is blocking for Phase 3 verification, not informational.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 gaps are listed and phase-owned.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 10 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-27 for planning
