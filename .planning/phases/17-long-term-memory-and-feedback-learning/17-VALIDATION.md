---
phase: 17
slug: long-term-memory-and-feedback-learning
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-01
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_store.py packages/platform-runtime/tests/test_feedback_learning.py` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase17_long_term_memory_feedback_learning.py'` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the focused test command for the touched package.
- **After every plan wave:** Run the full suite command for runtime and contract Phase 17 tests.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 30 seconds for focused suites.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 17-01-T1 | 17-01 | 1 | LTM-03, LTM-04 | T-17-01-01 / T-17-01-02 | Scoped memory retrieval is bounded, copy-safe, and privacy-filtered. | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_store.py` | W0 | pending |
| 17-01-T2 | 17-01 | 1 | LTM-03, LTM-04 | T-17-01-03 / T-17-01-04 | Deleted, expired, low-confidence, and disallowed-sensitivity memories are excluded. | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_store.py` | W0 | pending |
| 17-02-T1 | 17-02 | 2 | FBK-01, FBK-02 | T-17-02-01 / T-17-02-02 | Feedback corrections influence current context only through refs; repeated negative feedback creates candidates. | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py` | W0 | pending |
| 17-02-T2 | 17-02 | 2 | FBK-03, FBK-04 | T-17-02-03 / T-17-02-04 | Route mismatch and skill candidates remain pending human review with no-auto-modify metadata; dedupe remains intact. | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/feedback-service/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py services/feedback-service/tests/test_feedback_queue.py` | W0 | pending |
| 17-03-T1 | 17-03 | 3 | LTM-03, LTM-04, FBK-01, FBK-02, FBK-03, FBK-04 | T-17-03-01 / T-17-03-02 | Contract fixture proves refs-only relationships across memory, feedback, context, and candidates. | contract | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase17_long_term_memory_feedback_learning.py'` | W0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:

- `packages/platform-runtime/tests/` already runs with stdlib `unittest`.
- `packages/contract-test-suite/tests/` already loads local JSON fixtures.
- No package install, server, database, external memory service, WeCom credentials, or Hermes runtime is required.

---

## Manual-Only Verifications

All Phase 17 behaviors have automated verification. Live legal-memory activation and external memory adapter acceptance are explicitly deferred and must not be manually accepted in this phase.

---

## Validation Sign-Off

- [x] All tasks have automated verify commands.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 30s for focused suites.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-07-01 by autonomous context gate/user delegation.
