---
phase: 05-wecom-shadow-loop-validation
verified: 2026-06-28T03:23:46Z
status: human_needed
score: "2/5 live acceptance truths fully verified; 3/5 require live WeCom evidence"
decision_coverage:
  honored: 15
  total: 15
  not_honored: []
---

# Phase 5: WeCom Shadow Loop Validation Verification Report

**Phase Goal:** Lawyers can use the existing WeCom loop while V2 shadow records results and feedback into standard events.
**Verified:** 2026-06-28T03:23:46Z
**Status:** human_needed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Lawyer sends an incoming WeCom task and receives channel acknowledgment within the WeCom timeout window. | UNCERTAIN - LIVE NEEDED | Fixture ACK timing validates 4 seconds in `05-WECOM-VALIDATION.md`; no live WeCom ACK evidence was collected. |
| 2 | Hermes still sends text, files, and template cards through the existing gateway path. | UNCERTAIN - LIVE NEEDED | Runbook and evidence report preserve the existing gateway path, but no live outbound text/file/card run was performed. |
| 3 | `contract_result_recorder` records the AgentResult after Hermes prepares the response. | VERIFIED | Phase 4 hook tests still pass; Phase 5 stream fixture replays `agent_result.feedback_target` and validates through `validate_wecom_shadow_evidence`. |
| 4 | Template card feedback is captured by the existing shim and can be normalized into FeedbackEvent. | PARTIAL - LIVE NEEDED | Sanitized callback fixtures normalize into schema-valid `FeedbackEvent` records; live shim capture into `feedback.jsonl` was not collected. |
| 5 | Existing Hermes lawfirm WeCom feedback behavior does not regress, and QQ Bot/WeChat remain unbroken non-acceptance channels. | UNCERTAIN - LIVE NEEDED | Evidence report records QQ Bot/WeChat status as blocked pending operator confirmation. |

**Score:** 2/5 truths fully verified by local evidence. The remaining truths need live Hermes/WeCom validation, not code fixes.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `services/hermes-contract-layer/src/hermes_contract_layer/wecom_validation.py` | WeCom evidence validation helper | VERIFIED | Exports `validate_wecom_shadow_evidence`, `WeComValidationIssue`, and `WeComValidationReport`; tests cover feedback target, channel, ACK, stream, and privacy issues. |
| `services/hermes-contract-layer/docs/wecom_shadow_loop_validation.md` | Live validation runbook | VERIFIED | Separates fixture and live status, requires opt-in deployment, rollback, privacy rules, and blocked evidence format. |
| `services/feedback-service/src/feedback_service/wecom_normalizer.py` | Minimal sanitized WeCom feedback normalizer | VERIFIED | Produces schema-valid FeedbackEvent dicts, dedupes repeated callbacks, and marks route-mismatch skill candidates human-reviewed/no-auto-modify. |
| `packages/contract-test-suite/tests/test_phase5_wecom_loop.py` | Phase 5 result-to-feedback replay tests | VERIFIED | Validates stream replay, full bundle relationships, normalizer output, route mismatch safeguards, and privacy scanning. |
| `packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl` | Sanitized result stream | VERIFIED | Replays with zero broken core relationships and includes `agent_result.feedback_target`. |
| `packages/contract-test-suite/fixtures/phase5_wecom_feedback_loop_fixture.json` | Full five-event result-feedback bundle | VERIFIED | Validates all schemas and asserts result/feedback target continuity. |
| `.planning/phases/05-wecom-shadow-loop-validation/05-WECOM-VALIDATION.md` | Fixture/live evidence report | VERIFIED | `fixture_status: passed`; `live_wecom_status: blocked`; lists missing runtime prerequisites. |

**Artifacts:** 7/7 exist and are substantive.

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `wecom_validation.py` | `event_stream_replay.py` | `load_event_stream` | VERIFIED | Phase 5 stream is schema-validated and replayed before WeCom-specific checks. |
| `wecom_normalizer.py` | `feedback_event.schema.json` | `validate_event("feedback_event", ...)` in tests | VERIFIED | Normalized events pass schema validation in feedback-service and Phase 5 contract-suite tests. |
| `test_phase5_wecom_loop.py` | `wecom_normalizer.py` | `normalize_wecom_feedback_records` | VERIFIED | Test asserts normalizer output matches the fixture FeedbackEvent shape. |
| `phase5_wecom_feedback_loop_fixture.json` | `fixture_replay.py` | `assert_relationship_integrity` | VERIFIED | Relationship report has zero broken links for turn, result, feedback target, route, and trace. |
| `05-WECOM-VALIDATION.md` | live runbook | status and blockers | VERIFIED | The report does not claim live pass and points to missing runtime evidence. |

