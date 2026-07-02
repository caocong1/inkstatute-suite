# Phase 17: Long-Term Memory and Feedback Learning - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 17 delivers a privacy-safe, platform-native long-term memory and feedback-learning foundation. It adds a dependency-light `MemoryStore` surface, scoped memory retrieval, feedback-to-current-context behavior, repeated-negative-feedback candidate generation, and human-review gates for routing, skill, and high-risk legal learning. The phase must preserve existing feedback dedupe and pending queue behavior, and it must not introduce external memory systems, vector databases, AI feedback classification, user-facing memory UI, live legal-memory activation, or automatic legal skill/routing modification.

</domain>

<decisions>
## Implementation Decisions

### Memory Store Shape
- Implement the first `MemoryStore` in `packages/platform-runtime` as a backend-neutral, dependency-free library surface aligned with the existing `ContextAssembler`, session resolver, and in-memory support store patterns.
- Provide a copy-safe in-memory store plus clear protocol/adapter shape; do not add a database, queue, vector store, or external memory dependency in this phase.
- Start retrieval with deterministic scope filtering and lightweight lexical/ranking metadata sufficient for fixture-backed evidence; vector search and external retrieval are deferred.
- Enforce privacy at the store/policy boundary by rejecting raw payload, full-text, secret-like, and sensitive document fields while requiring refs, scope, TTL/expiry, confidence, sensitivity, status/deletion metadata, and source evidence.

### Feedback To Context
- Convert safe, policy-allowed feedback corrections into `feedback_correction_refs` and/or memory refs for `ContextAssembler`; context records must keep text out and use references plus metadata.
- Add a small `FeedbackLearningPolicy` in `packages/platform-runtime` that consumes normalized `FeedbackEvent`-shaped dictionaries from `services/feedback-service` without making `feedback-service` depend on runtime internals.
- Aggregate repeated negative feedback by stable target/user/category/source refs to create `MemoryCandidate` or routing candidate records with confidence and evidence, rather than creating a reusable memory from every single negative click.
- Preserve existing feedback normalization, dedupe, and pending queue behavior unchanged; memory candidates and context-use records are derived outputs, not replacements for the Phase 6 queue.

### Human Review And Legal Safety
- Always require human review for route mismatch, skill candidates, high-risk legal conclusions, restricted sensitivity, and reusable legal conclusion memories.
- Default risky candidates to `pending` with `requires_human_review=true` and `no_auto_modify=true` when related to legal conclusions, routing, or skill changes.
- Represent approval/rejection as candidate/review metadata only; Phase 17 must not add mutation hooks, call skill optimization, alter routing rules, or modify legal conclusion skills.
- Store source evidence as source refs, feedback IDs, target IDs, hashes/lengths, confidence values, and review metadata. Do not store raw user messages, callback payloads, customer documents, legal facts, or generated legal conclusions.

### Test And Fixture Evidence
- Add stdlib unit tests for memory store CRUD/retrieval, policy gates, feedback learning, context assembly integration, privacy rejection, candidate review defaults, and preservation of feedback dedupe/pending queues.
- Add a sanitized fixture such as `phase17_long_term_memory_feedback_learning.json` connecting `FeedbackEvent`, `MemoryRecord`, `MemoryCandidate`, `MemoryUse`, and `ContextBundle` relationships.
- Avoid schema changes unless implementation proves the Phase 14 schemas cannot express required relationships. Prefer using existing fields and metadata before expanding platform contracts.
- Keep verification local and runnable from the repo root with explicit `PYTHONPATH` commands; tests and fixtures are the prepared test content and test environment expected before user review.

### the agent's Discretion
- The agent may choose exact module, class, function, and helper names inside `packages/platform-runtime`, provided the public shape is small, dependency-free, copy-safe, testable, and compatible with existing Phase 14 schemas.
- The agent may decide the first lexical ranking algorithm and threshold values, provided they are deterministic and covered by tests.
- The agent may decide whether `MemoryUse` records are returned directly from retrieval or created by a separate helper, provided context assembly can include selected memory refs and verification can trace memory usage.
- The agent must prepare concrete tests, sanitized fixtures, and runnable verification commands before asking the user to validate behavior. The user should not be asked to decide implementation details unless a legal/safety or production-enablement gate is reached.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/platform-contract/src/platform_contract/events.py` already defines `MemoryRecord`, `MemoryCandidate`, `MemoryUse`, `ContextBundle`, and `RunInterrupt` dataclasses.
- `packages/platform-contract/src/platform_contract/schemas/` already contains Phase 14 memory/context schemas.
- `packages/platform-runtime/src/platform_runtime/context_assembler.py` already accepts `memory_refs` and `feedback_correction_refs`, uses dependency-free dataclasses, safe metadata helpers, deterministic budgets, and copy-safe in-memory support stores.
- `packages/platform-runtime/src/platform_runtime/store.py` already provides a reference-first in-memory contract log store and forbidden raw-payload/full-text key rejection pattern.
- `services/feedback-service/src/feedback_service/queue.py` and `classification.py` already normalize, dedupe, classify, and expose pending feedback while marking route mismatch and skill candidates as human-reviewed/no-auto-modify.

### Established Patterns
- Runtime support code stays library-only with injected clocks/id factories and in-memory stores for tests; no server, database, queue, network, or backend construction side effects.
- Tests use Python stdlib `unittest`, fixture files, deterministic clocks/IDs, and explicit `PYTHONPATH` commands.
- Privacy checks reject exact `raw_payload` keys and full-text payload field names while allowing `raw_payload_ref`, `fixture://`, hashes, IDs, refs, and minimized metadata.
- Feedback queues are derived views and must remain idempotent, deterministic, and human-review-safe for route mismatch and skill candidate evidence.

### Integration Points
- `ContextAssemblyInput.memory_refs` and `ContextAssemblyInput.feedback_correction_refs` are the short-term context integration points for retrieved memories and current-session corrections.
- `MemoryRecord`, `MemoryCandidate`, and `MemoryUse` schemas are the platform contract shape for long-term memory, candidate approval flow, and context-use evidence.
- `FeedbackEvent` from `feedback-service` is the input shape for feedback learning; Phase 17 should not invert dependencies by making `feedback-service` import `platform_runtime`.
- Contract-test-suite fixtures can validate schema relationships and preserve non-legal composability evidence.

</code_context>

<specifics>
## Specific Ideas

- User delegated grey-area defaults to the agent and specifically asked for prepared test content and a test environment before asking for validation.
- Preferred implementation style: add `memory.py` or equivalent under `packages/platform-runtime/src/platform_runtime/`, export the public classes from `platform_runtime.__init__`, and cover with `packages/platform-runtime/tests/test_memory_store.py` plus feedback-learning tests.
- Preferred fixture name: `packages/contract-test-suite/fixtures/phase17_long_term_memory_feedback_learning.json`.
- Preferred verification commands should include focused runtime tests and contract/fixture validation commands that can run locally without credentials or live WeCom/Hermes access.

</specifics>

<deferred>
## Deferred Ideas

- External memory adapters such as Mem0 or Zep remain Phase 18 evaluation work.
- Vector database or graph database deployment is out of scope for this phase.
- Production live legal-memory activation is deferred until privacy, retention, deletion/export, tenant isolation, and human-review gates are accepted.
- User-facing memory management UI is deferred beyond v1.2.
- AI-based feedback classification and automatic legal skill/routing modification are out of scope.

</deferred>
