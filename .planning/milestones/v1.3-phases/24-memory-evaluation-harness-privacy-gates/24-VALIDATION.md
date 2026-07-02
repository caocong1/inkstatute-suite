---
phase: 24
slug: memory-evaluation-harness-privacy-gates
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
verified: 2026-07-02
---

# Phase 24 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` / pytest 9.1.1 |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_eval.py` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase24_memory_evaluation_harness_privacy_gates.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the focused automated command listed for that task.
- **After every plan wave:** Run the full suite command.
- **Before `$gsd-verify-work`:** Full suite must be green and Phase 24 verification artifact must be present.
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 1 | EVAL-01 | T-24-01 | Sanitized benchmark covers multi-turn recall, cross-session continuity, deletion/export, tenant isolation, feedback learning, and false-recall rejection | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_eval.py` | Yes | green |
| 24-01-02 | 01 | 1 | EVAL-02 | T-24-02 | Evaluation reports include relevance, source traceability, privacy scan results, and hard gate failures | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_eval.py` | Yes | green |
| 24-01-03 | 01 | 1 | EVAL-03 | T-24-03 | CI gates fail on unsafe payload fields, cross-tenant recall, missing deletion/export evidence, or unreviewed high-risk memory promotion | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_eval.py` | Yes | green |
| 24-01-04 | 01 | 1 | EVAL-04 | T-24-04 | Native memory path is measured as the baseline that external adapters must beat or complement | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_eval.py` | Yes | green |
| 24-02-01 | 02 | 2 | EVAL-01, EVAL-02 | T-24-05 | Synthetic fixture represents six scenario results, baseline score, and hard gate definitions using refs only | contract | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase24_memory_evaluation_harness_privacy_gates.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` | Yes | green |
| 25.1-03-01 | 25.1-03 | 1 | EVAL-01, EVAL-02 | T-25.1-06 | Evaluation harness proves durable native SQLite baseline and export evidence with sanitized fixtures only | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_eval.py::MemoryEvalSQLiteBaselineTests` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `packages/platform-runtime/tests/test_memory_eval.py` — covers EVAL-01 through EVAL-04.
- [x] `packages/contract-test-suite/fixtures/phase24_memory_evaluation_harness_privacy_gates.json` — synthetic fixture.
- [x] `packages/contract-test-suite/tests/test_phase24_memory_evaluation_harness_privacy_gates.py` — contract tests.
- [x] `.planning/phases/24-memory-evaluation-harness-privacy-gates/24-VERIFICATION.md` — formal verification artifact.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live external provider benchmark | EVAL-01..EVAL-04 | External providers are evaluated as sanitized spikes only; live provider UAT is a future gate | Keep external spikes as sanitized adapter-only evidence; do not claim live provider execution |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — all tasks verified; runtime and contract tests pass; Phase 24 verification artifact references Phase 25.1-03 durable/export eval evidence.
