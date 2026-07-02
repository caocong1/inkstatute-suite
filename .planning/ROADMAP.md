# Roadmap: 墨律 InkStatute

## Milestones

- Complete **V2 PRD Foundation** - Phases 1-8 completed by 2026-06-30; live Phase 5/8 human gates remain carried.
- Complete **v1.1 Platform Foundation** - Phases 09-13 shipped 2026-06-30.
- Complete **v1.2 Conversational Context and Memory Foundation** - Phases 14-19 shipped 2026-07-02 with accepted validation/operational tech debt.
- Complete **v1.3 Production Memory System and Evaluation Spikes** - Phases 20-25 and 25.1 shipped 2026-07-02.
  - Archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)

## Current Milestone: v1.4 Long-Term Memory Productization

**Goal:** Replace the evaluation-only memory approach with a single, productized long-term memory layer so the bot feels like one continuous companion.

**Requirements:** `.planning/REQUIREMENTS.md`

## Phases

- [x] **Phase 26: Memory Provider Evaluation and Selection** - Re-evaluate 2026 providers and select the best long-term memory backend for the product goal.
- [x] **Phase 27: Unified Memory Interface and Hindsight Adapter** - Define a single `Memory` interface and implement it with Hindsight as the primary backend.
- [x] **Phase 28: Memory Semantics: Focus vs Retention** - Distinguish transient task context from durable memory and implement recall/retention policy.
- [ ] **Phase 29: WeCom/Runtime Integration** - Wire memory into the ordinary WeCom/runtime flow before and after agent turns.
- [ ] **Phase 30: Error Handling and Observability** - Add retry, graceful degradation, and contract events for memory operations.
- [ ] **Phase 31: Real-Provider Validation and Regression Gates** - Validate with live Hindsight, add automated tests, and keep V2 gates green.

## Phase Details

### Phase 26: Memory Provider Evaluation and Selection

**Goal:** Re-evaluate 2026 external long-term memory providers and select the one that best fits the product goal of seamless, personalized, long-horizon memory.
**Depends on:** v1.3 completion
**Requirements:** MEM-01, MEM-02, MEM-03
**Success Criteria** (what must be TRUE):

1. A shortlist of 2026 providers (Hindsight, Mem0, Zep, Letta, LangMem, Supermemory, Honcho) is evaluated against accuracy, integration cost, self-hosting, and long-term personality retention.
2. A real API smoke test against the top candidate is performed and recorded.
3. The final selection is documented with explicit rejection rationale for the others.
4. The chosen provider can be self-hosted or deployed without adding new managed-cloud dependencies that break the single-tenant product shape.

**Plans:** 2 plans

Plans:
**Wave 1**
- 26-01-PLAN.md — Desk research and provider comparison matrix

**Wave 2**
- 26-02-PLAN.md — Live smoke test and final selection artifact

### Phase 27: Unified Memory Interface and Hindsight Adapter

**Goal:** Define a single backend-agnostic `Memory` interface and implement it with the selected provider as the primary and only long-term memory backend.
**Depends on:** Phase 26
**Requirements:** MEM-04, MEM-05, MEM-06, MEM-07
**Success Criteria** (what must be TRUE):

1. A `Memory` interface exposes `retain`, `recall`, and `reflect`/`condense` operations with clear inputs and outputs.
2. A Hindsight adapter implements the interface using real Hindsight retain/recall/reflect APIs.
3. The previous `SQLiteMemoryStore` default path is removed from the runtime; SQLite remains allowed only for derived read-model caches.
4. The memory layer is initialized once per deployment and shared across all sessions.
5. Contract tests validate the interface and adapter behavior without requiring a live provider.

**Plans:** 3 plans

Plans:
**Wave 1**
- 27-01-PLAN.md — Memory interface design and contract tests

**Wave 2**
- 27-02-PLAN.md — Hindsight adapter implementation

**Wave 3**
- 27-03-PLAN.md — Remove SQLite default path and single-instance wiring

### Phase 28: Memory Semantics: Focus vs Retention

**Goal:** Distinguish transient task context from durable memory and implement a recall/retention policy that keeps the agent focused while building long-term personality.
**Depends on:** Phase 27
**Requirements:** MEM-08, MEM-09, MEM-10
**Success Criteria** (what must be TRUE):

1. On each turn, only memories relevant to the current message and task are recalled and injected into the agent context.
2. Durable facts, user preferences, project facts, and high-level lessons are retained across turns and tasks.
3. Throwaway task details are not polluting long-term memory.
4. A documented policy controls what gets retained, when, and at what granularity.

**Plans:** 2 plans

Plans:
**Wave 1**
- 28-01-PLAN.md — Retention policy and durable vs transient classification

**Wave 2**
- 28-02-PLAN.md — Recall policy and relevance scoring

### Phase 29: WeCom/Runtime Integration

**Goal:** Wire the unified memory layer into the ordinary WeCom/runtime flow so recall happens before the agent turn and retention happens after the reply is finalized.
**Depends on:** Phase 28
**Requirements:** MEM-11, MEM-12, MEM-13
**Success Criteria** (what must be TRUE):

1. `WeComSessionRuntime` recalls relevant memory before invoking the agent backend.
2. After the agent reply is finalized and passed through output policy, durable memory is retained.
3. The integration works with the existing Hermes one-shot adapter.
4. Output policy and delivery guard behavior remain unchanged; no internal notices or raw payloads leak to the user.

**Plans:** 2 plans

Plans:
**Wave 1**
- 29-01-PLAN.md — Pre-turn recall wiring

**Wave 2**
- 29-02-PLAN.md — Post-turn retention wiring and output policy preservation

### Phase 30: Error Handling and Observability

**Goal:** Add retry, graceful degradation, and contract events for memory operations so failures are handled internally and never surprise the user.
**Depends on:** Phase 29
**Requirements:** MEM-14, MEM-15, MEM-16
**Success Criteria** (what must be TRUE):

1. Retain/recall operations have exponential backoff retry with clear failure classification.
2. On critical memory failure, the bot still responds gracefully without exposing the memory failure or changing persona.
3. Contract events are emitted for retain, recall, and failure operations.
4. No silent fallback to a different memory UX occurs.

**Plans:** 2 plans

Plans:
**Wave 1**
- 30-01-PLAN.md — Retry, failure classification, and graceful degradation

**Wave 2**
- 30-02-PLAN.md — Memory operation contract events and observability

### Phase 31: Real-Provider Validation and Regression Gates

**Goal:** Validate the integration against a live self-hosted Hindsight instance, add automated tests, and keep the existing V2 gate suite green.
**Depends on:** Phase 30
**Requirements:** MEM-17, MEM-18, MEM-19, MEM-20
**Success Criteria** (what must be TRUE):

1. Live Hindsight tests prove multi-turn memory, cross-task recall, and preference retention.
2. Automated tests can run in CI without a live provider.
3. The existing V2 gate suite (`scripts/run_v2_gates.py`) still passes.
4. Deployment docs include provider setup, required secrets, and resource expectations.

**Plans:** 2 plans

Plans:
**Wave 1**
- 31-01-PLAN.md — Live provider validation and fixture-based CI tests

**Wave 2**
- 31-02-PLAN.md — V2 gate regression and deployment docs

## Next Milestone

- **TBD** — Start with `/gsd-new-milestone` after v1.4 ships.
