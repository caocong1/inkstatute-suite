# Roadmap: 墨律 InkStatute

## Milestones

- Complete **V2 PRD Foundation** - Phases 1-8 completed by 2026-06-30; live Phase 5/8 human gates remain carried.
- Complete **v1.1 Platform Foundation** - Phases 09-13 shipped 2026-06-30.
- Complete **v1.2 Conversational Context and Memory Foundation** - Phases 14-19 shipped 2026-07-02 with accepted validation/operational tech debt.
- Complete **v1.3 Production Memory System and Evaluation Spikes** - Phases 20-25 and 25.1 shipped 2026-07-02.
  - Archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)

## Current Milestone: v1.4 Long-Term Memory Productization

**Goal:** Replace the evaluation-only memory approach with a single, productized long-term memory layer so the bot feels like one continuous companion.

**Phases:**

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 26 | Memory Provider Evaluation and Selection | Re-evaluate 2026 providers and select the best long-term memory backend | MEM-01, MEM-02, MEM-03 | Selection rationale, live smoke test, rejected-provider evidence |
| 27 | Unified Memory Interface and Hindsight Adapter | Define a single `Memory` interface and implement it with Hindsight as the primary backend | MEM-04, MEM-05, MEM-06, MEM-07 | Interface + adapter merged; SQLite default removed; single deployment-wide memory |
| 28 | Memory Semantics: Focus vs Retention | Distinguish transient task context from durable memory and implement recall/retention policy | MEM-08, MEM-09, MEM-10 | Relevant recall per turn; durable preferences retained; no throwaway pollution |
| 29 | WeCom/Runtime Integration | Wire memory into the ordinary WeCom/runtime flow before and after agent turns | MEM-11, MEM-12, MEM-13 | Recall before agent call; retain after reply; output policy unchanged |
| 30 | Error Handling and Observability | Add retry, graceful degradation, and contract events for memory operations | MEM-14, MEM-15, MEM-16 | Retry/backoff; user never sees memory failure; operation events emitted |
| 31 | Real-Provider Validation and Regression Gates | Validate with live Hindsight, add automated tests, and keep V2 gates green | MEM-17, MEM-18, MEM-19, MEM-20 | Live provider tests; CI fixtures; V2 gate pass; deployment docs |

## Next Milestone

- **TBD** — Start with `/gsd-new-milestone` after v1.4 ships.
