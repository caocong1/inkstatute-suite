---
phase: 21-rolling-summary-pipeline
status: passed
verified_at: 2026-07-02
score: 4/4
human_verification: []
review_status: local_self_review
---

# Phase 21 Verification

## Goal

Long-running conversations can produce safe rolling summary references that preserve intent, constraints, open questions, artifacts, and outcomes without stuffing raw history into backend context.

## Must-Haves

1. A policy-driven summary producer can create or update `RollingSummaryRecord` from safe source refs (SUM-01).
2. Summary records carry `summary_ref`, hash, length, task intent refs, user constraint refs, unanswered question refs, artifact refs, outcome refs, timestamps, and scope (SUM-02).
3. Summary generation can trigger from turn count, budget pressure, task completion, or explicit host request (SUM-03).
4. Summary generation fails closed when source refs, summarizer policy, or privacy checks are missing (SUM-04).
5. Contract or runtime tests prove summary text is not embedded in `ContextBundle` metadata by default.

## Evidence

- `packages/platform-runtime/src/platform_runtime/rolling_summary.py` implements `RollingSummaryPolicy`, `RollingSummaryTrigger`, and `RollingSummaryProducer`.
- Summary records are reference-first and carry `summary_ref`, hash, length, and scoped source refs.
- Triggers cover turn count, budget pressure, task completion, and explicit host request.
- `RollingSummaryProducer` raises `SummaryPrivacyError` when source refs or privacy checks are missing.
- `packages/platform-runtime/tests/test_rolling_summary.py` covers policy, trigger, producer, privacy failure, and ContextBundle metadata assertions.
- `packages/contract-test-suite/fixtures/phase21_rolling_summary_pipeline.json` provides a synthetic fixture with trigger evidence, source refs, and summary metadata with no raw text.
- `packages/contract-test-suite/tests/test_phase21_rolling_summary_pipeline.py` validates fixture schema, summary fields, and context-bundle privacy.

## Automated Checks

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_rolling_summary.py` — passed, 21 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` — passed.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase21_rolling_summary_pipeline.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` — passed.

## Notes

- This is fixture-backed code verification, not live WeCom UAT or the five-workday lawyer trial.
- No external service, database, queue, provider SDK, Hermes core change, raw legal payload store, or runtime secret was added.
- Summary text is never embedded in `ContextBundle` metadata by default; only `summary_ref` and related refs are passed.

## Result

Phase 21 passed. SUM-01, SUM-02, SUM-03, and SUM-04 are satisfied at the rolling summary pipeline boundary.
