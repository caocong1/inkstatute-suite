# Requirements: Production Memory System and Evaluation Spikes

**Defined:** 2026-07-02
**Milestone:** v1.3 Production Memory System and Evaluation Spikes
**Source of Truth:** User request on 2026-07-02, `docs/architecture/memory/production-memory-system-strategy.md`, `.planning/milestones/v1.2-REQUIREMENTS.md`, `docs/architecture/memory/external-memory-adapter-recommendation.md`, `律师助理 Bot 的 Agent 记忆组件选型研究.md`
**Core Value:** InkStatute can provide useful long-running lawyer-assistant memory through its own privacy-safe platform-native memory loop, while external memory systems remain measurable optional adapters rather than unreviewed legal-data dependencies.

## v1.3 Requirements

### Native Memory Storage

- [ ] **MEM-01**: The platform has a durable platform-native `MemoryStore` implementation that persists `MemoryRecord`, `MemoryCandidate`, and `MemoryUse` evidence without requiring an external memory service.
- [ ] **MEM-02**: Stored memory remains reference-first, preserving refs, hashes, lengths, scopes, TTL/expiry, deletion metadata, sensitivity, confidence, review state, and safe summaries only.
- [ ] **MEM-03**: Memory storage rejects raw legal/customer payloads, full document text, callback bodies, secrets, and unsafe full-text metadata recursively.
- [ ] **MEM-04**: Memory records can be queried by tenant, workspace, user, session, labels, source refs, sensitivity, confidence, TTL, deletion status, and deterministic relevance.
- [ ] **MEM-05**: Memory deletion, tombstone, retention expiry, and export workflows are represented in code and tests.

### Rolling Summaries

- [ ] **SUM-01**: The platform can create or update rolling session summaries from safe source refs without embedding raw legal/customer text in `ContextBundle` metadata.
- [ ] **SUM-02**: Rolling summary records preserve task intent refs, user constraint refs, unanswered question refs, artifact refs, outcome refs, hash, length, timestamps, and scope.
- [ ] **SUM-03**: Summary generation is policy-driven and can be triggered by turn count, budget pressure, task completion, or explicit host request.
- [ ] **SUM-04**: Summary generation fails closed when source refs, policy, or privacy checks are missing.

### Recall Orchestration

- [ ] **REC-01**: Before backend submission, a memory orchestration layer can retrieve approved memory refs for the resolved WeCom/session scope.
- [ ] **REC-02**: Retrieved memories, rolling summary refs, recent turn refs, feedback correction refs, artifact refs, and output-policy refs are assembled into a bounded `ContextBundle`.
- [ ] **REC-03**: The orchestrator enforces tenant/workspace/user/session isolation and fails closed on ambiguous or cross-scope retrieval.
- [ ] **REC-04**: Context assembly records `MemoryUse` evidence for selected memories without storing raw legal/customer text.
- [ ] **REC-05**: Ordinary WeCom continuation and new-session flows can use the memory orchestrator without exposing agent/session commands to users.

### Feedback Review and Learning

- [ ] **FBL-01**: Safe feedback corrections can affect the next context assembly as refs in the same session.
- [ ] **FBL-02**: Repeated negative feedback can create pending memory candidates with source refs, confidence, proposed scope, sensitivity, and review metadata.
- [ ] **FBL-03**: A review workflow can approve, reject, edit, tombstone, or defer memory candidates.
- [ ] **FBL-04**: Approved memory candidates become durable memory records; rejected candidates do not enter recall.
- [ ] **FBL-05**: Route mismatch, skill candidate, and high-risk legal conclusion evidence remains human-reviewed and never auto-modifies legal skills.

### Evaluation and Privacy Gates

