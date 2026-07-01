# Requirements: Conversational Context and Memory Foundation

**Defined:** 2026-06-30  
**Milestone:** v1.2 Conversational Context and Memory Foundation  
**Source of Truth:** User request on 2026-06-30, `.planning/research/SUMMARY.md`, `.planning/drafts/agent-platform-north-star.md`, `docs/requirements/V2-PRD.md`  
**Core Value:** Ordinary WeCom users can continuously talk to InkStatute without knowing agent/session commands, while the platform preserves bounded short-term context, privacy-safe long-term memory, recoverable skill clarification, feedback learning, and backend-neutral contracts.

## v1.2 Requirements

### Session Continuity

- [x] **CTX-01**: Ordinary users can continue a conversation without typing `/new`, `/resume`, or any agent/session command.
- [x] **CTX-02**: The platform can resolve a stable `conversation_id` and an active `session_id/thread_id` from channel, user, bot, active task, pending interrupt, and idle-window signals.
- [x] **CTX-03**: The platform can automatically start a new session when the message is clearly a new task, the prior session is stale, or the active session has terminated.
- [x] **CTX-04**: Session decisions are recorded as minimized metadata with raw payload references, not raw legal text.

### Short-Term Context

- [x] **STM-01**: Runtime can assemble bounded short-term context from the current turn, recent turns, active task state, artifacts, pending clarification, and a rolling session summary.
- [x] **STM-02**: Context assembly enforces a deterministic budget and never sends unbounded conversation history to the backend model.
- [x] **STM-03**: Rolling summaries preserve task intent, user constraints, unanswered questions, artifact refs, and final outcomes without storing sensitive full text by default.
- [x] **STM-04**: Contract tests prove current turn, pending clarification, and output-policy constraints are never dropped during trimming.

### Long-Term Memory

- [x] **LTM-01**: The platform defines backend-neutral `MemoryRecord`, `MemoryCandidate`, `MemoryUse`, and `ContextBundle` schemas and Python bindings.
- [x] **LTM-02**: Memory records support scope, source refs, confidence, sensitivity, TTL/expiry, deletion metadata, and raw payload references.
- [x] **LTM-03**: Long-term memory retrieval can provide relevant privacy-safe memories across sessions without making contract logs a raw conversation database.
- [x] **LTM-04**: Memory writes are gated by policy so high-risk legal conclusions, customer raw payloads, secrets, and unreviewed skill changes are not stored as reusable memory.

### Skill Clarification and Interrupts

- [x] **INT-01**: A backend/skill can return a platform interrupt that maps to `waiting_for_user` / `needs_clarification` and persists the required resume state.
- [x] **INT-02**: WeCom delivery sends the clarification question as ordinary lawyer-assistant output, and the user's next answer resumes the paused run instead of starting an unrelated task.
- [x] **INT-03**: Interrupts preserve multiple-choice or freeform question metadata when available, but do not require ordinary users to know any agent terminology.
- [x] **INT-04**: Timeout, cancellation, and duplicate-answer behavior are deterministic and privacy-safe.

### Feedback and Learning

- [x] **FBK-01**: Feedback events can influence the next context assembly for the same session as corrections or constraints.
- [x] **FBK-02**: Repeated negative feedback can create memory or routing candidates with source refs and confidence, but cannot automatically modify high-risk legal skills.
- [x] **FBK-03**: Route mismatch and `skill_candidate` evidence remains human-reviewed with no-auto-modify metadata.
- [x] **FBK-04**: Feedback dedupe and pending queues continue to work with memory candidates and context-use records.

### External Memory Adapter Evaluation

- [x] **EXT-01**: The milestone compares platform-native memory against Mem0/Zep-style external memory systems for deployment, privacy, tenant isolation, deletion/export, latency, and adapter fit.
- [ ] **EXT-02**: External memory stores can be represented behind a `MemoryStore` adapter contract and capability manifest without becoming the default legal path.
- [ ] **EXT-03**: Any external adapter spike uses synthetic or sanitized fixtures only.
- [ ] **EXT-04**: The final recommendation documents whether Mem0, Zep, another store, or platform-native storage should be used for later production work.

## Deferred Beyond v1.2

- Production use of a third-party hosted memory service for live legal users.
- Vector database or graph database deployment as a required runtime dependency.
- User-facing memory management UI.
- Automatic legal skill synthesis or automatic modification of legal conclusions.
- Live lawyer trial acceptance; Phase 8 remains a parallel human gate.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Asking ordinary users to type `/new` or session commands | The product must be usable by people who do not understand agents. |
| Storing full raw legal/customer text in memory records | Privacy rules require reference-first storage and minimized summaries. |
| Making Mem0/Zep mandatory in the first implementation | They need legal/privacy/security evaluation before production use. |
| Replacing contract logs with a new authoritative conversation DB | Existing architecture keeps read views derived from contract logs. |
| Auto-applying route/skill changes from feedback | Legal safety requires human review for high-risk changes. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CTX-01 | Phase 15 | Complete |
| CTX-02 | Phase 15 | Complete |
| CTX-03 | Phase 15 | Complete |
| CTX-04 | Phase 15 | Complete |
| STM-01 | Phase 16 | Complete |
| STM-02 | Phase 16 | Complete |
| STM-03 | Phase 16 | Complete |
| STM-04 | Phase 16 | Complete |
| LTM-01 | Phase 14 | Complete |
| LTM-02 | Phase 14 | Complete |
| LTM-03 | Phase 17 | Complete |
| LTM-04 | Phase 17 | Complete |
| INT-01 | Phase 15 | Complete |
| INT-02 | Phase 15 | Complete |
| INT-03 | Phase 15 | Complete |
| INT-04 | Phase 15 | Complete |
| FBK-01 | Phase 17 | Complete |
| FBK-02 | Phase 17 | Complete |
| FBK-03 | Phase 17 | Complete |
| FBK-04 | Phase 17 | Complete |
| EXT-01 | Phase 14 | Complete |
| EXT-02 | Phase 18 | Pending |
| EXT-03 | Phase 18 | Pending |
| EXT-04 | Phase 18 | Pending |

**Coverage:**

- v1.2 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2026-06-30*
*Last updated: 2026-06-30 after v1.2 milestone initialization*
