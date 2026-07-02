---
phase: 23
slug: feedback-to-memory-review-loop
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
verified: 2026-07-02
---

# Phase 23 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` / pytest 9.1.1 |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py packages/platform-runtime/tests/test_memory_review.py` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase23_feedback_to_memory_review_loop.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py' && PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src python -m pytest services/feedback-service/tests/test_memory_wiring.py -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the focused automated command listed for that task.
- **After every plan wave:** Run the full suite command.
- **Before `$gsd-verify-work`:** Full suite must be green and Phase 23 verification artifact must be present.
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | FBL-01 | T-23-01 | Safe feedback corrections enter next same-session context as refs without raw message text | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py` | Yes | green |
| 23-01-02 | 01 | 1 | FBL-02 | T-23-02 | Repeated negative feedback creates pending memory candidates with source refs, confidence, proposed scope, sensitivity, and review metadata | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py` | Yes | green |
| 23-01-03 | 01 | 1 | FBL-03 | T-23-03 | Reviewer actions approve, reject, edit, tombstone, or defer candidates without auto-promoting unsafe content | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_review.py` | Yes | green |
| 23-01-04 | 01 | 1 | FBL-04 | T-23-04 | Approved candidates become durable MemoryRecord entries; rejected/deferred do not enter recall | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_review.py` | Yes | green |
| 23-01-05 | 01 | 1 | FBL-05 | T-23-05 | Route mismatch, skill candidate, and high-risk legal conclusion evidence remains human-reviewed with no_auto_modify | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_review.py` | Yes | green |
| 23-02-01 | 02 | 2 | FBL-01..FBL-05 | T-23-06 | Synthetic fixture represents review decisions, candidates, and correction refs using refs only | contract | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase23_feedback_to_memory_review_loop.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` | Yes | green |
| 25.1-02-01 | 25.1-02 | 2 | FBL-01, FBL-02, REC-02 | T-25.1-04 | Existing feedback callback/service ingestion calls wire_feedback_to_memory, stores safe correction refs, and queues pending candidates with refs/hashes/lengths only | service integration | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src python -m pytest services/feedback-service/tests/test_memory_wiring.py::FeedbackCallbackMemoryIngestionTests -q` | Yes | green |
| 25.1-02-02 | 25.1-02 | 2 | FBL-03, FBL-04 | T-25.1-05 | Human review actions are required for candidate promotion; rejected/deferred/route-skill candidates do not enter recall | unit + service integration | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src python -m pytest services/feedback-service/tests/test_memory_wiring.py::FeedbackMemoryReviewActionTests -q` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `packages/platform-runtime/tests/test_feedback_learning.py` — covers FBL-01 and FBL-02.
- [x] `packages/platform-runtime/tests/test_memory_review.py` — covers FBL-03 through FBL-05.
- [x] `services/feedback-service/src/feedback_service/memory_wiring.py` — service helper for feedback-to-memory wiring.
- [x] `services/feedback-service/tests/test_memory_wiring.py` — covers FBL-01 through FBL-04 at service boundary.
- [x] `packages/contract-test-suite/fixtures/phase23_feedback_to_memory_review_loop.json` — synthetic fixture.
- [x] `packages/contract-test-suite/tests/test_phase23_feedback_to_memory_review_loop.py` — contract tests.
- [x] `.planning/phases/23-feedback-to-memory-review-loop/23-VERIFICATION.md` — formal verification artifact.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live WeCom UAT | Carried Phase 5/8 gates | Requires operator-confirmed live WeCom environment and real lawyer trial evidence | Keep carried as human gate; do not claim closure from Phase 23 automated fixtures |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — all tasks verified; runtime, service, and contract tests pass; Phase 23 verification artifact references Phase 25.1-02 feedback-service wiring evidence.
