---
phase: 05-wecom-shadow-loop-validation
plan: 02
subsystem: feedback-service
tags: [feedback-event, wecom, normalizer, dedupe, privacy]

requires:
  - phase: 05-01
    provides: WeCom evidence validation helper and live/fixture validation boundary
provides:
  - Dependency-free feedback-service package scaffold
  - Minimal WeCom feedback and pending-preview normalizer
  - Sanitized Phase 5 feedback.jsonl and pending_previews.jsonl fixtures
  - Schema-valid FeedbackEvent output for rating and route-mismatch callbacks
affects: [phase-05-plan-03, phase-06-read-and-feedback-service-apis, phase-07-ci-composability-privacy-gates]

tech-stack:
  added: []
  patterns:
    - Keep Phase 5 feedback-service as offline normalization only
    - Group repeated callbacks by feedback target, action, user, and timestamp bucket
    - Require human review and no_auto_modify metadata for route-mismatch skill candidates

key-files:
  created:
    - services/feedback-service/pyproject.toml
    - services/feedback-service/README.md
    - services/feedback-service/src/feedback_service/__init__.py
    - services/feedback-service/src/feedback_service/wecom_normalizer.py
    - services/feedback-service/tests/test_wecom_normalizer.py
    - packages/contract-test-suite/fixtures/phase5_wecom_feedback_sample.jsonl
    - packages/contract-test-suite/fixtures/phase5_wecom_pending_previews_sample.jsonl
    - .planning/phases/05-wecom-shadow-loop-validation/05-02-SUMMARY.md
  modified:
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "The normalizer accepts already-loaded sanitized dictionaries and does not read live Hermes files directly."
  - "Repeated WeCom callbacks collapse into one canonical FeedbackEvent with duplicate callback references."
  - "Route-wrong feedback produces `route_mismatch=true`, a high-risk skill candidate, `requires_human_review=true`, and `no_auto_modify` metadata."

patterns-established:
  - "Feedback normalizer outputs schema-valid plain dictionaries and leaves production APIs, queues, and broad classification to Phase 6."
  - "Raw callback bodies are not preserved; records must use `raw_payload_ref` and exact `raw_payload` keys are rejected as issues."

requirements-completed:
  - REQ-wecom-daily-test-loop

duration: 5min
completed: 2026-06-28
---

# Phase 05 Plan 02: WeCom Feedback Normalizer Summary

Sanitized WeCom callback and pending-preview records can now normalize into schema-valid `FeedbackEvent` payloads without adding Phase 6 service surfaces.

## Performance

- **Duration:** 5min
- **Started:** 2026-06-28T03:13:05Z
- **Completed:** 2026-06-28T03:18:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `services/feedback-service/` as a dependency-free Python package.
- Added `normalize_wecom_feedback_records`, `FeedbackNormalizationIssue`, and `NormalizedFeedbackBatch`.
- Added sanitized `phase5_wecom_feedback_sample.jsonl` and `phase5_wecom_pending_previews_sample.jsonl` fixtures.
- Added schema-validation tests proving normalized rating and route-mismatch feedback become valid `FeedbackEvent` records.
- Added dedupe metadata for repeated card clicks and no-auto-modify metadata for route-mismatch skill candidates.

## Task Commits

1. **Task 1: Scaffold minimal feedback-service package and tests** - `c6429ca` (feat)
2. **Task 2: Normalize sanitized WeCom feedback into FeedbackEvent** - `54217a5` (feat)

## Files Created/Modified

- `services/feedback-service/pyproject.toml` - dependency-free package metadata.
- `services/feedback-service/README.md` - Phase 5 scope and Phase 6 deferral guardrails.
- `services/feedback-service/src/feedback_service/__init__.py` - public exports.
- `services/feedback-service/src/feedback_service/wecom_normalizer.py` - minimal sanitized feedback normalizer.
- `services/feedback-service/tests/test_wecom_normalizer.py` - import, schema, dedupe, route-mismatch, and privacy tests.
- `packages/contract-test-suite/fixtures/phase5_wecom_feedback_sample.jsonl` - sanitized feedback callback fixture.
- `packages/contract-test-suite/fixtures/phase5_wecom_pending_previews_sample.jsonl` - sanitized pending preview fixture.

## Decisions Made

- Normalizer inputs are in-memory mappings so repo code does not read live runtime `feedback.jsonl` directly.
- Idempotency keys use `feedback_target + action + user_id + created_at_bucket`.
- Missing previews, unsupported actions, missing required references, and exact `raw_payload` keys become structured issues.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## Verification

- PASS: `PYTHONPATH=services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/feedback-service/tests -v`
- PASS: `python -m compileall services/feedback-service/src services/feedback-service/tests`
- PASS: `git diff --check`

## User Setup Required

None. Live Hermes feedback files remain outside the repo and must be sanitized before use as fixtures.

## Next Phase Readiness

Plan 05-03 can connect result-side WeCom contract streams to normalized `FeedbackEvent` output and record fixture-backed versus live WeCom evidence status.

---
*Phase: 05-wecom-shadow-loop-validation*
*Completed: 2026-06-28*
