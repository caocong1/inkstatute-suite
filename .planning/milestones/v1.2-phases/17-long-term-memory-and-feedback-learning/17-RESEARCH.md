# Phase 17 Research: Long-Term Memory and Feedback Learning

## Research Complete

Phase 17 should extend the Phase 14 memory contracts and Phase 16 context assembly runtime without changing platform boundaries. The implementation path is local and dependency-free: add runtime memory support in `packages/platform-runtime`, keep `services/feedback-service` as the existing normalized feedback producer, and prove behavior with stdlib unit tests plus sanitized contract-suite fixtures.

## Source Findings

### Existing Contract Surface

- `platform_contract.events.MemoryRecord` already supports scope, status, sensitivity, source refs, optional summary/subject/user/session, `raw_payload_ref`, confidence, TTL/expiry, deletion metadata, `industry_context`, and metadata.
- `MemoryCandidate` already supports pending/approved/rejected/suppressed status, proposed scope/sensitivity/action, proposed record ref, reason, confidence, human review, raw payload ref, and metadata.
- `MemoryUse` already records selected memory use into a context bundle through `memory_id`, `context_bundle_id`, `purpose`, optional run/turn, relevance score, policy result, source refs, and metadata.
- `ContextBundle` already carries `memory_refs`, so Phase 17 does not need to change the schema to prove memory retrieval feeding bounded context.

### Existing Runtime Patterns

- `platform_runtime.context_assembler` is the closest implementation analog: stdlib-only dataclasses, injected clock/id factories, copy-safe in-memory support store, scope keys, deterministic selection/trimming, and `_safe_metadata` privacy enforcement.
- `platform_runtime.store` provides the current privacy rejection vocabulary: exact `raw_payload` plus full-text keys such as `raw_text`, `payload_text`, `full_text`, `document_text`, `customer_document_text`, and `case_facts`.
- `platform_runtime.__init__` exports public runtime helper classes directly, so Phase 17 should export the memory store/policy symbols there.
- Phase 16 tests establish the expected test environment: `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest ...`.

### Existing Feedback Patterns

- `feedback_service.queue.normalize_feedback_inputs` already dedupes normalized callback, contract, and compatibility feedback events.
- `feedback_service.classification.classify_feedback_event` already classifies rating/correction/fact/citation/route/format/compliance/skill candidate feedback.
- Route mismatch and skill candidate classifications already return `requires_human_review=True` and `no_auto_modify=True`.
- Phase 17 should consume FeedbackEvent-shaped dictionaries and classification-like metadata without making `feedback-service` import `platform_runtime`.

## Recommended Technical Shape

### Memory Store

Implement `packages/platform-runtime/src/platform_runtime/memory.py` with:

- `MemoryStorePolicy`: scope allowance, maximum retrieved refs, default TTL/sensitivity, minimum confidence, retrieval weighting, and review requirements.
- `MemoryQuery`: tenant/workspace/session/user scope, current turn refs/text for hash-only matching, optional topic/subject/category labels, now timestamp, and max results.
- `MemorySearchResult`: `MemoryRecord`, relevance score, matched fields/refs, and policy result.
- `InMemoryMemoryStore`: copy-safe upsert/get/list/search/delete behavior over `MemoryRecord` dataclasses.
- Privacy helpers reused or mirrored from existing runtime code so forbidden keys are rejected consistently.

Initial retrieval should be deterministic:

- Filter by tenant/workspace.
- Enforce scope visibility: session memories require matching session, user memories require matching user, workspace and tenant memories require matching workspace/tenant.
- Exclude deleted/suppressed/expired records.
- Require minimum confidence and allowed sensitivity.
- Score simple lexical/metadata overlap between query text/labels and `subject`, `summary`, `source_refs`, and metadata labels.
- Return bounded results in stable order: relevance desc, confidence desc, updated_at desc, memory_id asc.

### Feedback Learning Policy

Implement a small policy in the same runtime module or a sibling module:

- `FeedbackLearningPolicy`: thresholds for immediate correction refs and repeated negative candidate creation.
- `FeedbackLearningInput`: scope/session/run/context IDs plus FeedbackEvent dictionaries.
- `FeedbackLearningResult`: feedback correction refs, memory candidates, routing candidates, memory uses, and metadata.
- Safe correction feedback should influence current-session context through `feedback_correction_refs` only.
- Repeated negative feedback should create `MemoryCandidate` records with `status="pending"`, source refs, confidence, and review metadata.
- Route mismatch and skill candidate feedback must produce human-review-only candidates with `no_auto_modify=true`.

### Contract Evidence

Add a fixture under `packages/contract-test-suite/fixtures/phase17_long_term_memory_feedback_learning.json` containing:

- A sanitized FeedbackEvent correction.
- A repeated negative feedback cluster represented by refs/count metadata.
- A MemoryRecord used by ContextBundle via `memory_refs`.
- A MemoryCandidate with pending/human-review/no-auto-modify metadata.
- A MemoryUse linking a memory record into a context bundle.

Register and test this fixture using the existing schema validation helpers. Do not create another validator.

## Validation Architecture

### Automated Checks

- Runtime memory store tests:
  - scoped retrieval never leaks across tenant/workspace/session/user boundaries.
  - deleted/suppressed/expired/low-confidence/restricted records are excluded by policy.
  - retrieval is deterministic and bounded.
  - store reads are copy-safe.
  - forbidden raw/full-text fields are rejected.

- Runtime feedback-learning tests:
  - safe correction feedback yields `feedback_correction_refs` for current context.
  - repeated negative feedback yields pending MemoryCandidate records.
  - route mismatch and skill candidate feedback are always human-review/no-auto-modify.
  - context assembly can include selected memory refs and feedback correction refs.

- Feedback service preservation tests:
  - existing feedback dedupe collapses duplicates exactly as before.
  - pending queue outputs remain reference-first and human-review-safe.

- Contract-suite tests:
  - Phase 17 fixture validates with existing schemas.
  - MemoryRecord, MemoryCandidate, MemoryUse, ContextBundle, and FeedbackEvent relationships are traceable by IDs/refs.
  - recursive privacy scans reject forbidden raw/full-text keys and secret/internal notice strings.

### Verification Commands

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_store.py`
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py`
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_context_assembler.py`
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase17_long_term_memory_feedback_learning.py'`
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'`
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests`

## Risks And Mitigations

| Risk | Mitigation |
|------|------------|
| Memory becomes a raw conversation database | Store refs, summaries, hashes/lengths, TTL/deletion metadata, and source refs only; reject full-text/raw payload keys. |
| Feedback accidentally modifies legal skills | Candidates only; default `pending`, `requires_human_review=true`, `no_auto_modify=true`; no mutation hooks. |
| Retrieval leaks across tenants/users/sessions | Use full scope filtering and tests for cross-scope isolation. |
| External memory dependency sneaks in | Keep Phase 17 platform-native and stdlib-only; Phase 18 owns adapter evaluation. |
| Existing feedback queue behavior regresses | Add preservation tests and avoid making feedback-service depend on platform-runtime. |