**Wiring:** 5/5 verifiable links checked.

## Requirements Coverage

| Requirement | Status | Blocking Issue |
|---|---|---|
| `REQ-wecom-daily-test-loop`: Preserve and validate the existing WeCom daily-use loop while shadow-recording contract events and normalized feedback. | HUMAN NEEDED | Local fixture replay and normalization are verified, but live Hermes/WeCom ACK, outbound delivery, callback capture, and QQ/WeChat non-regression are blocked pending operator-run evidence. |

**Coverage:** 0/1 requirements fully satisfied for live acceptance; 1/1 locally fixture-validated.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| None | - | - | - | No code stubs, raw payload fields, committed runtime logs, secrets, callback bodies, customer documents, databases, queues, CI workflows, or automatic legal skill modification were introduced. |

## Human Verification Required

### 1. Live WeCom Short Legal Retrieval

**Test:** Follow `services/hermes-contract-layer/docs/wecom_shadow_loop_validation.md` for one short WeCom legal retrieval task.
**Expected:** ACK within timeout, text response, template card delivery, contract JSONL result record, and sanitized feedback callback reference.
**Why human:** Requires live Hermes lawfirm profile, connected WeCom channel, and sanitized runtime evidence.

### 2. Live WeCom Long/Document Task

**Test:** Run one long or document task through WeCom with the opt-in recorder configured.
**Expected:** ACK, completion push, text/file/card delivery, AgentResult record after response preparation, and feedback target continuity.
**Why human:** Requires live runtime and a safe document/test payload outside the repo.

### 3. QQ Bot and WeChat Non-Acceptance Non-Regression

**Test:** Operator confirms QQ Bot and WeChat behavior were not changed by Phase 5 shadow validation.
**Expected:** Existing non-acceptance channels remain connected/unbroken or blocker is recorded.
**Why human:** Requires connected channel/runtime confirmation.

## Gaps Summary

No code gaps found. Automated fixture validation, schema validation, replay relationships, privacy scanning, and service-local tests pass.

Critical live gate:

1. **Live WeCom validation evidence missing**
   - Missing: live ACK timing, outbound text/file/card evidence, callback `feedback.jsonl` reference, and QQ Bot/WeChat non-regression confirmation.
   - Impact: Phase 5 cannot claim live WeCom acceptance.
   - Fix: Complete the opt-in runbook and update `05-WECOM-VALIDATION.md` with sanitized evidence references.

## Recommended Fix Plans

No code fix plan is recommended. The remaining work is operator validation, not implementation. Do not proceed as if live acceptance passed until `live_wecom_status` is updated from `blocked` to `passed` with evidence references.

## Behavioral Verification

| Check | Result | Detail |
|---|---|---|
| Compile source and tests | PASS | `python -m compileall services/hermes-contract-layer/src services/hermes-contract-layer/tests services/feedback-service/src services/feedback-service/tests packages/contract-test-suite/src packages/contract-test-suite/tests` |
| Phase 5 contract replay test | PASS | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src:../../services/feedback-service/src:../../services/hermes-contract-layer/src python -m unittest discover -s tests -p 'test_phase5_wecom_loop.py' -v` ran 5 tests. |
| Contract-test-suite runner | PASS | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` ran 41 tests. |
| Hermes contract-layer tests | PASS | `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v` ran 24 tests. |
| Feedback-service tests | PASS | `PYTHONPATH=services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/feedback-service/tests -v` ran 9 tests. |
| Documentation/evidence grep | PASS | Evidence report and README include fixture/live status and live-validation distinction. |
| Decision coverage | PASS | All 15 trackable Phase 5 decisions are honored by shipped artifacts. |

## Decision Coverage

All trackable CONTEXT.md decisions are honored by shipped artifacts.

---
*Verified: 2026-06-28T03:23:46Z*
*Verifier: the agent*