- [ ] **EVAL-01**: A repeatable sanitized memory evaluation fixture suite covers multi-turn recall, cross-session continuity, deletion/export, tenant isolation, feedback learning, and false-recall cases.
- [ ] **EVAL-02**: Evaluation reports measure relevance, source traceability, P50/P95 latency where applicable, context-size impact, deletion correctness, and privacy scan results.
- [ ] **EVAL-03**: CI or local gate commands fail when unsafe payload fields, cross-tenant recall, missing deletion evidence, or unreviewed high-risk memory promotion is detected.
- [ ] **EVAL-04**: The native memory path is established as the baseline that external adapters must beat or complement.

### External Memory Spikes

- [ ] **XMEM-01**: Zep/Hindsight-style graph or audit memory can be evaluated through `MemoryStoreAdapter` using only synthetic or sanitized fixtures.
- [ ] **XMEM-02**: OpenViking/ReMe-style file-auditable memory can be evaluated through `MemoryStoreAdapter` using only synthetic or sanitized fixtures.
- [ ] **XMEM-03**: Mem0-style quick PoC memory can be represented as a fast-add/search/delete/export candidate without becoming the legal production default.
- [ ] **XMEM-04**: External candidate manifests record deployment model, data residency, secrets, tenant isolation, raw-payload blocking, human-review support, delete/export support, and source refs.
- [ ] **XMEM-05**: The milestone ends with a recommendation that either keeps platform-native memory only, adds an external adapter behind gates, or defers external adoption with evidence.

## Deferred Beyond v1.3

- Live production use of hosted external memory services with real legal/customer payloads.
- User-facing memory management UI for lawyers or operators.
- Automatic legal skill synthesis or automatic modification of legal conclusions.
- Cross-tenant or firm-wide shared memory scopes beyond explicit policy and review.
- Replacing contract logs or reference stores as the audit authority.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Making Zep, Hindsight, OpenViking, ReMe, Mem0, Letta, or another provider mandatory | v1.3 must first prove the native legal-safe production loop and evaluate providers through gates. |
| Storing complete raw legal/customer text in memory records | Privacy and legal work-product rules require refs, hashes, summaries, and deletion-aware metadata by default. |
| Auto-promoting high-risk legal conclusions into reusable memory | Legal safety requires human review for high-risk conclusions, route repairs, and skill changes. |
| Building a broad memory UI | The immediate gap is runtime behavior, persistence, policy, and evaluation evidence. |
| Rebuilding Hermes core/session/router/skills/MCP/model gateway | Memory orchestration belongs in InkStatute platform/runtime and adapters, not a Hermes fork. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MEM-01 | Phase 20 | Pending |
| MEM-02 | Phase 20 | Pending |
| MEM-03 | Phase 20 | Pending |
| MEM-04 | Phase 20 | Pending |
| MEM-05 | Phase 20 | Pending |
| SUM-01 | Phase 21 | Pending |
| SUM-02 | Phase 21 | Pending |
| SUM-03 | Phase 21 | Pending |
| SUM-04 | Phase 21 | Pending |
| REC-01 | Phase 22 | Pending |
| REC-02 | Phase 22 | Pending |
| REC-03 | Phase 22 | Pending |
| REC-04 | Phase 22 | Pending |
| REC-05 | Phase 22 | Pending |
| FBL-01 | Phase 23 | Pending |
| FBL-02 | Phase 23 | Pending |
| FBL-03 | Phase 23 | Pending |
| FBL-04 | Phase 23 | Pending |
| FBL-05 | Phase 23 | Pending |
| EVAL-01 | Phase 24 | Pending |
| EVAL-02 | Phase 24 | Pending |
| EVAL-03 | Phase 24 | Pending |
| EVAL-04 | Phase 24 | Pending |
| XMEM-01 | Phase 25 | Pending |
| XMEM-02 | Phase 25 | Pending |
| XMEM-03 | Phase 25 | Pending |
| XMEM-04 | Phase 25 | Pending |
| XMEM-05 | Phase 25 | Pending |

**Coverage:**

- v1.3 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-07-02*
*Last updated: 2026-07-02 after v1.3 milestone definition*

