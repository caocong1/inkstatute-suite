# Requirements: v1.4 Long-Term Memory Productization

**Milestone:** v1.4 Long-Term Memory Productization
**Source of Truth:** User directive on 2026-07-03 — replace the evaluation-only memory approach with a single, productized long-term memory layer that feels seamless to end users.
**Core Value:** The bot feels like one continuous companion: it focuses on the current task, yet remembers facts, preferences, and personality across days and tasks, without exposing the user to sessions, context windows, or fallback modes.

## v1.4 Requirements

### Memory Provider Selection

- [ ] **MEM-01**: Re-evaluate 2026 external long-term memory providers (Hindsight, Mem0, Zep, Letta, LangMem, Supermemory, Honcho) against the product goal of seamless, long-horizon, personalized memory.
- [ ] **MEM-02**: Select the provider that best balances recall accuracy, integration simplicity, self-hosting, and long-term personality retention.
- [ ] **MEM-03**: Document the selection rationale and the providers that were rejected, with evidence from current benchmarks, docs, and a real API/integration smoke test.

### Unified Memory Layer

- [ ] **MEM-04**: Define a single, backend-agnostic `Memory` interface used by the rest of the platform (WeCom service, runtime, feedback). The interface exposes retain, recall, and reflect/condense operations.
- [ ] **MEM-05**: Implement the interface with the selected external provider as the primary and only long-term memory backend. No user-visible fallback to a different memory UX.
- [ ] **MEM-06**: Remove or deprecate the previous `SQLiteMemoryStore` default path so it does not become a silent, product-incomplete fallback. SQLite may remain for derived read-model caches only.
- [ ] **MEM-07**: Ensure the memory layer is initialized once per deployment and shared across all sessions, so the bot has a single continuous memory.

### Short-Term Focus + Long-Term Memory

- [ ] **MEM-08**: On each turn, recall only the memories relevant to the current user message and task, so the agent remains focused and token-efficient.
- [ ] **MEM-09**: Across turns, retain durable facts, user preferences, project facts, and high-level lessons so the bot develops a stable personality and remembers cross-task context.
- [ ] **MEM-10**: Provide a mechanism to distinguish transient task context from durable memory, so the agent does not pollute long-term memory with throwaway details.

### Integration into the Running System

- [ ] **MEM-11**: Wire the unified memory layer into the ordinary WeCom/runtime flow so that recall happens before the agent is invoked and retention happens after the agent reply is finalized.
- [ ] **MEM-12**: Ensure the integration works with the existing Hermes one-shot adapter and any future agent backend that supports the platform contract.
- [ ] **MEM-13**: Preserve existing output policy and delivery guard behavior; memory integration must not leak internal notices or raw payloads to the user.

### Error Handling and Observability

- [ ] **MEM-14**: Define clear failure modes for the external memory provider (network, provider crash, quota, malformed response) and implement internal retry/backoff with structured logging.
- [ ] **MEM-15**: On critical memory failure, the bot must still respond to the user with a graceful degradation that does not expose the memory failure or switch to a different memory persona.
- [ ] **MEM-16**: Emit contract events for memory operations (retain, recall, failure) so the behavior is observable, replayable, and debuggable.

### Verification and Real-World Validation

- [ ] **MEM-17**: Validate the integration against a live, self-hosted instance of the selected provider using real API calls and sanitized test personas.
- [ ] **MEM-18**: Provide automated tests that prove multi-turn memory, cross-task recall, and preference retention without requiring a live provider for every CI run.
- [ ] **MEM-19**: Run the existing V2 gate suite after the memory layer change and confirm no regressions in contract, composability, or privacy behavior.
- [ ] **MEM-20**: Update deployment docs with provider setup, required secrets, and resource expectations.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-tenant isolation or complex RBAC | Single-tenant deployment in this version; keep the product simple. |
| Manual legal-review workflow for every memory | No user-requested human-in-the-loop gate; trust the provider's extraction. |
| Building a new UI for memory management | Product goal is seamlessness; no separate memory UI. |
| Production Codex CLI or other agent backends | Scope is memory; agent backend expansion stays in a future milestone. |
| Full multi-channel rollout | WeCom remains the production channel. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MEM-01 | Phase 26 | Not started |
| MEM-02 | Phase 26 | Not started |
| MEM-03 | Phase 26 | Not started |
| MEM-04 | Phase 27 | Not started |
| MEM-05 | Phase 27 | Not started |
| MEM-06 | Phase 27 | Not started |
| MEM-07 | Phase 27 | Not started |
| MEM-08 | Phase 28 | Not started |
| MEM-09 | Phase 28 | Not started |
| MEM-10 | Phase 28 | Not started |
| MEM-11 | Phase 29 | Not started |
| MEM-12 | Phase 29 | Not started |
| MEM-13 | Phase 29 | Not started |
| MEM-14 | Phase 30 | Not started |
| MEM-15 | Phase 30 | Not started |
| MEM-16 | Phase 30 | Not started |
| MEM-17 | Phase 31 | Not started |
| MEM-18 | Phase 31 | Not started |
| MEM-19 | Phase 31 | Not started |
| MEM-20 | Phase 31 | Not started |

*Requirements defined: 2026-07-03*
