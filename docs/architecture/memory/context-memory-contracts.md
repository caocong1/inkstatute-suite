# Context and Memory Contracts

Phase 14 defines the contract surface for conversational context, memory, and run interruption. It does not implement a runtime memory store, external memory integration, session resolver, or context assembler.

## Vocabulary

- `MemoryRecord` is a derived, privacy-safe memory item. It can carry a short summary plus source references, sensitivity, scope, TTL/deletion metadata, confidence, and optional industry context.
- `MemoryCandidate` is a proposed memory or routing update. It remains pending until policy and, where required, human review approve or reject it.
- `MemoryUse` records that a memory was selected into a context bundle for a run.
- `ContextBundle` is the bounded set of references assembled for a backend run: recent turn refs, rolling summary ref, active task refs, artifact refs, memory refs, interrupt id, and trimming metadata.
- `RunInterrupt` is the persisted waiting-for-user state for skill/backend clarification. It points to prompt and resume-state references rather than embedding raw source payloads.

## Privacy Policy

Memory and context records are reference-first. Raw legal/customer text, full callback payloads, secrets, identity numbers, phone numbers, bank accounts, addresses, and uploaded documents must stay outside these records by default. Contract payloads may store minimized summaries and references such as `source_refs`, `raw_payload_ref`, `summary_ref`, `prompt_ref`, and `resume_state_ref`.

Memory scopes are limited to `session`, `user`, `workspace`, and `tenant`. Wider scopes require stronger evidence, lower sensitivity, and stricter deletion/export support. Sensitivity is explicit: `public`, `internal`, `confidential`, or `restricted`.

High-risk legal conclusions, route mismatch repairs, and skill/routing candidates remain human-reviewed. V2 may record `MemoryCandidate` or `SkillCandidate` evidence, but it must not auto-modify legal conclusion skills or promote a legal memory to production use without review.

Deletion and retention are part of the contract. `MemoryRecord` supports TTL expiration and deletion metadata so downstream stores can implement deletion, export, and audit workflows without changing the schema.

## External Memory Evaluation

Platform-native memory is the default for this milestone because it is easiest to keep reference-first, tenant-isolated, and deletion/export aware.

Mem0, Zep, or similar external memory systems can be evaluated later only behind a `MemoryStore` adapter contract and capability manifest. The evaluation must cover:

- Deployment model: hosted, self-hosted, network access, operational ownership, and failure modes.
- Privacy: raw payload handling, redaction hooks, encryption, secret management, and whether summaries can be stored without source text.
- Tenant isolation: workspace/tenant boundaries, cross-tenant leakage prevention, and auditability.
- Deletion/export: per-user deletion, tenant export, TTL support, tombstones, and propagation guarantees.
- Latency and relevance: retrieval time, scoring transparency, deterministic testability, and bounded context assembly.
- Adapter fit: ability to represent `MemoryRecord`, `MemoryCandidate`, `MemoryUse`, and `ContextBundle` without legal-specific top-level fields.

No external memory system becomes mandatory for legal production in Phase 14. A later phase may recommend one only after sanitized fixture evaluation and privacy gates pass.
