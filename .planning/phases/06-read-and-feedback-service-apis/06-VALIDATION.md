---
phase: "06"
slug: read-and-feedback-service-apis
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-28
---

# Phase 06 - Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | stdlib `unittest` |
| Config file | none |
| Quick run command | `PYTHONPATH=services/conversation-read-view/src:packages/contract-test-suite/src python -m unittest discover services/conversation-read-view/tests` |
| Full suite command | `PYTHONPATH=packages/contract-test-suite/src:services/conversation-read-view/src:services/feedback-service/src:services/wecom-service/src python -m unittest discover packages/contract-test-suite/tests` |
| Estimated runtime | ~15 seconds |

## Sampling Rate

- After every task commit: run the task's listed `python -m unittest` command.
- After every plan wave: run the relevant service tests plus contract-test-suite integration tests.
- Before `$gsd-verify-work`: run all Phase 6 service tests, contract-test-suite tests, and `python -m compileall`.
- Max feedback latency: 30 seconds for local automated feedback.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | REQ-conversation-read-view | T-06-01-authority | New read-view package has no runtime dependencies and no database authority | unit/source | `PYTHONPATH=services/conversation-read-view/src:packages/contract-test-suite/src python -m unittest discover services/conversation-read-view/tests` | yes | pending |
| 06-01-02 | 01 | 1 | REQ-conversation-read-view | T-06-01-privacy | Read model rejects exact `raw_payload` and preserves only references | unit | `PYTHONPATH=services/conversation-read-view/src:packages/contract-test-suite/src python -m unittest discover services/conversation-read-view/tests` | yes | pending |
| 06-01-03 | 01 | 1 | REQ-conversation-read-view | T-06-01-ordering | Out-of-order inputs produce deterministic conversation/task views | unit | `PYTHONPATH=services/conversation-read-view/src:packages/contract-test-suite/src python -m unittest discover services/conversation-read-view/tests` | yes | pending |
| 06-02-01 | 02 | 1 | REQ-feedback-service | T-06-02-classification | Feedback classifications cover all PRD event categories without AI calls | unit | `PYTHONPATH=services/feedback-service/src:services/wecom-service/src:packages/contract-test-suite/src python -m unittest discover services/feedback-service/tests` | yes | pending |
| 06-02-02 | 02 | 1 | REQ-feedback-service | T-06-02-dedupe | Repeated callbacks and shim writes collapse by stable idempotency key | unit | `PYTHONPATH=services/feedback-service/src:services/wecom-service/src:packages/contract-test-suite/src python -m unittest discover services/feedback-service/tests` | yes | pending |
| 06-02-03 | 02 | 1 | REQ-feedback-service | T-06-02-human-review | Route mismatch emits pending human-review skill-candidate queue items with no auto modification | unit | `PYTHONPATH=services/feedback-service/src:services/wecom-service/src:packages/contract-test-suite/src python -m unittest discover services/feedback-service/tests` | yes | pending |
| 06-03-01 | 03 | 2 | REQ-conversation-read-view | T-06-03-api-privacy | GET handlers expose read-only dictionaries with reference-only metadata | integration | `PYTHONPATH=services/conversation-read-view/src:services/feedback-service/src:packages/contract-test-suite/src python -m unittest discover services/conversation-read-view/tests` | yes | pending |
| 06-03-02 | 03 | 2 | REQ-feedback-service | T-06-03-feedback-route | GET feedback route returns only pending derived queue items by default | integration | `PYTHONPATH=packages/contract-test-suite/src:services/conversation-read-view/src:services/feedback-service/src:services/wecom-service/src python -m unittest discover packages/contract-test-suite/tests` | yes | pending |
| 06-03-03 | 03 | 2 | REQ-conversation-read-view, REQ-feedback-service | T-06-03-relationships | Phase 6 fixtures preserve turn/result/feedback relationships and secret-free reference output | integration | `PYTHONPATH=packages/contract-test-suite/src:services/conversation-read-view/src:services/feedback-service/src:services/wecom-service/src python -m unittest discover packages/contract-test-suite/tests` | yes | pending |

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:

- `unittest` is already used across services and packages.
- `contract_test_suite.event_stream_replay` and `fixture_replay` already validate schemas and relationships.
- Existing Phase 5 and Phase 5.5 fixtures provide baseline WeCom/result/feedback examples.

## Manual-Only Verifications

All Phase 6 behaviors have automated verification. Live WeCom acceptance remains blocked by Phase 5.5 live credentials and is not claimed by this phase.

## Validation Sign-Off

- [x] All tasks have automated verify commands or existing Wave 0 coverage.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing framework references.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 30 seconds for local checks.
- [x] `nyquist_compliant: true` set in frontmatter.

Approval: approved 2026-06-28

