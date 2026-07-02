---
phase: 21
slug: rolling-summary-pipeline
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
verified: 2026-07-02
---

# Phase 21 - Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_rolling_summary.py` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase21_rolling_summary_pipeline.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` |
| **Estimated runtime** | ~30 seconds |

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite
- **Before verify:** Full suite must be green
- **Max feedback latency:** 30 seconds

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Behavior | Test Type | Status |
|---------|------|------|-------------|----------|-----------|--------|
| 21-01-01 | 01 | 1 | SUM-04 | SummaryPrivacyError and RollingSummaryPolicy safe defaults | unit | green |
| 21-01-02 | 01 | 1 | SUM-03 | RollingSummaryTrigger evaluates all four trigger modes correctly | unit | green |
| 21-01-03 | 01 | 1 | SUM-01, SUM-02, SUM-04 | RollingSummaryProducer creates records, fails closed on missing source_refs and forbidden metadata | unit | green |
| 21-01-04 | 01 | 1 | SUM-01..SUM-04 | All exports, 21 test cases pass, no raw text in ContextBundle metadata | unit | green |
| 21-02-01 | 02 | 2 | SUM-01..SUM-04 | Synthetic fixture with trigger reason and source_refs, no raw text | contract | green |
| 21-02-02 | 02 | 2 | SUM-01..SUM-04 | Contract tests pass, schema validation updated | contract | green |

## Wave 0 Requirements

- [x] `packages/platform-runtime/tests/test_rolling_summary.py` - 21 tests covering all SUM requirements
- [x] `packages/contract-test-suite/fixtures/phase21_rolling_summary_pipeline.json` - synthetic fixture
- [x] `packages/contract-test-suite/tests/test_phase21_rolling_summary_pipeline.py` - contract tests
- [x] `packages/contract-test-suite/tests/test_schema_validation.py` - include phase21-rolling-summary-pipeline-001

## Validation Sign-Off

- [x] All tasks have automated verify commands
- [x] No watch-mode flags
- [x] Feedback latency < 30 seconds
- [x] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** green — all 6 tasks verified; 138 runtime tests pass; 8 contract fixture tests pass; schema validation updated
