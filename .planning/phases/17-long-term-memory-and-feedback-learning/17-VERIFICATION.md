---
phase: 17-long-term-memory-and-feedback-learning
status: passed
verified_at: 2026-07-01T15:49:08Z
score: 6/6
human_verification: []
review_status: clean_after_fix
---

# Phase 17 Verification

## Goal

Long-term memory and feedback learning support can provide backend-neutral, privacy-safe context evidence without requiring live WeCom, Hermes runtime state, raw legal payloads, or an external memory service.

## Must-Haves

1. `LTM-03`: Memory records can be retrieved into context by scope, confidence, sensitivity, TTL, deletion status, and deterministic relevance.
2. `LTM-04`: Memory records, candidates, and uses preserve source refs, TTL/deletion/review metadata, and raw payload references without storing raw payloads by default.
3. `FBK-01`: Safe feedback corrections can enter current-session context as references plus hash/length metadata.
4. `FBK-02`: Repeated negative feedback can create pending memory candidates with source refs, confidence, and review metadata.
5. `FBK-03`: Route mismatch and skill candidate evidence remains pending, human-reviewed, and no-auto-modify.
6. `FBK-04`: Feedback service dedupe/pending queue behavior remains compatible with the Phase 17 learning outputs.

## Evidence

- `packages/platform-runtime/src/platform_runtime/memory.py` adds `InMemoryMemoryStore`, scoped `MemoryQuery` retrieval, `MemoryStorePolicy`, `MemorySearchResult`, `FeedbackLearningPolicy`, `FeedbackLearningInput`, and `FeedbackLearningResult`.
- `packages/platform-runtime/tests/test_memory_store.py` covers scope filtering, deterministic ranking, copy safety, policy exclusions, privacy rejection, deleted records, zero-match filtering, and empty-query listing.
- `packages/platform-runtime/tests/test_feedback_learning.py` covers correction refs, context assembler compatibility, repeated negative candidates, single-click threshold blocking, route/skill human-review gates, and raw payload rejection.
- `packages/contract-test-suite/fixtures/phase17_long_term_memory_feedback_learning.json` provides synthetic refs-only evidence for context bundles, memory records, memory candidates, memory uses, and feedback events.
- `packages/contract-test-suite/tests/test_phase17_long_term_memory_feedback_learning.py` validates fixture relationships, privacy scans, correction refs, candidate metadata, human review, deletion exclusion, and prepared local verification commands.
- `packages/contract-test-suite/tests/test_schema_validation.py` includes `phase17-long-term-memory-feedback-learning-001` in the existing fixture registry.

## Automated Checks

- `python -m json.tool packages/contract-test-suite/fixtures/phase17_long_term_memory_feedback_learning.json >/dev/null` - passed.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_store.py` - passed, 9 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py` - passed, 6 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` - passed, 90 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/feedback-service/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py services/feedback-service/tests/test_feedback_queue.py` - passed, 16 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase17_long_term_memory_feedback_learning.py'` - passed, 8 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` - passed, 9 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src:packages/platform-runtime/src:packages/backends/hermes/src:packages/solution-loader/src:solutions/lawfirm/src:solutions/demo_non_legal/src:packages/channels/wecom/src:packages/channels/web_sse/src:services/wecom-service/src:services/feedback-service/src:services/conversation-read-view/src python -m unittest discover -s packages/contract-test-suite/tests` - passed, 171 tests.

## Review

The code review gate passed after one inline fix. The review found that term-bearing memory searches returned zero-match visible records when the result limit allowed it; commit `ee8d4af` filters those records and adds regression coverage. No open review findings remain.

## Notes

- This is local synthetic acceptance, not live WeCom/legal acceptance and not external memory adapter production approval.
- The full contract-suite command needs the actual repository solution roots `solutions/lawfirm/src` and `solutions/demo_non_legal/src`; the earlier `packages/solutions/...` path shape does not exist in this repo.
- Existing Phase 14/platform-contract dirty worktree changes remain outside Phase 17 and were not committed here.

## Result

Phase 17 passed. The platform runtime now has privacy-safe long-term memory retrieval, refs-only feedback learning outputs, pending human-review candidates, and prepared local verification content for user validation and Phase 18 adapter evaluation.
